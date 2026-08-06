"""
RekanVault background worker (P3 — RV-DEC-P2-0005).

Polls the durable processing-jobs queue and dispatches each claimed job
to a registered handler. Handlers are keyed by ``job_type`` string and
resolved through a module-level dict — no class hierarchy, no plugin
discovery. The worker finishes the in-flight job on SIGTERM/SIGINT,
commits the result, and exits cleanly.

Ponytail:
  * A single ``WorkerDaemon`` class. The signal handler stays on the
    instance (the existing test depends on it).
  * A module-level ``JOB_HANDLERS`` dict — three entries today. Adding
    a fourth is a one-liner, no factory required.
  * No job-type enum or abstract ``JobHandler`` — the worker treats
    handlers as ``async callables`` that own their own transactions.
"""

from __future__ import annotations

import asyncio
import signal
import uuid
from typing import Any, Awaitable, Callable

from apps.api.config import settings
from rekanvault.evidence.chunker import Chunker
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.indexing import IndexingPipeline
from rekanvault.sources.manager import SourceManager
from rekanvault.storage.database import _async_session_factory, init_db
from rekanvault.storage.document_repo import DocumentRepository
from rekanvault.storage.jobs import JobQueueManager
from rekanvault.storage.qdrant import QdrantStore

# Job handler signature: ``async (session, payload) -> None``.
# On success, complete_job. On raised exception, fail_job (auto dead-letters
# at max_attempts via JobQueueManager.fail_job).
JobHandler = Callable[[Any, dict[str, Any]], Awaitable[None]]

_PILOT_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _handle_sync_source(session: Any, payload: dict[str, Any]) -> None:
    manager = SourceManager()
    source_id = uuid.UUID(str(payload["source_id"]))
    workspace_id = uuid.UUID(str(payload.get("workspace_id", str(_PILOT_WORKSPACE_ID))))
    await manager.run_sync(session=session, workspace_id=workspace_id, source_id=source_id)


async def _handle_scan_source(session: Any, payload: dict[str, Any]) -> None:
    manager = SourceManager()
    source_id = uuid.UUID(str(payload["source_id"]))
    workspace_id = uuid.UUID(str(payload.get("workspace_id", str(_PILOT_WORKSPACE_ID))))
    await manager.run_scan(session=session, workspace_id=workspace_id, source_id=source_id)


async def _handle_reconcile_source(session: Any, payload: dict[str, Any]) -> None:
    manager = SourceManager()
    source_id = uuid.UUID(str(payload["source_id"]))
    workspace_id = uuid.UUID(str(payload.get("workspace_id", str(_PILOT_WORKSPACE_ID))))
    # Reconcile is a sync with the reconcile flag set — a full rescan over
    # the change feed. Today we treat it as a regular sync; the heavier
    # drift diffing lives in ``rekanvault.ingestion.reconciliation`` and
    # can be wired into the handler when needed.
    await manager.run_sync(session=session, workspace_id=workspace_id, source_id=source_id)


def _build_pipeline(session: Any) -> IndexingPipeline:
    """Construct an IndexingPipeline with shared collaborators.

    Single source of truth for the DI graph used by both index and
    deactivate handlers. ponytail: caller ensures the Qdrant collection
    exists before the first index job.
    """
    doc_repo = DocumentRepository()
    return IndexingPipeline(
        session=session,
        chunker=Chunker(repo=doc_repo),
        embed=EmbeddingService(),
        qdrant=QdrantStore(settings),
        doc_repo=doc_repo,
    )


async def _handle_index_document_version(session: Any, payload: dict[str, Any]) -> None:
    pipeline = _build_pipeline(session)
    document_version_id = uuid.UUID(str(payload["document_version_id"]))
    await pipeline.index_version(document_version_id)


async def _handle_deactivate_document(session: Any, payload: dict[str, Any]) -> None:
    """Drop a document from the index AND mark it deactivated in Postgres.

    Payload carries ``document_id``; the latest version's chunks are
    removed from Qdrant, then the row status flips to ``deactivated``.
    """
    pipeline = _build_pipeline(session)
    document_id = uuid.UUID(str(payload["document_id"]))
    doc_repo = DocumentRepository()
    latest = await doc_repo.get_latest_version(session, document_id)
    if latest is not None:
        await pipeline.deactivate_version(latest.id)
    await doc_repo.deactivate_document(session, document_id)


