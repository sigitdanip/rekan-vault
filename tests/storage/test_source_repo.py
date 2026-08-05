"""
Tests for ``rekanvault.storage.source_repo``.

Same pattern as the credential repo tests: ``AsyncMock`` session,
``MagicMock`` for select results, no fixtures. CRUD + cursor + sync-job
lifecycle.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rekanvault.storage.models import (
    ProviderCursor,
    Source,
    SyncJob,
    utc_now,
)
from rekanvault.storage.source_repo import SourceRepository

# ---------- helpers --------------------------------------------------------


def _staged_adds(session: AsyncMock) -> list[Any]:
    return [call.args[0] for call in session.add.call_args_list if call.args]


# ---------- create_source --------------------------------------------------


@pytest.mark.asyncio
async def test_create_source_stages_a_new_row() -> None:
    session = AsyncMock()
    repo = SourceRepository()
    workspace_id = uuid.uuid4()

    source = await repo.create_source(
        session=session,
        workspace_id=workspace_id,
        provider="google_drive",
        name="My Drive",
        config={"folder_id": "abc"},
    )

    assert isinstance(source, Source)
    assert source.workspace_id == workspace_id
    assert source.provider == "google_drive"
    assert source.name == "My Drive"
    assert source.config == {"folder_id": "abc"}
    session.add.assert_called_once_with(source)
    session.flush.assert_awaited_once()


# ---------- cursor save + load --------------------------------------------


@pytest.mark.asyncio
async def test_save_provider_cursor_creates_then_updates() -> None:
    """First call inserts a cursor; second call updates the same row
    in place (the model has a unique on ``source_id``)."""
    session = AsyncMock()
    repo = SourceRepository()
    workspace_id = uuid.uuid4()
    source_id = uuid.uuid4()

    # First call: no existing cursor → new ProviderCursor added.
    first_lookup = MagicMock()
    first_lookup.scalar_one_or_none.return_value = None
    session.execute.return_value = first_lookup

    cursor = await repo.save_provider_cursor(
        session=session,
        workspace_id=workspace_id,
        source_id=source_id,
        cursor_value="cursor-1",
    )
    assert isinstance(cursor, ProviderCursor)
    assert cursor.cursor_value == "cursor-1"
    assert session.add.call_count == 1

    # Second call: existing cursor → mutate in place, no new add.
    existing = cursor
    second_lookup = MagicMock()
    second_lookup.scalar_one_or_none.return_value = existing
    session.execute.return_value = second_lookup

    cursor2 = await repo.save_provider_cursor(
        session=session,
        workspace_id=workspace_id,
        source_id=source_id,
        cursor_value="cursor-2",
    )
    assert cursor2 is existing
    assert existing.cursor_value == "cursor-2"
    # session.add was NOT called again — in-place update.
    assert session.add.call_count == 1


# ---------- sync job lifecycle --------------------------------------------


@pytest.mark.asyncio
async def test_create_and_complete_sync_job() -> None:
    """``create_sync_job`` stages a SyncJob with status=pending; the
    later ``complete_sync_job`` issues an update statement."""
    session = AsyncMock()
    repo = SourceRepository()
    workspace_id = uuid.uuid4()
    source_id = uuid.uuid4()

    job = await repo.create_sync_job(
        session=session,
        workspace_id=workspace_id,
        source_id=source_id,
        job_type="sync",
    )
    assert isinstance(job, SyncJob)
    assert job.status == "pending"
    assert job.workspace_id == workspace_id
    assert job.source_id == source_id
    assert job.started_at is not None
    # job_type is folded into stats (no dedicated column on sync_jobs).
    assert (job.stats or {}).get("job_type") == "sync"

    # complete_sync_job reads the row first (to preserve embedded
    # fields), then issues an UPDATE.
    fetched = MagicMock()
    fetched.scalar_one_or_none.return_value = job
    session.execute.return_value = fetched
    await repo.complete_sync_job(
        session=session,
        workspace_id=workspace_id,
        sync_job_id=job.id,
        status="completed",
        stats={"scanned": 5, "new": 3, "updated": 2, "errors": 0},
    )
    # 1 SELECT (fetch) + 1 UPDATE.
    assert session.execute.await_count == 2
    assert session.flush.await_count == 1  # from create


@pytest.mark.asyncio
async def test_latest_sync_job_returns_most_recent() -> None:
    expected = SyncJob(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        status="completed",
        started_at=utc_now(),
        completed_at=utc_now(),
    )
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = expected
    session.execute.return_value = result

    repo = SourceRepository()
    latest = await repo.latest_sync_job(
        session=session,
        workspace_id=expected.workspace_id,
        source_id=expected.source_id,
    )
    assert latest is expected


# ---------- list_sources --------------------------------------------------


@pytest.mark.asyncio
async def test_list_sources_returns_workspace_scoped_rows() -> None:
    s1 = Source(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        provider="notion",
        name="A",
        config={},
    )
    s2 = Source(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        provider="google_drive",
        name="B",
        config={},
    )
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [s1, s2]
    session.execute.return_value = result

    repo = SourceRepository()
    sources = await repo.list_sources(session=session, workspace_id=s1.workspace_id)
    assert sources == [s1, s2]
