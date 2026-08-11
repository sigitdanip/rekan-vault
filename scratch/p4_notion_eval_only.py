"""P4-NOTION — eval-only (data already ingested)."""
from __future__ import annotations
import asyncio, math, sys, time, uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import logging; logging.disable(logging.CRITICAL)

from apps.api.config import settings
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.retrieval import RetrievalPipeline
from rekanvault.evaluation.runner import EvaluationRunner, _count_targets, _idcg, load_golden_questions
from rekanvault.storage.database import get_db_session, init_db
from rekanvault.storage.qdrant import QdrantStore

NOTION_GOLDEN_PATH = "docs/REKANVAULT_GOLDEN_SET_NOTION.md"

async def main():
    init_db()
    embed = EmbeddingService()
    qdrant = QdrantStore(settings)
    await qdrant.ensure_collection()

    all_qs = load_golden_questions(NOTION_GOLDEN_PATH)
    qs = [q for q in all_qs if q["category"] not in ("NEGATIVE", "INSUFFICIENT")]
    n = len(qs)
    print(f"Running {n}/{len(all_qs)} scorable questions (hybrid + rerank, 1s delay)...")
    print()

    async for session in get_db_session():
        retrieval = RetrievalPipeline(session=session, embed=embed, qdrant=qdrant)
        runner = EvaluationRunner(pipeline=retrieval)
        hits_total, rr_total, dcg_total = 0, 0.0, 0.0
        cats: dict[str, dict[str, int]] = {}
        t0 = time.time()
        for i, qq in enumerate(qs):
            category = qq["category"]
            detail = await runner.evaluate_question(qq, top_k=10)
            ranks = detail["ranks"]
            correct = detail["correct"]
            first_rank = detail["first_rank"]
            cats.setdefault(category, {"t": 0, "h": 0})
            cats[category]["t"] += 1
            if correct is True:
                hits_total += 1
                cats[category]["h"] += 1
            if first_rank is not None:
                rr_total += 1.0 / first_rank
            for r in ranks:
                dcg_total += 1.0 / math.log2(r + 1)
            mark = "HIT" if correct else ("MISS" if correct is False else "N/A")
            print(f"  [{i+1:>2}/{n}] {qq['id']:6s} [{category:12s}] {mark:4s} rank={first_rank}  \"{qq['question'][:70]}\"")
            await asyncio.sleep(1.0)
        elapsed = time.time() - t0
        await session.commit()
        break

    recall = hits_total / n if n else 0.0
    mrr = rr_total / n if n else 0.0
    idcg_sum = sum(_idcg(_count_targets(qq.get("target_source", ""))) for qq in qs)
    ndcg = dcg_total / idcg_sum if idcg_sum > 0 else (1.0 if dcg_total == 0 else 0.0)

    print(f"\n{'='*60}")
    print(f"P4-NOTION EVAL")
    print(f"{'='*60}")
    print(f"Recall@10:      {recall:.4f}")
    print(f"MRR:            {mrr:.4f}")
    print(f"nDCG@10:        {ndcg:.4f}")
    print(f"Hits:           {hits_total}/{n} ({hits_total/n*100:.1f}%)")
    print(f"Eval time:      {elapsed:.0f}s")
    print(f"\nBy category:")
    for cat, c in sorted(cats.items()):
        pct = c["h"] / c["t"] * 100 if c["t"] else 0
        mark = "OK" if pct >= 90 else "~" if pct >= 50 else "X"
        print(f"  {cat:15s}: {c['h']:>3}/{c['t']:<3} ({pct:.0f}%) {mark}")

    await qdrant.close()

if __name__ == "__main__":
    asyncio.run(main())
