"""P4 Combined eval — GDrive + Notion golden sets. Saves every 10 questions."""
import asyncio, json, logging, math, os, sys, time, uuid
logging.disable(50)
os.environ["SQLALCHEMY_WARN_20"] = "false"

from apps.api.config import settings
from rekanvault.storage.database import init_db, get_db_session
from rekanvault.storage.qdrant import QdrantStore
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.retrieval import RetrievalPipeline
from rekanvault.evaluation.runner import (
    _all_correct_ranks, _count_targets, _idcg, _min_required, load_golden_questions,
)

SKIP = frozenset({"NEGATIVE", "INSUFFICIENT"})
GOLDEN_FILES = ["docs/REKANVAULT_GOLDEN_SET.md", "docs/REKANVAULT_GOLDEN_SET_NOTION.md"]
RESULTS = "/tmp/p4_combined_results.json"
BATCH = 10

async def main():
    t0 = time.time()
    embed = EmbeddingService()
    qdrant = QdrantStore(settings)
    ws_id = uuid.UUID(settings.RV_PILOT_WORKSPACE_ID)

    all_qs = []
    for path in GOLDEN_FILES:
        qs = load_golden_questions(path)
        s = [q for q in qs if q["category"] not in SKIP]
        all_qs.extend(s)
        print(f"{path}: {len(s)} scorable", flush=True)
    print(f"Total: {len(all_qs)}\n", flush=True)

    init_db()
    t_eval = time.time()
    async for session in get_db_session():
        rp = RetrievalPipeline(session=session, embed=embed, qdrant=qdrant)
        print("Warmup...", flush=True)
        await rp.search("warmup", ws_id, top_k=3)
        print("Ready.\n", flush=True)

        details = []
        done_ids = set()
        if os.path.exists(RESULTS):
            with open(RESULTS) as f:
                details = json.load(f)
            done_ids = {d["id"] for d in details}
            print(f"Resuming: {len(done_ids)} done\n", flush=True)

        for i, qq in enumerate(all_qs):
            if qq["id"] in done_ids:
                continue
            cat, target = qq["category"], qq.get("target_source", "")
            n_targets = _count_targets(target)
            try:
                results = await rp.search(qq["question"], ws_id, top_k=10)
                ranks = _all_correct_ranks(results, target, max_rank=10, max_hits=n_targets or None)
            except Exception as e:
                print(f"ERR {qq['id']}: {type(e).__name__}", flush=True)
                try: await session.rollback()
                except: pass
                results, ranks = [], []
            required = _min_required(cat, n_targets)
            correct = len(ranks) >= required if n_targets > 0 else None
            first_rank = ranks[0] if ranks else None
            details.append({
                "id": qq["id"], "category": cat, "correct": correct,
                "first_rank": first_rank, "ranks": ranks,
                "n_targets": n_targets, "required": required,
            })
            status = "HIT" if correct is True else ("N/A" if correct is None else "MISS")
            elapsed = time.time() - t_eval
            print(f"[{len(details):3d}/{len(all_qs)}] {qq['id']} {cat:15s} {status:4s} ranks={ranks} ({elapsed:.0f}s)", flush=True)
            await asyncio.sleep(0.3)
            if len(details) % BATCH == 0:
                with open(RESULTS, "w") as f:
                    json.dump(details, f, indent=2)

        with open(RESULTS, "w") as f:
            json.dump(details, f, indent=2)

        n = len(details)
        hits = sum(1 for d in details if d["correct"] is True)
        rr_sum = sum(1.0/d["first_rank"] for d in details if d.get("first_rank"))
        dcg_sum = sum(sum(1.0/math.log2(r+1) for r in d.get("ranks",[])) for d in details)
        idcg_sum = sum(_idcg(d["n_targets"]) for d in details)

        cats = {}
        for d in details:
            c = d["category"]
            cats.setdefault(c, {"t":0,"h":0})
            cats[c]["t"] += 1
            if d["correct"] is True: cats[c]["h"] += 1

        print(f"\n{'='*60}", flush=True)
        print(f"P4 COMBINED EVAL — {n} scorable (GDrive + Notion)", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"Recall@10:  {hits/n:.4f}  (target >= 0.85)", flush=True)
        print(f"MRR:        {rr_sum/n:.4f}", flush=True)
        print(f"nDCG@10:    {dcg_sum/idcg_sum:.4f}" if idcg_sum else "nDCG: N/A", flush=True)
        print(f"Hits:       {hits}/{n} ({hits/n*100:.1f}%)", flush=True)
        print(f"Eval time:  {elapsed:.0f}s | Total: {time.time()-t0:.0f}s", flush=True)
        print(f"\nBy category:", flush=True)
        for cat_name in sorted(cats):
            c = cats[cat_name]
            pct = c["h"]/c["t"]*100 if c["t"] else 0
            mark = "✓" if pct >= 90 else "~" if pct >= 50 else "✗"
            print(f"  {cat_name:15s}: {c['h']:>3}/{c['t']:<3} ({pct:.0f}%) {mark}", flush=True)
        await session.commit(); break
    await qdrant.close()

asyncio.run(main())
