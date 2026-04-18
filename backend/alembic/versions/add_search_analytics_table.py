"""Add search_analytics table

Revision ID: b8f3a1c2d4e5
Revises: None
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "b8f3a1c2d4e5"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "search_analytics",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("search_id", sa.String(64), nullable=False, index=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.CHAR(36), nullable=False, index=True),
        sa.Column("user_id", sa.CHAR(36), nullable=True, index=True),
        sa.Column("search_type", sa.String(32), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, default=0),
        sa.Column("search_time_ms", sa.Float(), nullable=False, default=0.0),
        sa.Column("filters", JSONB(), nullable=True),
        sa.Column("clicked_document_id", sa.CHAR(36), nullable=True),
        sa.Column("clicked_position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Index for time-range queries
    op.create_index("ix_search_analytics_created_at", "search_analytics", ["created_at"])


def downgrade():
    op.drop_index("ix_search_analytics_created_at")
    op.drop_table("search_analytics")
