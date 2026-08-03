"""
Unit tests for AuditWriter and content redaction policy.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from rekanvault.governance.audit import AuditWriter


@pytest.mark.asyncio
async def test_audit_writer_sanitizes_raw_content() -> None:
    session = AsyncMock()
    writer = AuditWriter(session=session)

    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    changes = {
        "title": "New Strategy Document",
        "content_text": "Top secret company launch strategy details...",
        "raw_body": "Internal memo raw body text",
        "byte_size": 2048,
    }

    entry = await writer.log_event(
        workspace_id=ws_id,
        actor_id=actor_id,
        action="document.create",
        resource_type="document",
        resource_id="doc_xyz",
        idempotency_key="idem_doc_1",
        changes=changes,
    )

    assert entry.workspace_id == ws_id
    assert entry.changes["title"] == "New Strategy Document"
    assert entry.changes["content_text"] == "[REDACTED_BY_AUDIT_POLICY]"
    assert entry.changes["raw_body"] == "[REDACTED_BY_AUDIT_POLICY]"
    assert entry.changes["byte_size"] == 2048
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_audit_permission_widening() -> None:
    session = AsyncMock()
    writer = AuditWriter(session=session)

    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    grant_id = str(uuid.uuid4())

    entry = await writer.log_event(
        workspace_id=ws_id,
        actor_id=actor_id,
        action="permission.widen",
        resource_type="grant",
        resource_id=grant_id,
        changes={
            "permission": "document.write",
            "previous_level": "read",
            "new_level": "write",
            "target_user": str(uuid.uuid4()),
        },
    )

    assert entry.action == "permission.widen"
    assert entry.resource_type == "grant"
    assert entry.resource_id == grant_id
    assert entry.actor_id == actor_id
    assert entry.workspace_id == ws_id
    assert entry.changes["permission"] == "document.write"
    assert entry.changes["new_level"] == "write"
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_audit_schema_migration() -> None:
    session = AsyncMock()
    writer = AuditWriter(session=session)

    ws_id = uuid.uuid4()
    migration_id = str(uuid.uuid4())

    entry = await writer.log_event(
        workspace_id=ws_id,
        action="schema.migration",
        resource_type="schema_migration",
        resource_id=migration_id,
        changes={
            "version": "0042",
            "description": "Add grant_scope column to grants table",
        },
    )

    assert entry.action == "schema.migration"
    assert entry.resource_type == "schema_migration"
    assert entry.resource_id == migration_id
    assert entry.workspace_id == ws_id
    assert entry.changes["version"] == "0042"
    assert entry.changes["description"] == "Add grant_scope column to grants table"
    session.add.assert_called_once()
