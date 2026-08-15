"""
Golden-set evaluation runner for the retrieval pipeline (P4-T7 / ``RV-DEC-0015``).

Scores a set of questions against the hybrid ``RetrievalPipeline`` and
computes three retrieval metrics:

* **Recall@10** — fraction of questions whose expected target document
  appears in the top 10 retrieved chunks.  For multi-target questions
  (SYNTHESIS, MULTIHOP) the question is correct only when the required
  minimum number of distinct targets are matched.
* **MRR** — mean of ``1 / rank`` for the first correct result (0 if
  not found).  For multi-target questions the first hit's rank is used.
* **nDCG@10** — per-question ``DCG / IDCG`` where IDCG is computed from
  the actual number of relevant targets (not hardcoded to 1.0).

A hit is defined as any retrieved chunk whose ``metadata`` contains the
expected ``target_source`` path string (substring / fnmatch across metadata
values, since the exact field name varies between lexical and dense
retrievers).
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch as _fnmatch
import math
import re
import uuid
from pathlib import Path
from typing import Any

from rekanvault.evidence.retrieval import RetrievalPipeline

DEFAULT_GOLDEN_PATH = "docs/REKANVAULT_GOLDEN_SET.md"
DEFAULT_TOP_K = 10

_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEPARATOR_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")

# Categories that must match ALL cited targets to count as correct.
_ALL_TARGET_CATEGORIES: frozenset[str] = frozenset({"MULTIHOP"})

# Categories that must match at least ceil(N/2) of N targets.
_HALF_TARGET_CATEGORIES: frozenset[str] = frozenset({"SYNTHESIS"})


def _clean_cell(cell: str) -> str:
    s = cell.strip()
    if s.startswith("`") and s.endswith("`"):
        s = s[1:-1]
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    return s.strip()


def _row_cells(line: str) -> list[str]:
    return [_clean_cell(c) for c in line.strip().strip("|").split("|")]


def load_golden_questions(path: str = DEFAULT_GOLDEN_PATH) -> list[dict[str, str]]:
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
        if not (qid.startswith("Q-") or qid.startswith("NQ-")):
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


# ---- hit detection ---------------------------------------------------------


def _split_targets(target_source: str) -> list[str]:
    """Split a multi-target cell on ``&``, ``,``, ``;`` delimiters."""
    return [t.strip().strip("`").lower() for t in re.split(r"\s*[&;,]\s*", target_source) if t.strip()]


def _is_hit(hit: dict[str, Any], target_source: str) -> bool:
    """True if any metadata value matches any of the target paths.

    Matches via:
    - **fnmatch** for wildcard patterns (``*``, ``?``), with substring
      fallback on the static portion when fnmatch alone fails.
    - **substring** match in both directions (target in metadata OR
      metadata in target), plus bare-filename match.
    """
    if not target_source or target_source == "None":
        return False
    meta = hit.get("metadata") or {}
    if isinstance(meta, dict):
        meta_strings = [
            str(v).lower()
            for k, v in meta.items()
            if v is not None
        ]
    else:
        meta_strings = [str(meta).lower()]

    for target_str in _split_targets(target_source):
        target_filename = target_str.split("/")[-1]
        has_wildcard = "*" in target_str or "?" in target_str
        for m in meta_strings:
            if has_wildcard:
                if _fnmatch.fnmatch(m, target_str) or _fnmatch.fnmatch(target_str, m):
                    return True
                # Fallback: substring-match the static portions of the
                # wildcard (e.g. "/README.txt" from "*/README.txt").
                static_parts = [p for p in target_str.split("*") if p and len(p) > 2]
                if any(p in m for p in static_parts):
                    return True
            elif target_str in m or target_filename in m or m in target_str:
                return True
    return False


def _first_correct_rank(
    results: list[dict[str, Any]],
    target_source: str,
    *,
    max_rank: int = DEFAULT_TOP_K,
) -> int | None:
    """1-based rank of the first hit, or None if no hit in top ``max_rank``."""
    for rank, hit in enumerate(results, start=1):
        if rank > max_rank:
            break
        if _is_hit(hit, target_source):
            return rank
    return None


def _all_correct_ranks(
    results: list[dict[str, Any]],
    target_source: str,
    *,
    max_rank: int = DEFAULT_TOP_K,
    max_hits: int | None = None,
) -> list[int]:
    """All 1-based ranks (ascending) where a hit was found, capped at
    ``max_rank`` and (when set) ``max_hits`` distinct documents."""
    ranks: list[int] = []
    seen: set[str] = set()
    for rank, hit in enumerate(results, start=1):
        if rank > max_rank:
            break
        if max_hits is not None and len(ranks) >= max_hits:
            break
        if _is_hit(hit, target_source):
            doc_id = str(hit.get("document_id", ""))
            if doc_id not in seen:
                ranks.append(rank)
                seen.add(doc_id)
    return ranks


# ---- per-category correctness ----------------------------------------------


def _count_targets(target_source: str) -> int:
    """Number of distinct target paths in a target_source string."""
    if not target_source or target_source == "None":
        return 0
    return len(_split_targets(target_source))


def _min_required(category: str, n_targets: int) -> int:
    """Minimum distinct target matches required for the question to be
    considered correct, given ``n_targets`` total targets."""
    if n_targets == 0:
        return 0  # NEGATIVE / INSUFFICIENT — never correct by hit
    if category in _ALL_TARGET_CATEGORIES:
        return n_targets
    if category in _HALF_TARGET_CATEGORIES:
        return max(1, (n_targets + 1) // 2)  # ceil(n/2)
    return 1  # default: any single target match


# ---- scoring ---------------------------------------------------------------


def _idcg(n_targets: int) -> float:
    """Ideal DCG for ``n_targets`` relevant documents at ranks 1..n."""
    if n_targets == 0:
        return 0.0
    return sum(1.0 / math.log2(i + 1) for i in range(1, n_targets + 1))


# ---- runner ----------------------------------------------------------------


class EvaluationRunner:
    """Runs the golden set through a ``RetrievalPipeline`` and scores it."""

    def __init__(self, pipeline: RetrievalPipeline) -> None:
        self._pipeline = pipeline

    async def evaluate_question(
        self,
        question: dict[str, Any],
        *,
        top_k: int = DEFAULT_TOP_K,
        ablate_title_hacks: bool = False,
    ) -> dict[str, Any]:
        workspace_id = question.get("workspace_id")
        if workspace_id is None:
            workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000001")  # pilot default
        if not isinstance(workspace_id, uuid.UUID):
            workspace_id = uuid.UUID(str(workspace_id))

        results = await self._pipeline.search(
            question["question"],
            workspace_id,
            top_k=top_k,
            ablate_title_hacks=ablate_title_hacks,
        )
        target = question.get("target_source", "")
        category = question.get("category", "")

        n_targets = _count_targets(target)
        ranks = _all_correct_ranks(results, target, max_rank=top_k, max_hits=n_targets or None)
        required = _min_required(category, n_targets)
        correct = len(ranks) >= required if n_targets > 0 else None
        first_rank = ranks[0] if ranks else None

        return {
            "question_id": question.get("id", ""),
            "category": category,
            "expected": question.get("expected_answer", ""),
            "retrieved_ids": [r.get("chunk_id", "") for r in results],
            "retrieved_scores": [float(r.get("score", 0.0)) for r in results],
            "correct": correct,  # None for NEGATIVE/INSUFFICIENT
            "first_rank": first_rank,
            "ranks": ranks,
            "n_targets": n_targets,
            "required": required,
            "retrieved_source_types": [r.get("metadata", {}).get("source_type", "unknown") for r in results],
        }

    async def evaluate_set(
        self,
        questions: list[dict[str, Any]],
        *,
        top_k: int = DEFAULT_TOP_K,
        ablate_title_hacks: bool = False,
    ) -> dict[str, Any]:
        details: list[dict[str, Any]] = []
        for q in questions:
            details.append(await self.evaluate_question(q, top_k=top_k, ablate_title_hacks=ablate_title_hacks))

        count = len(details)
        if count == 0:
            return {
                "recall_at_10": 0.0,
                "mrr": 0.0,
                "ndcg_at_10": 0.0,
                "count": 0,
                "category_breakdown": {},
                "details": details,
            }

        scorable = [d for d in details if d["n_targets"] > 0]
        scorable_count = len(scorable)

        hits = sum(1 for d in scorable if d["correct"] is True)
        recall = hits / scorable_count if scorable_count else 0.0

        category_breakdown: dict[str, dict[str, int]] = {}
        for d in scorable:
            cat = d.get("category", "") or "UNCATEGORIZED"
            entry = category_breakdown.setdefault(cat, {"hits": 0, "total": 0})
            entry["total"] += 1
            if d["correct"] is True:
                entry["hits"] += 1

        rr_sum = 0.0
        dcg_sum = 0.0
        idcg_sum = 0.0
        for d in details:
            first_rank = d["first_rank"]
            if first_rank is not None:
                rr_sum += 1.0 / first_rank
            question_dcg = sum(1.0 / math.log2(r + 1) for r in d["ranks"])
            dcg_sum += question_dcg
            idcg_sum += _idcg(d["n_targets"])

        mrr = rr_sum / count
        if idcg_sum > 0:
            ndcg = dcg_sum / idcg_sum
        elif dcg_sum == 0:
            ndcg = 1.0  # no relevant docs in the set → perfect
        else:
            ndcg = 0.0

        source_type_counts: dict[str, int] = {}
        for d in details:
            for st in d.get("retrieved_source_types", []):
                source_type_counts[st] = source_type_counts.get(st, 0) + 1

        return {
            "recall_at_10": recall,
            "mrr": mrr,
            "ndcg_at_10": ndcg,
            "count": count,
            "scorable_count": scorable_count,
            "source_type_counts": source_type_counts,
            "category_breakdown": category_breakdown,
            "details": details,
        }


__all__ = [
    "DEFAULT_GOLDEN_PATH",
    "DEFAULT_TOP_K",
    "EvaluationRunner",
    "_all_correct_ranks",
    "_first_correct_rank",
    "_is_hit",
    "_min_required",
    "load_golden_questions",
]


# ---- CLI entry point -------------------------------------------------------


async def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="RekanVault evaluation runner")
    parser.add_argument(
        "--golden-path",
        default=DEFAULT_GOLDEN_PATH,
        help=f"Path to golden-set markdown (default: {DEFAULT_GOLDEN_PATH})",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Top-K for retrieval")
    args = parser.parse_args()

    questions = load_golden_questions(args.golden_path)
    if not questions:
        print(f"No questions found in {args.golden_path}")
        return

    print(f"Loaded {len(questions)} questions from {args.golden_path}")

    # Lazy imports — only needed for CLI, not library callers.
    import logging
    import os

    logging.disable(logging.CRITICAL)
    os.environ.setdefault("SQLALCHEMY_WARN_20", "false")

    from apps.api.config import settings
    from rekanvault.evidence.embedding import EmbeddingService
    from rekanvault.evidence.retrieval import RetrievalPipeline
    from rekanvault.storage.database import get_db_session, init_db
    from rekanvault.storage.qdrant import QdrantStore

    embed = EmbeddingService()
    qdrant = QdrantStore(settings)
    init_db()

    async for session in get_db_session():
        pipeline = RetrievalPipeline(session=session, embed=embed, qdrant=qdrant)
        runner = EvaluationRunner(pipeline)
        ablate_title_hacks = os.environ.get("RV_ABLATE_TITLE_HACKS", "").strip().lower() in ("1", "true", "yes", "on")
        result = await runner.evaluate_set(questions, top_k=args.top_k, ablate_title_hacks=ablate_title_hacks)

        print(f"\n{'='*60}")
        print(f"Results — {result['count']} questions")
        print(f"{'='*60}")
        print(f"Recall@10:  {result['recall_at_10']:.4f}")
        print(f"MRR:        {result['mrr']:.4f}")
        print(f"nDCG@10:    {result['ndcg_at_10']:.4f}")

        cb = result.get("category_breakdown", {})
        if cb:
            print("\nPer-category Recall@10:")
            for cat in sorted(cb):
                entry = cb[cat]
                total = entry["total"]
                hits = entry["hits"]
                rate = hits / total if total else 0.0
                print(f"  {cat}: {hits}/{total} ({rate:.0%})")

        stc = result.get("source_type_counts", {})
        if stc:
            print("\nSource type breakdown:")
            for st, cnt in sorted(stc.items(), key=lambda x: -x[1]):
                print(f"  {st or 'unknown':20s}: {cnt}")
        break

    await qdrant.close()


if __name__ == "__main__":
    asyncio.run(_run_cli())
