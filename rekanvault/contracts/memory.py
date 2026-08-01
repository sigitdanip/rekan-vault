from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    FACT = "fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    WORKFLOW = "workflow"


class MemoryImpact(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryRecord(BaseModel):
    memory_id: str
    workspace_id: str
    memory_type: MemoryType
    title: str
    content: str
    confidence: float = 1.0
    impact: MemoryImpact = MemoryImpact.MEDIUM
    source_document_ids: list[str] = Field(default_factory=list)
    superseded_by: str | None = None
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)
