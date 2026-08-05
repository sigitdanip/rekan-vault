"""
Source lifecycle manager (P3 — ingestion orchestration).

Coordinates: source registration, scan, sync, and health. Wraps the
``BaseConnector`` subclasses (``GoogleDriveConnector``, ``NotionConnector``)
and the storage repos. Pure orchestration — no business logic embedded in
the connectors or the repos lives here.

Ponytail: a single class with four methods that match the four lifecycle
operations. No abstract ``ISourceManager`` — only one source manager
exists. Connector resolution is a small dict lookup, not a registry class.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Type

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.contracts.documents import NormalizedDocument
from rekanvault.contracts.errors import ErrorCode, NotFoundError, RekanVaultError
from rekanvault.sources.base import BaseConnector
from rekanvault.sources.google_drive import GoogleDriveConnector
from rekanvault.sources.notion import NotionConnector
from rekanvault.storage.document_repo import DocumentRepository
from rekanvault.storage.models import Document, Source
from rekanvault.storage.source_repo import SourceRepository

_CONNECTOR_REGISTRY: dict[str, Type[BaseConnector]] = {
    "google_drive": GoogleDriveConnector,
    "notion": NotionConnector,
}


def register_connector(provider: str, cls: Type[BaseConnector]) -> None:
    """Add or replace a connector implementation for a provider name.

    Used by tests to swap in fakes — the registry lives at module scope
    so a single ``register_connector`` call takes effect everywhere.
    """
    _CONNECTOR_REGISTRY[provider] = cls


def _resolve_connector(provider: str) -> Type[BaseConnector]:
    if provider not in _CONNECTOR_REGISTRY:
        raise RekanVaultError(
            message=f"Unknown source provider: {provider}",
            code=ErrorCode.VALIDATION_ERROR,
            target="source",
            details={"provider": provider, "known": sorted(_CONNECTOR_REGISTRY.keys())},
        )
    return _CONNECTOR_REGISTRY[provider]


class SourceManager:
    """Orchestrates source registration and per-source scan/sync/health."""

    def __init__(
        self,
        source_repo: SourceRepository | None = None,
        document_repo: DocumentRepository | None = None,
    ) -> None:
        self._sources = source_repo or SourceRepository()
        self._documents = document_repo or DocumentRepository()

    # ---- registration ------------------------------------------------------

    async def register_source(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        provider: str,
        name: str,
        root_external_id: str,
        root_path: str,
        config: dict[str, Any] | None = None,
    ) -> Source:
        """Create a Source + initial SourceRoot row.

        The token (if any) is encrypted by the caller via
        ``credential_repo.store_credential`` and bound to the source UUID
        by the connector. We don't store the token here.
        """
        # Validate provider up front — fail before we write the row.
        _resolve_connector(provider)

        source = await self._sources.create_source(
            session=session,
            workspace_id=workspace_id,
            provider=provider,
            name=name,
            config=config,
        )
        await self._sources.create_source_root(
            session=session,
            workspace_id=workspace_id,
            source_id=source.id,
            external_id=root_external_id,
            path_or_name=root_path,
        )
        return source

    # ---- scan / sync -------------------------------------------------------

    async def run_scan(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> dict[str, int]:
        """Full inventory scan. Returns stats — caller persists them on
        the SyncJob row and the Source.status field."""
        source = await self._require_source(session, workspace_id, source_id)
        connector = self._build_connector(source)
        sync_job = await self._sources.create_sync_job(
            session=session,
            workspace_id=workspace_id,
            source_id=source_id,
            job_type="scan",
        )

        documents: list[NormalizedDocument] = []
        errors = 0
        try:
            documents = await connector.scan()
        except RekanVaultError:
            errors += 1
            await self._sources.complete_sync_job(
                session=session,
                workspace_id=workspace_id,
                sync_job_id=sync_job.id,
                status="failed",
                stats={"errors": 1, "scanned": 0, "persisted": 0},
            )
            await self._sources.update_source_status(session, workspace_id, source_id, "error")
            raise

        new_count, updated_count = await self._persist_documents(
            session=session,
            workspace_id=workspace_id,
            source_id=source_id,
            documents=documents,
        )

        stats = {
            "scanned": len(documents),
            "new": new_count,
            "updated": updated_count,
            "errors": errors,
        }
        await self._sources.complete_sync_job(
            session=session,
            workspace_id=workspace_id,
            sync_job_id=sync_job.id,
            status="completed",
            stats=stats,
        )
        await self._sources.update_source_status(session, workspace_id, source_id, "active")
        return stats

    async def run_sync(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> dict[str, int]:
        """Incremental change-feed poll. Loads the stored cursor, calls
        ``fetch_changes``, persists the result, advances the cursor.

        Notion's ``fetch_changes`` returns a dict with ``new_cursor`` and
        ``changes_count``; Google Drive's returns ``newStartPageToken``.
        We persist whatever the connector hands us as an opaque string."""
        source = await self._require_source(session, workspace_id, source_id)
        connector = self._build_connector(source)
        cursor = await self._sources.get_provider_cursor(session, workspace_id, source_id)
        cursor_value = cursor.cursor_value if cursor is not None else None

        sync_job = await self._sources.create_sync_job(
            session=session,
            workspace_id=workspace_id,
            source_id=source_id,
            job_type="sync",
        )

        try:
            result = await connector.fetch_changes(cursor_value)
        except RekanVaultError:
            await self._sources.complete_sync_job(
                session=session,
                workspace_id=workspace_id,
                sync_job_id=sync_job.id,
                status="failed",
                stats={"errors": 1, "changes": 0},
            )
            await self._sources.update_source_status(session, workspace_id, source_id, "error")
            raise

        # fetch_changes returns a generic dict; the only contract we trust
        # is ``new_cursor`` (string) — every connector normalizes that.
        new_cursor = str(result.get("new_cursor", ""))
        if new_cursor:
            await self._sources.save_provider_cursor(
                session=session,
                workspace_id=workspace_id,
                source_id=source_id,
                cursor_value=new_cursor,
            )

        stats = {
            "changes": int(result.get("changes_count", 0)),
            "new_cursor_set": bool(new_cursor),
        }
        await self._sources.complete_sync_job(
            session=session,
            workspace_id=workspace_id,
            sync_job_id=sync_job.id,
            status="completed",
            stats=stats,
        )
        await self._sources.update_source_status(session, workspace_id, source_id, "active")
        return stats

    # ---- health -----------------------------------------------------------

    async def get_health(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Health snapshot: latest sync status, cursor freshness, doc count,
        error/warning counts. Read-only — no side effects."""
        source = await self._require_source(session, workspace_id, source_id)
        latest = await self._sources.latest_sync_job(session, workspace_id, source_id)
        cursor = await self._sources.get_provider_cursor(session, workspace_id, source_id)
        doc_count = await self._count_documents(session, workspace_id, source_id)

        stats = dict(latest.stats or {}) if latest else {}
        error_count = int(stats.get("errors", 0))
        warning_count = int(stats.get("warnings", 0))

        return {
            "source_id": str(source_id),
            "status": _map_health_status(source.status, latest),
            "online": source.status == "active",
            "last_sync_at": latest.completed_at if latest and latest.completed_at else None,
            "last_sync_status": latest.status if latest else None,
            "error_count": error_count,
            "warning_count": warning_count,
            "cursor_freshness_seconds": _seconds_since(cursor.updated_at) if cursor is not None else None,
            "document_count": doc_count,
        }

    # ---- internals ---------------------------------------------------------

    async def _persist_documents(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        documents: list[NormalizedDocument],
    ) -> tuple[int, int]:
        """Persist every NormalizedDocument. Return (new_count, updated_count)
        by checking which external_ids already had a row before we wrote."""
        pre_existing: set[str] = set()
        for doc in documents:
            existing = await self._documents.get_by_external_id(
                session=session,
                workspace_id=workspace_id,
                source_id=source_id,
                external_id=doc.locator.native_id,
            )
            if existing is not None:
                pre_existing.add(doc.locator.native_id)
        new_count = 0
        updated_count = 0
        for doc in documents:
            is_new = doc.locator.native_id not in pre_existing
            await self._documents.upsert_document(
                session=session,
                workspace_id=workspace_id,
                source_id=source_id,
                normalized=doc,
            )
            if is_new:
                new_count += 1
            else:
                updated_count += 1
        return new_count, updated_count

    async def _count_documents(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> int:
        stmt = select(func.count(Document.id)).where(
            Document.workspace_id == workspace_id,
            Document.source_id == source_id,
        )
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def _require_source(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> Source:
        source = await self._sources.get_source(session, workspace_id, source_id)
        if source is None:
            raise NotFoundError(
                message=f"Source not found: {source_id}",
                target="source",
                details={"source_id": str(source_id)},
            )
        return source

    def _build_connector(self, source: Source) -> BaseConnector:
        cls = _resolve_connector(source.provider)
        # Connectors take a string source_id (RekanVault-prefixed) and a
        # free-form config dict. They derive the DB UUID internally
        # (see google_drive._load_credentials).
        return cls(source_id=f"src_{source.id.hex[:16]}", config=dict(source.config or {}))


__all__ = ["SourceManager", "register_connector"]


def _seconds_since(when: datetime) -> int:
    return max(0, int((datetime.now(timezone.utc) - when).total_seconds()))


# P3-T8 contract: status ∈ {healthy, degraded, error, unconfigured}.
# Source.status uses a different vocabulary; this is the only mapping.
_HEALTH_STATUS_MAP: dict[str, str] = {
    "active": "healthy",
    "error": "error",
    "disconnected": "unconfigured",
}


def _map_health_status(internal_status: str, latest: Any) -> str:
    base = _HEALTH_STATUS_MAP.get(internal_status, "unconfigured")
    if base == "healthy" and latest is None:
        return "unconfigured"
    if base == "healthy" and (dict(latest.stats or {}) if latest else {}).get("errors", 0):
        return "degraded"
    return base
