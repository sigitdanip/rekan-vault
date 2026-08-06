"""
Tests for ``rekanvault.evidence.indexing.IndexingPipeline`` (P4-T5/T6).

Every collaborator is an ``AsyncMock`` / ``MagicMock`` — no real DB,
no real Qdrant, no real sentence-transformers model load. The pipeline
is a pure orchestrator; these tests pin the contract of one happy path
and one empty path.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client.http import models

from rekanvault.evidence.chunker import Chunk
from rekanvault.evidence.indexing import CHUNK_TEXT_PAYLOAD_MAX_CHARS, IndexingPipeline
from rekanvault.storage.models import Document, DocumentVersion

# ---------- helpers --------------------------------------------------------


def _make_version(*, document_id: uuid.UUID | None = None) -> DocumentVersion:
    """Build a DocumentVersion with a populated ``document`` + ``source``."""
    doc = Document(
        id=document_id or uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        external_id="doc-1",
        title="Doc",
        mime_type="text/plain",
        corpus_id=uuid.uuid4(),
    )
    doc.source = MagicMock()
    doc.source.provider = "google_drive"
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        workspace_id=doc.workspace_id,
        version_number=1,
        fingerprint="fp",
        content_hash="h",
        byte_size=0,
    )
    version.document = doc
    return version


def _make_chunk(version: DocumentVersion, *, text: str = "hello", seq: int = 1) -> Chunk:
    return Chunk(
        chunk_id=f"doc-1#v1#chunk_{seq:03d}",
        document_version_id=version.id,
        workspace_id=version.workspace_id,
        start_block_index=0,
        end_block_index=0,
        content_text=text,
        token_count=1,
    )


def _make_pipeline() -> tuple[IndexingPipeline, dict[str, Any]]:
    session = MagicMock()
    chunker = MagicMock()
    embed = MagicMock()
    qdrant = MagicMock()
    doc_repo = MagicMock()

    chunker.chunk_version = AsyncMock()
    embed.embed = MagicMock()
    qdrant.upsert_chunks = AsyncMock()
    qdrant.delete_by_filter = AsyncMock()
    doc_repo.get_version = AsyncMock()
    doc_repo.list_versions_for_document = AsyncMock()

    pipeline = IndexingPipeline(
        session=session,
        chunker=chunker,
        embed=embed,
        qdrant=qdrant,
        doc_repo=doc_repo,
    )
    return pipeline, {
        "chunker": chunker,
        "embed": embed,
        "qdrant": qdrant,
        "doc_repo": doc_repo,
    }


# ---------- tests ----------------------------------------------------------


@pytest.mark.asyncio
async def test_index_version_chunks_and_embeds() -> None:
    pipeline, mocks = _make_pipeline()
    version = _make_version()
    chunks = [_make_chunk(version, text=f"text {i}", seq=i + 1) for i in range(3)]
    mocks["doc_repo"].get_version.return_value = version
    mocks["chunker"].chunk_version.return_value = chunks
    mocks["embed"].embed.return_value = [[0.1] * 4, [0.2] * 4, [0.3] * 4]

    count = await pipeline.index_version(version.id)

    assert count == 3
    mocks["chunker"].chunk_version.assert_awaited_once()
    mocks["embed"].embed.assert_called_once()
    texts_arg = mocks["embed"].embed.call_args[0][0]
    assert texts_arg == ["text 0", "text 1", "text 2"]
    mocks["qdrant"].upsert_chunks.assert_awaited_once()

    points = mocks["qdrant"].upsert_chunks.call_args[0][0]
    assert len(points) == 3
    expected_vectors = [[0.1] * 4, [0.2] * 4, [0.3] * 4]
    for idx, point in enumerate(points, start=1):
        assert point["id"] == f"doc-1#v1#chunk_{idx:03d}"
        assert point["vector"] == {"dense": expected_vectors[idx - 1]}
        payload = point["payload"]
        assert payload["workspace_id"] == str(version.workspace_id)
        assert payload["document_id"] == str(version.document.id)
        assert payload["version_id"] == str(version.id)
        assert payload["source_type"] == "google_drive"
        assert payload["status"] == "active"
        assert payload["corpus_id"] == str(version.document.corpus_id)
        assert payload["block_start"] == 0
        assert payload["block_end"] == 0
        assert "created_at" in payload


@pytest.mark.asyncio
async def test_index_version_empty_chunks() -> None:
    pipeline, mocks = _make_pipeline()
    version = _make_version()
    mocks["doc_repo"].get_version.return_value = version
    mocks["chunker"].chunk_version.return_value = []

    count = await pipeline.index_version(version.id)

    assert count == 0
    mocks["embed"].embed.assert_not_called()
    mocks["qdrant"].upsert_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_index_version_missing_version_returns_zero() -> None:
    pipeline, mocks = _make_pipeline()
    mocks["doc_repo"].get_version.return_value = None

    count = await pipeline.index_version(uuid.uuid4())

    assert count == 0
    mocks["chunker"].chunk_version.assert_not_called()
    mocks["qdrant"].upsert_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_index_version_truncates_chunk_text() -> None:
    pipeline, mocks = _make_pipeline()
    version = _make_version()
    long_text = "x" * (CHUNK_TEXT_PAYLOAD_MAX_CHARS + 250)
    chunk = _make_chunk(version, text=long_text, seq=1)
    mocks["doc_repo"].get_version.return_value = version
    mocks["chunker"].chunk_version.return_value = [chunk]
    mocks["embed"].embed.return_value = [[0.0] * 4]

    await pipeline.index_version(version.id)

    points = mocks["qdrant"].upsert_chunks.call_args[0][0]
    assert len(points[0]["payload"]["chunk_text"]) == CHUNK_TEXT_PAYLOAD_MAX_CHARS


@pytest.mark.asyncio
async def test_deactivate_version_deletes_from_qdrant() -> None:
    pipeline, mocks = _make_pipeline()
    version = _make_version()
    mocks["doc_repo"].get_version.return_value = version

    count = await pipeline.deactivate_version(version.id)

    # ponytail: returns 0 by design — Qdrant delete doesn't surface count.
    assert count == 0
    mocks["qdrant"].delete_by_filter.assert_awaited_once()
    filter_arg: models.Filter = mocks["qdrant"].delete_by_filter.call_args[0][0]
    assert isinstance(filter_arg, models.Filter)
    assert filter_arg.must is not None
    conditions = [c for c in filter_arg.must if isinstance(c, models.FieldCondition)]
    assert len(conditions) == 2
    keys = {cond.key for cond in conditions}
    assert keys == {"document_id", "version_id"}


@pytest.mark.asyncio
async def test_deactivate_version_missing_version_returns_zero() -> None:
    pipeline, mocks = _make_pipeline()
    mocks["doc_repo"].get_version.return_value = None

    count = await pipeline.deactivate_version(uuid.uuid4())

    assert count == 0
    mocks["qdrant"].delete_by_filter.assert_not_called()


@pytest.mark.asyncio
async def test_handle_document_change_indexes_new_and_deactivates_olds() -> None:
    pipeline, mocks = _make_pipeline()
    document_id = uuid.uuid4()
    new_version = _make_version(document_id=document_id)
    old_version = _make_version(document_id=document_id)
    mocks["doc_repo"].get_version.side_effect = [new_version, old_version, old_version]
    mocks["chunker"].chunk_version.return_value = [_make_chunk(new_version, seq=1)]
    mocks["embed"].embed.return_value = [[0.1] * 4]
    mocks["doc_repo"].list_versions_for_document.return_value = [new_version, old_version]

    await pipeline.handle_document_change(document_id, new_version.id)

    mocks["chunker"].chunk_version.assert_awaited_once()
    mocks["qdrant"].upsert_chunks.assert_awaited_once()
    # Only the old version is deactivated (new_version is the head).
    assert mocks["qdrant"].delete_by_filter.await_count == 1
    mocks["doc_repo"].list_versions_for_document.assert_awaited_once()
