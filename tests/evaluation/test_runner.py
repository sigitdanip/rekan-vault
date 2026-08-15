"""
Tests for ``rekanvault.evaluation.runner``.

Mock the ``RetrievalPipeline.search`` to return a controlled ranked list
of hits so each test exercises one metric in isolation. No real DB,
Qdrant, or model calls.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from rekanvault.evaluation.runner import (
    DEFAULT_GOLDEN_PATH,
    EvaluationRunner,
    load_golden_questions,
)
from rekanvault.evidence.retrieval import RetrievalPipeline


def _make_pipeline(hits_by_question: dict[str, list[dict[str, Any]]]) -> RetrievalPipeline:
    """Build a ``RetrievalPipeline`` whose ``search`` returns the hit
    list keyed by the question text."""
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)  # bypass __init__
    pipeline.search = AsyncMock(
        side_effect=lambda q, _ws, top_k=10, ablate_title_hacks=False: hits_by_question.get(q, [])
    )
    return pipeline


def _hit(chunk_id: str, score: float, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": "doc-x",
        "version_id": "v1",
        "content": "irrelevant",
        "score": score,
        "source": "both",
        "block_start": 0,
        "block_end": 0,
        "metadata": metadata or {},
    }


# ---------- load_golden_questions -----------------------------------------


def test_load_golden_questions(tmp_path: Path) -> None:
    md = (
        "# Golden Set\n\n"
        "| ID | Category | Question | Target Source / Path | Expected Answer |\n"
        "|---|---|---|---|---|\n"
        '| `Q-001` | EXACT | "foo bar" | `path/one.md` | first answer |\n'
        '| `Q-002` | ID_SEMANTIC | "apa ini" | `path/two.md` | second answer |\n'
        '| `Q-003` | EN_SEMANTIC | "what?" | `path/three.md` | third answer |\n'
    )
    f = tmp_path / "golden.md"
    f.write_text(md, encoding="utf-8")

    qs = load_golden_questions(str(f))

    assert len(qs) == 3
    assert qs[0] == {
        "id": "Q-001",
        "category": "EXACT",
        "question": "foo bar",
        "target_source": "path/one.md",
        "expected_answer": "first answer",
    }
    assert qs[1]["id"] == "Q-002"
    assert qs[2]["expected_answer"] == "third answer"


def test_load_golden_questions_real_file_exists() -> None:
    """The repo's real golden set must parse and yield > 100 questions."""
    qs = load_golden_questions(DEFAULT_GOLDEN_PATH)
    assert len(qs) > 100, f"expected > 100 questions, got {len(qs)}"
    sample = qs[0]
    assert set(sample.keys()) == {"id", "category", "question", "target_source", "expected_answer"}


# ---------- evaluate_set metrics ------------------------------------------


@pytest.mark.asyncio
async def test_recall_at_10() -> None:
    target = "documents/foo.md"
    hits_q1 = [_hit("c1", 0.9), _hit("c2", 0.8), _hit("c3", 0.7, {"external_id": "documents/foo.md"})]
    hits_q2 = [_hit("c1", 0.9, {"external_id": "other.md"}), _hit("c2", 0.8)]
    pipeline = _make_pipeline({"q1": hits_q1, "q2": hits_q2})
    runner = EvaluationRunner(pipeline)

    result = await runner.evaluate_set(
        [
            {"id": "Q-001", "category": "EXACT", "question": "q1", "target_source": target, "expected_answer": "x"},
            {"id": "Q-002", "category": "EXACT", "question": "q2", "target_source": target, "expected_answer": "x"},
        ]
    )

    assert result["count"] == 2
    assert result["recall_at_10"] == 0.5
    assert result["details"][0]["correct"] is True
    assert result["details"][0]["first_rank"] == 3
    assert result["details"][1]["correct"] is False
    assert result["details"][1]["first_rank"] is None
@pytest.mark.asyncio
async def test_mrr() -> None:
    # Two questions: q1 correct at rank 1, q2 correct at rank 5.
    # MRR = (1/1 + 1/5) / 2 = (1 + 0.2) / 2 = 0.6
    target = "documents/foo.md"
    q1_hits = [_hit("c1", 0.9, {"external_id": "documents/foo.md"})]
    q2_hits = [
        _hit("c1", 0.9),
        _hit("c2", 0.8),
        _hit("c3", 0.7),
        _hit("c4", 0.6),
        _hit("c5", 0.5, {"external_id": "documents/foo.md"}),
    ]
    pipeline = _make_pipeline({"q1": q1_hits, "q2": q2_hits})
    runner = EvaluationRunner(pipeline)

    result = await runner.evaluate_set(
        [
            {"id": "Q-001", "category": "EXACT", "question": "q1", "target_source": target, "expected_answer": "x"},
            {"id": "Q-002", "category": "EXACT", "question": "q2", "target_source": target, "expected_answer": "x"},
        ]
    )

    assert result["mrr"] == pytest.approx(0.6, rel=1e-9)

    # Single-question variants: rank 1 → MRR = 1.0; rank 5 → MRR = 0.2
    pipeline_1 = _make_pipeline({"q1": q1_hits})
    r1 = await EvaluationRunner(pipeline_1).evaluate_set(
        [{"id": "Q-001", "category": "EXACT", "question": "q1", "target_source": target, "expected_answer": "x"}]
    )
    assert r1["mrr"] == pytest.approx(1.0, rel=1e-9)

    pipeline_5 = _make_pipeline({"q2": q2_hits})
    r2 = await EvaluationRunner(pipeline_5).evaluate_set(
        [{"id": "Q-002", "category": "EXACT", "question": "q2", "target_source": target, "expected_answer": "x"}]
    )
    assert r2["mrr"] == pytest.approx(0.2, rel=1e-9)


