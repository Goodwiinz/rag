"""Assistant-role partial unique index on (thread_id, client_message_id).

Revision ID: y7z8a9b0c1d2
Revises: a9b0c1d2e3f4
Create Date: 2026-07-04 00:00:00.000000

Mirror of the user-row index from v0a1b2c3d4e5, restricted to assistant
rows. Lets the agent SSE path persist the assistant turn idempotently
(INSERT ... ON CONFLICT DO NOTHING) so a retried/reconnected stream for
the same user turn cannot duplicate the assistant message. The
client_message_id column already exists (v0a1b2c3d4e5).

Chained onto the a9b0c1d2e3f4 leaf so ancestry includes BOTH the
y3z4a5b6c7d8 merge and x2y3z4a5b6c7 (the chat_messages.stopped column,
which _persist_assistant_message now writes unconditionally) — review
caught that chaining onto w1x2y3z4a5b6 forked a new head that skipped
the stopped ancestor. Extends an existing head; adds no new fork.
"""

from alembic import op

revision = "y7z8a9b0c1d2"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            "uq_chat_messages_thread_client_msg_assistant "
            "ON chat_messages (thread_id, client_message_id) "
            "WHERE client_message_id IS NOT NULL AND role = 'assistant'"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "uq_chat_messages_thread_client_msg_assistant"
        )
