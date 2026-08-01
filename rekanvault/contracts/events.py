from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    SOURCE_DISCOVERED = "source.discovered"
    SOURCE_SYNCED = "source.synced"
    SOURCE_FAILED = "source.failed"
    DOCUMENT_CREATED = "document.created"
    DOCUMENT_UPDATED = "document.updated"
    DOCUMENT_DELETED = "document.deleted"
    VERSION_NORMALIZED = "version.normalized"
    EVIDENCE_INDEXED = "evidence.indexed"
    MEMORY_FORMED = "memory.formed"
    MEMORY_SUPERSEDED = "memory.superseded"
    ENTITY_RESOLVED = "entity.resolved"
    RELATION_CREATED = "relation.created"
    CONTEXT_PACK_CREATED = "context_pack.created"
    SKILL_PROGRESS_UPDATED = "skill.progress_updated"
    AUDIT_RECORDED = "audit.recorded"


class LifecycleEvent(BaseModel):
    event_id: str
    event_type: EventType
    workspace_id: str
    aggregate_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
