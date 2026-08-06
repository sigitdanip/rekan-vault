"""
End-to-end tests for the search API router (P4).

The :class:`RetrievalPipeline` and :class:`QdrantStore` are patched at
import-time on the search router so the tests don't pull real
embedding models or talk to a Qdrant cluster. ``get_db_session`` is
overridden the same way ``test_source_api.py`` does it — the contract
under test is the route handler + dependency injection.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import rekanvault.storage.database as db_module
from apps.api.routers.search import router as search_router

# ---------- helpers --------------------------------------------------------


def _make_hit(
    *,
    chunk_id: str | None = None,
    document_id: str | None = None,
    version_id: str | None = None,
    workspace_id: str | None = None,
    content: str = "alpha content",
    score: float = 0.9,
    source: str = "both",
    block_start: int = 0,
    block_end: int = 0,
) -> dict[str, Any]:
    """One fake retrieval result in the public shape ``pipeline.search`` returns."""
    return {
        "chunk_id": chunk_id or f"chunk-{uuid.uuid4().hex[:8]}",
        "document_id": document_id or str(uuid.uuid4()),
        "version_id": version_id or str(uuid.uuid4()),
        "workspace_id": workspace_id or str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
        "content": content,
        "score": score,
        "source": source,
        "block_start": block_start,
        "block_end": block_end,
        "metadata": {"block_type": "paragraph", "external_id": "ext-1"},
    }


def _mock_pipeline(search_impl: Any) -> MagicMock:
    """Build a ``MagicMock`` that stands in for the ``RetrievalPipeline`` class.

    ``search_impl`` is whatever the test wants ``pipeline.search`` to be —
    an ``AsyncMock(return_value=...)`` or a coroutine via ``side_effect``.
    """
    pipeline_instance = MagicMock()
    pipeline_instance.search = search_impl
    return MagicMock(return_value=pipeline_instance)


def _app_with_session(session: AsyncMock) -> FastAPI:
    """Bare FastAPI app + the search router + a session override.

    We deliberately don't import ``apps.api.main:app`` — the unit-test
    contract is "router + dependency injection", not the full app
    composition (correlation middleware, exception handlers, etc.).
    """
    app = FastAPI()

    async def _get_session() -> Any:
        yield session

    app.include_router(search_router, prefix="/api/v1", tags=["Search"])
    app.dependency_overrides[db_module.get_db_session] = _get_session
    return app


# ---------- happy path -----------------------------------------------------


@pytest.mark.asyncio
async def test_search_endpoint_returns_context_pack() -> None:
    """Two-hit retrieval: 200 with a ContextPack whose chunks match the
    pipeline output and whose metadata carries redacted diagnostics."""
    session = AsyncMock()
    hits = [
        _make_hit(content="alpha", score=0.9, source="both"),
        _make_hit(content="beta", score=0.6, source="lexical"),
    ]
    pipeline_cls = _mock_pipeline(AsyncMock(return_value=hits))

    with (
        patch("apps.api.routers.search.QdrantStore") as qdrant_store_mock,
        patch("apps.api.routers.search.RetrievalPipeline", pipeline_cls),
    ):
        app = _app_with_session(session)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search",
                json={"query": "alpha beta", "top_k": 5},
            )

    assert resp.status_code == 200
    body = resp.json()
    for field in (
        "context_pack_id",
        "workspace_id",
        "query",
        "evidence_chunks",
        "memories",
        "token_budget",
        "created_at",
        "metadata",
    ):
        assert field in body, f"missing {field}"
    assert body["query"] == "alpha beta"
    assert len(body["evidence_chunks"]) == 2
    assert body["evidence_chunks"][0]["content"] == "alpha"
    diag = body["metadata"]["diagnostics"]
    assert diag["pipeline"] == "p4_hybrid_v1"
    assert diag["lexical_hits"] == 2  # "both" counts toward both legs
    assert diag["dense_hits"] == 1
    assert diag["reranked_count"] == 2
    assert isinstance(diag["latency_ms"], int)
    assert diag["latency_ms"] >= 0
    qdrant_store_mock.assert_called_once()


# ---------- validation -----------------------------------------------------


@pytest.mark.asyncio
async def test_search_empty_query_returns_422() -> None:
    """``min_length=1`` on the query field rejects the empty string
    with Pydantic's 422 validation error envelope."""
    session = AsyncMock()
    app = _app_with_session(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/search", json={"query": ""})

    assert resp.status_code == 422


# ---------- no results -----------------------------------------------------


@pytest.mark.asyncio
async def test_search_no_results_returns_insufficient_evidence() -> None:
    """Empty pipeline result → assembler returns the
    ``insufficient_evidence`` pack; the response still has zero
    ``evidence_chunks`` and the INSUFFICIENT_EVIDENCE diagnostic marker."""
    session = AsyncMock()
    pipeline_cls = _mock_pipeline(AsyncMock(return_value=[]))

    with (
        patch("apps.api.routers.search.QdrantStore"),
        patch("apps.api.routers.search.RetrievalPipeline", pipeline_cls),
    ):
        app = _app_with_session(session)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "nothing"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["evidence_chunks"] == []
    assert body["metadata"].get("diagnostic") == "INSUFFICIENT_EVIDENCE"
    diag = body["metadata"]["diagnostics"]
    assert diag["lexical_hits"] == 0
    assert diag["dense_hits"] == 0
    assert diag["reranked_count"] == 0


# ---------- filters --------------------------------------------------------


@pytest.mark.asyncio
async def test_search_with_filters() -> None:
    """Filters are translated to a Qdrant ``Filter`` and forwarded to
    ``pipeline.search`` as the ``filters`` kwarg."""
    session = AsyncMock()
    hit = _make_hit()
    captured_kwargs: dict[str, Any] = {}

    async def _fake_search(query: str, workspace_id: uuid.UUID, *, top_k: int, filters: Any) -> list[dict[str, Any]]:
        captured_kwargs["query"] = query
        captured_kwargs["workspace_id"] = workspace_id
        captured_kwargs["top_k"] = top_k
        captured_kwargs["filters"] = filters
        return [hit]

    pipeline_cls = _mock_pipeline(AsyncMock(side_effect=_fake_search))

    with (
        patch("apps.api.routers.search.QdrantStore"),
        patch("apps.api.routers.search.RetrievalPipeline", pipeline_cls),
    ):
        app = _app_with_session(session)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search",
                json={"query": "alpha", "filters": {"source_type": "google_drive"}},
            )

    assert resp.status_code == 200
    qfilter = captured_kwargs["filters"]
    assert qfilter is not None
    assert len(qfilter.must) == 1
    cond = qfilter.must[0]
    assert cond.key == "source_type"
    assert cond.match.value == "google_drive"


# ---------- diagnostics ----------------------------------------------------


@pytest.mark.asyncio
async def test_search_includes_diagnostics() -> None:
    """The diagnostics dict is always present and carries every required
    key — pipeline name, hit counts, reranked count, latency."""
    session = AsyncMock()
    hits = [_make_hit(score=0.7, source="dense")]
    pipeline_cls = _mock_pipeline(AsyncMock(return_value=hits))

    with (
        patch("apps.api.routers.search.QdrantStore"),
        patch("apps.api.routers.search.RetrievalPipeline", pipeline_cls),
    ):
        app = _app_with_session(session)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/search", json={"query": "alpha"})

    assert resp.status_code == 200
    body = resp.json()
    diag = body["metadata"]["diagnostics"]
    for key in ("pipeline", "lexical_hits", "dense_hits", "reranked_count", "latency_ms"):
        assert key in diag, f"missing diagnostics key: {key}"
    assert diag["pipeline"] == "p4_hybrid_v1"
    assert diag["reranked_count"] == 1
    assert diag["dense_hits"] == 1
    assert diag["lexical_hits"] == 0
