"""Drop the retired, zero-writer research_evidence table.

Revision ID: r7_drop_research_evidence
Revises: r6_run_integrity_uniques
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "r7_drop_research_evidence"
down_revision = "r6_run_integrity_uniques"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS research_evidence")


def downgrade() -> None:
    op.create_table(
        "research_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_steps.id"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_sources.id"),
            nullable=False,
        ),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("grounding_status", sa.String(length=50), nullable=False),
        sa.Column("page_reference", sa.String(length=100), nullable=True),
    )
    op.create_index("idx_research_evidence_step", "research_evidence", ["step_id"])
    op.create_index("idx_research_evidence_source", "research_evidence", ["source_id"])
