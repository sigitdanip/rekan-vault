"""
Sources API router (P3).

CRUD + health + sync triggers for the source-management domain. The
router does no business logic — it delegates to ``SourceManager`` and
``JobQueueManager``. Session injection is via the global ``get_db_session``
dependency from ``rekanvault.storage.database``.

Ponytail: a single ``APIRouter`` with six endpoints, no per-endpoint
service class. The router IS the composition layer.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from rekanvault.contracts.errors import NotFoundError
from rekanvault.contracts.sources import (
    JobTriggerResponse,
    RegisterSourceRequest,
    SourceDetail,
    SourceHealth,
    SourceRootEntry,
    SourceSummary,
    SyncJobEntry,
)
from rekanvault.sources.manager import SourceManager
from rekanvault.storage.database import get_db_session
from rekanvault.storage.jobs import JobQueueManager
from rekanvault.storage.source_repo import SourceRepository

router = APIRouter()

_PILOT_WORKSPACE_ID = uuid.UUID(settings.RV_PILOT_WORKSPACE_ID)


def _workspace_id() -> uuid.UUID:
    """Return the workspace_id for the current request.

    Pilot mode: a single hard-coded workspace. The real implementation
    will read the verified Supabase JWT and look up the membership.
    """
    return _PILOT_WORKSPACE_ID


@router.get("", response_model=list[SourceSummary], tags=["Sources"])
async def list_sources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SourceSummary]:
    """List all sources in the current workspace."""
    repo = SourceRepository()
    workspace_id = _workspace_id()
    sources = await repo.list_sources(session=session, workspace_id=workspace_id)
    summaries: list[SourceSummary] = []
    for source in sources:
        latest = await repo.latest_sync_job(session=session, workspace_id=workspace_id, source_id=source.id)
        summaries.append(
            SourceSummary(
                source_id=str(source.id),
                provider=source.provider,
                name=source.name,
                status=source.status,
                workspace_id=str(source.workspace_id),
                created_at=source.created_at,
                last_sync_at=latest.completed_at if latest else None,
                last_sync_status=latest.status if latest else None,
            )
        )
    return summaries


@router.post("", response_model=SourceDetail, status_code=201, tags=["Sources"])
async def register_source(
    body: RegisterSourceRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceDetail:
    """Register a new source. SourceRoot row is created from the request."""
    manager = SourceManager()
    workspace_id = _workspace_id()
    source = await manager.register_source(
        session=session,
        workspace_id=workspace_id,
        provider=body.provider,
        name=body.name,
        root_external_id=body.root_external_id,
        root_path=body.root_path,
        config=body.config,
    )
    await session.commit()
    return _to_source_detail(
        source=source,
        roots=[
            SourceRootEntry(
                external_id=body.root_external_id,
                path_or_name=body.root_path,
                created_at=source.created_at,
            )
        ],
        cursor=None,
        cursor_updated_at=None,
        recent_jobs=[],
    )


@router.get("/{source_id}", response_model=SourceDetail, tags=["Sources"])
async def get_source(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    source_id: Annotated[uuid.UUID, Path()],
) -> SourceDetail:
    repo = SourceRepository()
    workspace_id = _workspace_id()
    source = await repo.get_source(session=session, workspace_id=workspace_id, source_id=source_id)
    if source is None:
        raise NotFoundError(
            message=f"Source not found: {source_id}",
            target="source",
            details={"source_id": str(source_id)},
        )

    roots = await repo.list_source_roots(session=session, workspace_id=workspace_id, source_id=source_id)
    cursor = await repo.get_provider_cursor(session=session, workspace_id=workspace_id, source_id=source_id)
    jobs = await repo.list_recent_sync_jobs(session=session, workspace_id=workspace_id, source_id=source_id)

    return _to_source_detail(
        source=source,
        roots=[
            SourceRootEntry(
                external_id=r.external_id,
                path_or_name=r.path_or_name,
                created_at=r.created_at,
            )
            for r in roots
        ],
        cursor=cursor.cursor_value if cursor else None,
        cursor_updated_at=cursor.updated_at if cursor else None,
        recent_jobs=[
            SyncJobEntry(
                sync_job_id=str(j.id),
                job_type=str((j.stats or {}).get("job_type", "unknown")),
                status=j.status,
                started_at=j.started_at,
                completed_at=j.completed_at,
                stats={k: v for k, v in (j.stats or {}).items() if k != "job_type"},
            )
            for j in jobs
        ],
    )


@router.get("/{source_id}/health", response_model=SourceHealth, tags=["Sources"])
async def get_source_health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    source_id: Annotated[uuid.UUID, Path()],
) -> SourceHealth:
    manager = SourceManager()
    workspace_id = _workspace_id()
    health = await manager.get_health(session=session, workspace_id=workspace_id, source_id=source_id)
    return SourceHealth(**health)


@router.post("/{source_id}/sync", response_model=JobTriggerResponse, tags=["Sources"])
async def trigger_sync(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    source_id: Annotated[uuid.UUID, Path()],
) -> JobTriggerResponse:
    """Enqueue a sync job for the worker to pick up."""
    repo = SourceRepository()
    workspace_id = _workspace_id()
    source = await repo.get_source(session=session, workspace_id=workspace_id, source_id=source_id)
    if source is None:
        raise NotFoundError(
            message=f"Source not found: {source_id}",
            target="source",
            details={"source_id": str(source_id)},
        )

    queue = JobQueueManager(session=session)
    idempotency_key = f"sync:{source_id}:{uuid.uuid4().hex[:12]}"
    job = await queue.enqueue_job(
        workspace_id=workspace_id,
        job_type="sync_source",
        payload={"source_id": str(source_id)},
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return JobTriggerResponse(
        sync_job_id=str(job.id),
        job_type="sync_source",
        status=job.status,
    )


@router.post("/{source_id}/reconcile", response_model=JobTriggerResponse, tags=["Sources"])
async def trigger_reconcile(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    source_id: Annotated[uuid.UUID, Path()],
) -> JobTriggerResponse:
    """Enqueue a reconcile job (full rescan + drift check)."""
    repo = SourceRepository()
    workspace_id = _workspace_id()
    source = await repo.get_source(session=session, workspace_id=workspace_id, source_id=source_id)
    if source is None:
        raise NotFoundError(
            message=f"Source not found: {source_id}",
            target="source",
            details={"source_id": str(source_id)},
        )

    queue = JobQueueManager(session=session)
    idempotency_key = f"reconcile:{source_id}:{uuid.uuid4().hex[:12]}"
    job = await queue.enqueue_job(
        workspace_id=workspace_id,
        job_type="reconcile_source",
        payload={"source_id": str(source_id)},
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return JobTriggerResponse(
        sync_job_id=str(job.id),
        job_type="reconcile_source",
        status=job.status,
    )


# ---- helpers ---------------------------------------------------------------


def _to_source_detail(
    *,
    source: Any,
    roots: list[SourceRootEntry],
    cursor: str | None,
    cursor_updated_at: Any,
    recent_jobs: list[SyncJobEntry],
) -> SourceDetail:
    return SourceDetail(
        source_id=str(source.id),
        workspace_id=str(source.workspace_id),
        provider=source.provider,
        name=source.name,
        status=source.status,
        config=dict(source.config or {}),
        roots=roots,
        cursor=cursor,
        cursor_updated_at=cursor_updated_at,
        recent_jobs=recent_jobs,
    )


__all__ = ["router"]
