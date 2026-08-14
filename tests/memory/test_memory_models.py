"""Unit tests for Phase 5 Typed Memory models (P5-T1, P5-T2, P5-T7)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rekanvault.memory.models import (
    HIGH_IMPACT_MEMORY_TYPES,
    TYPED_MEMORY_MODELS,
    DecisionMemory,
    FactMemory,
    ImpactLevel,
    MemoryType,
    ReviewStatus,
    determine_review_status,
)
from rekanvault.storage.memory_repo import MemoryRepository
from rekanvault.storage.models import MemoryEvidenceBinding, MemoryReviewItem, TypedMemory


def test_all_18_memory_types_covered() -> None:
    """P5-T1: All 18 typed memory classes exist in TYPED_MEMORY_MODELS."""
    assert len(MemoryType) == 18
    assert len(TYPED_MEMORY_MODELS) == 18
    for mem_type in MemoryType:
        assert mem_type in TYPED_MEMORY_MODELS


def test_fact_memory_instantiation() -> None:
    ws_id = uuid4()
    fact = FactMemory(
        workspace_id=ws_id,
        title="Python 3.12 Support",
        summary="RekanVault uses Python 3.12 strictly.",
        statement="Python 3.12 is enforced in pyproject.toml.",
        evidence_chunk_ids=["doc_1#v1#chunk_001"],
    )
    assert fact.memory_type == MemoryType.FACT
    assert fact.workspace_id == ws_id
    assert fact.impact == ImpactLevel.MEDIUM
    assert fact.review_status == ReviewStatus.PENDING_REVIEW


def test_extra_fields_forbidden_rejection() -> None:
    """P5-T2: Unknown/hallucinated fields trigger ValidationError."""
    ws_id = uuid4()
    with pytest.raises(ValidationError) as exc_info:
        DecisionMemory(
            workspace_id=ws_id,
            title="ADR P5-0001",
            summary="Approved 18 memory schemas.",
            rationale="Type safety.",
            hallucinated_field="unsupported_value",  # Extra field
        )
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_high_impact_review_routing() -> None:
    """P5-T7: High impact categories and low confidence route to pending_review."""
    # High impact memory types always enter pending_review
    for mem_type in HIGH_IMPACT_MEMORY_TYPES:
        status = determine_review_status(mem_type, ImpactLevel.LOW, confidence=1.0)
        assert status == ReviewStatus.PENDING_REVIEW

    # High impact level (HIGH, CRITICAL) routes to pending_review
    status_high = determine_review_status(MemoryType.PERSON, ImpactLevel.HIGH, confidence=1.0)
    assert status_high == ReviewStatus.PENDING_REVIEW

    # Low confidence (< 0.85) routes to pending_review
    status_low_conf = determine_review_status(MemoryType.PERSON, ImpactLevel.LOW, confidence=0.7)
    assert status_low_conf == ReviewStatus.PENDING_REVIEW

    # Low impact + high confidence auto-commits to approved
    status_approved = determine_review_status(MemoryType.PERSON, ImpactLevel.LOW, confidence=0.95)
    assert status_approved == ReviewStatus.APPROVED


# --------------------------------------------------------------------------
# MemoryRepository integration tests (Phase 5, P5-T3 / P5-T7)
#
# AsyncMock session, MagicMock select results — same fixture-free style as
# tests/storage/test_source_repo.py. Exercises create → get → list →
# review_status → evidence bindings in a single coherent flow.
# --------------------------------------------------------------------------


def _make_session_with_lookup(memory: TypedMemory | None) -> tuple[AsyncMock, MagicMock]:
    """Build an AsyncMock session whose first ``execute`` returns ``memory``."""
    session = AsyncMock()
    lookup = MagicMock()
    lookup.scalar_one_or_none.return_value = memory
    session.execute.return_value = lookup
    session.add = MagicMock()
    return session, lookup


def _staged_rows(session: AsyncMock) -> list[Any]:
    return [call.args[0] for call in session.add.call_args_list if call.args]


@pytest.mark.asyncio
async def test_repository_create_get_and_list_flow() -> None:
    """create_memory stages a row + evidence bindings + initial review entry;
    subsequent get/list reads hit the same workspace scope."""
    session = AsyncMock()
    session.add = MagicMock()
    repo = MemoryRepository(session)
    workspace_id = uuid4()

    fact = FactMemory(
        workspace_id=workspace_id,
        title="Python 3.12 Strict",
        summary="RekanVault pins Python 3.12.",
        statement="pyproject.toml sets requires-python='>=3.12'.",
        evidence_chunk_ids=["doc_1#v1#chunk_001", "doc_1#v1#chunk_002"],
        created_by_user_id=uuid4(),
        prompt_version="p5-extract-v1",
        confidence=0.7,  # Low confidence → PENDING_REVIEW (P5-T7)
    )

    row = await repo.create_memory(workspace_id=workspace_id, memory=fact)

    assert isinstance(row, TypedMemory)
    assert row.workspace_id == workspace_id
    assert row.memory_type == MemoryType.FACT.value
    assert row.review_status == ReviewStatus.PENDING_REVIEW.value
    assert row.payload == {"statement": "pyproject.toml sets requires-python='>=3.12'.", "verification_method": None}

    staged = _staged_rows(session)
    assert any(isinstance(r, TypedMemory) for r in staged)
    assert sum(isinstance(r, MemoryEvidenceBinding) for r in staged) == 2
    # Caller owns the transaction — repo never commits.
    session.commit.assert_not_called()
    session.flush.assert_awaited()

    # get_memory + list_memories: same workspace, same lookup path.
    session, _ = _make_session_with_lookup(row)
    repo = MemoryRepository(session)
    found = await repo.get_memory(memory_id=row.id, workspace_id=workspace_id)
    assert found is row


@pytest.mark.asyncio
async def test_repository_list_filters_by_workspace_and_status() -> None:
    """list_memories narrows results to the caller's workspace + filters
    on memory_type and review_status when supplied."""
    session = AsyncMock()
    rows = [MagicMock(spec=TypedMemory) for _ in range(2)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session.execute.return_value = result

    repo = MemoryRepository(session)
    workspace_id = uuid4()
    listed = await repo.list_memories(
        workspace_id=workspace_id,
        memory_type=MemoryType.FACT,
        review_status=ReviewStatus.APPROVED,
        limit=10,
        offset=0,
    )

    assert listed == rows
    stmt = session.execute.await_args.args[0]
    compiled = str(stmt.compile())
    assert "typed_memories.workspace_id" in compiled
    assert "memory_type" in compiled
    assert "review_status" in compiled


@pytest.mark.asyncio
async def test_repository_update_review_status_records_audit_and_blocks_rejection() -> None:
    """update_review_status mutates review_status, stages a
    MemoryReviewItem audit row, and rejects terminal→anything without
    an explicit override action."""
    ws_id = uuid4()
    existing = TypedMemory(
        id=uuid4(),
        workspace_id=ws_id,
        memory_type=MemoryType.FACT.value,
        title="t",
        summary="s",
        payload={},
        review_status=ReviewStatus.PENDING_REVIEW.value,
    )
    session, _ = _make_session_with_lookup(existing)
    repo = MemoryRepository(session)

    reviewer_id = uuid4()
    approved = await repo.update_review_status(
        memory_id=existing.id,
        workspace_id=ws_id,
        status=ReviewStatus.APPROVED,
        reviewer_id=reviewer_id,
        action="approve",
        reason="Reviewed manually",
        diff_payload={"before": "pending", "after": "approved"},
    )

    assert approved.review_status == ReviewStatus.APPROVED.value
    staged = _staged_rows(session)
    assert any(
        getattr(r, "action", None) == "approve"
        and getattr(r, "reviewer_id", None) == reviewer_id
        and getattr(r, "diff_payload", None) == {"before": "pending", "after": "approved"}
        for r in staged
    )

    # Re-approve without override → terminal-status guard fires.
    session, _ = _make_session_with_lookup(approved)
    repo = MemoryRepository(session)
    from rekanvault.contracts.errors import NotFoundError

    with pytest.raises(NotFoundError) as exc_info:
        await repo.update_review_status(
            memory_id=existing.id,
            workspace_id=ws_id,
            status=ReviewStatus.PENDING_REVIEW,
            action="reject",  # not 'correct' / 'reopen'
        )
    assert "Cannot transition" in str(exc_info.value)


@pytest.mark.asyncio
async def test_bulk_invalidate_transitions_multiple_to_unsupported() -> None:
    """P5-T11: bulk_invalidate marks every listed memory UNSUPPORTED,
    records audit rows, and skips already-UNSUPPORTED items."""
    ws_id = uuid4()
    ids = [uuid4() for _ in range(3)]

    def _make_memory(mid, status: str) -> TypedMemory:
        return TypedMemory(
            id=mid,
            workspace_id=ws_id,
            memory_type=MemoryType.FACT.value,
            title="t",
            summary="s",
            payload={},
            review_status=status,
        )

    lookup = MagicMock()
    # bulk_invalidate calls get_memory 3×, then update_review_status calls
    # get_memory_or_raise 2× for the non-skipped items = 5 lookups total.
    lookup.scalar_one_or_none.side_effect = [
        _make_memory(ids[0], ReviewStatus.PENDING_REVIEW.value),
        _make_memory(ids[1], ReviewStatus.APPROVED.value),
        _make_memory(ids[2], ReviewStatus.UNSUPPORTED.value),
        _make_memory(ids[0], ReviewStatus.PENDING_REVIEW.value),  # re-lookup for update
        _make_memory(ids[1], ReviewStatus.APPROVED.value),  # re-lookup for update
    ]
    session = AsyncMock()
    session.add = MagicMock()
    session.execute.return_value = lookup

    repo = MemoryRepository(session)
    count = await repo.bulk_invalidate(ws_id, ids, "batch cleanup")

    assert count == 2  # third was already UNSUPPORTED, skipped
    staged = _staged_rows(session)
    assert sum(isinstance(r, MemoryReviewItem) for r in staged) == 2


@pytest.mark.asyncio
async def test_record_and_list_extraction_failures() -> None:
    """record_extraction_failure stages a row; list_extraction_failures reads it."""
    from rekanvault.storage.models import ExtractionFailure

    ws_id = uuid4()
    doc_id = uuid4()
    ver_id = uuid4()

    session = AsyncMock()
    session.add = MagicMock()
    repo = MemoryRepository(session)
    row = await repo.record_extraction_failure(
        workspace_id=ws_id,
        document_id=doc_id,
        document_version_id=ver_id,
        chunk_id="doc#v1#chunk_001",
        error_code="VALIDATION_ERROR",
        error_message="LLM response did not match the expected schema",
    )
    assert isinstance(row, ExtractionFailure)
    assert row.chunk_id == "doc#v1#chunk_001"
    assert row.error_code == "VALIDATION_ERROR"
    session.add.assert_called_once_with(row)
    session.commit.assert_not_called()

    result = MagicMock()
    result.scalars.return_value.all.return_value = [row]
    session2 = AsyncMock()
    session2.execute.return_value = result
    repo2 = MemoryRepository(session2)
    listed = await repo2.list_extraction_failures(ws_id)
    assert listed == [row]
    stmt = session2.execute.await_args.args[0]
    assert "extraction_failures.workspace_id" in str(stmt.compile())
