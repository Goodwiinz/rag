"""Create integrity_scores table (Feature 5: AI Integrity Detector)

Revision ID: k6m0n1o2p3q4
Revises: j5l9m0n1o2p3
Create Date: 2026-02-21 12:00:00.000000

This migration creates the integrity_scores table for storing AI authorship
detection results produced by the RoBERTa-based classifier.

Changes:
- Create integrity_scores table with ai_probability, human_probability, method,
  analyzed_at, and segment_scores (JSONB) columns
- Add index on document_id for fast lookups
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "k6m0n1o2p3q4"
down_revision = "j5l9m0n1o2p3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create integrity_scores table
    op.create_table(
        "integrity_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ai_probability", sa.Float, nullable=False),
        sa.Column("human_probability", sa.Float, nullable=False),
        sa.Column(
            "method",
            sa.String(100),
            nullable=False,
            server_default="roberta-base-openai-detector",
        ),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "segment_scores",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
    )

    # Create index on document_id for fast lookups
    op.create_index(
        "ix_integrity_scores_document_id",
        "integrity_scores",
        ["document_id"],
    )
    op.create_unique_constraint(
        "uq_integrity_doc_method",
        "integrity_scores",
        ["document_id", "method"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_integrity_doc_method", "integrity_scores", type_="unique")
    op.drop_index("ix_integrity_scores_document_id", table_name="integrity_scores")
    op.drop_table("integrity_scores")
