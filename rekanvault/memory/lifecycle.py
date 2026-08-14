"""Phase 5 Memory Lifecycle Binding Reconciler (RV-DEC-P5-0004).

Re-evaluates memory evidence bindings when source documents change or are deleted.
Wired to document outbox events via the worker handler.

Ponytail: DB-only reconciler, no LLM. Caller owns the transaction
(``commit``/``rollback``); the reconciler only stages and flushes via the repo.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.contracts.errors import NotFoundError
from rekanvault.memory.models import ReviewStatus
from rekanvault.storage.memory_repo import MemoryRepository
from rekanvault.storage.models import MemoryEvidenceBinding


class MemoryLifecycleReconciler:
    """Re-evaluates memory bindings on source document changes.

    P5-T5: Source edit changes only affected memories.
    P5-T6: Source deletion transitions to unsupported when 0 anchors remain.

    The reconciler NEVER deletes ``TypedMemory`` rows — the audit trail
    must survive source churn (RV-DEC-P5-0004). Stale bindings are dropped;
    affected memories that lose all anchors transition to ``UNSUPPORTED``.
    Re-extraction of new bindings is the extract_memory handler's job.
    """

    # Reason recorded when a memory is already UNSUPPORTED — keeps the
    # reconciliation pass logged in the review-item audit trail.
    _ALREADY_UNSUPPORTED_REASON = "already_unsupported"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MemoryRepository(session)

    async def handle_source_update(
        self,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        changed_chunk_ids: list[str],
    ) -> int:
        """Drop stale bindings for chunks whose content changed in a new version.

        For each memory that lost an anchor, recount remaining active bindings;
        if the count drops to zero, transition that memory to ``UNSUPPORTED``.
        Returns the number of distinct affected memories (for telemetry).
        """
        if not changed_chunk_ids:
            return 0

        stale = await self.repo.find_bindings_by_chunk_ids(workspace_id, changed_chunk_ids)
        # Restrict to bindings anchored to *this* document — a chunk_id collision
        # across documents must not trigger cross-document eviction.
        stale = [b for b in stale if b.document_id == document_id]
        return await self._evict_and_reconcile(workspace_id, stale)

    async def handle_source_deletion(
        self,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> int:
        """Drop every binding anchored to a deleted document and reconcile orphans.

        Memory rows are preserved (audit trail). Memories that lose all anchors
        transition to ``UNSUPPORTED``.
        """
        bindings = await self.repo.find_bindings_by_document_id(workspace_id, document_id)
        return await self._evict_and_reconcile(workspace_id, bindings)

    async def _evict_and_reconcile(
        self,
        workspace_id: uuid.UUID,
        bindings: Iterable[MemoryEvidenceBinding],
    ) -> int:
        """Delete bindings and transition any memory that lost its last anchor.

        Returns the number of distinct affected memories (binding loss touched
        them, whether or not they ended up UNSUPPORTED).
        """
        affected: set[uuid.UUID] = set()
        orphans: list[uuid.UUID] = []

        for binding in bindings:
            affected.add(binding.memory_id)
            await self.repo.remove_evidence_binding(binding.id)
            remaining = await self.repo.count_active_bindings(binding.memory_id)
            if remaining == 0:
                orphans.append(binding.memory_id)

        for memory_id in orphans:
            await self._transition_to_unsupported(memory_id, workspace_id)

        return len(affected)

    async def _transition_to_unsupported(
        self,
        memory_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> None:
        """Move a memory to ``UNSUPPORTED`` with an audit-trail review entry.

        Idempotent: if the memory is already UNSUPPORTED, a no-op audit row
        is still recorded so the reconciliation pass shows up in history.
        """
        memory = await self.repo.get_memory(memory_id, workspace_id)
        if memory is None:
            raise NotFoundError(
                f"TypedMemory {memory_id} not found in workspace {workspace_id}",
                target="typed_memory",
                details={"memory_id": str(memory_id), "workspace_id": str(workspace_id)},
            )

        if memory.review_status == ReviewStatus.UNSUPPORTED.value:
            await self.repo.update_review_status(
                memory_id=memory_id,
                workspace_id=workspace_id,
                status=ReviewStatus.UNSUPPORTED,
                action="unsupported",
                reason=self._ALREADY_UNSUPPORTED_REASON,
            )
            return

        await self.repo.update_review_status(
            memory_id=memory_id,
            workspace_id=workspace_id,
            status=ReviewStatus.UNSUPPORTED,
            action="unsupported",
            reason="Evidence anchors removed (source deleted or updated)",
        )


__all__ = ["MemoryLifecycleReconciler"]
