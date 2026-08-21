"""Add durable assistant progress steps.

Revision ID: add_chat_progress_steps
Revises: add_org_id_to_analytics_metrics
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "add_chat_progress_steps"
down_revision = "add_org_id_to_analytics_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "progress_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "progress_steps")
