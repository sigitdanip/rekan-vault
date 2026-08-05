"""
Source repository (P3 — source persistence layer).

CRUD + cursor + sync-job lifecycle for ``Source`` / ``SourceRoot`` /
``ProviderCursor`` / ``SyncJob``. Used by ``SourceManager`` and the API
router; no business logic, just persistence.

Ponytail: one class, table-per-method-group. No abstract repository, no
generic CRUD — there's exactly one schema and one set of callers.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.storage.models import (
    ProviderCursor,
    Source,
    SourceRoot,
    SyncJob,
    utc_now,
)


class SourceRepository:
    """Persistence for source-management rows.

    Every method takes an explicit ``workspace_id`` so the query is
    RLS-ready (security invariant from P2).
    """

    # ---- Source ------------------------------------------------------------

    async def create_source(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        provider: str,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> Source:
        source = Source(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            provider=provider,
            name=name,
            config=dict(config or {}),
        )
        session.add(source)
        await session.flush()
        return source

    async def get_source(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> Source | None:
        stmt = select(Source).where(Source.workspace_id == workspace_id, Source.id == source_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sources(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> list[Source]:
        stmt = select(Source).where(Source.workspace_id == workspace_id).order_by(Source.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_source_status(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        status: str,
    ) -> None:
        stmt = (
            update(Source)
            .where(Source.workspace_id == workspace_id, Source.id == source_id)
            .values(status=status, updated_at=utc_now())
        )
        await session.execute(stmt)

    # ---- SourceRoot --------------------------------------------------------

    async def create_source_root(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        external_id: str,
        path_or_name: str,
    ) -> SourceRoot:
        root = SourceRoot(
            id=uuid.uuid4(),
            source_id=source_id,
            workspace_id=workspace_id,
            external_id=external_id,
            path_or_name=path_or_name,
        )
        session.add(root)
        await session.flush()
        return root

    async def list_source_roots(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> list[SourceRoot]:
        stmt = (
            select(SourceRoot)
            .where(SourceRoot.workspace_id == workspace_id, SourceRoot.source_id == source_id)
            .order_by(SourceRoot.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ---- ProviderCursor ----------------------------------------------------

    async def save_provider_cursor(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        cursor_value: str,
    ) -> ProviderCursor:
        """Upsert a provider cursor — one row per source (unique on
        ``source_id``). The cursor is the change-feed watermark the next
        ``run_sync`` picks up from."""
        existing = await self.get_provider_cursor(session, workspace_id, source_id)
        if existing is not None:
            existing.cursor_value = cursor_value
            existing.updated_at = utc_now()
            await session.flush()
            return existing
        cursor = ProviderCursor(
            id=uuid.uuid4(),
            source_id=source_id,
            workspace_id=workspace_id,
            cursor_value=cursor_value,
        )
        session.add(cursor)
        await session.flush()
        return cursor

    async def get_provider_cursor(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> ProviderCursor | None:
        stmt = select(ProviderCursor).where(
            ProviderCursor.workspace_id == workspace_id,
            ProviderCursor.source_id == source_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # ---- SyncJob -----------------------------------------------------------

    async def create_sync_job(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        job_type: str,
    ) -> SyncJob:
        # Schema has no job_type column on sync_jobs (P2 baseline); the
        # type rides along in stats so the API can surface it.
        job = SyncJob(
            id=uuid.uuid4(),
            source_id=source_id,
            workspace_id=workspace_id,
            status="pending",
            started_at=utc_now(),
            stats={"job_type": job_type},
        )
        session.add(job)
        await session.flush()
        return job

    async def complete_sync_job(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        sync_job_id: uuid.UUID,
        status: str,
        stats: dict[str, Any] | None = None,
    ) -> None:
        # Merge so we don't clobber job_type (and any other fields the
        # create path staged into stats). The full row is the source of
        # truth, so callers that want to override must pass them in.
        existing = await session.execute(
            select(SyncJob).where(SyncJob.workspace_id == workspace_id, SyncJob.id == sync_job_id)
        )
        row = existing.scalar_one_or_none()
        merged: dict[str, Any] = dict(row.stats or {}) if row else {}
        merged.update(dict(stats or {}))
        stmt = (
            update(SyncJob)
            .where(SyncJob.workspace_id == workspace_id, SyncJob.id == sync_job_id)
            .values(
                status=status,
                stats=merged,
                completed_at=utc_now(),
            )
        )
        await session.execute(stmt)

    async def latest_sync_job(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> SyncJob | None:
        stmt = (
            select(SyncJob)
            .where(SyncJob.workspace_id == workspace_id, SyncJob.source_id == source_id)
            .order_by(SyncJob.started_at.desc().nulls_last())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent_sync_jobs(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        limit: int = 10,
    ) -> list[SyncJob]:
        stmt = (
            select(SyncJob)
            .where(SyncJob.workspace_id == workspace_id, SyncJob.source_id == source_id)
            .order_by(SyncJob.started_at.desc().nulls_last())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["SourceRepository"]
