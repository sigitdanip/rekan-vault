"""Unit tests for rekanvault.evaluation.extraction_corpus_runner."""

from __future__ import annotations

from rekanvault.evaluation.extraction_corpus_runner import CorpusExtractionReport


def _report() -> CorpusExtractionReport:
    return CorpusExtractionReport(
        workspace_id="ws",
        active_documents=1,
        total_chunks=10,
        chunks_ok=9,
        chunks_failed=1,
        total_memories=20,
        type_distribution={"Fact": 2, "Asset": 1},
        failure_codes={"VALIDATION_ERROR": 1},
        elapsed_s=1.0,
    )


def test_failure_rate() -> None:
    assert _report().failure_rate == 0.1


def test_failure_rate_zero_guard() -> None:
    report = CorpusExtractionReport(
        workspace_id="ws",
        active_documents=0,
        total_chunks=0,
        chunks_ok=0,
        chunks_failed=0,
        total_memories=0,
        type_distribution={},
        failure_codes={},
        elapsed_s=0.0,
    )
    assert report.failure_rate == 0.0


def test_to_dict_sorts_types_and_rounds() -> None:
    data = _report().to_dict()
    assert data["failure_rate"] == 0.1
    assert data["memories_per_chunk"] == 2.0
    assert list(data["type_distribution"].items()) == [("Asset", 1), ("Fact", 2)]
    assert data["failure_codes"] == {"VALIDATION_ERROR": 1}
    assert data["bindings"] == {}
