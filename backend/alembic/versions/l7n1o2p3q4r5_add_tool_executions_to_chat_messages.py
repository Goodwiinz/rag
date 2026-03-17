"""Add tool_executions JSONB column to chat_messages

Revision ID: l7n1o2p3q4r5
Revises: k6m0n1o2p3q4
Create Date: 2026-03-16 12:00:00.000000

Adds a JSONB column to store tool execution details (args, results, duration)
on assistant messages so they persist across page reloads.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "l7n1o2p3q4r5"
down_revision = ("k6m0n1o2p3q4", "perf_indexes_n1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("tool_executions", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "tool_executions")
