from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    audit_id: str
    workspace_id: str
    action: str
    actor_id: str
    resource_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    details: dict[str, Any] = Field(default_factory=dict)
