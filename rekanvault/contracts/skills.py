from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SkillNode(BaseModel):
    skill_id: str
    workspace_id: str
    title: str
    description: str
    prerequisites: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillProgress(BaseModel):
    skill_id: str
    workspace_id: str
    mastery_score: float = 0.0
    evidence_count: int = 0
    last_updated: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
