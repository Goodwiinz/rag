"""add kg_sync_runs

Revision ID: w1b2c3d4e5f6
Revises: v0a1b2c3d4e5
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "w1b2c3d4e5f6"
down_revision = "v0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kg_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"),
                  primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=False, unique=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("orphan_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("drift_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fixed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("run_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','success','failed')",
            name="kg_sync_runs_status_check",
        ),
    )
    op.create_index("ix_kg_sync_runs_started_at", "kg_sync_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_kg_sync_runs_started_at", table_name="kg_sync_runs")
    op.drop_table("kg_sync_runs")
