"""extraction_failures

Revision ID: 20260814_0004
Revises: 20260812_0003
Create Date: 2026-08-14 12:00:00.000000

Adds chunk-level extraction failure tracking (P5): records chunks whose
LLM extraction failed after retries + salvage, so a re-run can sweep gaps.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260814_0004"
down_revision: Union[str, None] = "20260812_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extraction_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_id", sa.String(length=255), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index("ix_extraction_failures_workspace_id", "extraction_failures", ["workspace_id"])
    op.create_index("ix_extraction_failures_document_id", "extraction_failures", ["document_id"])
    op.create_index("ix_extraction_failures_document_version_id", "extraction_failures", ["document_version_id"])
    op.create_index("ix_extraction_failures_chunk_id", "extraction_failures", ["chunk_id"])


def downgrade() -> None:
    op.drop_table("extraction_failures")
