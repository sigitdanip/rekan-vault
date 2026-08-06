"""Evidence layer: assemble retrieval hits into ranked, cited evidence packs."""

from __future__ import annotations

from rekanvault.evidence.assembler import EvidenceAssembler, insufficient_evidence
from rekanvault.evidence.chunker import Chunk, Chunker
from rekanvault.evidence.citation import CitationResolver

__all__ = [
    "Chunk",
    "Chunker",
    "CitationResolver",
    "EvidenceAssembler",
    "insufficient_evidence",
]
