"""Add client_message_id to chat_messages for idempotent inserts.

Revision ID: v0a1b2c3d4e5
Revises: u9a0b1c2d3e4
Create Date: 2026-05-13 00:00:00.000000

Replaces the 60s dedup SELECT in backend/src/api/agent/jobs.py with
INSERT ... ON CONFLICT DO NOTHING by adding a partial unique index on
(thread_id, client_message_id) restricted to user-role rows.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


revision = "v0a1b2c3d4e5"
down_revision = "u9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("client_message_id", PG_UUID(as_uuid=True), nullable=True),
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
