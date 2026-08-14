"""Unit tests for P5 direct-write memory audit trail (P5-T8).

Direct-write templates (RV-DEC-P5-0003) must:
- Record author ID (created_by_user_id)
- Set confidence to 1.0 (human-authored)
- Create MemoryReviewItem audit rows for PENDING_REVIEW items
- Auto-approve low-impact items without review entries
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rekanvault.memory.models import (
    DecisionMemory,
    IdeaMemory,
    LessonMemory,
    ReviewStatus,
    RiskMemory,
)
from rekanvault.storage.memory_repo import MemoryRepository
from rekanvault.storage.models import MemoryReviewItem, TypedMemory


def _staged_rows(session: Any) -> list[Any]:
    return [call.args[0] for call in session.add.call_args_list if call.args]


def _make_session_with_memory(memory: TypedMemory) -> tuple[AsyncMock, MagicMock]:
    session = AsyncMock()
    lookup = MagicMock()
    lookup.scalar_one_or_none.return_value = memory
    session.execute.return_value = lookup
    session.add = MagicMock()
    return session, lookup


@pytest.mark.asyncio
async def test_direct_write_decision_creates_review_entry() -> None:
    """P5-T8: High-impact Decision → PENDING_REVIEW + review audit row."""
    ws_id = uuid4()
    user_id = uuid4()

    decision = DecisionMemory(
        workspace_id=ws_id,
        title="Pilot scope freeze",
        summary="Lock the pilot corpus for 0.1.0.",
        rationale="Narrow scope = faster feedback.",
        created_by_user_id=user_id,
    )

    session = AsyncMock()
    session.add = MagicMock()
    repo = MemoryRepository(session)
    row = await repo.create_memory(ws_id, decision)

    assert row.review_status == ReviewStatus.PENDING_REVIEW.value
    assert row.confidence == 1.0

    staged = _staged_rows(session)
    assert any(isinstance(r, TypedMemory) for r in staged)
    assert any(isinstance(r, MemoryReviewItem) for r in staged)


@pytest.mark.asyncio
async def test_direct_write_idea_auto_approves() -> None:
    """P5-T8: Low-impact Idea with confidence=1.0 → auto-APPROVED, no review row."""
    ws_id = uuid4()
    user_id = uuid4()

    idea = IdeaMemory(
        workspace_id=ws_id,
        title="Draft onboarding guide",
        summary="Create a 1-page guide for new team members.",
        proposal="Write and publish an onboarding doc.",
        created_by_user_id=user_id,
    )

    session = AsyncMock()
    session.add = MagicMock()
    repo = MemoryRepository(session)
    row = await repo.create_memory(ws_id, idea)

    assert row.review_status == ReviewStatus.APPROVED.value

    staged = _staged_rows(session)
    assert not any(isinstance(r, MemoryReviewItem) for r in staged)


@pytest.mark.asyncio
async def test_direct_write_risk_routes_to_pending_review() -> None:
    """P5-T8: Risk (HIGH_IMPACT) → PENDING_REVIEW regardless of confidence."""
    ws_id = uuid4()

    risk = RiskMemory(
        workspace_id=ws_id,
        title="Single VPS failure",
        summary="If the VPS dies we lose API + worker + web.",
        threat="VPS hardware failure.",
        mitigation="Daily backups to off-host storage.",
    )

    session = AsyncMock()
    session.add = MagicMock()
    repo = MemoryRepository(session)
    row = await repo.create_memory(ws_id, risk)

    assert row.review_status == ReviewStatus.PENDING_REVIEW.value

    staged = _staged_rows(session)
    assert any(isinstance(r, MemoryReviewItem) for r in staged)


@pytest.mark.asyncio
async def test_direct_write_sets_confidence_to_one() -> None:
    """P5-T8: Direct-write confidence is always 1.0 (human-authored)."""
    ws_id = uuid4()

    risk = RiskMemory(
        workspace_id=ws_id,
        title="Spike in API latency",
        summary="Qdrant free-tier latency spiked 3x during reindex.",
        threat="Performance degradation under reindex load.",
    )

    session = AsyncMock()
    session.add = MagicMock()
    repo = MemoryRepository(session)
    row = await repo.create_memory(ws_id, risk)

    assert row.confidence == 1.0


@pytest.mark.asyncio
async def test_direct_write_preserves_author_id() -> None:
    """P5-T8: created_by_user_id is preserved through create_memory."""
    ws_id = uuid4()
    user_id = uuid4()

    decision = DecisionMemory(
        workspace_id=ws_id,
        title="Use uv for Python deps",
        summary="uv is faster and produces reproducible lockfiles.",
        rationale="Speed + reproducibility.",
        created_by_user_id=user_id,
    )

    session = AsyncMock()
    session.add = MagicMock()
    repo = MemoryRepository(session)
    row = await repo.create_memory(ws_id, decision)

    assert row.created_by_user_id == user_id


@pytest.mark.asyncio
async def test_direct_write_lesson_auto_approves() -> None:
    """P5-T8: Low-impact Lesson → auto-APPROVED, no review row."""
    ws_id = uuid4()

    lesson = LessonMemory(
        workspace_id=ws_id,
        title="Always validate chunk IDs",
        summary="P4 bug: chunk_id mismatch caused zero recall for 45 min.",
        takeaway="Run chunk_id parity checks before deploying new chunker.",
    )

    session = AsyncMock()
    session.add = MagicMock()
    repo = MemoryRepository(session)
    row = await repo.create_memory(ws_id, lesson)

    assert row.review_status == ReviewStatus.APPROVED.value

    staged = _staged_rows(session)
    assert not any(isinstance(r, MemoryReviewItem) for r in staged)
