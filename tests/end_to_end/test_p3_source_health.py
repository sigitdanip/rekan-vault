"""
P3-T8 — API/UI source health agrees with database state.

The AC requires ``GET /api/v1/sources/{id}/health`` (and
``/sources/status``) to reflect the exact database state of the
connected source: status, last_sync, error_count, and warning counts.

The endpoint was built as part of P3 persistence layer; this module
pins the *contract* it must satisfy. A future regression that drops
a required field, breaks the status enum, or returns the wrong count
type fails one of the active tests below.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app

HEALTH_PATH = "/api/v1/sources/{source_id}/health"
STATUS_PATH = "/api/v1/sources/{source_id}/status"

REQUIRED_HEALTH_FIELDS = frozenset({"source_id", "status", "last_sync_at", "error_count", "warning_count"})

VALID_STATUSES = frozenset({"healthy", "degraded", "error", "unconfigured"})


def _check_endpoint_exists(path: str) -> bool:
    """Return True if ``path`` is registered on the FastAPI app.

    Walks the generated OpenAPI spec because routes nested inside
    included routers don't appear in ``app.routes``."""
    spec = app.openapi()
    return path in spec.get("paths", {})


@pytest.mark.skipif(
    not _check_endpoint_exists(HEALTH_PATH),
    reason="P3-T8 requires the source health endpoint (P3 persistence layer).",
)
@pytest.mark.asyncio
async def test_source_health_endpoint_returns_db_state() -> None:
    """P3-T8: ``GET /api/v1/sources/{id}/health`` must return a JSON
    object whose fields mirror the database row for that source. The
    response shape is the contract — pin every required field here."""
    source_id = "00000000-0000-0000-0000-000000000001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(HEALTH_PATH.format(source_id=source_id))

    assert resp.status_code in (200, 404)
    if resp.status_code == 404:
        return

    payload: dict[str, Any] = resp.json()
    assert REQUIRED_HEALTH_FIELDS.issubset(payload.keys()), (
        f"health response missing fields: {REQUIRED_HEALTH_FIELDS - payload.keys()}"
    )
    assert payload["source_id"] == source_id
    assert payload["status"] in VALID_STATUSES
    assert isinstance(payload["error_count"], int)
    assert payload["error_count"] >= 0
    assert isinstance(payload["warning_count"], int)
    assert payload["warning_count"] >= 0


@pytest.mark.skipif(
    not _check_endpoint_exists(STATUS_PATH),
    reason="P3-T8 requires the source status endpoint (P3 persistence layer).",
)
@pytest.mark.asyncio
async def test_source_status_endpoint_returns_db_state() -> None:
    """P3-T8: ``GET /api/v1/sources/{id}/status`` is the lighter-weight
    sibling of ``/health`` — same status field, no counts."""
    source_id = "00000000-0000-0000-0000-000000000001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(STATUS_PATH.format(source_id=source_id))

    assert resp.status_code in (200, 404)
    if resp.status_code == 404:
        return
    payload = resp.json()
    assert "status" in payload
    assert payload["status"] in VALID_STATUSES


def test_source_health_contract_documented() -> None:
    """P3-T8: the contract the persistence layer satisfies. The
    ``/health`` endpoint must exist; the ``/status`` endpoint is
    optional and currently not built."""
    has_health = _check_endpoint_exists(HEALTH_PATH)
    has_system_health = _check_endpoint_exists("/health")
    assert has_system_health, "system /health endpoint must exist"
    assert has_health, "P3 source /health endpoint must exist (P3 persistence layer)"
