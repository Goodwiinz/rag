"""Ensure upsert-target unique constraints exist (create_all drift heal)

Revision ID: ensure_upsert_uq_constraints
Revises: uq_project_thread_constraint
Create Date: 2026-07-01 00:00:00

The DOKS dev cluster boots with ENVIRONMENT=development, so app startup runs
``Base.metadata.create_all`` against Supabase. ``create_all`` uses checkfirst:
it SKIPS existing tables and never ALTERs them, so any constraint added to a
model after its table first existed never lands, and the alembic migration that
was supposed to add it may have been stamped-not-run at bootstrap (its
``create_table``/``add_column`` is a no-op against the pre-existing table). The
result is tables that physically lack the unique constraints their runtime
``ON CONFLICT`` upserts require -> ``InvalidColumnReferenceError`` 500s.

This migration idempotently (re)creates the two remaining at-risk upsert
targets. It runs AFTER ``uq_project_thread_constraint`` (which already repaired
``project_threads``), and is a guaranteed no-op where the constraints already
exist -- so it heals whether or not the original ``u9a0b1c2d3e4`` /
``v0a1b2c3d4e5`` migrations actually executed.

Targets:
- collection_documents.uq_collection_documents  (tool_helpers.py link upsert)
- chat_messages partial unique on (thread_id, client_message_id) WHERE user
  (jobs.py _persist_user_message idempotency upsert)
"""

from alembic import op

revision = "ensure_upsert_uq_constraints"
down_revision = "uq_project_thread_constraint"
branch_labels = None
depends_on = None

CHAT_MSG_INDEX = "uq_chat_messages_thread_client_msg_user"


def upgrade() -> None:
    # --- collection_documents: uq_collection_documents (collection_id, document_id)
    op.execute(
        """
        DELETE FROM collection_documents a
        USING collection_documents b
        WHERE a.ctid < b.ctid
          AND a.collection_id = b.collection_id
          AND a.document_id   = b.document_id;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_collection_documents'
            ) THEN
                ALTER TABLE collection_documents
                ADD CONSTRAINT uq_collection_documents
                UNIQUE (collection_id, document_id);
            END IF;
        END
        $$;
        """
    )

    # --- chat_messages: column + partial unique index for the idempotency upsert.
    op.execute(
        "ALTER TABLE chat_messages "
        "ADD COLUMN IF NOT EXISTS client_message_id UUID"
    )
    op.execute(
        """
        DELETE FROM chat_messages a
        USING chat_messages b
        WHERE a.ctid < b.ctid
          AND a.thread_id = b.thread_id
          AND a.client_message_id = b.client_message_id
          AND a.client_message_id IS NOT NULL
          AND a.role = 'user'
          AND b.role = 'user';
        """
    )
    # CONCURRENTLY cannot run inside the migration's transaction.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            f"{CHAT_MSG_INDEX} "
            "ON chat_messages (thread_id, client_message_id) "
            "WHERE client_message_id IS NOT NULL AND role = 'user'"
        )


def downgrade() -> None:
    # Non-destructive: these constraints may pre-date this migration (added by
    # u9a0b1c2d3e4 / v0a1b2c3d4e5), so downgrade is a deliberate no-op rather
    # than dropping shared objects those revisions own.
    pass
