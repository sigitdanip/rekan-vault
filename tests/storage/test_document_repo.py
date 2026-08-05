"""
Tests for ``rekanvault.storage.document_repo``.

Follows the existing pattern: ``AsyncMock`` session, ``MagicMock`` for
select results, no fixtures, no conftest. The repository only stages
rows; we assert the staged shape (the value passed to ``session.add``)
rather than the SQL.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rekanvault.contracts.documents import (
    DocumentBlock,
    DocumentLocator,
    DocumentVersion,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.storage.document_repo import DocumentRepository
from rekanvault.storage.models import ContentBlock, Document
from rekanvault.storage.models import DocumentVersion as DbDocumentVersion

# ---------- helpers --------------------------------------------------------


def _block(block_id: str, content: str, block_type: str = "paragraph", sequence: int = 1) -> DocumentBlock:
    return DocumentBlock(
        block_id=block_id,
        block_type=block_type,
        content=content,
        sequence=sequence,
    )


def _normalized(
    *,
    native_id: str,
    title: str = "Doc",
    content: str = "hello",
    block_id: str | None = None,
) -> NormalizedDocument:
    bid = block_id or f"blk_{native_id}"
    return NormalizedDocument(
        document_id=f"doc_{native_id}",
        workspace_id="ws_test",
        source_id="src_test",
        title=title,
        provider=SourceProvider.NOTION,
        locator=DocumentLocator(
            provider=SourceProvider.NOTION,
            native_id=native_id,
            uri=f"https://example.com/{native_id}",
        ),
        active_version_id="ver_1",
        versions=[
            DocumentVersion(
                version_id="ver_1",
                document_id=f"doc_{native_id}",
                version_number=1,
                content_hash="h1",
                blocks=[_block(bid, content)],
            )
        ],
    )


def _session_with_lookup(existing: Document | None) -> AsyncMock:
    """Session whose first ``select(Document)`` resolves to ``existing``;
    subsequent selects return whatever the test wires up."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute.return_value = result
    return session


def _staged_adds(session: AsyncMock) -> list[Any]:
    """Flatten the args of every ``session.add`` call (ignores the
    keyword-arg form, which the repo doesn't use)."""
    return [call.args[0] for call in session.add.call_args_list if call.args]


# ---------- upsert: new document ------------------------------------------


@pytest.mark.asyncio
async def test_upsert_new_document_creates_row_version_and_blocks() -> None:
    """No existing row → one Document + one DocumentVersion + N ContentBlocks."""
    session = _session_with_lookup(existing=None)
    repo = DocumentRepository()
    workspace_id = uuid.uuid4()
    source_id = uuid.uuid4()
    doc = _normalized(native_id="alpha", content="block-1-text")

    returned = await repo.upsert_document(
        session=session,
        workspace_id=workspace_id,
        source_id=source_id,
        normalized=doc,
    )

    assert isinstance(returned, Document)
    assert returned.workspace_id == workspace_id
    assert returned.source_id == source_id
    assert returned.external_id == "alpha"
    assert returned.title == "Doc"

    added = _staged_adds(session)
    assert sum(isinstance(a, Document) for a in added) == 1
    versions = [a for a in added if isinstance(a, DbDocumentVersion)]
    blocks = [a for a in added if isinstance(a, ContentBlock)]
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].content_hash != ""  # sha256 of "block-1-text"
    assert len(blocks) == 1
    assert blocks[0].block_index == 0
    assert blocks[0].content_text == "block-1-text"


# ---------- upsert: unchanged skips write ---------------------------------


