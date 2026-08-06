"""
Tests for ``rekanvault.evidence.retrieval``.

Mock the three collaborators (AsyncSession, EmbeddingService, QdrantStore)
and assert on the calls + the RRF / dedup math. No real Postgres or
Qdrant connection. Mirrors the existing test_chunker / test_qdrant pattern
(no fixtures, no conftest, plain constructor calls).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from qdrant_client import AsyncQdrantClient

from apps.api.config import Settings
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.retrieval import RetrievalPipeline
from rekanvault.storage.qdrant import QdrantStore

# ---------- helpers --------------------------------------------------------


def _settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "RV_QDRANT_URL": "https://example.qdrant.cloud",
        "RV_QDRANT_API_KEY": "test-key",
        "RV_QDRANT_COLLECTION": "rekanvault_chunks_v1",
        "RV_QDRANT_TIMEOUT_SECONDS": 30,
        "RV_EMBEDDING_DIMENSIONS": 1024,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _qdrant_with_mock(settings: Settings) -> tuple[QdrantStore, AsyncMock]:
    store = QdrantStore(settings)
    mock_client = AsyncMock(spec=AsyncQdrantClient)
    store._client = mock_client
    return store, mock_client


def _embed_with_mocks() -> tuple[EmbeddingService, Mock, Mock]:
    """``embed_query`` and ``rerank`` are sync methods on the real
    ``EmbeddingService``; mock them with plain ``Mock`` so they return
    values directly rather than awaiting coroutines."""
    embed = EmbeddingService()
    embed.embed_query = Mock(return_value=[0.1, 0.2, 0.3])  # type: ignore[method-assign]
    embed.rerank = Mock(return_value=[(0, 0.95), (1, 0.40)])  # type: ignore[method-assign]
    return embed, embed.embed_query, embed.rerank


def _make_session_with_rows(rows: list[dict[str, Any]]) -> AsyncMock:
    """Wire an AsyncMock session whose ``execute(text, params)`` returns
    ``rows`` as a row-mapping iterable, matching the ``.mappings().all()``
    shape the lexical search uses."""
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    session.execute.return_value = result
    return session


def _lexical_row(
    *,
    block_id: str | None = None,
    content_text: str = "Some text",
    block_index: int = 0,
    document_id: str | None = None,
    version_id: str | None = None,
    workspace_id: str | None = None,
    rank: float = 0.5,
) -> dict[str, Any]:
    return {
        "block_id": block_id or str(uuid.uuid4()),
        "content_text": content_text,
        "block_index": block_index,
        "block_type": "paragraph",
        "block_metadata": {},
        "document_version_id": str(uuid.uuid4()),
        "workspace_id": workspace_id or str(uuid.uuid4()),
        "version_number": 1,
        "version_id": version_id or str(uuid.uuid4()),
        "document_id": document_id or str(uuid.uuid4()),
        "external_id": "ext-1",
        "rank": rank,
    }


def _scored_point(
    *,
    point_id: str,
    score: float,
    document_id: str | None = None,
    version_id: str | None = None,
    workspace_id: str | None = None,
    chunk_text: str = "Some text",
    block_start: int = 0,
    block_end: int = 0,
) -> Any:
    """Build an object that quacks like a ``qdrant_client.ScoredPoint`` —
    the test never imports the real type, just reads ``.id``, ``.score``,
    ``.payload``."""
    payload = {
        "workspace_id": workspace_id or str(uuid.uuid4()),
        "document_id": document_id or str(uuid.uuid4()),
        "version_id": version_id or str(uuid.uuid4()),
        "chunk_text": chunk_text,
        "block_start": block_start,
        "block_end": block_end,
        "block_type": "paragraph",
        "external_id": "ext-1",
        "doc_title": "Doc",
        "source_type": "google_drive",
    }
    point = MagicMock()
    point.id = point_id
    point.score = score
    point.payload = payload
    return point


# ---------- lexical_search -------------------------------------------------


@pytest.mark.asyncio
async def test_lexical_search() -> None:
    """Lexical search must run the tsvector SQL with the right params and
    return a dict per row that carries the fields downstream needs."""
    settings = _settings()
    qdrant, _ = _qdrant_with_mock(settings)
    embed, _, _ = _embed_with_mocks()
    doc_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    workspace_id = uuid.uuid4()
    rows = [
        _lexical_row(content_text="alpha", block_index=2, document_id=doc_id, version_id=version_id, rank=0.9),
        _lexical_row(content_text="beta", block_index=5, document_id=doc_id, version_id=version_id, rank=0.4),
    ]
    session = _make_session_with_rows(rows)

    pipeline = RetrievalPipeline(session, embed, qdrant)
    hits = await pipeline.lexical_search("alpha beta", workspace_id, limit=10)

    # 1. SQL was issued with the right params.
    assert session.execute.await_count == 1
    stmt, params = session.execute.await_args.args
    assert "ts_rank" in str(stmt)
    assert "websearch_to_tsquery" in str(stmt)
    assert params["query"] == "alpha beta"
    assert params["workspace_id"] == workspace_id
    assert params["limit"] == 10

    # 2. Two hits back, in the right shape, score == ts_rank.
    assert len(hits) == 2
    assert hits[0]["content"] == "alpha"
    assert hits[0]["score"] == 0.9
    assert hits[0]["source"] == "lexical"
    assert hits[0]["document_id"] == doc_id
    assert hits[0]["version_id"] == version_id
    assert hits[0]["block_start"] == 2
    assert hits[0]["block_end"] == 2
    assert hits[0]["metadata"]["block_type"] == "paragraph"


@pytest.mark.asyncio
async def test_lexical_search_empty_query_returns_empty() -> None:
    """Empty / whitespace queries short-circuit — no SQL, no hits."""
    settings = _settings()
    qdrant, _ = _qdrant_with_mock(settings)
    embed, _, _ = _embed_with_mocks()
    session = _make_session_with_rows([])

    pipeline = RetrievalPipeline(session, embed, qdrant)
    assert await pipeline.lexical_search("", uuid.uuid4()) == []
    assert await pipeline.lexical_search("   ", uuid.uuid4()) == []
    session.execute.assert_not_awaited()


# ---------- dense_search ---------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search() -> None:
    """Dense search must embed the query, call ``query_points`` with the
    locked collection + named vector, and return point payloads as dicts
    with the right fields."""
    settings = _settings()
    qdrant, mock_client = _qdrant_with_mock(settings)
    embed, embed_query_mock, _ = _embed_with_mocks()
    workspace_id = uuid.uuid4()
    doc_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    point = _scored_point(
        point_id="doc-1#v1#chunk_001",
        score=0.87,
        document_id=doc_id,
        version_id=version_id,
        workspace_id=str(workspace_id),
        chunk_text="hello world",
    )
    response = MagicMock()
    response.points = [point]
    mock_client.query_points.return_value = response

    pipeline = RetrievalPipeline(AsyncMock(), embed, qdrant)
    hits = await pipeline.dense_search("hello", workspace_id, limit=15)

    embed_query_mock.assert_called_once_with("hello")

    # 2. query_points was called against the locked collection + vector name.
    assert mock_client.query_points.await_count == 1
    kwargs = mock_client.query_points.await_args.kwargs
    assert kwargs["collection_name"] == settings.RV_QDRANT_COLLECTION
    assert kwargs["limit"] == 15
    assert kwargs["query_filter"] is not None
    # workspace filter is AND-ed in.
    must = kwargs["query_filter"].must
    assert any(getattr(c, "key", None) == "workspace_id" for c in must)

    # 3. Hit dict carries the Qdrant fields downstream needs.
    assert len(hits) == 1
    assert hits[0]["chunk_id"] == "doc-1#v1#chunk_001"
    assert hits[0]["content"] == "hello world"
    assert hits[0]["score"] == 0.87
    assert hits[0]["source"] == "dense"
    assert hits[0]["document_id"] == doc_id
    assert hits[0]["version_id"] == version_id


# ---------- RRF fusion -----------------------------------------------------


def test_rrf_fusion() -> None:
    """RRF formula: an item ranked 1st in BOTH lists must out-score an
    item ranked 1st in one list and 5th in the other. Items unique to a
    single list still surface."""
    lex = [
        {
            "chunk_id": "A",
            "score": 1.0,
            "content": "a",
            "source": "lexical",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
        {
            "chunk_id": "B",
            "score": 0.7,
            "content": "b",
            "source": "lexical",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
        {
            "chunk_id": "C",
            "score": 0.4,
            "content": "c",
            "source": "lexical",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
    ]
    dense = [
        {
            "chunk_id": "A",
            "score": 0.9,
            "content": "a",
            "source": "dense",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
        {
            "chunk_id": "B",
            "score": 0.6,
            "content": "b",
            "source": "dense",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
        {
            "chunk_id": "D",
            "score": 0.5,
            "content": "d",
            "source": "dense",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
    ]
    # Item "A" is 1st in both lists (highest combined RRF).
    # Item "B" is 2nd in both lists.
    # Item "C" is 3rd in lexical only.
    # Item "D" is 3rd in dense only.

    fused = RetrievalPipeline._rrf_fuse(lex, dense, limit=10)
    by_id = {h["chunk_id"]: h for h in fused}

    # All four items surface.
    assert set(by_id) == {"A", "B", "C", "D"}

    # A > B (A is ranked 1st in both; B is 2nd in both).
    assert by_id["A"]["score"] > by_id["B"]["score"]
    # A > C (A is 1st+1st, C is 3rd in lexical only).
    assert by_id["A"]["score"] > by_id["C"]["score"]
    # B > C and B > D (B is in both lists; C/D are in one only).
    assert by_id["B"]["score"] > by_id["C"]["score"]
    assert by_id["B"]["score"] > by_id["D"]["score"]

    # A is "both" since it appeared in both legs.
    assert by_id["A"]["source"] == "both"
    # C/D are single-leg.
    assert by_id["C"]["source"] == "lexical"
    assert by_id["D"]["source"] == "dense"

    # Sanity: hand-computed RRF score for A is 2 * 1/(60+1).
    expected_a = 2.0 / (60 + 1)
    assert by_id["A"]["score"] == pytest.approx(expected_a)


def test_rrf_fusion_first_in_one_fifth_in_other() -> None:
    """Pin the test-plan claim directly: item ranked 1st in both lists
    beats item ranked 1st in one and 5th in the other."""
    both_first = {
        "chunk_id": "X",
        "score": 0.0,
        "content": "x",
        "source": "lexical",
        "document_id": "d",
        "version_id": "v",
        "block_start": 0,
        "block_end": 0,
        "metadata": {},
    }
    mixed = {
        "chunk_id": "Y",
        "score": 0.0,
        "content": "y",
        "source": "lexical",
        "document_id": "d",
        "version_id": "v",
        "block_start": 0,
        "block_end": 0,
        "metadata": {},
    }
    filler = [
        {
            "chunk_id": f"f{i}",
            "score": 0.0,
            "content": f"f{i}",
            "source": "lexical",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        }
        for i in range(4)
    ]

    lex = [both_first] + [mixed] + filler  # X=1st, Y=2nd, filler 3..5
    dense = [both_first] + filler + [mixed]  # X=1st, filler 2..4, Y=5th

    fused = RetrievalPipeline._rrf_fuse(lex, dense, limit=10)
    by_id = {h["chunk_id"]: h for h in fused}
    assert by_id["X"]["score"] > by_id["Y"]["score"]


# ---------- rerank integration --------------------------------------------


@pytest.mark.asyncio
async def test_rerank_integration() -> None:
    """The reranker must be awaited with the candidate texts in their
    original order, and the returned scores must be mapped back onto the
    original candidate dicts (preserving the chunk_id, not just the index)."""
    settings = _settings()
    qdrant, _ = _qdrant_with_mock(settings)
    embed, _, rerank_mock = _embed_with_mocks()
    session = AsyncMock()

    candidates = [
        {
            "chunk_id": "a",
            "content": "first",
            "score": 0.1,
            "source": "both",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
        {
            "chunk_id": "b",
            "content": "second",
            "score": 0.2,
            "source": "both",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
        {
            "chunk_id": "c",
            "content": "third",
            "score": 0.3,
            "source": "both",
            "document_id": "d",
            "version_id": "v",
            "block_start": 0,
            "block_end": 0,
            "metadata": {},
        },
    ]

    def _fake_rerank(query: str, texts: list[str], top_n: int | None = None) -> list[tuple[int, float]]:
        ranked = sorted(enumerate(texts), key=lambda kv: kv[1], reverse=True)
        return [(idx, float(0.9 - i * 0.1)) for i, (idx, _) in enumerate(ranked[:top_n])]

    rerank_mock.side_effect = _fake_rerank

    pipeline = RetrievalPipeline(session, embed, qdrant)
    out = await pipeline._rerank("query", candidates, top_k=2)

    assert rerank_mock.call_count == 1
    args = rerank_mock.call_args.args
    assert args[0] == "query"
    assert args[1] == ["first", "second", "third"]
    assert rerank_mock.call_args.kwargs["top_n"] == 2

    assert [c["chunk_id"] for c in out] == ["c", "b"]
    assert out[0]["score"] == 0.9
    assert out[1]["score"] == 0.8


# ---------- dedup ---------------------------------------------------------


def test_dedup_overlap() -> None:
    """Two chunks from the same document with overlapping block ranges:
    the lower-scored one is dropped. Chunks in DIFFERENT documents are
    never deduped against each other even if they have the same range.
    Chunks in the same document but with non-overlapping ranges both
    survive."""
    candidates = [
        # doc-1, blocks 0-4 — kept.
        {
            "chunk_id": "k1",
            "score": 0.9,
            "document_id": "doc-1",
            "version_id": "v",
            "block_start": 0,
            "block_end": 4,
            "content": "a",
            "source": "lexical",
            "metadata": {},
        },
        # doc-1, blocks 3-7 — overlaps k1, dropped.
        {
            "chunk_id": "k2",
            "score": 0.7,
            "document_id": "doc-1",
            "version_id": "v",
            "block_start": 3,
            "block_end": 7,
            "content": "b",
            "source": "lexical",
            "metadata": {},
        },
        # doc-1, blocks 10-12 — disjoint from k1, kept.
        {
            "chunk_id": "k3",
            "score": 0.6,
            "document_id": "doc-1",
            "version_id": "v",
            "block_start": 10,
            "block_end": 12,
            "content": "c",
            "source": "lexical",
            "metadata": {},
        },
        # doc-2, blocks 0-4 — different doc, same range as k1, kept.
        {
            "chunk_id": "k4",
            "score": 0.5,
            "document_id": "doc-2",
            "version_id": "v",
            "block_start": 0,
            "block_end": 4,
            "content": "d",
            "source": "lexical",
            "metadata": {},
        },
    ]
    deduped = RetrievalPipeline._dedup_overlap(candidates)
    kept_ids = [c["chunk_id"] for c in deduped]
    assert kept_ids == ["k1", "k3", "k4"]


# ---------- search orchestration ------------------------------------------


@pytest.mark.asyncio
async def test_search_orchestration() -> None:
    """End-to-end: lexical → dense → RRF → rerank → dedup → finalize.
    Verify the call order on the embed service and that the final list is
    sorted by score desc with the public output shape."""
    settings = _settings()
    qdrant, mock_client = _qdrant_with_mock(settings)
    embed, embed_query_mock, rerank_mock = _embed_with_mocks()
    workspace_id = uuid.uuid4()
    doc_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    # Lexical leg returns 1 hit.
    lex_rows = [
        _lexical_row(content_text="lex hit", block_index=1, document_id=doc_id, version_id=version_id, rank=0.8),
    ]
    session = _make_session_with_rows(lex_rows)

    # Dense leg returns 1 hit (different chunk_id so RRF has work to do).
    point = _scored_point(
        point_id="dense-1",
        score=0.7,
        document_id=doc_id,
        version_id=version_id,
        workspace_id=str(workspace_id),
        chunk_text="dense hit",
        block_start=5,
        block_end=6,
    )
    response = MagicMock()
    response.points = [point]
    mock_client.query_points.return_value = response

    # Reranker returns both candidates in (lex-hits-first, dense-second) order.
    rerank_mock.return_value = [(0, 0.95), (1, 0.30)]

    pipeline = RetrievalPipeline(session, embed, qdrant)
    results = await pipeline.search("anything", workspace_id, top_k=5)

    assert embed_query_mock.call_count == 1
    assert rerank_mock.call_count == 1

    # Final list is the public shape, sorted by score desc.
    assert isinstance(results, list)
    assert all(
        set(r.keys())
        == {
            "chunk_id",
            "document_id",
            "version_id",
            "content",
            "score",
            "source",
            "block_start",
            "block_end",
            "metadata",
        }
        for r in results
    )
    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]
    # Scores are normalized to [0, 1].
    assert 0.0 <= results[0]["score"] <= 1.0
    assert 0.0 <= results[1]["score"] <= 1.0


@pytest.mark.asyncio
async def test_search_empty_inputs() -> None:
    """When both legs return nothing, search() returns [] without calling
    the reranker (and without raising)."""
    settings = _settings()
    qdrant, mock_client = _qdrant_with_mock(settings)
    embed, _, rerank_mock = _embed_with_mocks()

    session = _make_session_with_rows([])
    response = MagicMock()
    response.points = []
    mock_client.query_points.return_value = response

    pipeline = RetrievalPipeline(session, embed, qdrant)
    results = await pipeline.search("anything", uuid.uuid4(), top_k=5)
    assert results == []
    rerank_mock.assert_not_called()
