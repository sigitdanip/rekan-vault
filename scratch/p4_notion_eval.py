"""P4-NOTION — Full pipeline Notion eval (Postgres + Qdrant).

Ingest the Sulaiman OS Notion workspace through the full pipeline
(upsert_document → IndexingPipeline → Qdrant), then run the Notion
golden question set through RetrievalPipeline.

Usage:  python scratch/p4_notion_eval.py
"""

from __future__ import annotations

import asyncio
import math as _math
import sys
import time
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import httpx
from apps.api.config import settings
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.indexing import IndexingPipeline
from rekanvault.evidence.chunker import Chunker
from rekanvault.evidence.retrieval import RetrievalPipeline
from rekanvault.evaluation.runner import (
    EvaluationRunner,
    _count_targets,
    _idcg,
    load_golden_questions,
)
from rekanvault.sources.notion import NotionConnector
from rekanvault.storage.database import get_db_session, init_db
from rekanvault.storage.document_repo import DocumentRepository
from rekanvault.storage.models import Source
from rekanvault.storage.qdrant import QdrantStore

NOTION_GOLDEN_PATH = "docs/REKANVAULT_GOLDEN_SET_NOTION.md"


async def main() -> None:
    import logging
    logging.disable(logging.CRITICAL)

    t_start = time.time()
    init_db()
    embed = EmbeddingService()
    qdrant = QdrantStore(settings)

    # Drop and recreate for clean Notion-only eval
    if await qdrant.client.collection_exists(settings.RV_QDRANT_COLLECTION):
        await qdrant.client.delete_collection(settings.RV_QDRANT_COLLECTION)
    await qdrant.ensure_collection()

    doc_repo = DocumentRepository()
    chunker = Chunker(repo=doc_repo)
    ws_id = uuid.UUID(settings.RV_PILOT_WORKSPACE_ID)
    src_id = uuid.UUID(settings.RV_PILOT_NOTION_SOURCE_ID)

    # ── Stage 1: Scan Notion ──
    print("=== STAGE 1: Notion Scan ===")
    token = settings.RV_NOTION_TOKEN
    page_id = settings.RV_NOTION_PAGE_ID
    if not token or not page_id:
        print("ERROR: RV_NOTION_TOKEN and RV_NOTION_PAGE_ID required")
        sys.exit(1)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.RV_NOTION_API_TIMEOUT_SECONDS)
    ) as client:
        connector = NotionConnector(
            source_id=str(src_id),
            config={"root_page_id": page_id},
            client=client,
            token=token,
        )
        documents = await connector.scan()

    print(f"Found {len(documents)} Notion pages/databases")

    # ── Stage 2: Postgres → Chunk → Embed → Qdrant ──
    print(f"\n=== STAGE 2: Postgres → Chunk → Embed → Qdrant ===")
    total_chunks = 0
    async for session in get_db_session():
        from sqlalchemy import select as _select
        existing = (await session.execute(
            _select(Source).where(Source.id == src_id)
        )).scalar_one_or_none()
        if existing is None:
            session.add(Source(
                id=src_id, workspace_id=ws_id,
                provider="notion", name="Pilot Notion",
                config={"root_page_id": page_id},
                status="active",
            ))
            await session.flush()

        for i, doc in enumerate(documents):
            db_doc = await doc_repo.upsert_document(session, ws_id, src_id, doc)
            dv = await doc_repo.get_latest_version(session, db_doc.id)
            if dv is None:
                continue
            await session.commit()

            pipeline = IndexingPipeline(
                session=session,
                chunker=chunker,
                embed=embed,
                qdrant=qdrant,
                doc_repo=doc_repo,
            )
            n = await pipeline.index_version(dv.id)
            total_chunks += n
            await session.commit()
            if (i + 1) % 20 == 0 or i == 0:
                print(f"  [{i+1}/{len(documents)}] {doc.title[:60]} → {n} chunks")

        await session.commit()
        break

    sync_elapsed = time.time() - t_start
    print(f"\nIndexed {total_chunks} chunks from {len(documents)} docs ({sync_elapsed:.0f}s)")

    if total_chunks == 0:
        print("No chunks — aborting eval.")
        await qdrant.close()
        return

    # ── Stage 3: Verify Postgres ──
    async for session in get_db_session():
        from sqlalchemy import text
        r = await session.execute(text("SELECT count(*) FROM content_blocks"))
        cb_count = r.scalar()
        print(f"ContentBlocks in Postgres: {cb_count}")
        await session.commit()
        break

    # ── Stage 4: Evaluate ──
    print(f"\n=== STAGE 4: Notion Golden Set Evaluation ===")
    all_qs = load_golden_questions(NOTION_GOLDEN_PATH)
    qs = [q for q in all_qs if q["category"] not in ("NEGATIVE", "INSUFFICIENT")]
    print(f"Running {len(qs)}/{len(all_qs)} scorable questions (full hybrid, 1s delay)...")

    async for session in get_db_session():
        retrieval = RetrievalPipeline(session=session, embed=embed, qdrant=qdrant)
        runner = EvaluationRunner(pipeline=retrieval)

        details: list[dict] = []
        cats: dict[str, dict[str, int]] = {}
        t0 = time.time()
        for i, qq in enumerate(qs):
            category = qq["category"]
            target = qq.get("target_source", "")
            n_targets = _count_targets(target)
            try:
                detail = await runner.evaluate_question(qq, top_k=10)
                ranks = detail["ranks"]
                correct = detail["correct"]
                first_rank = detail["first_rank"]
            except Exception:
                ranks, correct, first_rank, n_targets = [], None, None, 0
            cats.setdefault(category, {"t": 0, "h": 0})
            cats[category]["t"] += 1
            if correct is True:
                cats[category]["h"] += 1
            details.append({
                "id": qq["id"], "category": category, "correct": correct,
                "first_rank": first_rank, "ranks": ranks,
                "n_targets": n_targets,
            })
            status = "HIT" if correct is True else ("N/A" if correct is None else "MISS")
            if (i + 1) % 10 == 0 or i < 5:
                print(f"  [{i+1:3d}/{len(qs)}] {qq['id']} {category:15s} {status:4s} ranks={ranks} ({time.time()-t0:.0f}s)")
            await asyncio.sleep(1.0)
        elapsed = time.time() - t0
        await session.commit()
        break

    n = len(details)
    hits = sum(1 for d in details if d["correct"] is True)
    rr_sum = sum(1.0 / d["first_rank"] for d in details if d.get("first_rank"))
    dcg_sum = sum(sum(1.0 / _math.log2(r + 1) for r in d.get("ranks", [])) for d in details)
    idcg_sum = sum(_idcg(d["n_targets"]) for d in details)
    recall = hits / n if n else 0.0
    mrr = rr_sum / n if n else 0.0
    ndcg = dcg_sum / idcg_sum if idcg_sum > 0 else 0.0

    print(f"\n{'='*60}")
    print(f"P4-NOTION EVAL — {n} scorable questions")
    print(f"{'='*60}")
    print(f"Recall@10:      {recall:.4f}")
    print(f"MRR:            {mrr:.4f}")
    print(f"nDCG@10:        {ndcg:.4f}")
    print(f"Hits:           {hits}/{n} ({hits/n*100:.1f}%)" if n else "Hits: N/A")
    print(f"Scan+Index:     {sync_elapsed:.0f}s")
    print(f"Eval time:      {elapsed:.0f}s")
    print(f"Total:          {time.time()-t_start:.0f}s")
    print(f"\nBy category:")
    for cat_name in sorted(cats):
        c = cats[cat_name]
        pct = c["h"] / c["t"] * 100 if c["t"] else 0
        mark = "✓" if pct >= 90 else "~" if pct >= 50 else "✗"
        print(f"  {cat_name:15s}: {c['h']:>3}/{c['t']:<3} ({pct:.0f}%) {mark}")

    await qdrant.close()


if __name__ == "__main__":
    asyncio.run(main())
