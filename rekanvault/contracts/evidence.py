from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    version_id: str
    block_id: str | None = None
    title: str
    uri: str
    snippet: str


class EvidenceChunk(BaseModel):
    chunk_id: str
    document_id: str
    version_id: str
    workspace_id: str
    content: str
    token_count: int
    score: float = 0.0
    locator: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RerankedEvidence(BaseModel):
    chunks: list[EvidenceChunk]
    citations: list[Citation]
    sufficiency_score: float
