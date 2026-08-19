"""Add chat_messages.ttft_ms

Revision ID: add_chat_messages_ttft_ms
Revises: add_chat_messages_plan_reasoning
Create Date: 2026-08-18 00:00:00.000000

Persists time-to-first-token for the turn, measured from the same
stream-start reading as ``latency_ms`` so the two subtract cleanly into
"working" and "writing" halves. NULL for turns that streamed no token
(immediate error, stop before the first frame) and for every row written
before this column existed.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_chat_messages_ttft_ms"
down_revision = "add_chat_messages_plan_reasoning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("ttft_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "ttft_ms")
