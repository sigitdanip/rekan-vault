"""Evidence layer: assemble retrieval hits into ranked, cited evidence packs."""

from __future__ import annotations

from rekanvault.evidence.assembler import EvidenceAssembler, insufficient_evidence
from rekanvault.evidence.chunker import Chunk, Chunker
from rekanvault.evidence.citation import CitationResolver
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.evidence.retrieval import RetrievalPipeline

__all__ = [
    "Chunk",
    "Chunker",
    "CitationResolver",
    "EmbeddingService",
    "EvidenceAssembler",
    "RetrievalPipeline",
    "insufficient_evidence",
]
