"""Inline eval runner — indexes then evaluates 144 scorable questions
with full hybrid pipeline.  Saves per-question results every 5 questions
to /tmp/p4_eval_results.json."""

import asyncio
import json
import logging
import math
import os
import sys
import time
import uuid

logging.disable(logging.CRITICAL)
os.environ["SQLALCHEMY_WARN_20"] = "false"

from apps.api.config import settings
from rekanvault.storage.database import init_db, get_db_session
from rekanvault.storage.qdrant import QdrantStore
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.retrieval import RetrievalPipeline
from rekanvault.evaluation.runner import (
    _all_correct_ranks,
    _count_targets,
    _idcg,
    _min_required,
    load_golden_questions,
)

SKIP = frozenset({"NEGATIVE", "INSUFFICIENT"})
RESULTS = "/tmp/p4_eval_results.json"
BATCH = 5


async def run() -> None:
    t0 = time.time()

    embed = EmbeddingService()
    qdrant = QdrantStore(settings)
    ws_id = uuid.UUID(settings.RV_PILOT_WORKSPACE_ID)
    print("Models loaded.", flush=True)

    all_qs = load_golden_questions("docs/REKANVAULT_GOLDEN_SET.md")
    qs = [q for q in all_qs if q["category"] not in SKIP]
    print(f"Questions: {len(qs)} scorable", flush=True)

    init_db()
    async for session in get_db_session():
        rp = RetrievalPipeline(session=session, embed=embed, qdrant=qdrant)
        print("Warmup...", flush=True)
        await rp.search("warmup", ws_id, top_k=3)
        print("Warmup done.\n", flush=True)

        details: list[dict] = []
        for i, qq in enumerate(qs):
            cat = qq["category"]
            target = qq.get("target_source", "")
            n_targets = _count_targets(target)
            try:
                results = await rp.search(qq["question"], ws_id, top_k=10)
                ranks = _all_correct_ranks(results, target, max_rank=10, max_hits=n_targets or None)
            except Exception as e:
                print(f"ERR {qq['id']}: {e}", flush=True)
                results = []
                ranks = []
            required = _min_required(cat, n_targets)
            correct = len(ranks) >= required if n_targets > 0 else None
            first_rank = ranks[0] if ranks else None
            details.append(
                {
                    "id": qq["id"],
                    "category": cat,
                    "correct": correct,
                    "first_rank": first_rank,
                    "ranks": ranks,
                    "n_targets": n_targets,
                    "required": required,
                }
            )
            status = (
                "HIT"
                if correct is True
                else ("N/A" if correct is None else "MISS")
            )
            elapsed = time.time() - t0
            print(
                f"[{i + 1:3d}/{len(qs)}] {qq['id']} {cat:15s} {status:4s} "
                f"ranks={ranks} ({elapsed:.0f}s)",
                flush=True,
            )
            if (i + 1) % BATCH == 0:
                with open(RESULTS, "w") as f:
                    json.dump(details, f, indent=2)

        # Final save + report
        with open(RESULTS, "w") as f:
            json.dump(details, f, indent=2)

        n = len(details)
        hits = sum(1 for d in details if d["correct"] is True)
        rr_sum = sum(1.0 / d["first_rank"] for d in details if d.get("first_rank"))
        dcg_sum = sum(
            sum(1.0 / math.log2(r + 1) for r in d["ranks"]) for d in details
        )
        idcg_sum = sum(_idcg(d["n_targets"]) for d in details)
        recall = hits / n if n else 0.0
        mrr = rr_sum / n if n else 0.0
        ndcg = (
            dcg_sum / idcg_sum
            if idcg_sum > 0
            else (1.0 if dcg_sum == 0 else 0.0)
        )

        cats: dict[str, dict[str, int]] = {}
        for d in details:
            c = d["category"]
            cats.setdefault(c, {"t": 0, "h": 0})
            cats[c]["t"] += 1
            if d["correct"] is True:
                cats[c]["h"] += 1

        print(f"\n{'=' * 60}", flush=True)
        print(f"FULL HYBRID P4-GATE — {n} scorable", flush=True)
        print(f"{'=' * 60}", flush=True)
        print(f"Recall@10:  {recall:.4f}  (target >= 0.85)", flush=True)
        print(f"MRR:        {mrr:.4f}", flush=True)
        print(f"nDCG@10:    {ndcg:.4f}", flush=True)
        print(f"Hits:       {hits}/{n} ({hits / n * 100:.1f}%)", flush=True)
        print(f"Total time: {time.time() - t0:.0f}s", flush=True)
        print("\nBy category:", flush=True)
        for cat_name in sorted(cats):
            c = cats[cat_name]
            pct = c["h"] / c["t"] * 100 if c["t"] else 0
            mark = "✓" if pct >= 90 else "~" if pct >= 50 else "✗"
            print(
                f"  {cat_name:15s}: {c['h']:>3}/{c['t']:<3} ({pct:.0f}%) {mark}",
                flush=True,
            )

        await session.commit()
        break
    await qdrant.close()


if __name__ == "__main__":
    asyncio.run(run())
