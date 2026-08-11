"""P4-GATE full hybrid eval — batch runner with progress save to /tmp/p4_batch_results.json.

Runs the full hybrid pipeline (lexical + dense + RRF + rerank) across the
golden set.  NEGATIVE / INSUFFICIENT questions are skipped — they always
pass and would only drag down the real retrieval metrics.

Saves per-question results after every batch so a crash or thermal
shutdown doesn't lose progress.  Resume by re-running the script.
"""

import asyncio
import gc
import json
import math
import os
import time
import uuid

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.config import settings
from rekanvault.evaluation.runner import (
    _all_correct_ranks,
    _count_targets,
    _idcg,
    _min_required,
    load_golden_questions,
)
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.retrieval import RetrievalPipeline
from rekanvault.storage.qdrant import QdrantStore

RESULTS_FILE = "/tmp/p4_batch_results.json"
BATCH_SIZE = 15
COOLDOWN_SECONDS = 5

SKIP_CATEGORIES: frozenset[str] = frozenset({"NEGATIVE", "INSUFFICIENT"})


def _migrate_detail(d: dict) -> dict:
    """Upgrade old-format detail dicts (``rank``, ``correct`` as bool)
    to the current schema (``first_rank``, ``ranks``, ``n_targets``,
    ``required``, ``correct`` as bool|None).

    Old format couldn't distinguish "missed" from "NEGATIVE" (both had
    ``correct=False``).  We detect SKIP_CATEGORIES entries by checking
    whether the category is in the skip set — those get ``correct=None``;
    genuine misses stay ``correct=False``.
    """
    if "first_rank" in d:
        return d  # already current format
    old_rank = d.get("rank")
    old_correct = d.get("correct", False)
    cat = d.get("category", "")
    if cat in SKIP_CATEGORIES:
        correct = None
    else:
        correct = bool(old_correct) and old_rank is not None
    return {
        "id": d["id"],
        "category": cat,
        "question": d.get("question", ""),
        "correct": correct,
        "first_rank": old_rank,
        "ranks": [old_rank] if old_rank else [],
        "n_targets": 0 if cat in SKIP_CATEGORIES else 1,
        "required": 0 if cat in SKIP_CATEGORIES else 1,
    }


