from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class EntityRecord(BaseModel):
    entity_id: str
    workspace_id: str
    canonical_name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationRecord(BaseModel):
    relation_id: str
    workspace_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    confidence: float = 1.0
    valid_from: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    valid_to: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
