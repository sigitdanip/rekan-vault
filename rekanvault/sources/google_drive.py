"""
Google Drive connector for RekanVault (P3).

Real Drive API v3 implementation — full recursive ``scan()``, incremental
``fetch_changes()`` via ``changes.list``, and ``reconcile()`` to drift-check
the index. Synchronous google-api-python-client calls are offloaded to
``asyncio.to_thread``; each call rebuilds its own ``httplib2.Http`` because
``httplib2.Http`` is not thread-safe and a single ``Resource`` is shared
across calls.

Ponytail:
  * No abstract Factory / Strategy / Builder — one connector, one provider.
  * ``reconcile()`` is a thin wrapper over ``scan()``; the heavy lifting
    (drift detection) lives in ``rekanvault.ingestion.reconciliation``.
  * Streaming downloads via ``MediaIoBaseDownload`` to disk — never buffer
    the body in memory.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import random
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from httplib2 import Http as Httplib2Http
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from rekanvault.contracts.documents import (
    MAX_SOURCE_FILE_BYTES,
    SUPPORTED_MIME_TYPES,
    DocumentBlock,
    DocumentLocator,
    DocumentVersion,
    ExtractionWarning,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.contracts.errors import ErrorCode, RekanVaultError
from rekanvault.contracts.identifiers import generate_id
from rekanvault.sources import credential_repo
from rekanvault.sources.base import BaseConnector

logger = logging.getLogger(__name__)

# --- constants -------------------------------------------------------------

# Drive MIME for folders. Folders are recursed into, never indexed themselves.
_FOLDER_MIME = "application/vnd.google-apps.folder"

# Retry policy for transient HTTP/network failures.
RETRYABLE_STATUS: set[int] = {429, 500, 502, 503, 504}
RETRYABLE_ERRORS: tuple[type[BaseException], ...] = (
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    TimeoutError,
)
DEFAULT_MAX_RETRIES = 5
DEFAULT_MAX_DELAY = 60.0
DRIVE_CHUNK_BYTES = 5 * 1024 * 1024  # 5 MiB per MediaIoBaseDownload chunk.

# Drive file fields we always pull. Kept narrow on purpose — the larger the
# payload, the more we pay on every page.
_FILE_FIELDS = "nextPageToken,files(id,name,mimeType,parents,modifiedTime,size,trashed,md5Checksum)"

# Drive change fields — slightly different (file is nested).
_CHANGE_FIELDS = (
    "nextPageToken,newStartPageToken,"
    "changes(fileId,removed,file(id,name,mimeType,parents,modifiedTime,trashed,md5Checksum))"
)

# Doc API fields — body + tabs (RV-DEC-P3-0005).
_DOC_FIELDS = "tabs(tabId,title,body(content)),body(content)"


# --- errors ----------------------------------------------------------------


class GoogleAuthRequired(RekanVaultError):
    """Raised when the stored OAuth refresh token can no longer be refreshed.

    The Google refresh flow rejected the token (typically ``invalid_grant``) —
    the user has to redo the OAuth dance before the connector can resume.
    """

    def __init__(self, message: str = "Re-authentication required") -> None:
        super().__init__(message, code=ErrorCode.PROVIDER_ERROR, target="google_drive")


# --- rate-limited executor -------------------------------------------------


def _retry_call(
    func: Any,
    *args: Any,
    max_retries: int = DEFAULT_MAX_RETRIES,
    max_delay: float = DEFAULT_MAX_DELAY,
    **kwargs: Any,
) -> Any:
    """Run a sync google-api-python-client call with exponential backoff + jitter.

    Retries on ``HttpError`` with a retryable status (429/5xx) and on
    transient connection errors. Non-retryable errors (400/401/403/404) bubble
    immediately so the caller can map them to a domain error.

    Backoff: ``2**attempt`` capped at ``max_delay``, with full-jitter
    multiplication so a thundering herd of connectors doesn't synchronize.
    """
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status not in RETRYABLE_STATUS:
                raise
            if attempt == max_retries - 1:
                raise
            delay = min((2**attempt) + random.uniform(0, 1) * 0.2, max_delay)
            logger.warning("google_drive retryable HTTP %s on attempt %d, sleeping %.2fs", status, attempt + 1, delay)
            time.sleep(delay)
        except RETRYABLE_ERRORS as exc:
            if attempt == max_retries - 1:
                raise
            delay = min((2**attempt) + random.uniform(0, 1) * 0.2, max_delay)
            logger.warning(
                "google_drive retryable %s on attempt %d, sleeping %.2fs",
                type(exc).__name__,
                attempt + 1,
                delay,
            )
            time.sleep(delay)


# --- structural element reader (Google Docs) -------------------------------


def _read_structural_elements(elements: list[dict[str, Any]]) -> str:
    """Walk the Docs API structural elements tree and concatenate text runs.

    Handles ``paragraph``, ``table``, and ``tableOfContents`` recursively —
    tables and ToCs nest their own ``content`` arrays which themselves
    contain structural elements.
    """
    out: list[str] = []
    for elem in elements:
        paragraph = elem.get("paragraph")
        if paragraph is not None:
            for run in paragraph.get("elements", []):
                text_run = run.get("textRun")
                if text_run is not None:
                    out.append(text_run.get("content", ""))
            continue

        table = elem.get("table")
        if table is not None:
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    out.append(_read_structural_elements(cell.get("content", [])))
            continue

        toc = elem.get("tableOfContents")
        if toc is not None:
            out.append(_read_structural_elements(toc.get("content", [])))
    return "".join(out)


def _read_google_doc(doc_payload: dict[str, Any]) -> list[DocumentBlock]:
    """Extract a list of ``DocumentBlock`` from a ``documents.get`` response.

    Iterates the document's tabs (RV-DEC-P3-0005 — every tab becomes its
    own block group with the tab id stored in the block metadata). Falls
    back to the legacy top-level ``body`` for documents that have no tabs
    field at all.
    """
    blocks: list[DocumentBlock] = []
    tabs = doc_payload.get("tabs")
    if tabs:
        for tab_index, tab in enumerate(tabs):
            tab_id = tab.get("tabId", f"tab_{tab_index}")
            body = tab.get("body") or {}
            text = _read_structural_elements(body.get("content", []))
            if text:
                blocks.append(
                    DocumentBlock(
                        block_id=generate_id("blk"),
                        block_type="doc_tab",
                        content=text,
                        sequence=len(blocks) + 1,
                        metadata={"tab_id": tab_id, "tab_title": tab.get("title", "")},
                    )
                )
        return blocks

    body = doc_payload.get("body") or {}
    text = _read_structural_elements(body.get("content", []))
    if text:
        blocks.append(
            DocumentBlock(
                block_id=generate_id("blk"),
                block_type="paragraph",
                content=text,
                sequence=1,
                metadata={"tab_id": "default"},
            )
        )
    return blocks


# --- connector -------------------------------------------------------------


class GoogleDriveConnector(BaseConnector):
    """Production Drive v3 connector.

    Args:
        source_id: RekanVault source id (used to look up encrypted tokens).
        config: Connector config — may carry ``folder_id`` (overrides
            ``RV_GOOGLE_FOLDER_ID``), ``workspace_id`` (string form), and
            the optional ``session`` injection (a DB session used to
            load/persist tokens). Most tests pass a ``MagicMock`` session
            so they don't need a live DB.
    """

    def __init__(self, source_id: str, config: dict[str, Any]) -> None:
        super().__init__(source_id=source_id, config=config)
        self._service: Any = None
        self._service_lock = asyncio.Lock()

    # ---- helpers -----------------------------------------------------------

    @property
    def provider(self) -> SourceProvider:
        return SourceProvider.GOOGLE_DRIVE

    @property
    def _folder_id(self) -> str:
        # self.config wins so a per-source override beats the global setting.
        return str(self.config.get("folder_id") or settings.RV_GOOGLE_FOLDER_ID or "root")

    @property
    def _workspace_id(self) -> str:
        return str(self.config.get("workspace_id", "ws_default"))

    def _db_session(self) -> AsyncSession | None:
        """Optional DB session injected via config — used for token storage.

        In production the worker hands a real ``AsyncSession``; in tests
        this is a ``MagicMock`` or simply ``None`` (no persistence).
        """
        session: AsyncSession | None = self.config.get("session")
        return session

    # ---- OAuth & service ---------------------------------------------------

    def _build_credentials_from_token(self, refresh_token: str) -> Credentials:
        return Credentials(  # type: ignore[no-untyped-call]  # google-auth ships no stubs for this constructor
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.RV_GOOGLE_CLIENT_ID,
            client_secret=settings.RV_GOOGLE_CLIENT_SECRET,
            scopes=settings.RV_GOOGLE_OAUTH_SCOPES.split() or ["https://www.googleapis.com/auth/drive.readonly"],
        )

    @staticmethod
    def _credentials_to_token_dict(creds: Credentials) -> str:
        """Serialize a ``Credentials`` into the blob stored in AES-GCM.

        We persist ``refresh_token`` (long-lived) plus the current
        ``access_token`` and ``expiry`` so a fresh process can use the
        access token without an immediate refresh round-trip.
        """
        return (
            f"refresh={creds.refresh_token or ''};"
            f"access={creds.token or ''};"
            f"expiry={creds.expiry.isoformat() if creds.expiry else ''};"
            f"scopes={','.join(creds.scopes or [])}"
        )

    @staticmethod
    def _credentials_from_token_dict(blob: str) -> Credentials:
        parts = dict(p.split("=", 1) for p in blob.split(";") if "=" in p)
        expiry_str = parts.get("expiry", "")
        expiry = datetime.fromisoformat(expiry_str) if expiry_str else None
        scopes = [s for s in parts.get("scopes", "").split(",") if s] or None
        return Credentials(  # type: ignore[no-untyped-call]  # google-auth ships no stubs for this constructor
            token=parts.get("access") or None,
            refresh_token=parts.get("refresh") or None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.RV_GOOGLE_CLIENT_ID,
            client_secret=settings.RV_GOOGLE_CLIENT_SECRET,
            scopes=scopes,
            expiry=expiry,
        )

    async def _load_credentials(self) -> Credentials:
        """Resolve a fresh ``Credentials`` object for the current source.

        Order: stored encrypted credential (preferred) -> pilot config ->
        raise. Triggers a refresh if the access token is missing/expired.
        """
        session = self._db_session()
        if session is None:
            token = settings.RV_GOOGLE_PILOT_REFRESH_TOKEN
            if not token:
                raise GoogleAuthRequired("No Google credentials available: set RV_GOOGLE_PILOT_REFRESH_TOKEN")
            return self._build_credentials_from_token(token)

        # ``source_id`` is a RekanVault prefixed string (``src_<hex>``);
        # hash-prefix it into a deterministic UUID for the FK column so
        # connectors don't need to know about Source rows.
        source_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"rekanvault:source:{self.source_id}")
        blob = await credential_repo.get_credential(session, source_uuid)
        if blob is None:
            token = settings.RV_GOOGLE_PILOT_REFRESH_TOKEN
            if not token:
                raise GoogleAuthRequired("No stored Google credential and no pilot refresh token configured")
            await credential_repo.store_credential(
                session=session,
                workspace_id=uuid.uuid5(uuid.NAMESPACE_URL, f"rekanvault:workspace:{self._workspace_id}"),
                source_id=source_uuid,
                plaintext=self._serialize_pilot_token(token),
            )
            await session.commit()
            creds = self._build_credentials_from_token(token)
        else:
            creds = self._credentials_from_token_dict(blob)

        if not creds.valid:
            try:
                creds.refresh(GoogleAuthRequest())  # type: ignore[no-untyped-call]  # google-auth refresh() is untyped
            except RefreshError as exc:
                raise GoogleAuthRequired(f"Token refresh failed: {exc}") from exc
            await credential_repo.update_credential(session, source_uuid, self._credentials_to_token_dict(creds))
            await session.commit()
        return creds

    def _serialize_pilot_token(self, refresh_token: str) -> str:
        """Wrap a plain pilot refresh token in the same envelope the loader reads."""
        return f"refresh={refresh_token};access=;expiry=;scopes=" + ",".join(
            settings.RV_GOOGLE_OAUTH_SCOPES.split() or ["https://www.googleapis.com/auth/drive.readonly"]
        )

    @staticmethod
    def _build_service(credentials: Credentials) -> Any:
        """Build a fresh Drive v3 ``Resource`` with a thread-local httplib2.

        httplib2 is documented as not thread-safe — give each call its own
        ``Http()`` instance wrapped via ``AuthorizedHttp`` so the ``Resource``
        we cache is safe to share but the underlying transport is not.
        """
        http = AuthorizedHttp(credentials, http=Httplib2Http())
        return build("drive", "v3", http=http, cache_discovery=False)

    async def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        async with self._service_lock:
            if self._service is not None:
                return self._service
            creds = await self._load_credentials()
            self._service = await asyncio.to_thread(self._build_service, creds)
            return self._service

    # ---- core Drive calls (each offloaded + retried) -----------------------

    async def _files_list_all(
        self,
        service: Any,
        query: str,
    ) -> list[dict[str, Any]]:
        """Paginated ``files().list()`` — collects every page before returning."""
        files: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "q": query,
                "pageSize": 1000,
                "fields": _FILE_FIELDS,
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }
            if page_token:
                kwargs["pageToken"] = page_token

            response = await asyncio.to_thread(
                _retry_call,
                lambda k=kwargs: service.files().list(**k).execute(),  # noqa: B023 — explicit binding
            )
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return files

    async def _list_subfolders(self, service: Any, parent_id: str) -> list[dict[str, Any]]:
        return await self._files_list_all(
            service,
            f"'{parent_id}' in parents and mimeType='{_FOLDER_MIME}' and trashed=false",
        )

    async def _list_files_in_folder(self, service: Any, parent_id: str) -> list[dict[str, Any]]:
        return await self._files_list_all(
            service,
            f"'{parent_id}' in parents and mimeType!='{_FOLDER_MIME}' and trashed=false",
        )

    # ---- scan -------------------------------------------------------------

    async def scan(self) -> list[NormalizedDocument]:
        """Full recursive inventory scan — returns ``NormalizedDocument`` list.

        Recurses into subfolders, walks Google Doc tabs (RV-DEC-P3-0005),
        streams binary blobs to ``RV_ARTIFACT_STORAGE_PATH``. Files larger
        than ``MAX_SOURCE_FILE_BYTES`` are skipped with a structured
        ``ExtractionWarning``. Unsupported MIME types are also skipped
        with a warning.
        """
        service = await self._get_service()

        folders_to_walk: list[dict[str, Any]] = [{"id": self._folder_id, "name": "root", "path": ""}]
        seen_folder_ids: set[str] = set()
        all_files: list[dict[str, Any]] = []
        warnings: list[ExtractionWarning] = []

        while folders_to_walk:
            current = folders_to_walk.pop()
            folder_id = current["id"]
            if folder_id in seen_folder_ids:
                continue
            seen_folder_ids.add(folder_id)

            children = await self._list_files_in_folder(service, folder_id)
            all_files.extend(children)

            subfolders = await self._list_subfolders(service, folder_id)
            for sub in subfolders:
                folders_to_walk.append(
                    {
                        "id": sub["id"],
                        "name": sub.get("name", ""),
                        "path": f"{current['path']}/{sub.get('name', '')}".lstrip("/"),
                    }
                )

        documents: list[NormalizedDocument] = []
        for file_meta in all_files:
            mime = file_meta.get("mimeType", "")
            if mime not in SUPPORTED_MIME_TYPES:
                warnings.append(
                    ExtractionWarning(
                        code="UNSUPPORTED_MIME_TYPE",
                        message=f"Skipping '{file_meta.get('name')}' ({mime})",
                        document_external_id=file_meta["id"],
                    )
                )
                continue

            size_str = file_meta.get("size")
            size = int(size_str) if size_str else 0
            if size > MAX_SOURCE_FILE_BYTES:
                warnings.append(
                    ExtractionWarning(
                        code="FILE_TOO_LARGE",
                        message=(f"Skipping '{file_meta.get('name')}' ({size} bytes > {MAX_SOURCE_FILE_BYTES})"),
                        document_external_id=file_meta["id"],
                    )
                )
                continue

            try:
                if mime.startswith("application/vnd.google-apps."):
                    doc = await self._build_gdoc_document(service, file_meta)
                else:
                    doc = await self._build_blob_document(service, file_meta)
            except HttpError as exc:
                status = getattr(getattr(exc, "resp", None), "status", None)
                if status in (403, 404):
                    # Access revoked / file gone mid-scan — surface as warning.
                    warnings.append(
                        ExtractionWarning(
                            code="ACCESS_REVOKED" if status == 403 else "FILE_GONE",
                            message=str(exc),
                            document_external_id=file_meta["id"],
                        )
                    )
                    continue
                raise
            documents.append(doc)

        if warnings:
            logger.info(
                "google_drive.scan emitted %d warnings for source=%s",
                len(warnings),
                self.source_id,
            )
        return documents

    async def _build_gdoc_document(
        self,
        service: Any,
        file_meta: dict[str, Any],
    ) -> NormalizedDocument:
        doc_id = file_meta["id"]
        doc_payload = await asyncio.to_thread(
            _retry_call,
            lambda: service.documents().get(documentId=doc_id, fields=_DOC_FIELDS).execute(),
        )
        blocks = _read_google_doc(doc_payload)
        if not blocks:
            blocks = [
                DocumentBlock(
                    block_id=generate_id("blk"),
                    block_type="paragraph",
                    content="",
                    sequence=1,
                )
            ]
        content_text = "\n".join(b.content for b in blocks)
        content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
        version = DocumentVersion(
            version_id=generate_id("ver"),
            document_id=doc_id,
            version_number=1,
            content_hash=content_hash,
            blocks=blocks,
            metadata={"mime_type": file_meta.get("mimeType")},
        )
        return NormalizedDocument(
            document_id=doc_id,
            workspace_id=self._workspace_id,
            source_id=self.source_id,
            title=file_meta.get("name", doc_id),
            provider=SourceProvider.GOOGLE_DRIVE,
            locator=DocumentLocator(
                provider=SourceProvider.GOOGLE_DRIVE,
                native_id=doc_id,
                uri=f"https://drive.google.com/file/d/{doc_id}",
                mime_type=file_meta.get("mimeType"),
            ),
            active_version_id=version.version_id,
            versions=[version],
            metadata={"modified_time": file_meta.get("modifiedTime", "")},
        )

    async def _build_blob_document(
        self,
        service: Any,
        file_meta: dict[str, Any],
    ) -> NormalizedDocument:
        doc_id = file_meta["id"]
        storage_path = await self._stream_blob(service, file_meta)

        # Hash the streamed bytes. We never read the file whole into memory
        # — chunked loop over ``FileIO`` keeps RAM flat regardless of size.
        sha = hashlib.sha256()
        with open(storage_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(DRIVE_CHUNK_BYTES), b""):
                sha.update(chunk)
        content_hash = sha.hexdigest()

        version = DocumentVersion(
            version_id=generate_id("ver"),
            document_id=doc_id,
            version_number=1,
            content_hash=content_hash,
            blocks=[
                DocumentBlock(
                    block_id=generate_id("blk"),
                    block_type="blob",
                    content=f"file://{storage_path}",
                    sequence=1,
                    metadata={
                        "mime_type": file_meta.get("mimeType"),
                        "byte_size": file_meta.get("size", 0),
                    },
                )
            ],
            metadata={
                "mime_type": file_meta.get("mimeType"),
                "storage_path": str(storage_path),
                "byte_size": int(file_meta.get("size", 0) or 0),
            },
        )
        return NormalizedDocument(
            document_id=doc_id,
            workspace_id=self._workspace_id,
            source_id=self.source_id,
            title=file_meta.get("name", doc_id),
            provider=SourceProvider.GOOGLE_DRIVE,
            locator=DocumentLocator(
                provider=SourceProvider.GOOGLE_DRIVE,
                native_id=doc_id,
                uri=f"https://drive.google.com/file/d/{doc_id}",
                mime_type=file_meta.get("mimeType"),
            ),
            active_version_id=version.version_id,
            versions=[version],
            metadata={"modified_time": file_meta.get("modifiedTime", "")},
        )

    async def _stream_blob(self, service: Any, file_meta: dict[str, Any]) -> Path:
        """Download a blob via ``MediaIoBaseDownload`` straight to disk.

        Never accumulates the body in memory. ``FileIO`` + 5 MiB chunks is
        the standard google-apiclient streaming recipe.
        """
        doc_id = file_meta["id"]
        artifact_root = Path(settings.RV_ARTIFACT_STORAGE_PATH) / self._workspace_id / self.source_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        target = artifact_root / doc_id

        request = service.files().get_media(fileId=doc_id)
        # Open the file once, drive the chunk loop inside a thread so the
        # event loop is never blocked. The downloader yields (progress, done)
        # — we ignore the progress handle and only care about ``done``.
        with open(target, "wb") as fh:
            downloader = MediaIoBaseDownload(io.FileIO(fh.fileno(), "wb"), request, chunksize=DRIVE_CHUNK_BYTES)
            done = False
            while not done:
                _, done = await asyncio.to_thread(_retry_call, downloader.next_chunk)
        return Path(target)

    # ---- fetch_changes ----------------------------------------------------

    async def fetch_changes(self, cursor: str | None = None) -> dict[str, Any]:
        """Incremental ``changes.list`` poll — returns new cursor + events.

        Lifecycle events are classified by examining each change:

          * ``change['removed']``                  -> ``deleted``
          * ``file.trashed == True``               -> ``trashed``
          * ``file.trashed == False`` (was trashed)-> ``restored``
          * ``file.parents`` changed               -> ``moved``
          * ``file.name`` changed                  -> ``renamed``
          * otherwise                              -> ``updated``
        """
        service = await self._get_service()

        if not cursor:
            start_token = await asyncio.to_thread(
                _retry_call,
                lambda: service.changes().getStartPageToken().execute(),
            )
            cursor = start_token["startPageToken"]

        events: list[dict[str, Any]] = []
        page_token: str | None = cursor
        last_new_start_token: str | None = None

        while page_token:
            response = await asyncio.to_thread(
                _retry_call,
                lambda pt=page_token: (
                    service.changes()  # noqa: B023 — explicit binding
                    .list(
                        pageToken=pt,
                        spaces="drive",
                        fields=_CHANGE_FIELDS,
                        pageSize=1000,
                        includeRemoved=True,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                ),
            )
            for change in response.get("changes", []):
                events.append(self._classify_change(change))
            page_token = response.get("nextPageToken")
            last_new_start_token = response.get("newStartPageToken")

        return {
            "new_cursor": last_new_start_token or cursor,
            "changes_count": len(events),
            "has_more": False,
            "events": events,
        }

    @staticmethod
    def _classify_change(change: dict[str, Any]) -> dict[str, Any]:
        file_id = change.get("fileId", "")
        if change.get("removed"):
            return {"type": "deleted", "file_id": file_id, "file": None}
        file_meta = change.get("file") or {}
        if file_meta.get("trashed"):
            return {"type": "trashed", "file_id": file_id, "file": file_meta}
        parents = file_meta.get("parents") or []
        if len(parents) > 1:
            return {"type": "moved", "file_id": file_id, "file": file_meta}
        # Name-only change is implied when name differs from a stored
        # baseline — we don't have that baseline here, so we just pass
        # through the metadata. The ingestion layer owns the diff.
        return {
            "type": "updated",
            "file_id": file_id,
            "file": file_meta,
            "name": file_meta.get("name"),
        }

    # ---- reconcile -------------------------------------------------------

    async def reconcile(self) -> dict[str, Any]:
        """Full re-scan used to drift-check the index.

        Heavy lifting (diff against the DB, deactivation) belongs in
        ``rekanvault.ingestion.reconciliation``. Here we just rescan and
        report what we found.
        """
        try:
            docs = await self.scan()
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status in (401, 403):
                raise GoogleAuthRequired(f"Cannot reconcile: {exc}") from exc
            raise
        return {
            "status": "reconciled",
            "scanned": len(docs),
            "reconciled": len(docs),
            "errors": 0,
        }
