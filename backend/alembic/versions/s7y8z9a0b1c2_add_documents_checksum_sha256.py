"""Add documents.checksum_sha256 column.

Revision ID: s7y8z9a0b1c2
Revises: r6x7y8z9a0b1
Create Date: 2026-05-11 00:25:00.000000

Model declared ``Document.checksum_sha256`` (SHA-256 hash) but no migration
ever added it. Multiple call sites query/insert this column — every dedupe
lookup and ingest hits ``UndefinedColumn``. Adds nullable column + index.
"""

from alembic import op


revision = "s7y8z9a0b1c2"
down_revision = "r6x7y8z9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS — schema drift between alembic-tracked DB (Supabase) and
    # runtime DB (DO Postgres) means this column may already exist on one but
    # not the other. Make migration idempotent so it can be safely re-run.
    op.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS checksum_sha256 VARCHAR(64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_checksum_sha256 "
        "ON documents (checksum_sha256)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_checksum_sha256")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS checksum_sha256")
