"""
Golden-set evaluation runner for the retrieval pipeline (P4-T7 / ``RV-DEC-0015``).

Scores a set of questions against the hybrid ``RetrievalPipeline`` and
computes three retrieval metrics:

* **Recall@10** — fraction of questions whose expected target document
  appears in the top 10 retrieved chunks.
* **MRR** — mean of ``1 / rank`` for the first correct result (0 if
  not found).
* **nDCG@10** — simplified single-relevance ``1 / log2(rank + 1)`` for
  a hit in the top 10, divided by the ideal DCG of 1.0. Questions with
  no hit score 0.

A hit is defined as any retrieved chunk whose ``metadata`` contains the
expected ``target_source`` path string (substring match across metadata
values, since the exact field name varies between lexical and dense
retrievers).

Ponytail: one class, no strategy/factory. The metric math is short and
stable — keep it here as pure functions of the per-question results so
each test exercises one piece at a time.
"""

from __future__ import annotations

import math
import re
import uuid
from pathlib import Path
from typing import Any

from rekanvault.evidence.retrieval import RetrievalPipeline

DEFAULT_GOLDEN_PATH = "docs/REKANVAULT_GOLDEN_SET.md"

_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEPARATOR_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")


def _clean_cell(cell: str) -> str:
    """Strip surrounding whitespace, backticks, and a single matched
    pair of double-quotes from a markdown table cell."""
    s = cell.strip()
    if s.startswith("`") and s.endswith("`"):
        s = s[1:-1]
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    return s.strip()


def _row_cells(line: str) -> list[str]:
    """Split a markdown table row into cells, dropping the empty bookends
    that result from leading/trailing pipes."""
    return [_clean_cell(c) for c in line.strip().strip("|").split("|")]


def load_golden_questions(path: str = DEFAULT_GOLDEN_PATH) -> list[dict[str, str]]:
    """Parse the golden question set markdown into a list of dicts.

    Skips the header row, the separator row, and any non-table lines.
    Each row produces::

        {"id": "Q-001", "category": "EXACT", "question": "...",
         "target_source": "...", "expected_answer": "..."}

    ``target_source`` is the string ``"None"`` (as in the markdown) when
    the question is out-of-corpus; the runner treats that as a no-hit
    question (recall = 0, MRR = 0, nDCG = 0).
    """
    questions: list[dict[str, str]] = []
    p = Path(path)
    if not p.exists():
        return questions

    for raw_line in p.read_text(encoding="utf-8").splitlines():
        if not _TABLE_ROW_RE.match(raw_line):
            continue
        if _SEPARATOR_RE.match(raw_line):
            continue
        cells = _row_cells(raw_line)
        if len(cells) < 5:
            continue
        qid, category, question, target, answer = cells[0], cells[1], cells[2], cells[3], cells[4]
        if not qid.startswith("Q-"):
            continue
        questions.append(
            {
                "id": qid,
                "category": category,
                "question": question,
                "target_source": target,
                "expected_answer": answer,
            }
        )
    return questions


def _is_hit(hit: dict[str, Any], target_source: str) -> bool:
    """True if any metadata value contains the target_source substring."""
    if not target_source or target_source == "None":
        return False
    meta = hit.get("metadata") or {}
    needle = target_source.lower()
    for value in meta.values():
        if value is None:
            continue
        if needle in str(value).lower():
            return True
    return False


def _first_correct_rank(results: list[dict[str, Any]], target_source: str) -> int | None:
    """1-based rank of the first hit; None if not in the list."""
    for rank, hit in enumerate(results, start=1):
        if _is_hit(hit, target_source):
            return rank
    return None


class EvaluationRunner:
    """Runs the golden set through a ``RetrievalPipeline`` and scores it."""

    def __init__(self, pipeline: RetrievalPipeline) -> None:
        self._pipeline = pipeline

    async def evaluate_question(self, question: dict[str, Any]) -> dict[str, Any]:
        """Run one question through the pipeline. Returns a per-question
        result dict with the retrieved ids, scores, correctness, and rank
        of the first correct hit (1-based, or ``None`` if not found).
        """
        workspace_id = question.get("workspace_id")
        if workspace_id is None:
            workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        if not isinstance(workspace_id, uuid.UUID):
            workspace_id = uuid.UUID(str(workspace_id))

        results = await self._pipeline.search(
            question["question"],
            workspace_id,
            top_k=10,
        )
        target = question.get("target_source", "")
        rank = _first_correct_rank(results, target)
        return {
            "question_id": question.get("id", ""),
            "category": question.get("category", ""),
            "expected": question.get("expected_answer", ""),
            "retrieved_ids": [r.get("chunk_id", "") for r in results],
            "retrieved_scores": [float(r.get("score", 0.0)) for r in results],
            "correct": rank is not None,
            "rank": rank,
        }

    async def evaluate_set(self, questions: list[dict[str, Any]]) -> dict[str, Any]:
        """Score the full set. Returns ``{recall_at_10, mrr, ndcg_at_10,
        count, details: [...]}``."""
        details: list[dict[str, Any]] = []
        for q in questions:
            details.append(await self.evaluate_question(q))

        count = len(details)
        if count == 0:
            return {
                "recall_at_10": 0.0,
                "mrr": 0.0,
                "ndcg_at_10": 0.0,
                "count": 0,
                "details": details,
            }

        hits = sum(1 for d in details if d["correct"])
        recall = hits / count

        rr_sum = 0.0
        dcg_sum = 0.0
        for d in details:
            rank = d["rank"]
            if rank is not None:
                rr_sum += 1.0 / rank
                if rank <= 10:
                    dcg_sum += 1.0 / math.log2(rank + 1)

        mrr = rr_sum / count
        # Ideal DCG with one relevant doc at rank 1 is 1 / log2(2) = 1.0.
        ideal_dcg = 1.0
        ndcg = dcg_sum / (count * ideal_dcg)

        return {
            "recall_at_10": recall,
            "mrr": mrr,
            "ndcg_at_10": ndcg,
            "count": count,
            "details": details,
        }


__all__ = [
    "DEFAULT_GOLDEN_PATH",
    "EvaluationRunner",
    "load_golden_questions",
]
