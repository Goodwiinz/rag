"""ensure uq_collection_documents constraint exists

Earlier revisions created ``collection_documents`` with a
``UniqueConstraint('collection_id', 'document_id')`` named
``uq_collection_documents``. Some environments were bootstrapped via
``Base.metadata.create_all`` while the ORM model declared the
constraint using the Django-style ``class Meta: unique_together``
(silently ignored by SQLAlchemy), leaving the table without the
constraint. Agent ingest then crashes on
``ON CONFLICT (collection_id, document_id) DO NOTHING`` with
``asyncpg.exceptions.InvalidColumnReferenceError``.

This migration is idempotent — it adds the constraint only when
missing and deduplicates rows first so the constraint can be created.

Revision ID: u9a0b1c2d3e4
Revises: t8z9a0b1c2d3
Create Date: 2026-05-12
"""

from alembic import op

revision = "u9a0b1c2d3e4"
down_revision = "t8z9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_collection_documents'
            ) THEN
                ALTER TABLE collection_documents
                ADD CONSTRAINT uq_collection_documents
                UNIQUE (collection_id, document_id);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE collection_documents "
        "DROP CONSTRAINT IF EXISTS uq_collection_documents;"
    )
