"""Tests for ``rekanvault.evidence.citation``."""

from __future__ import annotations

from typing import Any

from rekanvault.contracts.evidence import Citation
from rekanvault.evidence.citation import CitationResolver


def _meta(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "My Doc",
        "source_type": "google_drive",
        "external_id": "abc123",
    }
    base.update(overrides)
    return base


# ---------- Google Drive --------------------------------------------------


def test_resolve_gdrive_citation() -> None:
    resolver = CitationResolver()
    meta = _meta(source_type="google_drive", external_id="abc123")

    c = resolver.resolve(
        meta,
        document_id="doc-1",
        version_id="ver-1",
        content="hello world",
    )

    assert isinstance(c, Citation)
    assert c.document_id == "doc-1"
    assert c.version_id == "ver-1"
    assert c.title == "My Doc"
    assert c.uri == "https://drive.google.com/file/d/abc123/view"
    assert c.snippet == "hello world"
    assert c.block_id is None


def test_resolve_gdrive_with_block_id() -> None:
    """block_id is optional and left None for non-block sources."""
    resolver = CitationResolver()
    meta = _meta(block_id="block-xyz")

    c = resolver.resolve(meta, document_id="d", version_id="v", content="x")

    assert c.block_id == "block-xyz"


# ---------- Notion --------------------------------------------------------


def test_resolve_notion_citation() -> None:
    resolver = CitationResolver()
    meta = _meta(
        source_type="notion",
        external_id="def456",
        block_id="notion-block-uuid-1",
        title="Notion Page",
    )

    c = resolver.resolve(meta, document_id="d-2", version_id="v-2", content="page body")

    assert c.uri == "https://notion.so/def456"
    # Notion block UUIDs preserved per P3-T8.
    assert c.block_id == "notion-block-uuid-1"
    assert c.title == "Notion Page"
    assert c.snippet == "page body"


# ---------- Unknown source -----------------------------------------------


def test_resolve_unknown_source() -> None:
    resolver = CitationResolver()
    meta = _meta(source_type="mystery_source", external_id="zzz")

    c = resolver.resolve(meta, document_id="d", version_id="v", content="hi")

    # Generic placeholder URI rather than raising — the citation stays
    # usable; consumers can tell from the host.
    assert c.uri == "https://example.invalid/zzz"


def test_resolve_snippet_truncates_to_200_chars() -> None:
    resolver = CitationResolver()
    long_content = "x" * 500

    c = resolver.resolve(_meta(), document_id="d", version_id="v", content=long_content)

    assert len(c.snippet) == 200
    assert c.snippet == "x" * 200
