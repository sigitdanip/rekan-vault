"""Unit tests for P5-T4 extraction idempotency.

Verifies the ``extract_memory:{version.id}`` idempotency key contract and the
``JobQueueManager.enqueue_job`` idempotency behavior that backs it, plus
the worker handler registration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rekanvault.storage.jobs import JobQueueManager
from rekanvault.storage.models import ProcessingJob


def test_extract_memory_uses_version_idempotency_key() -> None:
    """P5-T4: ``document_repo.py`` enqueues extract_memory with
    ``idempotency_key=f"extract_memory:{version.id}"`` — re-running the
    same document version must collapse to a single job."""
    import inspect

    from rekanvault.storage import document_repo

    source = inspect.getsource(document_repo)
    # Both _insert_new and _insert_new_version enqueue with this key pattern.
    assert source.count('idempotency_key=f"extract_memory:{version.id}"') >= 1
    assert 'job_type="extract_memory"' in source


@pytest.mark.asyncio
async def test_enqueue_job_idempotency_returns_existing_job() -> None:
    """JobQueueManager.enqueue_job short-circuits when an existing job
    already carries the same idempotency_key."""
    session = AsyncMock()
    existing_job = ProcessingJob(
        id=uuid4(),
        workspace_id=uuid4(),
        job_type="extract_memory",
        payload={"doc_id": "123"},
        idempotency_key="extract_memory:abc-123",
    )
    lookup = MagicMock()
    lookup.scalar_one_or_none.return_value = existing_job
    session.execute.return_value = lookup
    session.add = MagicMock()

    queue = JobQueueManager(session)
    result = await queue.enqueue_job(
        workspace_id=existing_job.workspace_id,
        job_type="extract_memory",
        payload={"doc_id": "123"},
        idempotency_key="extract_memory:abc-123",
    )

    assert result is existing_job
    # Short-circuit path: no new job staged, no commit.
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_job_creates_new_job_when_no_idempotency_collision() -> None:
    """When no existing job carries the idempotency_key, a new
    ProcessingJob is constructed and added to the session."""
    session = AsyncMock()
    lookup = MagicMock()
    lookup.scalar_one_or_none.return_value = None
    session.execute.return_value = lookup
    session.add = MagicMock()

    workspace_id = uuid4()
    queue = JobQueueManager(session)
    result = await queue.enqueue_job(
        workspace_id=workspace_id,
        job_type="extract_memory",
        payload={"doc_id": "123"},
        idempotency_key="extract_memory:abc-123",
    )

    assert isinstance(result, ProcessingJob)
    assert result.workspace_id == workspace_id
    assert result.job_type == "extract_memory"
    assert result.idempotency_key == "extract_memory:abc-123"
    assert result.status == "pending"
    session.add.assert_called_once_with(result)
    # Caller owns the transaction — repo never commits.
    session.commit.assert_not_called()
    session.flush.assert_not_awaited()


def test_extract_memory_job_type_registered_in_worker() -> None:
    """The worker dispatcher must route ``extract_memory`` jobs to a handler."""
    from apps.worker import main as worker_main

    assert "extract_memory" in worker_main.JOB_HANDLERS
    assert worker_main.JOB_HANDLERS["extract_memory"] is worker_main._handle_extract_memory
