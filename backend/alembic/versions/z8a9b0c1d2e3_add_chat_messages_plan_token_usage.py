"""Add per-turn agent provenance columns to chat_messages

Revision ID: z8a9b0c1d2e3
Revises: y7z8a9b0c1d2
Create Date: 2026-07-05 00:00:00.000000

Persists the planner's advisory plan ([{step, description, tool, args_hint,
depends_on}]) and the turn's aggregated LLM token usage ({input_tokens,
output_tokens}) on the assistant row, so a page reload can rehydrate the plan
panel and token badge (previously session-only, lost on reload).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "z8a9b0c1d2e3"
down_revision = "y7z8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column(
            "token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "token_usage")
    op.drop_column("chat_messages", "plan")
