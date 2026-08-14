"""
Memory repository (P5 — typed memory persistence layer).

CRUD + review queue + evidence bindings for ``TypedMemory``,
``MemoryEvidenceBinding``, and ``MemoryReviewItem`` (RV-DEC-P5-0001).

Ponytail: one class, table-per-method-group. Callers own the transaction
(``commit``/``rollback``); the repo only stages and flushes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.contracts.errors import NotFoundError
from rekanvault.memory.models import (
    BaseTypedMemory,
    MemoryType,
    ReviewStatus,
    determine_review_status,
)
from rekanvault.storage.models import (
    ExtractionFailure,
    MemoryEvidenceBinding,
    MemoryReviewItem,
    TypedMemory,
    utc_now,
)

# Review actions that map to PENDING_REVIEW → terminal transitions.
_TERMINAL_REVIEW_STATUSES: frozenset[ReviewStatus] = frozenset(
    {ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.DEFERRED, ReviewStatus.UNSUPPORTED}
)


class MemoryRepository:
    """Persistence for Phase 5 typed-memory rows.

    Constructor takes the ``AsyncSession`` (DI). Methods take the
    ``workspace_id`` explicitly so queries are RLS-ready.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- TypedMemory --------------------------------------------------------

    async def create_memory(
        self,
        workspace_id: uuid.UUID,
        memory: BaseTypedMemory,
        *,
        document_id: uuid.UUID | None = None,
        version_id: uuid.UUID | None = None,
    ) -> TypedMemory:
        """Stage a new typed memory row + its evidence bindings + an
        initial review entry when status is ``PENDING_REVIEW``.

        ``document_id``/``version_id`` are recorded on each evidence
        binding so source-deletion re-evaluation (P5-T6) can locate the
        memories anchored to a document.

        Type-specific fields are serialized into ``payload`` as JSONB so
        the schema accommodates all 18 memory types without 18 column
        variants.
        """
        payload = self._serialize_payload(memory)

        # Apply auto-commit / mandatory-review rules (RV-DEC-P5-0001, P5-T7).
        # The caller may pre-set review_status (e.g. MemoryExtractor), but
        # we re-derive here so direct-write and any future code paths are
        # always governed by the same policy.
        derived_status = determine_review_status(
            memory_type=memory.memory_type,
            impact=memory.impact,
            confidence=memory.confidence,
        )

        row = TypedMemory(
            id=memory.id,
            workspace_id=workspace_id,
            memory_type=memory.memory_type.value,
            title=memory.title,
            summary=memory.summary,
            impact=memory.impact.value,
            confidence=memory.confidence,
            review_status=derived_status.value,
            payload=payload,
            created_by_user_id=memory.created_by_user_id,
            prompt_version=memory.prompt_version,
        )
        self.session.add(row)
        await self.session.flush()

        for chunk_id in memory.evidence_chunk_ids:
            self.session.add(
                MemoryEvidenceBinding(
                    id=uuid.uuid4(),
                    memory_id=row.id,
                    chunk_id=chunk_id,
                    document_id=document_id,
                    version_id=version_id,
                )
            )

        if derived_status == ReviewStatus.PENDING_REVIEW:
            self.session.add(
                MemoryReviewItem(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    memory_id=row.id,
                    reviewer_id=memory.created_by_user_id,
                    action="submit",
                    reason=None,
                    diff_payload=None,
                )
            )

        await self.session.flush()
        return row

    async def get_memory(
        self,
        memory_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> TypedMemory | None:
        stmt = select(TypedMemory).where(
            TypedMemory.workspace_id == workspace_id,
            TypedMemory.id == memory_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_memory_or_raise(
        self,
        memory_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> TypedMemory:
        row = await self.get_memory(memory_id, workspace_id)
        if row is None:
            raise NotFoundError(
                f"TypedMemory {memory_id} not found in workspace {workspace_id}",
                target="typed_memory",
                details={"memory_id": str(memory_id), "workspace_id": str(workspace_id)},
            )
        return row

    async def list_memories(
        self,
        workspace_id: uuid.UUID,
        memory_type: MemoryType | None = None,
        review_status: ReviewStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TypedMemory]:
        stmt = select(TypedMemory).where(TypedMemory.workspace_id == workspace_id)
        if memory_type is not None:
            stmt = stmt.where(TypedMemory.memory_type == memory_type.value)
        if review_status is not None:
            stmt = stmt.where(TypedMemory.review_status == review_status.value)
        stmt = stmt.order_by(TypedMemory.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_review_status(
        self,
        memory_id: uuid.UUID,
        workspace_id: uuid.UUID,
        status: ReviewStatus,
        reviewer_id: uuid.UUID | None = None,
        action: str = "approve",
        reason: str | None = None,
        diff_payload: dict[str, Any] | None = None,
    ) -> TypedMemory:
        """Move a memory into a new ``ReviewStatus`` and record the audit row.

        Transition rule: cannot move out of a terminal status without an
        explicit override (action="correct", "reopen", "bulk_invalidate",
        or "unsupported").
        """
        row = await self.get_memory_or_raise(memory_id, workspace_id)

        if row.review_status in {s.value for s in _TERMINAL_REVIEW_STATUSES}:
            current = ReviewStatus(row.review_status)
            if action not in {"correct", "reopen", "bulk_invalidate", "unsupported"}:
                raise NotFoundError(
                    f"Cannot transition TypedMemory {memory_id} from {current.value} to "
                    f"{status.value} without action='correct', 'reopen', 'bulk_invalidate' "
                    f"or 'unsupported' (got action='{action}').",
                    target="typed_memory.review_status",
                    details={
                        "memory_id": str(memory_id),
                        "current_status": current.value,
                        "requested_status": status.value,
                    },
                )

        row.review_status = status.value
        row.updated_at = utc_now()

        self.session.add(
            MemoryReviewItem(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                memory_id=row.id,
                reviewer_id=reviewer_id,
                action=action,
                reason=reason,
                diff_payload=diff_payload,
            )
        )
        await self.session.flush()
        return row

    # ---- MemoryEvidenceBinding ---------------------------------------------

    async def add_evidence_binding(
        self,
        memory_id: uuid.UUID,
        chunk_id: str,
        document_id: uuid.UUID | None = None,
        version_id: uuid.UUID | None = None,
    ) -> MemoryEvidenceBinding:
        binding = MemoryEvidenceBinding(
            id=uuid.uuid4(),
            memory_id=memory_id,
            chunk_id=chunk_id,
            document_id=document_id,
            version_id=version_id,
        )
        self.session.add(binding)
        await self.session.flush()
        return binding

    async def remove_evidence_binding(
        self,
        binding_id: uuid.UUID,
    ) -> None:
        stmt = select(MemoryEvidenceBinding).where(MemoryEvidenceBinding.id == binding_id)
        result = await self.session.execute(stmt)
        binding = result.scalar_one_or_none()
        if binding is not None:
            await self.session.delete(binding)
            await self.session.flush()

    async def get_evidence_bindings(
        self,
        memory_id: uuid.UUID,
    ) -> list[MemoryEvidenceBinding]:
        stmt = (
            select(MemoryEvidenceBinding)
            .where(MemoryEvidenceBinding.memory_id == memory_id)
            .order_by(MemoryEvidenceBinding.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active_bindings(
        self,
        memory_id: uuid.UUID,
    ) -> int:
        stmt = (
            select(func.count()).select_from(MemoryEvidenceBinding).where(MemoryEvidenceBinding.memory_id == memory_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def find_bindings_by_chunk_ids(
        self,
        workspace_id: uuid.UUID,
        chunk_ids: list[str],
    ) -> list[MemoryEvidenceBinding]:
        """Return all bindings whose ``chunk_id`` is in the supplied set, scoped to a workspace.

        The binding table carries no ``workspace_id`` column; we join through
        ``TypedMemory`` so the RLS filter is enforced.
        """
        if not chunk_ids:
            return []
        stmt = (
            select(MemoryEvidenceBinding)
            .join(TypedMemory, TypedMemory.id == MemoryEvidenceBinding.memory_id)
            .where(
                TypedMemory.workspace_id == workspace_id,
                MemoryEvidenceBinding.chunk_id.in_(chunk_ids),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_bindings_by_document_id(
        self,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> list[MemoryEvidenceBinding]:
        """Return all bindings anchored to a given document, scoped to a workspace."""
        stmt = (
            select(MemoryEvidenceBinding)
            .join(TypedMemory, TypedMemory.id == MemoryEvidenceBinding.memory_id)
            .where(
                TypedMemory.workspace_id == workspace_id,
                MemoryEvidenceBinding.document_id == document_id,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ---- Counts -------------------------------------------------------------

    async def count_memories_by_status(
        self,
        workspace_id: uuid.UUID,
        status: ReviewStatus,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(TypedMemory)
            .where(
                TypedMemory.workspace_id == workspace_id,
                TypedMemory.review_status == status.value,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def bulk_invalidate(
        self,
        workspace_id: uuid.UUID,
        memory_ids: list[uuid.UUID],
        reason: str,
    ) -> int:
        """Transition every listed memory to UNSUPPORTED with audit rows.

        Returns the count of affected memories.  Skips unknown IDs silently
        (idempotent — calling twice with the same list is a no-op for
        already-UNSUPPORTED rows).
        """
        count = 0
        for mid in memory_ids:
            memory = await self.get_memory(mid, workspace_id)
            if memory is None:
                continue
            if memory.review_status == ReviewStatus.UNSUPPORTED.value:
                continue
            await self.update_review_status(
                memory_id=mid,
                workspace_id=workspace_id,
                status=ReviewStatus.UNSUPPORTED,
                action="bulk_invalidate",
                reason=reason,
            )
            count += 1
        return count

    # ---- ExtractionFailure --------------------------------------------------

    async def record_extraction_failure(
        self,
        *,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        document_version_id: uuid.UUID,
        chunk_id: str,
        error_code: str,
        error_message: str | None = None,
    ) -> ExtractionFailure:
        """Stage a chunk-level extraction failure row for later retry."""
        row = ExtractionFailure(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            document_id=document_id,
            document_version_id=document_version_id,
            chunk_id=chunk_id,
            error_code=error_code,
            error_message=error_message,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_extraction_failures(
        self,
        workspace_id: uuid.UUID,
        limit: int = 100,
    ) -> list[ExtractionFailure]:
        stmt = (
            select(ExtractionFailure)
            .where(ExtractionFailure.workspace_id == workspace_id)
            .order_by(ExtractionFailure.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _serialize_payload(memory: BaseTypedMemory) -> dict[str, Any]:
        """Persist type-specific fields as JSONB.

        Everything except the shared ``BaseTypedMemory`` fields is
        captured — keeps the schema flat (one column) while still typed
        at the Pydantic layer.
        """
        shared = {
            "id",
            "workspace_id",
            "memory_type",
            "title",
            "summary",
            "impact",
            "confidence",
            "review_status",
            "evidence_chunk_ids",
            "created_by_user_id",
            "prompt_version",
            "created_at",
            "updated_at",
        }
        payload: dict[str, Any] = {}
        for field_name, value in memory.model_dump().items():
            if field_name in shared:
                continue
            payload[field_name] = _jsonable(value)
        return payload


def _jsonable(value: Any) -> Any:
    """Coerce values JSONB can store (datetime → ISO-8601 string)."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


__all__ = ["MemoryRepository"]
