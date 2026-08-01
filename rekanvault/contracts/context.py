from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from rekanvault.contracts.evidence import Citation, EvidenceChunk
from rekanvault.contracts.memory import MemoryRecord


class ContextPack(BaseModel):
    context_pack_id: str
    workspace_id: str
    query: str
    evidence_chunks: list[EvidenceChunk] = Field(default_factory=list)
    memories: list[MemoryRecord] = Field(default_factory=list)
    token_budget: int = 4096
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


class GroundedAnswer(BaseModel):
    query: str
    answer: str
    context_pack_id: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 1.0
    contradictions_detected: bool = False
