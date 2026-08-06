"""
Tests for ``rekanvault.evidence.chunker``.

P4-T1 (stable chunk IDs) is the primary test: re-processing the same
version must yield byte-identical chunks. The other tests pin the
structure-first policy: block-type boundaries are preserved, and
oversized blocks split with overlap.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from rekanvault.evidence import Chunker
from rekanvault.evidence.chunker import MAX_BLOCK_TOKENS
from rekanvault.storage.document_repo import DocumentRepository
from rekanvault.storage.models import ContentBlock, Document, DocumentVersion

# ---------- helpers --------------------------------------------------------


def _version(
    *,
    external_id: str = "doc-1",
    version_number: int = 1,
    workspace_id: uuid.UUID | None = None,
) -> DocumentVersion:
    """Build a DocumentVersion with its ``document`` relationship
    populated (the chunker reads ``external_id`` off the document)."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        source_id=uuid.uuid4(),
        external_id=external_id,
        title="Doc",
        mime_type="text/plain",
    )
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        workspace_id=doc.workspace_id,
        version_number=version_number,
        fingerprint="fp",
        content_hash="h",
        byte_size=0,
    )
    # Wire the backref directly: SQLAlchemy 2.x allows attribute assignment
    # on relationships without a flush, and the chunker reads document.external_id.
    version.document = doc
    return version


def _block(text: str, *, block_type: str = "paragraph", index: int) -> ContentBlock:
    return ContentBlock(
        id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        block_index=index,
        block_type=block_type,
        content_text=text,
        metadata_={},
    )


def _chunker_with(version: DocumentVersion, blocks: list[ContentBlock]) -> Chunker:
    """Wire a DocumentRepository with mocked get_version + get_content_blocks
    returning the supplied version and blocks."""
    repo = DocumentRepository()
    repo.get_version = AsyncMock(return_value=version)  # type: ignore[method-assign]
    repo.get_content_blocks = AsyncMock(return_value=blocks)  # type: ignore[method-assign]
    return Chunker(repo)


# ---------- stable chunk IDs (P4-T1) ---------------------------------------


@pytest.mark.asyncio
async def test_stable_chunk_ids() -> None:
    """Re-running chunk_version on the same version produces identical IDs
    and content (P4-T1 — deterministic rebuildability)."""
    version = _version(external_id="doc-stable", version_number=2)
    blocks = [
        _block("First paragraph.", block_type="paragraph", index=0),
        _block("Second paragraph.", block_type="paragraph", index=1),
        _block("A heading", block_type="heading", index=2),
        _block("Third paragraph.", block_type="paragraph", index=3),
    ]
    session: Any = AsyncMock()

    chunker = _chunker_with(version, blocks)
    first = await chunker.chunk_version(session, version.id)
    second = await chunker.chunk_version(session, version.id)

    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.content_text for c in first] == [c.content_text for c in second]
    assert [c.token_count for c in first] == [c.token_count for c in second]


# ---------- chunk id format ------------------------------------------------


@pytest.mark.asyncio
async def test_chunk_id_format() -> None:
    """IDs follow ``{external_id}#v{version_number}#chunk_{seq:03d}``."""
    version = _version(external_id="alpha-doc", version_number=7)
    # Use different block types so the structure-first policy keeps them
    # as separate chunks (format check is independent of merge behavior).
    blocks = [
        _block("one", block_type="heading", index=0),
        _block("two", block_type="paragraph", index=1),
        _block("three", block_type="list", index=2),
    ]
    session: Any = AsyncMock()
    chunker = _chunker_with(version, blocks)

    chunks = await chunker.chunk_version(session, version.id)
    ids = [c.chunk_id for c in chunks]

    assert ids == [
        "alpha-doc#v7#chunk_001",
        "alpha-doc#v7#chunk_002",
        "alpha-doc#v7#chunk_003",
    ]


# ---------- block-type boundary preservation ------------------------------


@pytest.mark.asyncio
async def test_block_boundary_respect() -> None:
    """Blocks of different types must not be merged — structural boundaries
    are preserved (RV-DEC-P4-0004, structure-first)."""
    version = _version()
    blocks = [
        _block("A long enough paragraph one.", block_type="paragraph", index=0),
        _block("A long enough paragraph two.", block_type="paragraph", index=1),
        _block("A heading line", block_type="heading", index=2),
        _block("A long enough paragraph three.", block_type="paragraph", index=3),
    ]
    session: Any = AsyncMock()
    chunker = _chunker_with(version, blocks)

    chunks = await chunker.chunk_version(session, version.id)

    # 4 blocks total → at least 3 chunks (the heading always starts a new one).
    # The two preceding paragraphs of the same type likely merged into one chunk.
    assert len(chunks) >= 3
    # Find the heading chunk; it should be alone (no merged neighbors).
    heading_chunk = next(c for c in chunks if c.metadata["block_types"] == ["heading"])
    assert heading_chunk.start_block_index == heading_chunk.end_block_index == 2
    # Adjacent chunks must not straddle the heading boundary.
    preceding = [c for c in chunks if c.end_block_index < 2]
    following = [c for c in chunks if c.start_block_index > 2]
    assert preceding, "expected a chunk spanning the pre-heading paragraphs"
    assert following, "expected a chunk for the post-heading paragraph"


# ---------- oversized block split with overlap ----------------------------


@pytest.mark.asyncio
async def test_large_block_split() -> None:
    """A single block > MAX_BLOCK_TOKENS is split into multiple chunks
    with overlap, and all splits share the same block_index range."""
    # 1 token ≈ 4 chars of English text. ~600 tokens ≫ 450 budget.
    long_text = " ".join(f"word{i}" for i in range(2400))  # ~2400 tokens
    assert len(long_text.split()) > MAX_BLOCK_TOKENS

    version = _version()
    blocks = [_block(long_text, block_type="paragraph", index=0)]
    session: Any = AsyncMock()
    chunker = _chunker_with(version, blocks)

    chunks = await chunker.chunk_version(session, version.id)

    assert len(chunks) > 1, "oversized block must split into multiple chunks"
    # Every split is a single-block chunk (start == end == original index).
    for c in chunks:
        assert c.start_block_index == 0
        assert c.end_block_index == 0
        assert c.metadata["block_types"] == ["paragraph"]
        assert c.token_count <= MAX_BLOCK_TOKENS
    # Consecutive splits must overlap: tail of chunk N == head of chunk N+1.
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        prev_tokens = prev.content_text.split()
        nxt_tokens = nxt.content_text.split()
        # Overlap >= 1 token (the 80-token overlap policy keeps a long tail).
        assert any(t in prev_tokens for t in nxt_tokens[:120]), (
            "expected overlap between consecutive splits"
        )
