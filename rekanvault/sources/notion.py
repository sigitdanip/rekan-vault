"""
Notion connector (P3 — RV-DEC-P3-0002, RV-DEC-P3-0003, RV-DEC-P3-0006).

Implements the Notion REST API version ``2026-03-11`` with httpx async:

  * ``scan()`` — recursive traversal of a root page; real 32-char block UUIDs are
    preserved as ``DocumentBlock.block_id`` so they can serve as citation
    locators downstream (P3-T8).
  * ``fetch_changes(cursor)`` — safety poll using ``/v1/search`` filtered by
    ``last_edited_time > cursor`` (Notion has no stable changes feed).
  * ``reconcile()`` — full rescan; deactivates documents that disappeared from
    Notion (access revoked / deleted).
  * ``verify_webhook_signature()`` — HMAC-SHA256 over the raw request body,
    ``hmac.compare_digest`` for timing-safe comparison.

Rate limiting: 3 req/s spacing via an ``asyncio.Lock`` + monotonic clock, with
Retry-After-precedence exponential backoff + jitter on 429/529 (and 5xx).

2026-03-11 breaking changes handled here:
  * ``archived`` → ``in_trash`` in every request param + response body.
  * ``after`` cursor → ``position`` object (used by Append only — not needed for
    read paths, but enforced in comments / type hints).
  * ``transcription`` block type → ``meeting_notes``.

2025-09-03 split still in force: ``/v1/databases/{id}/query`` →
``/v1/data_sources/{id}/query``. We hit ``GET /v1/databases/{id}`` first to
discover the data source(s), then query each.

Attachments (RV-DEC-P3-0006): file blocks preserve URL + expiry_time in
``DocumentBlock.metadata`` but are NOT downloaded. S3 URLs expire within an
hour, so persisting the URL is useless — we surface the reference, the worker
is responsible for re-fetching when needed.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import random
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from apps.api.config import settings
from rekanvault.contracts.documents import (
    DocumentBlock,
    DocumentLocator,
    DocumentVersion,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.contracts.errors import ErrorCode, RekanVaultError
from rekanvault.contracts.identifiers import generate_id
from rekanvault.sources.base import BaseConnector
from rekanvault.sources.http_client import create_source_client

_NOTION_API_BASE = "https://api.notion.com"
_MAX_DEPTH = 8
_PAGE_SIZE = 100
_RATE_SPACING_SECONDS = 0.34  # ~3 req/s
_MAX_RETRIES = 5
_RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}


def _strip_uuid_dashes(uuid_str: str) -> str:
    """Return the 32-char Notion UUID form (used as the canonical block locator)."""
    return uuid_str.replace("-", "")


def _rich_text_to_plain(rich_text: list[dict[str, Any]] | None) -> str:
    """Concatenate Notion rich_text[] into a single plain string."""
    if not rich_text:
        return ""
    parts: list[str] = []
    for rt in rich_text:
        if not isinstance(rt, dict):
            continue
        plain = rt.get("plain_text")
        if isinstance(plain, str):
            parts.append(plain)
            continue
        # Fall back to nested text field if plain_text missing.
        text_obj = rt.get("text")
        if isinstance(text_obj, dict):
            content = text_obj.get("content")
            if isinstance(content, str):
                parts.append(content)
    return "".join(parts)


def _extract_block_content(block: dict[str, Any]) -> str:
    """Map a Notion block's type-specific payload to a plain string."""
    block_type = block.get("type", "")
    payload = block.get(block_type)
    if not isinstance(payload, dict):
        return ""

    if block_type == "child_page":
        return str(payload.get("title", ""))
    if block_type == "child_database":
        return str(payload.get("title", ""))
    if block_type in {"transcription"}:
        # 2025-09-03 deprecated; should not appear in 2026-03-11 responses.
        return _rich_text_to_plain(payload.get("rich_text"))
    if block_type == "meeting_notes":
        # 2026-03-11 replacement for ``transcription``.
        return _rich_text_to_plain(payload.get("rich_text"))

    if "rich_text" in payload:
        return _rich_text_to_plain(payload.get("rich_text"))
    if "title" in payload:
        # Database / page title blocks.
        rich = payload.get("title")
        if isinstance(rich, list):
            return _rich_text_to_plain(rich)
        return str(rich)
    if "caption" in payload:
        return _rich_text_to_plain(payload.get("caption"))
    return ""


