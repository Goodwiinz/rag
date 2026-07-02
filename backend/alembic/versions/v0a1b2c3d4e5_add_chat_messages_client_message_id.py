"""Add client_message_id to chat_messages for idempotent inserts.

Revision ID: v0a1b2c3d4e5
Revises: u9a0b1c2d3e4
Create Date: 2026-05-13 00:00:00.000000

Replaces the 60s dedup SELECT in backend/src/api/agent/jobs.py with
INSERT ... ON CONFLICT DO NOTHING by adding a partial unique index on
(thread_id, client_message_id) restricted to user-role rows.
"""

from alembic import op

revision = "v0a1b2c3d4e5"
down_revision = "u9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent add: the DOKS dev cluster HISTORICALLY ran create_all at
    # startup (before the SUPABASE_DB_URL gate in #925) and may already have
    # materialised this column from the model, so a plain op.add_column would
    # raise "column already exists" and crash-loop the migration init container.
    op.execute(
        "ALTER TABLE chat_messages " "ADD COLUMN IF NOT EXISTS client_message_id UUID"
    )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            "uq_chat_messages_thread_client_msg_user "
            "ON chat_messages (thread_id, client_message_id) "
            "WHERE client_message_id IS NOT NULL AND role = 'user'"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS uq_chat_messages_thread_client_msg_user"
        )
    op.drop_column("chat_messages", "client_message_id")