@pytest.mark.asyncio
async def test_upsert_unchanged_returns_existing_without_new_version() -> None:
    """Fingerprint match → no new DocumentVersion, no new ContentBlocks."""
    existing = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        external_id="alpha",
        title="Doc",
        mime_type="application/octet-stream",
    )
    session = _session_with_lookup(existing=existing)
    # Second select (latest version) returns a version with the same
    # fingerprint the repo will compute.
    repo = DocumentRepository()

    # Pre-compute what the repo's fingerprint will be so we can wire
    # the mock to match it.
    from rekanvault.storage.document_repo import _fingerprint_for

    expected_fingerprint = _fingerprint_for(_normalized(native_id="alpha"))

    latest = DbDocumentVersion(
        id=uuid.uuid4(),
        document_id=existing.id,
        workspace_id=existing.workspace_id,
        version_number=1,
        fingerprint=expected_fingerprint,
        content_hash="h1",
        byte_size=11,
    )

    # Two execute() calls: first for get_by_external_id, second for
    # _latest_version. Wire them up sequentially.
    get_result = MagicMock()
    get_result.scalar_one_or_none.return_value = existing
    latest_result = MagicMock()
    latest_result.scalar_one_or_none.return_value = latest
    session.execute.side_effect = [get_result, latest_result]

    returned = await repo.upsert_document(
        session=session,
        workspace_id=existing.workspace_id,
        source_id=existing.source_id,
        normalized=_normalized(native_id="alpha"),
    )

    assert returned is existing
    added = _staged_adds(session)
    # No DocumentVersion or ContentBlock staged.
    assert not any(isinstance(a, DbDocumentVersion) for a in added)
    assert not any(isinstance(a, ContentBlock) for a in added)


# ---------- upsert: changed content → new version ------------------------


@pytest.mark.asyncio
async def test_upsert_changed_content_creates_new_version_with_incremented_number() -> None:
    """Fingerprint differs → new DocumentVersion with version_number bumped."""
    existing = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        external_id="beta",
        title="Doc",
        mime_type="text/plain",
    )
    session = _session_with_lookup(existing=existing)
    repo = DocumentRepository()

    # Wire latest-version result: returns version_number=1 with a
    # different fingerprint → upsert will write version_number=2.
    prior_version = DbDocumentVersion(
        id=uuid.uuid4(),
        document_id=existing.id,
        workspace_id=existing.workspace_id,
        version_number=1,
        fingerprint="old-fingerprint-doesnt-match",
        content_hash="h1",
        byte_size=5,
    )
    get_result = MagicMock()
    get_result.scalar_one_or_none.return_value = existing
    latest_result = MagicMock()
    latest_result.scalar_one_or_none.return_value = prior_version
    # 2 selects: get_by_external_id, _latest_version (in upsert). The
    # version_number is computed from this same row in _insert_new_version.
    session.execute.side_effect = [get_result, latest_result]

    changed = _normalized(native_id="beta", content="new-and-different")
    returned = await repo.upsert_document(
        session=session,
        workspace_id=existing.workspace_id,
        source_id=existing.source_id,
        normalized=changed,
    )

    assert returned is existing
    added = _staged_adds(session)
    versions = [a for a in added if isinstance(a, DbDocumentVersion)]
    blocks = [a for a in added if isinstance(a, ContentBlock)]
    assert len(versions) == 1
    assert versions[0].version_number == 2
    assert versions[0].content_hash != prior_version.content_hash
    assert len(blocks) == 1
    assert blocks[0].content_text == "new-and-different"
    # Title drift updates the parent Document row in place.
    assert existing.title == "Doc"  # unchanged in this test


# ---------- get_by_external_id --------------------------------------------


@pytest.mark.asyncio
async def test_get_by_external_id_returns_row_when_present() -> None:
    expected = Document(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        external_id="gamma",
        title="T",
        mime_type="text/plain",
    )
    session = _session_with_lookup(existing=expected)
    repo = DocumentRepository()

    result = await repo.get_by_external_id(
        session=session,
        workspace_id=expected.workspace_id,
        source_id=expected.source_id,
        external_id="gamma",
    )

    assert result is expected


@pytest.mark.asyncio
async def test_get_by_external_id_returns_none_when_missing() -> None:
    session = _session_with_lookup(existing=None)
    repo = DocumentRepository()

    result = await repo.get_by_external_id(
        session=session,
        workspace_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        external_id="missing",
    )

    assert result is None
