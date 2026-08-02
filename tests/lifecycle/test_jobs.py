"""
Unit tests for PostgreSQL Durable Job Queue & Outbox Engine (RV-DEC-P2-0005).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from rekanvault.storage.jobs import JobQueueManager
from rekanvault.storage.models import ProcessingJob


@pytest.mark.asyncio
async def test_enqueue_job_with_idempotency_key() -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute.return_value = mock_result

    queue = JobQueueManager(session=session)
    ws_id = uuid.uuid4()
    key = "idem_key_999"

    job = await queue.enqueue_job(
        workspace_id=ws_id,
        job_type="sync_ingestion",
        payload={"source_id": "src_1"},
        idempotency_key=key,
    )

    assert job.workspace_id == ws_id
    assert job.job_type == "sync_ingestion"
    assert job.idempotency_key == key
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_idempotency_returns_existing_job() -> None:
    existing_job = ProcessingJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        job_type="sync_ingestion",
        payload={},
        idempotency_key="dup_key_1",
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_job

    session = AsyncMock()
    session.execute.return_value = mock_result

    queue = JobQueueManager(session=session)
    job = await queue.enqueue_job(
        workspace_id=existing_job.workspace_id,
        job_type="sync_ingestion",
        payload={},
        idempotency_key="dup_key_1",
    )

    assert job.id == existing_job.id


@pytest.mark.asyncio
async def test_create_outbox_event() -> None:
    session = AsyncMock()
    queue = JobQueueManager(session=session)
    ws_id = uuid.uuid4()

    event = await queue.create_outbox_event(
        workspace_id=ws_id,
        event_type="document.ingested",
        payload={"doc_id": "doc_123"},
    )

    assert event.workspace_id == ws_id
    assert event.event_type == "document.ingested"
    assert event.status == "pending"
    session.add.assert_called_once()
