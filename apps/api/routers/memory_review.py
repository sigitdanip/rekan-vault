"""Phase 5 Memory Review API router.

Router delegates to ``MemoryRepository``. Session injection is via the
global ``get_db_session`` dependency from ``rekanvault.storage.database``.

Pilot mode hard-codes the workspace via ``_PILOT_WORKSPACE_ID``; the real
implementation will inject the caller's resolved workspace through auth
middleware (P2-T6).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from rekanvault.contracts.errors import NotFoundError, RekanVaultError
from rekanvault.memory.models import MemoryType, ReviewStatus
from rekanvault.storage.database import get_db_session
from rekanvault.storage.memory_repo import MemoryRepository

router = APIRouter()

_PILOT_WORKSPACE_ID = uuid.UUID(settings.RV_PILOT_WORKSPACE_ID)


def _workspace_id() -> uuid.UUID:
    """Return the workspace_id for the current request.

    Pilot mode: a single hard-coded workspace. The real implementation
    will read the verified Supabase JWT and look up the membership.
    """
    return _PILOT_WORKSPACE_ID


class ReviewActionRequest(BaseModel):
    """Request body for ``POST /api/v1/memories/{memory_id}/review``."""

    action: str = Field(..., description="approve, reject, dispute, defer, correct")
    reason: str | None = None
    diff_payload: dict[str, object] | None = None


class BulkInvalidateRequest(BaseModel):
    """Request body for ``POST /api/v1/memories/bulk-invalidate`` (P5-T11)."""

    memory_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    reason: str = Field(..., min_length=1)


def _to_memory_dict(memory: object) -> dict[str, object]:
    return {
        "id": str(memory.id),  # type: ignore[attr-defined]
        "memory_type": memory.memory_type,  # type: ignore[attr-defined]
        "title": memory.title,  # type: ignore[attr-defined]
        "summary": memory.summary,  # type: ignore[attr-defined]
        "impact": memory.impact,  # type: ignore[attr-defined]
        "confidence": memory.confidence,  # type: ignore[attr-defined]
        "review_status": memory.review_status,  # type: ignore[attr-defined]
        "created_at": memory.created_at.isoformat(),  # type: ignore[attr-defined]
        "payload": memory.payload,  # type: ignore[attr-defined]
    }


@router.get("", response_model=list[dict[str, object]], tags=["Memory"])
async def list_memories(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    memory_type: Annotated[MemoryType | None, Query()] = None,
    review_status: Annotated[ReviewStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, object]]:
    """List memories in the pilot workspace with optional filters."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    memories = await repo.list_memories(
        ws_id,
        memory_type=memory_type,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )
    return [_to_memory_dict(m) for m in memories]


@router.get("/{memory_id}", response_model=dict[str, object], tags=["Memory"])
async def get_memory(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    memory_id: Annotated[uuid.UUID, Path()],
) -> dict[str, object]:
    """Fetch a single memory by id; 404 if absent in this workspace."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    memory = await repo.get_memory(memory_id, ws_id)
    if memory is None:
        raise NotFoundError(
            message=f"Memory not found: {memory_id}",
            target="memory",
            details={"memory_id": str(memory_id)},
        )
    return _to_memory_dict(memory)


@router.post("/{memory_id}/review", response_model=dict[str, object], status_code=200, tags=["Memory"])
async def review_memory(
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    memory_id: Annotated[uuid.UUID, Path()],
) -> dict[str, object]:
    """Submit a review action (approve/reject/dispute/defer/correct).

    ``correct`` is still an APPROVED transition — it carries a
    ``diff_payload`` describing the correction.
    """
    status_map = {
        "approve": ReviewStatus.APPROVED,
        "reject": ReviewStatus.REJECTED,
        "dispute": ReviewStatus.DISPUTED,
        "defer": ReviewStatus.DEFERRED,
        "correct": ReviewStatus.APPROVED,
    }
    if body.action not in status_map:
        raise RekanVaultError(
            message=f"Invalid action: {body.action}",
            target="review",
            details={"allowed": sorted(status_map)},
        )

    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    new_status = status_map[body.action]
    result = await repo.update_review_status(
        memory_id,
        ws_id,
        new_status,
        action=body.action,
        reason=body.reason,
        diff_payload=body.diff_payload,
    )
    await session.commit()
    return {
        "id": str(result.id),
        "review_status": result.review_status,
        "action": body.action,
    }


@router.post("/bulk-invalidate", response_model=dict[str, object], status_code=200, tags=["Memory"])
async def bulk_invalidate(
    body: BulkInvalidateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, object]:
    """Batch-invalidate memories (P5-T11). Transitions every listed memory
    to UNSUPPORTED and records structured audit entries."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    count = await repo.bulk_invalidate(ws_id, body.memory_ids, body.reason)
    await session.commit()
    return {"affected_count": count, "action": "bulk_invalidate", "reason": body.reason}


__all__ = ["router", "ReviewActionRequest", "BulkInvalidateRequest"]
