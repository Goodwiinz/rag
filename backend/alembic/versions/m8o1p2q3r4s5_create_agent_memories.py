"""Create agent_memories table for persistent agent memory store

Revision ID: m8o1p2q3r4s5
Revises: l7n1o2p3q4r5
Create Date: 2026-03-25 10:00:00.000000

Adds the agent_memories table to support cross-conversation memory
for the agent system (Phase 7 of Agent v2 plan). Stores user insights,
preferences, and context extracted from conversations, indexed in both
PostgreSQL (for durability) and Qdrant (for semantic search).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "m8o1p2q3r4s5"
down_revision = "l7n1o2p3q4r5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column(
            "id",
            postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(50), server_default="insight"),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), server_default="0"),
        sa.Column("metadata_", postgresql.JSONB(), server_default="{}"),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_agent_memories_user",
        "agent_memories",
        ["user_id"],
    )
    op.create_index(
        "idx_agent_memories_org",
        "agent_memories",
        ["organization_id"],
    )
    op.create_index(
        "idx_agent_memories_type",
        "agent_memories",
        ["memory_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_agent_memories_type", table_name="agent_memories")
    op.drop_index("idx_agent_memories_org", table_name="agent_memories")
    op.drop_index("idx_agent_memories_user", table_name="agent_memories")
    op.drop_table("agent_memories")
