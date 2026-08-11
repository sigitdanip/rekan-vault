"""Search API router (P4 — hybrid retrieval).

Exposes ``POST /api/v1/search`` which runs the :class:`RetrievalPipeline`
across lexical + dense indexes, assembles the hits into a
:class:`ContextPack` via :class:`EvidenceAssembler`, and attaches redacted
diagnostics to the response metadata.

The pilot hard-codes the workspace (see ``_PILOT_WORKSPACE_ID``); the
production wiring will inject the caller's resolved workspace through
auth middleware (P2-T6).
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from qdrant_client.http import models as qmodels
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from rekanvault.contracts.context import ContextPack
from rekanvault.contracts.errors import ErrorCode, RekanVaultError
from rekanvault.evidence.assembler import EvidenceAssembler, insufficient_evidence
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.retrieval import RetrievalPipeline
from rekanvault.storage.database import get_db_session
from rekanvault.storage.qdrant import QdrantStore

router = APIRouter()

# Hard-coded workspace_id is acceptable for the pilot — production gets
# the real auth middleware (see P2-T6) that injects the caller identity.
_PILOT_WORKSPACE_ID = uuid.UUID(settings.RV_PILOT_WORKSPACE_ID)

# Module-level singletons — one QdrantStore and one EmbeddingService for
# all requests instead of per-request instantiation (prevents model reload
# and AsyncQdrantClient leak).
_embed: EmbeddingService | None = None
_qdrant: QdrantStore | None = None

# Filter keys surfaced to Qdrant as keyword matches. Unknown keys are
# rejected with 400 instead of forwarded to Qdrant (which would 500).
ALLOWED_FILTER_KEYS: frozenset[str] = frozenset({"source_type", "corpus_id", "status"})


class SearchRequest(BaseModel):
    """Request body for ``POST /api/v1/search``.

    ``filters`` is a free-form ``dict`` so callers can pass any subset of
    ``{workspace_id, source_type, corpus_id, status, ...}``. Unknown keys
    are forwarded to the Qdrant filter builder as keyword matches (TBD:
    tighter validation once the supported filter set is locked).
    """

    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] | None = None


# The response is the ``ContextPack`` itself — no extra envelope. The
# search route returns whatever the assembler produced, plus diagnostics
# in ``metadata``.
SearchResponse = ContextPack


def _workspace_id() -> uuid.UUID:
    """Return the workspace_id for the current request.

    Pilot mode: a single hard-coded workspace. The real implementation
    will read the verified Supabase JWT and look up the membership.
    """
    return _PILOT_WORKSPACE_ID


def _get_embed() -> EmbeddingService:
    global _embed
    if _embed is None:
        _embed = EmbeddingService()
    return _embed


def _get_qdrant() -> QdrantStore:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantStore(settings)
    return _qdrant


def _build_qdrant_filter(filters: dict[str, Any] | None) -> qmodels.Filter | None:
    """Translate the request's ``filters`` dict into a Qdrant filter.

    Rejects unknown keys with a 400 (instead of forwarding to Qdrant
    where they produce a cryptic 500).  ``None`` values are silently
    dropped — the caller passed the key but wants no constraint.
    """
    if not filters:
        return None
    must: list[qmodels.Condition] = []
    for key, value in filters.items():
        if value is None:
            continue
        if key not in ALLOWED_FILTER_KEYS:
            raise RekanVaultError(
                message=f"Unknown filter key: {key}",
                code=ErrorCode.VALIDATION_ERROR,
                target="filter",
                details={"allowed": sorted(ALLOWED_FILTER_KEYS)},
            )
        must.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value)))
    if not must:
        return None
    return qmodels.Filter(must=must)


def _count_by_source(results: list[dict[str, Any]]) -> tuple[int, int]:
    """Return ``(lexical_hits, dense_hits)`` from a search result list.

    A hit with ``source == "both"`` counts toward both legs — that is the
    whole point of the hybrid score, so the diagnostic should reflect it.
    """
    lexical = sum(1 for r in results if r.get("source") in {"lexical", "both"})
    dense = sum(1 for r in results if r.get("source") in {"dense", "both"})
    return lexical, dense


@router.post("/search", response_model=SearchResponse, tags=["Search"])
async def search(
    body: SearchRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SearchResponse:
    """Run hybrid retrieval and return an evidence-packed context pack."""
    workspace_id = _workspace_id()
    started = time.perf_counter()

    try:
        pipeline = RetrievalPipeline(session, _get_embed(), _get_qdrant())
        qdrant_filter = _build_qdrant_filter(body.filters)
        results = await pipeline.search(
            body.query,
            workspace_id,
            top_k=body.top_k,
            filters=qdrant_filter,
        )

        assembler = EvidenceAssembler()
        if not results:
            pack = insufficient_evidence(body.query, str(workspace_id))
        else:
            reranked = assembler.assemble(results, top_k=body.top_k)
            pack = assembler.build_context_pack(body.query, reranked, str(workspace_id))
    except RekanVaultError:
        # Already typed — let the registered handler turn it into an envelope.
        raise
    except Exception as exc:  # noqa: BLE001 — boundary: any retrieval failure is a 500 to the caller
        raise RekanVaultError(
            message="Search pipeline failed",
            code=ErrorCode.INTERNAL_ERROR,
            target="search",
            details={"error_type": type(exc).__name__},
        ) from exc

    lexical_hits, dense_hits = _count_by_source(results)
    diagnostics = {
        "pipeline": "p4_hybrid_v1",
        "lexical_hits": lexical_hits,
        "dense_hits": dense_hits,
        "reranked_count": len(pack.evidence_chunks),
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }
    pack.metadata = {**pack.metadata, "diagnostics": diagnostics}
    return pack


__all__ = ["ALLOWED_FILTER_KEYS", "SearchRequest", "SearchResponse", "router"]
