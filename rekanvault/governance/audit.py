"""
Structured Audit Logging Writer (rekanvault.contracts.audit)
Enforces audit logging discipline: logs every high-impact mutation without including raw document/source content bodies.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.storage.models import AuditLog


class AuditWriter:
    """Writes audit events to PostgreSQL database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_event(
        self,
        workspace_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: str,
        actor_id: Optional[uuid.UUID] = None,
        idempotency_key: Optional[str] = None,
        changes: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """
        Creates and persists an audit log record.
        Sanitizes changes to strip raw content text/bodies.
        """
        sanitized_changes = self._sanitize_changes(changes or {})

        entry = AuditLog(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            idempotency_key=idempotency_key,
            changes=sanitized_changes,
            ip_address=ip_address,
        )
        self.session.add(entry)
        return entry

    @staticmethod
    def _sanitize_changes(changes: dict[str, Any]) -> dict[str, Any]:
        """Strips sensitive raw content body keys (e.g. content_text, raw_body, ciphertext)."""
        forbidden_keys = {"content_text", "raw_body", "raw_content", "body", "ciphertext", "password"}
        sanitized: dict[str, Any] = {}
        for key, val in changes.items():
            if key.lower() in forbidden_keys:
                sanitized[key] = "[REDACTED_BY_AUDIT_POLICY]"
            elif isinstance(val, dict):
                sanitized[key] = AuditWriter._sanitize_changes(val)
            else:
                sanitized[key] = val
        return sanitized
