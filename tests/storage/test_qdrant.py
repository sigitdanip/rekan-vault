"""
Tests for ``rekanvault.storage.qdrant``.

Mock the ``AsyncQdrantClient`` with ``AsyncMock`` and assert on the
calls the store makes — no real Qdrant connection. Mirrors the
document_repo / source_repo pattern (no fixtures, no conftest).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from apps.api.config import Settings
from rekanvault.storage.qdrant import (
    PAYLOAD_INDEXES,
    PAYLOAD_KEYS,
    DenseVectorName,
    QdrantStore,
)

# ---------- helpers --------------------------------------------------------


def _settings(**overrides: Any) -> Settings:
    """Build a Settings instance with the Qdrant-relevant fields wired
    up. Uses Settings(**) so we don't depend on the live ``.env``."""
    defaults: dict[str, Any] = {
        "RV_QDRANT_URL": "https://example.qdrant.cloud",
        "RV_QDRANT_API_KEY": "test-key",
        "RV_QDRANT_COLLECTION": "rekanvault_chunks_v1",
        "RV_QDRANT_TIMEOUT_SECONDS": 30,
        "RV_EMBEDDING_DIMENSIONS": 1024,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _store_with_mock(settings: Settings) -> tuple[QdrantStore, AsyncMock]:
    """Instantiate ``QdrantStore`` and swap its internal client with an
    ``AsyncMock`` so no real HTTP is attempted. Returns ``(store, mock)``
    so tests can assert on the mock."""
    store = QdrantStore(settings)
    mock_client = AsyncMock(spec=AsyncQdrantClient)
    # ``spec=`` blocks attribute creation, so we replace the attribute
    # directly on the instance, then re-attach the spec-mocked methods.
    store._client = mock_client
    return store, mock_client


def _vector(size: int = 1024) -> list[float]:
    return [0.01 * i for i in range(size)]


# ---------- construction ---------------------------------------------------


def test_init_uses_settings_for_client() -> None:
    """The client is constructed with the URL, API key, and timeout from
    settings — no hardcoded values."""
    settings = _settings(
        RV_QDRANT_URL="https://the.url",
        RV_QDRANT_API_KEY="the-key",
        RV_QDRANT_TIMEOUT_SECONDS=42,
    )
    with patch("rekanvault.storage.qdrant.AsyncQdrantClient") as client_cls:
        QdrantStore(settings)

    client_cls.assert_called_once_with(
        url="https://the.url",
        api_key="the-key",
        timeout=42,
    )


def test_collection_name_exposes_settings_value() -> None:
    settings = _settings(RV_QDRANT_COLLECTION="custom_chunks")
    store, _ = _store_with_mock(settings)
    assert store.collection_name == "custom_chunks"


# ---------- ensure_collection ---------------------------------------------


@pytest.mark.asyncio
async def test_ensure_collection_creates_if_missing() -> None:
    """Collection missing → create + index all payload fields."""
    settings = _settings()
    store, mock_client = _store_with_mock(settings)
    mock_client.collection_exists.return_value = False

    await store.ensure_collection()

    mock_client.collection_exists.assert_awaited_once_with(settings.RV_QDRANT_COLLECTION)
    # create_collection was called exactly once with the locked vector shape.
    assert mock_client.create_collection.await_count == 1
    create_call = mock_client.create_collection.await_args
    assert create_call is not None
    assert create_call.kwargs["collection_name"] == settings.RV_QDRANT_COLLECTION
    vectors_config = create_call.kwargs["vectors_config"]
    assert DenseVectorName in vectors_config
    assert vectors_config[DenseVectorName].size == 1024
    assert vectors_config[DenseVectorName].distance == models.Distance.COSINE
    # Payload indexes: every entry in PAYLOAD_INDEXES is created.
    assert mock_client.create_payload_index.await_count == len(PAYLOAD_INDEXES)
    index_field_names = {
        call.kwargs["field_name"] for call in mock_client.create_payload_index.await_args_list
    }
    expected_field_names = {name for name, _ in PAYLOAD_INDEXES}
    assert index_field_names == expected_field_names
    # Each index uses the matching schema (keyword vs datetime).
    indexed_schemas = {
        call.kwargs["field_name"]: call.kwargs["field_schema"]
        for call in mock_client.create_payload_index.await_args_list
    }
    for name, schema in PAYLOAD_INDEXES:
        assert indexed_schemas[name] == schema


@pytest.mark.asyncio
async def test_ensure_collection_skips_create_when_exists() -> None:
    """Collection already present → no create_collection call, but
    payload indexes are still re-asserted."""
    settings = _settings()
    store, mock_client = _store_with_mock(settings)
    mock_client.collection_exists.return_value = True

    await store.ensure_collection()

    mock_client.create_collection.assert_not_awaited()
    assert mock_client.create_payload_index.await_count == len(PAYLOAD_INDEXES)


# ---------- upsert_chunks -------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_chunks_stages_point_structs_with_dense_vector() -> None:
    """Two chunks → one upsert call carrying two PointStructs, each
    with the dense vector + filtered payload."""
    settings = _settings()
    store, mock_client = _store_with_mock(settings)

    embedding = _vector()
    chunks = [
        {
            "chunk_id": "doc_a#v1#chunk_0",
            "embedding": embedding,
            "workspace_id": "ws_1",
            "document_id": "doc_a",
            "version_id": "ver_1",
            "block_type": "paragraph",
            "doc_title": "A",
            "source_type": "notion",
            "status": "active",
            "created_at": "2026-08-06T00:00:00Z",
            "corpus_id": "corpus_pilot",
            "chunk_text": "hello world",
            "external_id": "ext_a",
            "block_start": 0,
            "block_end": 1,
            "token_count": 10,
            "extra_field_dropped": "should not be stored",
        },
        {
            "chunk_id": "doc_a#v1#chunk_1",
            "embedding": embedding,
            "workspace_id": "ws_1",
            "document_id": "doc_a",
            "version_id": "ver_1",
            "block_type": "heading",
            "doc_title": "A",
            "source_type": "notion",
            "status": "active",
            "created_at": "2026-08-06T00:00:00Z",
            "corpus_id": "corpus_pilot",
            "chunk_text": "second chunk",
            "external_id": "ext_a",
            "block_start": 2,
            "block_end": 3,
            "token_count": 5,
        },
    ]

    await store.upsert_chunks(chunks)

    assert mock_client.upsert.await_count == 1
    call = mock_client.upsert.await_args
    assert call is not None
    assert call.kwargs["collection_name"] == settings.RV_QDRANT_COLLECTION
    points = call.kwargs["points"]
    assert isinstance(points, list)
    assert len(points) == 2
    assert all(isinstance(p, models.PointStruct) for p in points)

    # Original locator preserved in payload; Qdrant point ID is a derived UUID.
    assert [p.payload["chunk_locator"] for p in points] == ["doc_a#v1#chunk_0", "doc_a#v1#chunk_1"]  # type: ignore[index]
    for p in points:
        assert isinstance(p.id, str)
        assert len(p.id) == 36  # UUID string length
        assert isinstance(p.vector, dict)  # type: ignore[union-attr]
        assert DenseVectorName in p.vector
        assert list(p.vector[DenseVectorName]) == embedding

    # Payload: every key in PAYLOAD_KEYS plus chunk_locator, no extras leak.
    first_payload = points[0].payload
    assert first_payload is not None
    assert set(first_payload.keys()) == set(PAYLOAD_KEYS) | {"chunk_locator"}
    assert "extra_field_dropped" not in first_payload
    assert first_payload["workspace_id"] == "ws_1"
    assert first_payload["chunk_text"] == "hello world"


@pytest.mark.asyncio
async def test_upsert_chunks_omits_missing_payload_keys() -> None:
    """A chunk without every PAYLOAD_KEY just gets the subset it has."""
    settings = _settings()
    store, mock_client = _store_with_mock(settings)
    chunks = [
        {
            "chunk_id": "doc_b#v1#chunk_0",
            "embedding": _vector(),
            "workspace_id": "ws_1",
            "chunk_text": "minimal",
        }
    ]

    await store.upsert_chunks(chunks)

    points = mock_client.upsert.await_args.kwargs["points"]
    assert len(points) == 1
    assert points[0].payload == {
        "workspace_id": "ws_1",
        "chunk_text": "minimal",
        "chunk_locator": "doc_b#v1#chunk_0",
    }


@pytest.mark.asyncio
async def test_upsert_chunks_empty_is_a_noop() -> None:
    """Empty batch → no client.upsert call."""
    settings = _settings()
    store, mock_client = _store_with_mock(settings)

    await store.upsert_chunks([])

    mock_client.upsert.assert_not_awaited()


# ---------- delete_by_filter ---------------------------------------------


@pytest.mark.asyncio
async def test_delete_by_filter_passes_filter_through() -> None:
    settings = _settings()
    store, mock_client = _store_with_mock(settings)
    filter_ = models.Filter(
        must=[models.FieldCondition(key="workspace_id", match=models.MatchValue(value="ws_1"))]
    )

    await store.delete_by_filter(filter_)

    mock_client.delete.assert_awaited_once()
    call = mock_client.delete.await_args
    assert call is not None
    assert call.kwargs["collection_name"] == settings.RV_QDRANT_COLLECTION
    assert call.kwargs["points_selector"] is filter_


# ---------- rebuild_from_postgres ----------------------------------------


@pytest.mark.asyncio
async def test_rebuild_drops_existing_collection_then_recreates() -> None:
    """When the collection exists: delete + recreate + reindex."""
    settings = _settings()
    store, mock_client = _store_with_mock(settings)
    # First call: collection_exists (in rebuild) → True. Then collection
    # delete, then ensure_collection runs collection_exists again → False
    # so it creates + indexes.
    mock_client.collection_exists.side_effect = [True, False]

    await store.rebuild_from_postgres()

    mock_client.delete_collection.assert_awaited_once_with(settings.RV_QDRANT_COLLECTION)
    mock_client.create_collection.assert_awaited_once()
    assert mock_client.create_payload_index.await_count == len(PAYLOAD_INDEXES)


@pytest.mark.asyncio
async def test_rebuild_skips_delete_when_collection_missing() -> None:
    """No existing collection → no delete, just create + index."""
    settings = _settings()
    store, mock_client = _store_with_mock(settings)
    mock_client.collection_exists.return_value = False

    await store.rebuild_from_postgres()

    mock_client.delete_collection.assert_not_awaited()
    mock_client.create_collection.assert_awaited_once()


# ---------- close ---------------------------------------------------------


@pytest.mark.asyncio
async def test_close_delegates_to_client() -> None:
    settings = _settings()
    store, mock_client = _store_with_mock(settings)

    await store.close()

    mock_client.close.assert_awaited_once()


# ---------- constant sanity ----------------------------------------------


def test_payload_indexes_match_p4_t3_filter_fields() -> None:
    """The exact set the task spec calls out — guard against accidental
    reordering or schema drift."""
    assert PAYLOAD_INDEXES == (
        ("workspace_id", models.PayloadSchemaType.KEYWORD),
        ("document_id", models.PayloadSchemaType.KEYWORD),
        ("version_id", models.PayloadSchemaType.KEYWORD),
        ("source_type", models.PayloadSchemaType.KEYWORD),
        ("status", models.PayloadSchemaType.KEYWORD),
        ("created_at", models.PayloadSchemaType.DATETIME),
        ("corpus_id", models.PayloadSchemaType.KEYWORD),
        ("doc_title", models.PayloadSchemaType.TEXT),
    )