JOB_HANDLERS: dict[str, JobHandler] = {
    "sync_source": _handle_sync_source,
    "scan_source": _handle_scan_source,
    "reconcile_source": _handle_reconcile_source,
    "index_document_version": _handle_index_document_version,
    "deactivate_document": _handle_deactivate_document,
}


class WorkerDaemon:
    def __init__(self, worker_id: str | None = None) -> None:
        self.running = False
        self.grace_period = settings.RV_SHUTDOWN_GRACE_SECONDS
        self.poll_interval_seconds = max(0.05, settings.RV_JOB_POLL_INTERVAL_MS / 1000.0)
        self.lease_seconds = settings.RV_JOB_LEASE_SECONDS
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._stop_event: asyncio.Event | None = None
        self._inflight: asyncio.Task[Any] | None = None

    def handle_signal(self, signum: int, frame: Any) -> None:
        print(
            f"[Worker {self.worker_id}] Received signal {signum}. "
            f"Initiating graceful shutdown (grace period: {self.grace_period}s)..."
        )
        self.running = False
        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()

    async def run(self) -> None:
        self.running = True
        self._stop_event = asyncio.Event()
        print(
            f"[Worker {self.worker_id}] Starting RekanVault worker daemon "
            f"(version={settings.RV_RELEASE_VERSION}, env={settings.RV_ENV}, "
            f"queues={settings.RV_WORKER_QUEUES}, concurrency={settings.RV_WORKER_CONCURRENCY})..."
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.handle_signal, sig, None)
            except NotImplementedError:
                signal.signal(sig, self.handle_signal)

        # Best-effort DB init — if no DB is reachable the worker sleeps
        # rather than crashing, which is what the smoke tests rely on.
        if _async_session_factory is None:
            try:
                init_db()
            except Exception as exc:  # noqa: BLE001 — startup is best-effort
                print(f"[Worker {self.worker_id}] DB init skipped: {exc}")

        # Best-effort Qdrant collection init. ``ensure_collection`` is
        # idempotent, so re-running on every boot is safe. Skipped if
        # Qdrant is unreachable — the first index job will then fail
        # loudly and the worker keeps polling.
        try:
            qdrant = QdrantStore(settings)
            await qdrant.ensure_collection()
            await qdrant.close()
        except Exception as exc:  # noqa: BLE001 — startup is best-effort
            print(f"[Worker {self.worker_id}] Qdrant init skipped: {exc}")

        await self._dispatch_loop()

        if self._inflight is not None and not self._inflight.done():
            try:
                await asyncio.wait_for(self._inflight, timeout=self.grace_period)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._inflight.cancel()

        print(f"[Worker {self.worker_id}] Graceful shutdown complete. Exiting clean.")

    async def _dispatch_loop(self) -> None:
        """Claim-and-dispatch loop. Exits when ``running`` flips to False."""
        assert self._stop_event is not None
        factory = _async_session_factory
        while self.running:
            if factory is None:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
                except asyncio.TimeoutError:
                    pass
                continue

            try:
                await self._process_one(factory)
            except Exception as exc:  # noqa: BLE001 — log + keep looping
                print(f"[Worker {self.worker_id}] Dispatch loop error: {exc}")
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
                except asyncio.TimeoutError:
                    pass

    async def _process_one(self, factory: Any) -> None:
        """Claim one job, run its handler, complete or fail it. No-op if the
        queue is empty."""
        async with factory() as session:
            queue = JobQueueManager(session=session)
            job = await queue.claim_next_job(
                worker_actor_id=self.worker_id,
                lease_duration_seconds=self.lease_seconds,
            )
            if job is None:
                await session.commit()
                if self._stop_event is not None:
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
                    except asyncio.TimeoutError:
                        pass
                return

            handler = JOB_HANDLERS.get(job.job_type)
            if handler is None:
                await queue.fail_job(job_id=job.id, error_message=f"No handler for job_type={job.job_type}")
                await session.commit()
                return

            try:
                await handler(session, dict(job.payload or {}))
                await queue.complete_job(job_id=job.id)
                await session.commit()
            except Exception as exc:  # noqa: BLE001 — handler errors must not crash the worker
                await session.rollback()
                async with factory() as fail_session:
                    fail_queue = JobQueueManager(session=fail_session)
                    await fail_queue.fail_job(job_id=job.id, error_message=str(exc)[:512])
                    await fail_session.commit()


def main() -> None:
    worker = WorkerDaemon()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        print("[Worker] KeyboardInterrupt caught. Exiting.")


__all__ = ["JOB_HANDLERS", "WorkerDaemon", "main"]


if __name__ == "__main__":
    main()