async def main() -> None:
    # Load or init results — migrate old format if needed.
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            state = json.load(f)
        state["details"] = [_migrate_detail(d) for d in state["details"]]
        done_ids = {d["id"] for d in state["details"]}
        print(f"Resuming: {len(done_ids)} already done")
    else:
        state: dict = {"details": [], "batches_completed": 0}
        done_ids = set()

    # Module-level singletons — embed loaded once, qdrant client shared.
    embed = EmbeddingService()
    qdrant = QdrantStore(settings)
    ws_id = uuid.UUID(settings.RV_PILOT_WORKSPACE_ID)

    all_qs = load_golden_questions("docs/REKANVAULT_GOLDEN_SET.md")
    scorable_qs = [q for q in all_qs if q["category"] not in SKIP_CATEGORIES]
    remaining = [q for q in scorable_qs if q["id"] not in done_ids]

    if not remaining and done_ids:
        print("All done! Computing final scores...")
        _print_final(state["details"])
        await qdrant.close()
        return

    print(f"Golden set: {len(all_qs)} total, {len(scorable_qs)} scorable "
          f"(skipped {len(all_qs) - len(scorable_qs)} negative/insufficient)")
    print(f"Remaining: {len(remaining)} questions")

    engine = create_async_engine(settings.RV_DATABASE_URL, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        rp = RetrievalPipeline(session=session, embed=embed, qdrant=qdrant)

        print("Warmup...")
        await rp.search("test", ws_id, top_k=3)
        print("Ready.\n")

        batch_num = state["batches_completed"]
        while remaining:
            batch = remaining[:BATCH_SIZE]
            remaining = remaining[BATCH_SIZE:]
            batch_num += 1
            t0 = time.time()
            print(f"\n=== BATCH {batch_num}: {len(batch)} questions ===", flush=True)

            for i, qq in enumerate(batch):
                qid, cat, qtext = qq["id"], qq["category"], qq["question"]
                target = qq.get("target_source", "")
                n_targets = _count_targets(target)
                try:
                    results = await rp.search(qtext, ws_id, top_k=10)
                except Exception:
                    try:
                        await session.rollback()
                    except PendingRollbackError:
                        pass
                    await asyncio.sleep(1)
                    results = await rp.search(qtext, ws_id, top_k=10)
                try:
                    ranks = _all_correct_ranks(results, target, max_rank=10)
                except Exception as e:
                    print(f"  {qid} ERROR: {e}", flush=True)
                    ranks = []
                required = _min_required(cat, n_targets)
                correct = len(ranks) >= required if n_targets > 0 else None
                first_rank = ranks[0] if ranks else None
                state["details"].append(
                    {
                        "id": qid,
                        "category": cat,
                        "question": qtext[:60],
                        "correct": correct,
                        "first_rank": first_rank,
                        "ranks": ranks,
                        "n_targets": n_targets,
                        "required": required,
                    }
                )
                status = "HIT" if correct is True else ("N/A" if correct is None else "MISS")
                print(f"  {qid} {cat:15s} {status:4s} ranks={ranks}  "
                      f"{i + 1}/{len(batch)}", flush=True)

            batch_time = time.time() - t0
            state["batches_completed"] = batch_num
            with open(RESULTS_FILE, "w") as f:
                json.dump(state, f, indent=2)
            print(f"  Batch {batch_num} done in {batch_time / 60:.0f}m. Saved.", flush=True)

            _print_running(state["details"])

            await asyncio.sleep(COOLDOWN_SECONDS)

            # Release CPU model memory between batches so the reranker
            # doesn't accumulate and cause thermal throttling.
            gc.collect()

    _print_final(state["details"])
    await qdrant.close()
    await engine.dispose()


def _print_running(details: list[dict]) -> None:
    """Inline score display after each batch."""
    scorable = [d for d in details if d.get("n_targets", 0) > 0]
    n = len(scorable)
    if n == 0:
        return
    hits, rr_sum, dcg_sum, idcg_sum = _compute_metrics(details)
    recall = hits / n if n else 0.0
    ndcg = dcg_sum / idcg_sum if idcg_sum > 0 else (1.0 if dcg_sum == 0 else 0.0)
    print(f"  Running: R@10={recall:.3f} MRR={rr_sum / n:.3f} "
          f"nDCG={ndcg:.3f} ({hits}/{n})", flush=True)


def _print_final(details: list[dict]) -> None:
    """Final score report — all categories, scorable-only metrics."""
    scorable = [d for d in details if d.get("n_targets", 0) > 0]
    n = len(scorable)
    if n == 0:
        return
    hits, rr_sum, dcg_sum, idcg_sum = _compute_metrics(details)
    recall = hits / n if n else 0.0
    ndcg = dcg_sum / idcg_sum if idcg_sum > 0 else (1.0 if dcg_sum == 0 else 0.0)

    cats: dict[str, dict[str, int]] = {}
    for d in details:
        cat = d["category"]
        cats.setdefault(cat, {"t": 0, "h": 0})
        cats[cat]["t"] += 1
        if d["correct"] is True:
            cats[cat]["h"] += 1

    print(f"\n{'=' * 60}")
    print(f"FULL HYBRID P4-GATE — {n} scorable questions")
    print(f"{'=' * 60}")
    print(f"Recall@10:  {recall:.4f}  (target >= 0.85)")
    print(f"MRR:        {rr_sum / n:.4f}")
    print(f"nDCG@10:    {ndcg:.4f}")
    print(f"Hits:       {hits}/{n} ({hits / n * 100:.1f}%)")
    for cat_name in sorted(cats):
        c = cats[cat_name]
        pct = c["h"] / c["t"] * 100 if c["t"] else 0
        mark = "✓" if pct >= 90 else "~" if pct >= 50 else "✗"
        print(f"  {cat_name:15s}: {c['h']:>3}/{c['t']:<3} ({pct:.0f}%) {mark}")


def _compute_metrics(details: list[dict]) -> tuple[int, float, float, float]:
    """Return (hits, rr_sum, dcg_sum, idcg_sum) over scorable details only."""
    scorable = [d for d in details if d.get("n_targets", 0) > 0]
    n = len(scorable)
    hits = sum(1 for d in scorable if d["correct"] is True)
    rr_sum = sum(1.0 / d["first_rank"] for d in scorable if d.get("first_rank"))
    dcg_sum = sum(
        sum(1.0 / math.log2(r + 1) for r in d.get("ranks", [])) for d in scorable
    )
    idcg_sum = sum(_idcg(d.get("n_targets", 0)) for d in scorable) if n > 0 else 1.0
    return hits, rr_sum, dcg_sum, idcg_sum


if __name__ == "__main__":
    asyncio.run(main())
