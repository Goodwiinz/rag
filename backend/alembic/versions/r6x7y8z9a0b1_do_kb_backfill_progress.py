"""Add do_kb_backfill_progress table.

Revision ID: r6x7y8z9a0b1
Revises: q5w6x7y8z9a0
Create Date: 2026-05-08 14:00:00.000000

Tracks Phase 3 backfill state per organization so the script is resumable
across crashes and runs.
"""

from alembic import op
import sqlalchemy as sa


revision = "r6x7y8z9a0b1"
down_revision = "q5w6x7y8z9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "do_kb_backfill_progress",
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("last_document_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_do_kb_backfill_progress_status",
        "do_kb_backfill_progress",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_do_kb_backfill_progress_status", table_name="do_kb_backfill_progress"
    )
    op.drop_table("do_kb_backfill_progress")
