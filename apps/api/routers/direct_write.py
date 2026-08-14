"""Phase 5 Direct-Write Memory API router.

Six POST endpoints for human-authored typed memories (RV-DEC-P5-0003).
Each endpoint materializes a typed Pydantic model, persists it via
``MemoryRepository``, commits, and returns the stored row as a plain dict.

Pilot mode hard-codes the workspace via ``_PILOT_WORKSPACE_ID``; the real
implementation will inject the caller's resolved workspace through auth
middleware (P2-T6).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from rekanvault.memory.models import (
    DecisionMemory,
    IdeaMemory,
    ImpactLevel,
    LessonMemory,
    ProcedureMemory,
    ProjectMemory,
    ReviewStatus,
    RiskMemory,
)
from rekanvault.storage.database import get_db_session
from rekanvault.storage.memory_repo import MemoryRepository

router = APIRouter()

_PILOT_WORKSPACE_ID = uuid.UUID(settings.RV_PILOT_WORKSPACE_ID)
_PILOT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _workspace_id() -> uuid.UUID:
    """Return the workspace_id for the current request.

    Pilot mode: a single hard-coded workspace. The real implementation
    will read the verified Supabase JWT and look up the membership.
    """
    return _PILOT_WORKSPACE_ID


# ---- Request models --------------------------------------------------------


class DecisionCreateRequest(BaseModel):
    """Request body for ``POST /decisions``."""

    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    rationale: str
    alternatives_considered: list[str] = Field(default_factory=list)
    decision_maker: str | None = None
    impact: ImpactLevel = ImpactLevel.MEDIUM


class IdeaCreateRequest(BaseModel):
    """Request body for ``POST /ideas``."""

    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    proposal: str
    potential_impact: str | None = None
    impact: ImpactLevel = ImpactLevel.LOW


class ProjectCreateRequest(BaseModel):
    """Request body for ``POST /projects``."""

    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    project_code: str | None = None
    status: str = "active"
    owner: str | None = None
    impact: ImpactLevel = ImpactLevel.MEDIUM


class RiskCreateRequest(BaseModel):
    """Request body for ``POST /risks``."""

    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    threat: str
    mitigation: str | None = None
    severity: str = "MEDIUM"
    impact: ImpactLevel = ImpactLevel.HIGH


class LessonCreateRequest(BaseModel):
    """Request body for ``POST /lessons``."""

    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    takeaway: str
    context_description: str | None = None
    impact: ImpactLevel = ImpactLevel.MEDIUM


class ProcedureCreateRequest(BaseModel):
    """Request body for ``POST /procedures``."""

    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    steps: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    impact: ImpactLevel = ImpactLevel.LOW


# ---- helpers ---------------------------------------------------------------


def _ok(result: Any) -> dict[str, Any]:
    """Extract the standard response fields from a TypedMemory row."""
    return {
        "id": str(result.id),
        "memory_type": getattr(result, "memory_type", ""),
        "title": getattr(result, "title", ""),
        "review_status": getattr(result, "review_status", ""),
        "confidence": getattr(result, "confidence", 1.0),
    }


# ---- Endpoints -------------------------------------------------------------


@router.post("/decisions", response_model=dict[str, Any], status_code=201, tags=["Memory"])
async def create_decision(
    body: DecisionCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Direct-write a Decision memory. High-impact — routes to PENDING_REVIEW."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    memory = DecisionMemory(
        workspace_id=ws_id,
        created_by_user_id=_PILOT_USER_ID,
        title=body.title,
        summary=body.summary,
        impact=body.impact,
        confidence=1.0,
        review_status=ReviewStatus.PENDING_REVIEW,
        rationale=body.rationale,
        alternatives_considered=body.alternatives_considered,
        decision_maker=body.decision_maker,
    )
    result = await repo.create_memory(ws_id, memory)
    await session.commit()
    return _ok(result)


@router.post("/ideas", response_model=dict[str, Any], status_code=201, tags=["Memory"])
async def create_idea(
    body: IdeaCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Direct-write an Idea memory. Low impact — auto-approved."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    memory = IdeaMemory(
        workspace_id=ws_id,
        created_by_user_id=_PILOT_USER_ID,
        title=body.title,
        summary=body.summary,
        impact=body.impact,
        confidence=1.0,
        review_status=ReviewStatus.APPROVED,
        proposal=body.proposal,
        potential_impact=body.potential_impact,
    )
    result = await repo.create_memory(ws_id, memory)
    await session.commit()
    return _ok(result)


@router.post("/projects", response_model=dict[str, Any], status_code=201, tags=["Memory"])
async def create_project(
    body: ProjectCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Direct-write a Project memory. Auto-approved."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    memory = ProjectMemory(
        workspace_id=ws_id,
        created_by_user_id=_PILOT_USER_ID,
        title=body.title,
        summary=body.summary,
        impact=body.impact,
        confidence=1.0,
        review_status=ReviewStatus.APPROVED,
        project_code=body.project_code,
        status=body.status,
        owner=body.owner,
    )
    result = await repo.create_memory(ws_id, memory)
    await session.commit()
    return _ok(result)


@router.post("/risks", response_model=dict[str, Any], status_code=201, tags=["Memory"])
async def create_risk(
    body: RiskCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Direct-write a Risk memory. High-impact — routes to PENDING_REVIEW."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    memory = RiskMemory(
        workspace_id=ws_id,
        created_by_user_id=_PILOT_USER_ID,
        title=body.title,
        summary=body.summary,
        impact=body.impact,
        confidence=1.0,
        review_status=ReviewStatus.PENDING_REVIEW,
        threat=body.threat,
        mitigation=body.mitigation,
        severity=body.severity,
    )
    result = await repo.create_memory(ws_id, memory)
    await session.commit()
    return _ok(result)


@router.post("/lessons", response_model=dict[str, Any], status_code=201, tags=["Memory"])
async def create_lesson(
    body: LessonCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Direct-write a Lesson memory. Auto-approved."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    memory = LessonMemory(
        workspace_id=ws_id,
        created_by_user_id=_PILOT_USER_ID,
        title=body.title,
        summary=body.summary,
        impact=body.impact,
        confidence=1.0,
        review_status=ReviewStatus.APPROVED,
        takeaway=body.takeaway,
        context_description=body.context_description,
    )
    result = await repo.create_memory(ws_id, memory)
    await session.commit()
    return _ok(result)


@router.post("/procedures", response_model=dict[str, Any], status_code=201, tags=["Memory"])
async def create_procedure(
    body: ProcedureCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Direct-write a Procedure memory. Low impact — auto-approved."""
    repo = MemoryRepository(session)
    ws_id = _workspace_id()
    memory = ProcedureMemory(
        workspace_id=ws_id,
        created_by_user_id=_PILOT_USER_ID,
        title=body.title,
        summary=body.summary,
        impact=body.impact,
        confidence=1.0,
        review_status=ReviewStatus.APPROVED,
        steps=body.steps,
        prerequisites=body.prerequisites,
    )
    result = await repo.create_memory(ws_id, memory)
    await session.commit()
    return _ok(result)


__all__ = ["router"]
