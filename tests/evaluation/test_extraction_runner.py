"""Unit tests for rekanvault.evaluation.extraction_runner."""

from __future__ import annotations

from rekanvault.evaluation.extraction_runner import (
    DEFAULT_EXTRACTION_GOLDEN_PATH,
    ExtractionEvaluationRunner,
    load_extraction_golden_set,
)


def test_load_extraction_golden_set_file_exists() -> None:
    cases = load_extraction_golden_set(DEFAULT_EXTRACTION_GOLDEN_PATH)
    assert len(cases) == 18, f"Expected 18 extraction test cases, got {len(cases)}"
    first = cases[0]
    assert first["id"] == "EXT-001"
    assert first["memory_type"] == "Fact"
    assert first["locator"] == "SOP_Presales_RekanDigital.docx#v1#chunk_001"
    assert "Kode Dokumen" in first["expected_memory"]["title"]


def test_evaluate_set_100_percent_pass() -> None:
    cases = load_extraction_golden_set(DEFAULT_EXTRACTION_GOLDEN_PATH)
    runner = ExtractionEvaluationRunner()
    results = runner.evaluate_set(cases)

    assert results["total_cases"] == 18
    assert results["valid_cases"] == 18
    assert results["schema_validation_rate"] == 1.0
