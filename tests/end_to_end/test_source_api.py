"""
End-to-end tests for the sources API router (P3).

Stubs the ``get_db_session`` dependency so we exercise the real
FastAPI route handlers without a live database. The session is a
``MagicMock`` whose ``execute`` returns whatever the test wires up.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.routers.sources import router as sources_router
from rekanvault.storage.models import Source

# ---------- helpers --------------------------------------------------------


def _make_source(*, workspace_id: uuid.UUID, provider: str = "google_drive", status: str = "active") -> Source:
    return Source(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        provider=provider,
        name=f"{provider}-source",
        config={"folder_id": "root"},
        status=status,
    )


def _wire_session(session: AsyncMock, *, source: Source | None) -> None:
    """Default the session's first ``scalar_one_or_none`` to ``source``."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = source
    result.scalars.return_value.all.return_value = [source] if source else []
    session.execute.return_value = result


def _app_with_session(session: AsyncMock) -> FastAPI:
    """A bare FastAPI app with the sources router + a session override.

    We DON'T reuse ``apps.api.main:app`` because it pulls in the
    correlation-id middleware, exception handlers, and the lifespan —
    the unit-test contract here is "the router + dependency injection"."""
    app = FastAPI()

    async def _get_session() -> Any:
        yield session

    app.include_router(sources_router, prefix="/api/v1/sources", tags=["Sources"])
    app.dependency_overrides[__import__("rekanvault.storage.database", fromlist=["get_db_session"]).get_db_session] = (
        _get_session
    )
    return app


# ---------- list sources --------------------------------------------------


@pytest.mark.asyncio
async def test_list_sources_returns_summary_payload() -> None:
    workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    src = _make_source(workspace_id=workspace_id)
    src.created_at = datetime.now(timezone.utc)
    session = AsyncMock()
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [src]
    sync_result = MagicMock()
    sync_result.scalar_one_or_none.return_value = None
    session.execute.side_effect = [list_result, sync_result]

    app = _app_with_session(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/sources")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["provider"] == src.provider
    assert body[0]["status"] == src.status
    assert body[0]["source_id"] == str(src.id)
    assert body[0]["last_sync_at"] is None


# ---------- register source -----------------------------------------------


@pytest.mark.asyncio
async def test_register_source_creates_row_and_returns_detail() -> None:
    """POST /sources: the Source is created via the manager; the response
    mirrors the new state. We mock ``register_source`` to avoid the
    manager's full pipeline (which would need a real connector)."""
    session = AsyncMock()
    workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    new_source = _make_source(workspace_id=workspace_id, provider="notion")
    new_source.created_at = datetime.now(timezone.utc)

    with patch(
        "rekanvault.sources.manager.SourceManager.register_source",
        AsyncMock(return_value=new_source),
    ):
        app = _app_with_session(session)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/sources",
                json={
                    "provider": "notion",
                    "name": "notion-source",
                    "root_external_id": "page-1",
                    "root_path": "/Root",
                    "config": {},
                },
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["source_id"] == str(new_source.id)
    assert body["provider"] == "notion"
    assert len(body["roots"]) == 1
    assert body["roots"][0]["external_id"] == "page-1"
    assert body["cursor"] is None
    assert session.commit.await_count == 1


# ---------- get source health ---------------------------------------------


@pytest.mark.asyncio
async def test_get_source_health_returns_required_p3_t8_fields() -> None:
    workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    source = _make_source(workspace_id=workspace_id, status="active")
    session = AsyncMock()
    # Manager.get_health does 4 queries: source lookup, latest sync job,
    # cursor, doc count. Provide a return for each.
    source_result = MagicMock()
    source_result.scalar_one_or_none.return_value = source
    sync_result = MagicMock()
    sync_result.scalar_one_or_none.return_value = None
    cursor_result = MagicMock()
    cursor_result.scalar_one_or_none.return_value = None
    count_result = MagicMock()
    count_result.scalar_one.return_value = 7
    session.execute.side_effect = [
        source_result,
        sync_result,
        cursor_result,
        count_result,
    ]

    app = _app_with_session(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/sources/{source.id}/health")

    assert resp.status_code == 200
    body = resp.json()
    # P3-T8 contract: every required field is present.
    for field in ("source_id", "status", "last_sync_at", "error_count", "warning_count"):
        assert field in body, f"missing {field}"
    assert body["source_id"] == str(source.id)
    assert body["status"] in {"healthy", "degraded", "error", "unconfigured"}
    assert body["error_count"] == 0
    assert body["warning_count"] == 0
    assert body["document_count"] == 7


# ---------- trigger sync (POST /sync) -------------------------------------


@pytest.mark.asyncio
async def test_trigger_sync_enqueues_processing_job() -> None:
    workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    source = _make_source(workspace_id=workspace_id)
    session = AsyncMock()
    # First call: get_source → returns the source; the idempotency check
    # is a second select that returns None.
    source_result = MagicMock()
    source_result.scalar_one_or_none.return_value = source
    idem_result = MagicMock()
    idem_result.scalar_one_or_none.return_value = None
    session.execute.side_effect = [source_result, idem_result]

    app = _app_with_session(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/v1/sources/{source.id}/sync")

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_type"] == "sync_source"
    assert body["status"] == "pending"
    # session.add was called for the new ProcessingJob.
    assert session.add.call_count == 1
    session.commit.assert_awaited_once()