@pytest.mark.asyncio
async def test_ndcg() -> None:
    target = "documents/foo.md"
    q_hits = [
        _hit("c1", 0.9),
        _hit("c2", 0.8, {"external_id": "documents/foo.md"}),  # rank 2
    ]
    pipeline = _make_pipeline({"q1": q_hits})
    runner = EvaluationRunner(pipeline)

    result = await runner.evaluate_set(
        [{"id": "Q-001", "category": "EXACT", "question": "q1", "target_source": target, "expected_answer": "x"}]
    )

    expected = 1.0 / math.log2(3)  # ≈ 0.6309
    assert result["ndcg_at_10"] == pytest.approx(expected, rel=1e-9)
    assert result["ndcg_at_10"] == pytest.approx(0.63, rel=1e-2)


@pytest.mark.asyncio
async def test_empty_questions() -> None:
    pipeline = _make_pipeline({})
    runner = EvaluationRunner(pipeline)
    result = await runner.evaluate_set([])
    assert result["recall_at_10"] == 0.0
    assert result["mrr"] == 0.0
    assert result["ndcg_at_10"] == 0.0
    assert result["count"] == 0
    assert result["category_breakdown"] == {}
    assert result["details"] == []


@pytest.mark.asyncio
async def test_category_breakdown() -> None:
    """Per-category hits/total is computed over scorable questions only."""
    target = "documents/foo.md"
    hits_q1 = [_hit("c1", 0.9, {"external_id": "documents/foo.md"})]
    hits_q2 = [_hit("c1", 0.9)]  # miss
    hits_q3 = [_hit("c1", 0.9, {"external_id": "documents/foo.md"})]
    pipeline = _make_pipeline({"q1": hits_q1, "q2": hits_q2, "q3": hits_q3})
    runner = EvaluationRunner(pipeline)

    result = await runner.evaluate_set(
        [
            {"id": "Q-001", "category": "EXACT", "question": "q1", "target_source": target, "expected_answer": "x"},
            {"id": "Q-002", "category": "EXACT", "question": "q2", "target_source": target, "expected_answer": "x"},
            {"id": "Q-003", "category": "ID_SEMANTIC", "question": "q3", "target_source": target, "expected_answer": "x"},
        ]
    )

    assert result["category_breakdown"] == {
        "EXACT": {"hits": 1, "total": 2},
        "ID_SEMANTIC": {"hits": 1, "total": 1},
    }


@pytest.mark.asyncio
async def test_evaluate_set_threads_ablate_title_hacks() -> None:
    """ablate_title_hacks must be forwarded to pipeline.search."""
    seen: list[bool] = []
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    pipeline.search = AsyncMock(
        side_effect=lambda q, _ws, top_k=10, ablate_title_hacks=False: seen.append(ablate_title_hacks) or []
    )
    runner = EvaluationRunner(pipeline)

    await runner.evaluate_set(
        [{"id": "Q-001", "category": "EXACT", "question": "q1", "target_source": "p.md", "expected_answer": "x"}],
        ablate_title_hacks=True,
    )
    assert seen == [True]

    seen.clear()
    await runner.evaluate_set(
        [{"id": "Q-001", "category": "EXACT", "question": "q1", "target_source": "p.md", "expected_answer": "x"}]
    )
    assert seen == [False]


@pytest.mark.asyncio
async def test_evaluate_question_shape() -> None:
    """Per-question result carries the keys the spec requires."""
    pipeline = _make_pipeline({"q": [_hit("c1", 0.9, {"external_id": "p.md"})]})
    runner = EvaluationRunner(pipeline)
    q = {
        "id": "Q-100",
        "category": "EXACT",
        "question": "q",
        "target_source": "p.md",
        "expected_answer": "ans",
    }
    r = await runner.evaluate_question(q)
    assert r["question_id"] == "Q-100"
    assert r["category"] == "EXACT"
    assert r["expected"] == "ans"
    assert r["retrieved_ids"] == ["c1"]
    assert r["retrieved_scores"] == [0.9]
    assert r["correct"] is True
    assert r["first_rank"] == 1


@pytest.mark.asyncio
async def test_negative_question_target_none() -> None:
    """Out-of-corpus questions with target_source='None' score as correct=None."""
    pipeline = _make_pipeline({"q": [_hit("c1", 0.9, {"external_id": "any.md"})]})
    runner = EvaluationRunner(pipeline)
    q = {
        "id": "Q-061",
        "category": "NEGATIVE",
        "question": "q",
        "target_source": "None",
        "expected_answer": "INSUFFICIENT_EVIDENCE",
    }
    r = await runner.evaluate_question(q)
    assert r["correct"] is None
    assert r["first_rank"] is None
