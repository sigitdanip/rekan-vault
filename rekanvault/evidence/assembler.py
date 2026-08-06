"""Evidence assembler and ContextPack builder.

Transforms raw retrieval results (ranked chunk dicts) into a
:class:`RerankedEvidence` with citations and a sufficiency score, then
optionally packs them into a :class:`ContextPack` respecting a token
budget.

ponytail: one class per responsibility, no factories, no interfaces.
The sufficiency heuristic is intentionally simple — tune later when
we have real retrieval quality data.
"""

from __future__ import annotations

import uuid
from typing import Any

from rekanvault.contracts.context import ContextPack
from rekanvault.contracts.evidence import Citation, EvidenceChunk, RerankedEvidence
from rekanvault.evidence.citation import CitationResolver


def insufficient_evidence(query: str, workspace_id: str, *, token_budget: int = 4096) -> ContextPack:
    """Build a :class:`ContextPack` signalling no usable evidence was found.

    Used by the retriever/orchestrator when retrieval returns nothing
    usable. The diagnostic message lives in ``metadata`` so the rest
    of the pipeline can still reason about the empty pack.
    """
    return ContextPack(
        context_pack_id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        query=query,
        evidence_chunks=[],
        memories=[],
        token_budget=token_budget,
        metadata={"diagnostic": "INSUFFICIENT_EVIDENCE"},
    )


class EvidenceAssembler:
    """Assemble ranked chunks into :class:`RerankedEvidence` and packs.

    Pure: no I/O, no async. Caller hands in already-retrieved chunks.
    """

    def __init__(self, citation_resolver: CitationResolver | None = None) -> None:
        self._citations = citation_resolver or CitationResolver()

    def assemble(
        self,
        retrieved_chunks: list[dict[str, Any]],
        *,
        top_k: int = 10,
        sufficiency_threshold: float = 0.0,
    ) -> RerankedEvidence:
        """Build a :class:`RerankedEvidence` from retrieved chunk dicts.

        Each input dict must carry: ``chunk_id``, ``document_id``,
        ``version_id``, ``workspace_id``, ``content``, ``token_count``,
        ``score``, ``metadata``. Any extra keys land in the chunk's
        ``metadata`` field.

        Returns an empty pack (zero sufficiency) when the input is
        empty or when the top score is below ``sufficiency_threshold``.
        """
        if not retrieved_chunks:
            return RerankedEvidence(chunks=[], citations=[], sufficiency_score=0.0)

        # Sort by score desc, then take top_k. Stable sort is fine —
        # we just need the top_k.
        ordered = sorted(retrieved_chunks, key=lambda c: c.get("score", 0.0), reverse=True)
        top_score = ordered[0].get("score", 0.0)
        if top_score < sufficiency_threshold:
            return RerankedEvidence(chunks=[], citations=[], sufficiency_score=0.0)

        chosen = ordered[:top_k]

        chunks: list[EvidenceChunk] = []
        citations: list[Citation] = []
        for raw in chosen:
            chunk = self._to_chunk(raw)
            chunks.append(chunk)
            citations.append(
                self._citations.resolve(
                    raw.get("metadata", {}),
                    document_id=chunk.document_id,
                    version_id=chunk.version_id,
                    content=chunk.content,
                )
            )

        # ponytail: simple heuristic — penalise when we returned fewer
        # than top_k results. Tune once we have real retrieval quality
        # numbers.
        sufficiency_score = min(1.0, top_score * (len(chunks) / top_k))

        return RerankedEvidence(
            chunks=chunks,
            citations=citations,
            sufficiency_score=sufficiency_score,
        )

    def build_context_pack(
        self,
        query: str,
        reranked: RerankedEvidence,
        workspace_id: str,
        *,
        token_budget: int = 4096,
    ) -> ContextPack:
        """Build a :class:`ContextPack` honouring ``token_budget``.

        Walks the chunks in score order and stops adding once the
        budget is exhausted. Empty pack is returned (not raised) when
        nothing fits.
        """
        selected: list[EvidenceChunk] = []
        used = 0
        for chunk in reranked.chunks:
            # ponytail: token_count is sourced from the chunker; we
            # trust it. If a chunk has 0/negative tokens we still add
            # it once so the user gets at least one result.
            cost = max(chunk.token_count, 0)
            if selected and used + cost > token_budget:
                break
            selected.append(chunk)
            used += cost
            if used >= token_budget:
                break

        return ContextPack(
            context_pack_id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            query=query,
            evidence_chunks=selected,
            memories=[],
            token_budget=token_budget,
        )

    @staticmethod
    def _to_chunk(raw: dict[str, Any]) -> EvidenceChunk:
        metadata = dict(raw.get("metadata") or {})
        # Surface a couple of well-known keys at the top level for
        # callers that don't want to dig into metadata. Anything else
        # stays in metadata.
        locator = metadata.pop("locator", None) or {}
        return EvidenceChunk(
            chunk_id=str(raw["chunk_id"]),
            document_id=str(raw["document_id"]),
            version_id=str(raw["version_id"]),
            workspace_id=str(raw["workspace_id"]),
            content=str(raw.get("content", "")),
            token_count=int(raw.get("token_count", 0)),
            score=float(raw.get("score", 0.0)),
            locator=dict(locator) if isinstance(locator, dict) else {},
            metadata=metadata,
        )
