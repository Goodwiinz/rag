"""Add covering index for chat_messages duplicate-check hot path.

Revision ID: t8z9a0b1c2d3
Revises: s7y8z9a0b1c2
Create Date: 2026-05-11 00:00:00.000000

backend/src/api/agent/jobs.py:289-300 runs a SELECT on
(thread_id, user_id, role, created_at) before every assistant turn to
guard against client-retry duplicates. Existing indexes cover
(thread_id, created_at) and (thread_id, role) but not user_id, forcing
an index scan + heap filter per stream. Add a focused composite index.

CONCURRENTLY so prod traffic isn't blocked on long tables.
"""

from alembic import op


revision = "t8z9a0b1c2d3"
down_revision = "s7y8z9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Must run outside a transaction for CONCURRENTLY.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_chat_messages_thread_user_role_created "
            "ON chat_messages (thread_id, user_id, role, created_at DESC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_chat_messages_thread_user_role_created"
        )