def _extract_block_metadata(block: dict[str, Any]) -> dict[str, Any]:
    """Pull type-specific metadata (file URLs, properties) without the content text."""
    block_type = block.get("type", "")
    payload = block.get(block_type)
    if not isinstance(payload, dict):
        return {}

    if block_type in {"file", "image", "video", "pdf", "audio"}:
        # Preserve attachment reference per RV-DEC-P3-0006. S3 URLs expire within
        # an hour so we keep the metadata but do NOT download the file here.
        file_obj = payload.get("file") or payload.get("external")
        if isinstance(file_obj, dict):
            return {
                "kind": block_type,
                "url": str(file_obj.get("url", "")),
                "expiry_time": str(file_obj.get("expiry_time", "")),
                "filename": str(payload.get("name", "")),
            }
    if block_type == "child_page":
        return {"kind": "child_page", "title": str(payload.get("title", ""))}
    if block_type == "child_database":
        return {"kind": "child_database", "title": str(payload.get("title", ""))}
    return {}


class NotionConnector(BaseConnector):
    """Production Notion connector — Notion API ``2026-03-11``."""

    def __init__(
        self,
        source_id: str,
        config: dict[str, Any],
        client: httpx.AsyncClient | None = None,
        token: str | None = None,
    ) -> None:
        super().__init__(source_id=source_id, config=config)
        self._client = client or create_source_client(timeout_seconds=settings.RV_NOTION_API_TIMEOUT_SECONDS)
        self._owns_client = client is None
        self._token = token or settings.RV_NOTION_TOKEN
        self._api_version = settings.RV_NOTION_API_VERSION
        self._last_request_ts = 0.0
        self._rate_lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def provider(self) -> SourceProvider:
        return SourceProvider.NOTION

    # ---- rate limit + retry -------------------------------------------------

    async def _rate_limit(self) -> None:
        """Space consecutive requests to ~3 req/s."""
        async with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_ts
            if elapsed < _RATE_SPACING_SECONDS:
                await asyncio.sleep(_RATE_SPACING_SECONDS - elapsed)
            self._last_request_ts = time.monotonic()

    async def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """One HTTP call with rate limit + retry/backoff/jitter on transient errors."""
        url = f"{_NOTION_API_BASE}{path}" if path.startswith("/") else path
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": self._api_version,
            "Content-Type": "application/json",
            **kwargs.pop("headers", {}),
        }

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            await self._rate_limit()
            try:
                resp = await self._client.request(method, url, headers=headers, **kwargs)
            except httpx.TransportError as exc:  # network blip — retryable
                last_exc = exc
                delay = min(2**attempt, 30) + random.uniform(0, 0.25)
                await asyncio.sleep(delay)
                continue

            if resp.status_code in _RETRYABLE_STATUS:
                if attempt == _MAX_RETRIES - 1:
                    raise RekanVaultError(
                        message=f"Notion API {method} {path} failed after {_MAX_RETRIES} retries: HTTP {resp.status_code}",
                        code=ErrorCode.RATE_LIMITED if resp.status_code == 429 else ErrorCode.PROVIDER_ERROR,
                        target="notion_api",
                        details={"status": resp.status_code},
                    )
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = min(2**attempt, 30)
                else:
                    delay = min(2**attempt, 30)
                delay += random.uniform(0, 0.25)  # jitter
                await asyncio.sleep(delay)
                continue

            if resp.status_code == 401:
                raise RekanVaultError(
                    message="Notion API authentication failed",
                    code=ErrorCode.UNAUTHORIZED,
                    target="notion_api",
                )
            if resp.status_code == 404:
                raise RekanVaultError(
                    message=f"Notion resource not found: {path}",
                    code=ErrorCode.NOT_FOUND,
                    target="notion_api",
                )
            return resp

        # Network kept failing — surface the last error.
        raise RekanVaultError(
            message=f"Notion API {method} {path} failed: {last_exc}",
            code=ErrorCode.PROVIDER_ERROR,
            target="notion_api",
        ) from last_exc

    # ---- scan() ------------------------------------------------------------

    async def scan(self) -> list[NormalizedDocument]:
        root_page_id = str(self.config.get("root_page_id") or settings.RV_NOTION_PAGE_ID)
        if not root_page_id:
            return []

        documents: list[NormalizedDocument] = []
        seen_page_ids: set[str] = set()
        await self._collect_page(
            page_id=root_page_id,
            documents=documents,
            seen_page_ids=seen_page_ids,
            depth=0,
        )
        return documents

    async def _collect_page(
        self,
        page_id: str,
        documents: list[NormalizedDocument],
        seen_page_ids: set[str],
        depth: int,
    ) -> None:
        if depth > _MAX_DEPTH:
            return
        if page_id in seen_page_ids:
            return
        seen_page_ids.add(page_id)

        page_meta = await self._fetch_page_meta(page_id)
        if page_meta.get("in_trash"):
            return  # trashed pages are not surfaced (RV-DEC-P3-0003)
        title = page_meta.get("title", "Untitled")
        blocks = await self._walk_block_children(page_id, depth=depth)

        document = self._build_document(
            page_id=page_id,
            title=title,
            blocks=blocks,
            in_trash=False,
        )
        if document is not None:
            documents.append(document)

        # Child pages and databases are first-class documents in Notion's
        # sidebar; surface them as their own ``NormalizedDocument`` so each is
        # independently searchable / citable. Dedup via ``seen_page_ids``.
        for child in await self._list_all_children(page_id):
            block_type = child.get("type", "")
            child_id = str(child.get("id", ""))
            if not child_id or child_id in seen_page_ids:
                continue
            if block_type == "child_page":
                await self._collect_page(
                    page_id=child_id,
                    documents=documents,
                    seen_page_ids=seen_page_ids,
                    depth=depth + 1,
                )
            elif block_type == "child_database":
                await self._collect_database_rows(
                    database_id=child_id,
                    documents=documents,
                    seen_page_ids=seen_page_ids,
                    depth=depth + 1,
                )

    async def _fetch_page_meta(self, page_id: str) -> dict[str, Any]:
        resp = await self._call("GET", f"/v1/pages/{page_id}")
        page = resp.json()
        # 2026-03-11: top-level `in_trash` replaces `archived`.
        in_trash = bool(page.get("in_trash", page.get("archived", False)))
        title = _extract_page_title(page)
        return {"title": title, "in_trash": in_trash, "raw": page}

    async def _walk_block_children(self, block_id: str, depth: int) -> list[DocumentBlock]:
        """Recursively walk block children, preserving real Notion block IDs.

        Returns a flat list of ``DocumentBlock`` with globally-unique sequence
        numbers (1, 2, 3, ...). When a block has ``has_children=true`` or is a
        ``child_page`` / ``child_database``, the nested content is flattened in
        DFS order.
        """
        if depth > _MAX_DEPTH:
            return []
        blocks: list[DocumentBlock] = []
        sequence = 0
        for child in await self._list_all_children(block_id):
            sequence += 1
            block_type = child.get("type", "unknown")
            content = _extract_block_content(child)
            metadata = _extract_block_metadata(child)
            real_id = _strip_uuid_dashes(str(child.get("id", "")))
            if not real_id:
                continue  # Notion guarantees an id; skip if somehow missing.

            blocks.append(
                DocumentBlock(
                    block_id=real_id,
                    block_type=block_type,
                    content=content,
                    sequence=sequence,
                    metadata=metadata,
                )
            )

            if child.get("has_children"):
                nested = await self._walk_block_children(child["id"], depth=depth + 1)
                for nb in nested:
                    sequence += 1
                    blocks.append(nb.model_copy(update={"sequence": sequence}))
        return blocks

    async def _list_all_children(self, block_id: str) -> list[dict[str, Any]]:
        """Paginate /v1/blocks/{id}/children to exhaustion."""
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": _PAGE_SIZE}
            if cursor:
                params["start_cursor"] = cursor
            resp = await self._call("GET", f"/v1/blocks/{block_id}/children", params=params)
            data = resp.json()
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                return results
            next_cursor = data.get("next_cursor")
            if not next_cursor:
                return results
            cursor = next_cursor

    async def _collect_database_rows(
        self,
        database_id: str,
        documents: list[NormalizedDocument],
        seen_page_ids: set[str],
        depth: int,
    ) -> None:
        """Query a Notion database via the 2025-09-03 data_source split.

        Each row is a page — we recurse into ``_collect_page`` so row content
        gets its own ``NormalizedDocument`` (de-duplicated by ``seen_page_ids``).
        """
        # Step 1: discover the data source(s) backing this database.
        try:
            db_resp = await self._call("GET", f"/v1/databases/{database_id}")
        except RekanVaultError:
            return  # inaccessible database — skip, don't break the page walk
        db = db_resp.json()
        data_sources = db.get("data_sources", [])
        if not data_sources:
            return
        # A database may have multiple data sources; query the first.
        first = data_sources[0]
        ds_id = first.get("id") if isinstance(first, dict) else None
        if not ds_id:
            return

        cursor: str | None = None
        while True:
            body: dict[str, Any] = {"page_size": _PAGE_SIZE}
            if cursor:
                body["start_cursor"] = cursor
            resp = await self._call("POST", f"/v1/data_sources/{ds_id}/query", json=body)
            data = resp.json()
            for row in data.get("results", []):
                page_id = str(row.get("id", ""))
                if not page_id:
                    continue
                if bool(row.get("in_trash", row.get("archived", False))):
                    continue  # 2026-03-11: in_trash
                await self._collect_page(
                    page_id=page_id,
                    documents=documents,
                    seen_page_ids=seen_page_ids,
                    depth=depth,
                )
            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor

    # ---- fetch_changes() (safety poll) -------------------------------------

    async def fetch_changes(self, cursor: str | None = None) -> dict[str, Any]:
        """Safety poll via /v1/search filtered by last_edited_time > cursor."""
        if not self._token:
            return {"new_cursor": _now_iso(), "changes_count": 0, "has_more": False}

        # Default cursor: 24h back so we never miss edits on cold start.
        since = cursor or _now_iso_minus(hours=24)
        body: dict[str, Any] = {
            "page_size": _PAGE_SIZE,
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "filter": {
                "value": "page",
                "property": "object",
            },
        }

        seen: set[str] = set()
        changes = 0
        next_cursor: str | None = None
        while True:
            if next_cursor:
                body["start_cursor"] = next_cursor
            resp = await self._call("POST", "/v1/search", json=body)
            data = resp.json()
            for page in data.get("results", []):
                page_id = str(page.get("id", ""))
                if not page_id or page_id in seen:
                    continue
                seen.add(page_id)
                last_edited = str(page.get("last_edited_time", ""))
                if last_edited and last_edited < since:
                    # Newest-first sort: once we hit one older than the watermark,
                    # the rest of this page is older too.
                    continue
                # 2026-03-11: in_trash. Trashed pages still need a lifecycle
                # event (deactivation) so the count is inclusive.
                changes += 1
            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break
        return {
            "new_cursor": _now_iso(),
            "changes_count": changes,
            "has_more": False,
        }

    # ---- reconcile() -------------------------------------------------------

    async def reconcile(self) -> dict[str, Any]:
        """Full rescan. Returns a summary; per-doc diffing happens upstream
        where the DB session is available (this connector is DB-free)."""
        try:
            documents = await self.scan()
        except RekanVaultError as exc:
            return {"status": "error", "scanned": 0, "reconciled": 0, "errors": 1, "error": str(exc)}
        return {
            "status": "reconciled",
            "scanned": len(documents),
            "reconciled": len(documents),
            "errors": 0,
        }

    # ---- webhook signature verification (code only) -----------------------

    @staticmethod
    def verify_webhook_signature(
        raw_body: bytes,
        signature_header: str | None,
        verification_token: str,
    ) -> bool:
        """HMAC-SHA256 over the raw request body, timing-safe compared.

        Notion's signature header format is ``sha256=<hex>`` — the ``sha256=``
        prefix is stripped before comparison.

        Args:
            raw_body: Exact bytes of the webhook request body (not parsed JSON).
            signature_header: Value of the ``X-Notion-Signature`` header.
            verification_token: Shared secret — ``RV_NOTION_WEBHOOK_VERIFICATION_TOKEN``.

        Returns:
            ``True`` if the signature is valid. If the header is missing/empty,
            Notion's one-time handshake may be in flight and we conservatively
            return ``False`` — handlers should call :func:`is_handshake_payload`
            to accept the verification challenge.
        """
        if not signature_header or not verification_token:
            return False
        # Notion prefixes the signature with the algorithm name: ``sha256=<hex>``.
        expected = "sha256=" + hmac.new(verification_token.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature_header, expected)

    @staticmethod
    def is_handshake_payload(body: dict[str, Any]) -> bool:
        """Notion's webhook handshake sends ``{"verification_token": "..."}``."""
        return isinstance(body, dict) and bool(body.get("verification_token"))

    # ---- helpers -----------------------------------------------------------

    def _build_document(
        self,
        page_id: str,
        title: str,
        blocks: list[DocumentBlock],
        in_trash: bool,
    ) -> NormalizedDocument | None:
        if in_trash:
            return None
        if not blocks:
            # Still emit a single empty block so the page is tracked.
            real_id = _strip_uuid_dashes(page_id)
            blocks = [
                DocumentBlock(
                    block_id=real_id,
                    block_type="paragraph",
                    content="",
                    sequence=1,
                )
            ]
        content_text = "\n".join(b.content for b in blocks if b.content)
        content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

        doc_id = generate_id("doc")
        ver_id = generate_id("ver")
        version = DocumentVersion(
            version_id=ver_id,
            document_id=doc_id,
            version_number=1,
            content_hash=content_hash,
            blocks=blocks,
        )
        real_page_id = _strip_uuid_dashes(page_id)
        return NormalizedDocument(
            document_id=doc_id,
            workspace_id=str(self.config.get("workspace_id", "ws_default")),
            source_id=self.source_id,
            title=title,
            provider=SourceProvider.NOTION,
            locator=DocumentLocator(
                provider=SourceProvider.NOTION,
                native_id=real_page_id,
                uri=f"https://notion.so/{real_page_id}",
            ),
            active_version_id=ver_id,
            versions=[version],
        )


# ---- module-level helpers --------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_iso_minus(hours: int) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat()


def _extract_page_title(page: dict[str, Any]) -> str:
    """Pull the page title from a /v1/pages/{id} response (2026-03-11 shape)."""
    properties = page.get("properties", {})
    if not isinstance(properties, dict):
        return "Untitled"
    for prop in properties.values():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") == "title":
            title = prop.get("title")
            if isinstance(title, list):
                plain = _rich_text_to_plain(title)
                if plain:
                    return plain
    return "Untitled"
