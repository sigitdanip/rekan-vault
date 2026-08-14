"""p5_typed_memories

Revision ID: 20260812_0003
Revises: 20260802_0002
Create Date: 2026-08-12 12:00:00.000000

Adds authoritative PostgreSQL tables for Phase 5 Typed Memory Formation and Review:
- typed_memories
- memory_evidence_bindings
- memory_review_items
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260812_0003"
down_revision: Union[str, None] = "20260802_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. typed_memories
    op.create_table(
        "typed_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("impact", sa.String(length=32), nullable=False, server_default="MEDIUM"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index("ix_typed_memories_workspace_id", "typed_memories", ["workspace_id"])
    op.create_index("ix_typed_memories_memory_type", "typed_memories", ["memory_type"])
    op.create_index("ix_typed_memories_review_status", "typed_memories", ["review_status"])
    op.create_index("ix_typed_memories_created_by_user_id", "typed_memories", ["created_by_user_id"])

    # 2. memory_evidence_bindings
    op.create_table(
        "memory_evidence_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "memory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("typed_memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_id", sa.String(length=255), nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index("ix_memory_evidence_bindings_memory_id", "memory_evidence_bindings", ["memory_id"])
    op.create_index("ix_memory_evidence_bindings_chunk_id", "memory_evidence_bindings", ["chunk_id"])
    op.create_index("ix_memory_evidence_bindings_document_id", "memory_evidence_bindings", ["document_id"])
    op.create_index("ix_memory_evidence_bindings_version_id", "memory_evidence_bindings", ["version_id"])
    op.create_index("idx_memory_bindings_memory_chunk", "memory_evidence_bindings", ["memory_id", "chunk_id"])

    # 3. memory_review_items
    op.create_table(
        "memory_review_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "memory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("typed_memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("diff_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index("ix_memory_review_items_workspace_id", "memory_review_items", ["workspace_id"])
    op.create_index("ix_memory_review_items_memory_id", "memory_review_items", ["memory_id"])
    op.create_index("ix_memory_review_items_reviewer_id", "memory_review_items", ["reviewer_id"])


def downgrade() -> None:
    op.drop_table("memory_review_items")
    op.drop_table("memory_evidence_bindings")
    op.drop_table("typed_memories")
