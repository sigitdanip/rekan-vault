"""p4_schema_fts

Revision ID: 20260802_0002
Revises: 20260802_0001
Create Date: 2026-08-06 00:00:00.000000

Adds document lifecycle state + PostgreSQL full-text search infrastructure
for Phase 4 Evidence Layer and Hybrid RAG.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260802_0002"
down_revision: Union[str, None] = "20260802_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable PostgreSQL extensions for full-text search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # 2. Document lifecycle state (P4-T4 stale/revoked evidence)
    op.add_column(
        "documents",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column(
        "documents",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_deactivated_at", "documents", ["deactivated_at"])

    # 3. Full-text search on content_blocks (P4 lexical retrieval)
    # Generated tsvector column for simple config — language-specific
    # dictionaries can be layered on top via query-time tsvector operations
    # when the multilingual corpus grows.
    op.execute(
        sa.text(
            "ALTER TABLE content_blocks "
            "ADD COLUMN content_tsvector tsvector "
            "GENERATED ALWAYS AS (to_tsvector('simple', content_text)) STORED"
        )
    )
    op.create_index(
        "ix_content_blocks_tsvector",
        "content_blocks",
        ["content_tsvector"],
        postgresql_using="gin",
    )

    # Trigram index for fuzzy / LIKE-accelerated search
    op.create_index(
        "ix_content_blocks_text_trgm",
        "content_blocks",
        ["content_text"],
        postgresql_using="gin",
        postgresql_ops={"content_text": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_content_blocks_text_trgm")
    op.drop_index("ix_content_blocks_tsvector")
    op.execute(sa.text("ALTER TABLE content_blocks DROP COLUMN content_tsvector"))
    op.drop_index("ix_documents_deactivated_at")
    op.drop_index("ix_documents_status")
    op.drop_column("documents", "deactivated_at")
    op.drop_column("documents", "status")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
