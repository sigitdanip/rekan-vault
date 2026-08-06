"""Tests for ``rekanvault.evidence.assembler``.

Follows the existing pattern: no fixtures, no conftest, plain
constructor calls + assertions on the returned models.
"""

from __future__ import annotations

from typing import Any

from rekanvault.contracts.context import ContextPack
from rekanvault.contracts.evidence import Citation, RerankedEvidence
from rekanvault.evidence.assembler import EvidenceAssembler, insufficient_evidence

# ---------- helpers --------------------------------------------------------


def _chunk(
    chunk_id: str,
    *,
    score: float,
    token_count: int = 50,
    content: str = "some content",
    source_type: str = "google_drive",
    external_id: str = "ext-1",
    title: str = "Doc",
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": f"doc-{chunk_id}",
        "version_id": f"ver-{chunk_id}",
        "workspace_id": "ws-1",
        "content": content,
        "token_count": token_count,
        "score": score,
        "metadata": {
            "title": title,
            "source_type": source_type,
            "external_id": external_id,
        },
    }


# ---------- assemble ------------------------------------------------------


def test_assemble_returns_reranked_evidence() -> None:
    assembler = EvidenceAssembler()
    chunks = [
        _chunk("a", score=0.9),
        _chunk("b", score=0.7),
        _chunk("c", score=0.5),
    ]

    result = assembler.assemble(chunks, top_k=3)

    assert isinstance(result, RerankedEvidence)
    assert len(result.chunks) == 3
    # Sorted by score desc.
    assert [c.chunk_id for c in result.chunks] == ["a", "b", "c"]
    # One citation per chunk, in the same order.
    assert len(result.citations) == 3
    assert all(isinstance(c, Citation) for c in result.citations)
    assert result.citations[0].document_id == "doc-a"
    # top_score=0.9, num_results/top_k = 1.0 → 0.9
    assert result.sufficiency_score == 0.9


def test_assemble_respects_top_k() -> None:
    assembler = EvidenceAssembler()
    chunks = [_chunk(f"c{i}", score=1.0 - i * 0.1) for i in range(5)]

    result = assembler.assemble(chunks, top_k=2)

    assert len(result.chunks) == 2
    assert [c.chunk_id for c in result.chunks] == ["c0", "c1"]
    # 1.0 * (2/2) = 1.0
    assert result.sufficiency_score == 1.0


def test_empty_chunks_returns_zero_sufficiency() -> None:
    assembler = EvidenceAssembler()

    result = assembler.assemble([])

    assert result.chunks == []
    assert result.citations == []
    assert result.sufficiency_score == 0.0


def test_below_threshold_returns_empty() -> None:
    assembler = EvidenceAssembler()
    chunks = [
        _chunk("a", score=0.3),
        _chunk("b", score=0.2),
    ]

    result = assembler.assemble(chunks, top_k=5, sufficiency_threshold=0.5)

    assert result.chunks == []
    assert result.citations == []
    assert result.sufficiency_score == 0.0


# ---------- build_context_pack -------------------------------------------


def test_build_context_pack_stays_within_budget() -> None:
    assembler = EvidenceAssembler()
    chunks = [_chunk(f"c{i}", score=0.9 - i * 0.05, token_count=100) for i in range(10)]
    reranked = assembler.assemble(chunks, top_k=10)

    pack = assembler.build_context_pack("q", reranked, "ws-1", token_budget=250)

    assert isinstance(pack, ContextPack)
    assert pack.workspace_id == "ws-1"
    assert pack.query == "q"
    assert pack.token_budget == 250
    # 100 + 100 = 200, third would push us to 300 > 250.
    assert len(pack.evidence_chunks) == 2
    assert sum(c.token_count for c in pack.evidence_chunks) <= 250


def test_build_context_pack_empty_evidence() -> None:
    assembler = EvidenceAssembler()
    reranked = RerankedEvidence(chunks=[], citations=[], sufficiency_score=0.0)

    pack = assembler.build_context_pack("q", reranked, "ws-1", token_budget=1000)

    assert pack.evidence_chunks == []
    assert pack.context_pack_id  # uuid assigned


# ---------- insufficient_evidence helper ---------------------------------


def test_insufficient_evidence_helper() -> None:
    pack = insufficient_evidence("q", "ws-1")

    assert isinstance(pack, ContextPack)
    assert pack.workspace_id == "ws-1"
    assert pack.query == "q"
    assert pack.evidence_chunks == []
    assert pack.memories == []
    assert pack.metadata.get("diagnostic") == "INSUFFICIENT_EVIDENCE"
