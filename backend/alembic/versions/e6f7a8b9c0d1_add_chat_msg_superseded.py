"""Add chat_messages.superseded_by_message_id (edit-and-resend tombstones).

Durable edit-and-resend: editing a prior user turn tombstones that turn and
every message after it in the thread by pointing them at the NEW user row.
Display / model-context / export reads filter ``superseded_by_message_id IS
NULL``; by-id, idempotency and analytics reads deliberately do not.

The partial index serves the tombstone/audit direction only — the hot reads
add ``IS NULL`` on top of the existing (thread_id, created_at) indexes.

NOTE: this migration must not touch ``uq_chat_messages_thread_client_msg_user``
(revision v0a1b2c3d4e5). The ON CONFLICT upsert in
``agent_execution_service._persist_user_message`` relies on Postgres inferring
that index from a byte-identical literal ``index_where``.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-02
"""

from alembic import op  # type: ignore[attr-defined]

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS throughout: bootstrap databases materialise the column and
    # the index from the model via Base.metadata.create_all, so a plain
    # add_column/create_index would crash-loop the migration init container.
    op.execute(
        "ALTER TABLE chat_messages "
        "ADD COLUMN IF NOT EXISTS superseded_by_message_id UUID"
    )
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_chat_messages_superseded_by_message_id'
            ) THEN
                ALTER TABLE chat_messages
                    ADD CONSTRAINT fk_chat_messages_superseded_by_message_id
                    FOREIGN KEY (superseded_by_message_id)
                    REFERENCES chat_messages(id) ON DELETE SET NULL;
            END IF;
        END $$
        """)
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_chat_messages_superseded "
            "ON chat_messages (thread_id) "
            "WHERE superseded_by_message_id IS NOT NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_chat_messages_superseded")
    op.execute(
        "ALTER TABLE chat_messages "
        "DROP CONSTRAINT IF EXISTS fk_chat_messages_superseded_by_message_id"
    )
    op.execute(
        "ALTER TABLE chat_messages DROP COLUMN IF EXISTS superseded_by_message_id"
    )
