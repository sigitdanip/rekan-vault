"""
P4 retrieval pipeline (SDLC §9 — parallel retrieval + RRF + rerank + dedup).

Combines two retrieval signals and returns one ranked, deduplicated list of
evidence dicts:

* **Lexical** — PostgreSQL ``tsvector`` / ``ts_rank`` over ``content_blocks``
  via ``websearch_to_tsquery('simple', query)``; ``unaccent`` is applied to
  the query at the SQL level for diacritic-insensitive matching.
* **Dense** — Qdrant ``AsyncQdrantClient.query_points`` over the locked
  named "dense" vector.

Results are merged with Reciprocal Rank Fusion (``k=60``), reranked by the
local cross-encoder, then deduplicated by block-range overlap within a
single document.

ponytail: one class, explicit DI, no strategy/factory. The RRF + dedup math
is short and stable — keeping it as pure functions so it is easy to test
without spinning up Postgres or Qdrant.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from qdrant_client.http import models as qmodels
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.storage.qdrant import DenseVectorName, QdrantStore

# --- RRF constants (SDLC §9) ---------------------------------------------

RRF_K: int = 60  # standard RRF smoothing constant; tune per golden-set eval

# Lexical / dense recall fan-out. We over-fetch so the reranker has head
# room and dedup has something to remove.
LEXICAL_FANOUT_MULTIPLIER: int = 2
DENSE_FANOUT_MULTIPLIER: int = 2
RRF_FANOUT_MULTIPLIER: int = 3  # RRF output goes to the reranker

# SQL: tsvector lexical search over active documents in a workspace.
# Matches the GENERATED ``content_tsvector`` column from migration 0002
# (``to_tsvector('simple', content_text)``). ``unaccent`` wraps the query
# for diacritic-insensitive matching.
_LEXICAL_SQL = text(
    """
    SELECT
        cb.id              AS block_id,
        cb.content_text    AS content_text,
        cb.block_index     AS block_index,
        cb.block_type      AS block_type,
        cb.metadata        AS block_metadata,
        cb.document_version_id AS document_version_id,
        cb.workspace_id    AS workspace_id,
        dv.version_number  AS version_number,
        dv.id              AS version_id,
        d.id               AS document_id,
        d.external_id      AS external_id,
        ts_rank(
            cb.content_tsvector,
            websearch_to_tsquery(
                'simple',
                unaccent(:query)
            )
        ) AS rank
    FROM content_blocks cb
    JOIN document_versions dv ON cb.document_version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    WHERE d.workspace_id = :workspace_id
      AND d.status = 'active'
      AND cb.content_tsvector @@ websearch_to_tsquery(
            'simple',
            unaccent(:query)
        )
    ORDER BY rank DESC
    LIMIT :limit
    """
)


class RetrievalPipeline:
    """Hybrid retriever: lexical + dense → RRF → rerank → dedup.

    Constructor takes the three collaborators explicitly; no global state.
    Lifecycle of the underlying clients (DB engine, Qdrant) is the caller's
    problem — this class holds references and uses them per-call.
    """

    def __init__(
        self,
        session: AsyncSession,
        embed: EmbeddingService,
        qdrant: QdrantStore,
    ) -> None:
        self._session = session
        self._embed = embed
        self._qdrant = qdrant

    # ---- public API -------------------------------------------------------

    async def search(
        self,
        query: str,
        workspace_id: uuid.UUID,
        top_k: int = 20,
        filters: qmodels.Filter | None = None,
    ) -> list[dict[str, Any]]:
        """End-to-end hybrid retrieval. Returns scored, ranked, deduplicated
        chunk dicts in score-descending order.

        Each dict carries: ``chunk_id``, ``document_id``, ``version_id``,
        ``content``, ``score`` (normalized to [0, 1]), ``source``
        (``lexical`` / ``dense`` / ``both``), ``block_start``,
        ``block_end``, ``metadata``.
        """
        lexical_limit = top_k * LEXICAL_FANOUT_MULTIPLIER
        dense_limit = top_k * DENSE_FANOUT_MULTIPLIER
        rrf_limit = top_k * RRF_FANOUT_MULTIPLIER

        lexical_hits = await self.lexical_search(query, workspace_id, limit=lexical_limit)
        dense_hits = await self.dense_search(query, workspace_id, limit=dense_limit, filters=filters)

        fused = self._rrf_fuse(lexical_hits, dense_hits, limit=rrf_limit)

        # Rerank requires a non-empty input; if both legs were empty we
        # return the (also empty) fused list as-is.
        if not fused:
            return []

        reranked = await self._rerank(query, fused, top_k=top_k)
        deduped = self._dedup_overlap(reranked)
        return self._finalize(deduped)

    async def lexical_search(
        self,
        query: str,
        workspace_id: uuid.UUID,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        """Standalone PostgreSQL lexical search. Returns dicts with at
        least ``chunk_id`` (block_id-as-chunk_id), ``content``, ``score``,
        and the locator fields the fusion stage needs.
        """
        if not query.strip():
            return []

        result = await self._session.execute(
            _LEXICAL_SQL,
            {"query": query, "workspace_id": workspace_id, "limit": limit},
        )
        rows = result.mappings().all()
        hits: list[dict[str, Any]] = []
        for row in rows:
            # row is a RowMapping; coerce UUIDs to strings so downstream
            # merging and the JSON-shaped output stay uniform.
            hits.append(
                {
                    "chunk_id": str(row["block_id"]),
                    "document_id": str(row["document_id"]),
                    "version_id": str(row["version_id"]),
                    "workspace_id": str(row["workspace_id"]),
                    "content": row["content_text"],
                    "score": float(row["rank"]),
                    "source": "lexical",
                    "block_start": int(row["block_index"]),
                    "block_end": int(row["block_index"]),
                    "metadata": {
                        "block_type": row["block_type"],
                        "external_id": row["external_id"],
                        "version_number": int(row["version_number"]),
                        "block_metadata": dict(row["block_metadata"] or {}),
                    },
                }
            )
        return hits

    async def dense_search(
        self,
        query: str,
        workspace_id: uuid.UUID,
        limit: int = 40,
        filters: qmodels.Filter | None = None,
    ) -> list[dict[str, Any]]:
        """Standalone Qdrant dense search. Workspace filter is merged into
        the caller's ``filters`` if not already present; Qdrant's payload
        index on ``workspace_id`` makes the merge cheap."""
        if not query.strip():
            return []

        vector = self._embed.embed_query(query)
        merged = self._merge_workspace_filter(filters, workspace_id)

        response = await self._qdrant.client.query_points(
            collection_name=self._qdrant.collection_name,
            query=vector,
            using=DenseVectorName,
            limit=limit,
            query_filter=merged,
            with_payload=True,
        )

        hits: list[dict[str, Any]] = []
        for point in response.points:
            payload = point.payload or {}
            hits.append(
                {
                    "chunk_id": str(point.id),
                    "document_id": str(payload.get("document_id", "")),
                    "version_id": str(payload.get("version_id", "")),
                    "workspace_id": str(payload.get("workspace_id", workspace_id)),
                    "content": str(payload.get("chunk_text", "")),
                    "score": float(point.score or 0.0),
                    "source": "dense",
                    "block_start": int(payload.get("block_start", 0) or 0),
                    "block_end": int(payload.get("block_end", 0) or 0),
                    "metadata": {
                        "block_type": payload.get("block_type"),
                        "external_id": payload.get("external_id"),
                        "doc_title": payload.get("doc_title"),
                        "source_type": payload.get("source_type"),
                    },
                }
            )
        return hits

    # ---- fusion / rerank / dedup -----------------------------------------

    @staticmethod
    def _rrf_fuse(
        lexical: list[dict[str, Any]],
        dense: list[dict[str, Any]],
        *,
        limit: int,
        k: int = RRF_K,
    ) -> list[dict[str, Any]]:
        """Reciprocal Rank Fusion across the two ranked lists.

        ``score = sum_i 1 / (k + rank_i)`` where ``rank_i`` is 1-based and
        items missing from list ``i`` contribute 0. ``source`` is upgraded
        to ``both`` when an item appears in both lists.
        """
        scores: dict[str, float] = defaultdict(float)
        seen_lex: dict[str, dict[str, Any]] = {}
        seen_dense: dict[str, dict[str, Any]] = {}

        for rank, hit in enumerate(lexical, start=1):
            cid = hit["chunk_id"]
            scores[cid] += 1.0 / (k + rank)
            seen_lex[cid] = hit

        for rank, hit in enumerate(dense, start=1):
            cid = hit["chunk_id"]
            scores[cid] += 1.0 / (k + rank)
            seen_dense[cid] = hit

        # Build the merged records, picking the lexical hit as the base
        # when present (richer block metadata) and folding in dense-only
        # fields otherwise.
        fused: list[dict[str, Any]] = []
        for cid, fused_score in scores.items():
            if cid in seen_lex and cid in seen_dense:
                base = dict(seen_lex[cid])
                base["score"] = fused_score
                base["source"] = "both"
            elif cid in seen_lex:
                base = dict(seen_lex[cid])
                base["score"] = fused_score
            else:
                base = dict(seen_dense[cid])
                base["score"] = fused_score
            fused.append(base)

        fused.sort(key=lambda h: h["score"], reverse=True)
        return fused[:limit]

    async def _rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Cross-encoder rerank over candidate texts. Returns the
        ``top_k`` candidates (or all of them, whichever is fewer) with
        their ``score`` replaced by the cross-encoder score and re-sorted
        descending. The cross-encoder is CPU-bound; we still expose
        ``_rerank`` as ``async`` to keep the pipeline's call sites uniform,
        but the underlying call is synchronous (matches the real
        ``EmbeddingService.rerank`` which runs a local SentenceTransformer)."""
        texts = [c["content"] for c in candidates]
        ranked = self._embed.rerank(query, texts, top_n=min(top_k, len(candidates)))
        # ``ranked`` is a list of ``(original_index, score)`` in score
        # order. We project that back onto the original candidate dicts.
        reranked: list[dict[str, Any]] = []
        for orig_idx, score in ranked:
            cand = dict(candidates[orig_idx])
            cand["score"] = float(score)
            reranked.append(cand)
        return reranked

    @staticmethod
    def _dedup_overlap(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Within each ``document_id``, drop lower-scored candidates that
        overlap an already-kept candidate's block range. Items are
        processed in input order, which is the caller's score order."""
        kept: list[dict[str, Any]] = []
        # Per-doc list of (start, end) ranges we've already kept.
        ranges_by_doc: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for cand in candidates:
            doc_id = cand.get("document_id", "")
            start = int(cand.get("block_start", 0))
            end = int(cand.get("block_end", 0))
            if end < start:
                end = start  # defensive: malformed payload
            if any(_overlaps(start, end, ks, ke) for ks, ke in ranges_by_doc[doc_id]):
                continue
            kept.append(cand)
            ranges_by_doc[doc_id].append((start, end))
        return kept

    @staticmethod
    def _finalize(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize scores to [0, 1] via min-max, drop sort, return only
        the public-shape fields the caller asked for. Empty input → []."""
        if not candidates:
            return []
        scores = [float(c["score"]) for c in candidates]
        lo, hi = min(scores), max(scores)
        spread = hi - lo
        for cand in candidates:
            if spread > 0:
                cand["score"] = (float(cand["score"]) - lo) / spread
            else:
                # All scores identical → 1.0 keeps the ordering intact
                # without inventing a non-existent spread.
                cand["score"] = 1.0
        candidates.sort(key=lambda c: c["score"], reverse=True)
        return [
            {
                "chunk_id": c["chunk_id"],
                "document_id": c["document_id"],
                "version_id": c["version_id"],
                "content": c["content"],
                "score": c["score"],
                "source": c["source"],
                "block_start": c["block_start"],
                "block_end": c["block_end"],
                "metadata": c.get("metadata", {}),
            }
            for c in candidates
        ]

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _merge_workspace_filter(
        filters: qmodels.Filter | None,
        workspace_id: uuid.UUID,
    ) -> qmodels.Filter | None:
        """Force a ``workspace_id`` keyword match into the Qdrant filter.

        If the caller already passed a filter, AND the workspace match on
        top; if not, return a one-condition filter. ``None`` is a valid
        Qdrant filter (no constraint) so we never return that."""
        ws_match = qmodels.FieldCondition(
            key="workspace_id",
            match=qmodels.MatchValue(value=str(workspace_id)),
        )
        if filters is None:
            return qmodels.Filter(must=[ws_match])
        existing: list[qmodels.Condition] = []
        if filters.must:
            existing.extend(filters.must if isinstance(filters.must, list) else [filters.must])
        existing.append(ws_match)
        return qmodels.Filter(
            must=existing,
            should=filters.should,
            must_not=filters.must_not,
        )


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Closed-interval overlap test on [start, end] inclusive."""
    return a_start <= b_end and b_start <= a_end


__all__ = [
    "LEXICAL_FANOUT_MULTIPLIER",
    "DENSE_FANOUT_MULTIPLIER",
    "RRF_FANOUT_MULTIPLIER",
    "RRF_K",
    "RetrievalPipeline",
    "_overlaps",
]
