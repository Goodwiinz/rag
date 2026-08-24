"""add canonical tenant-scoped arxiv revision key

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-08-15

Existing arXiv metadata rows are deliberately left NULL: live data contains
duplicates whose project, citation, storage, and satellite references require
an audited survivor decision. New and repaired rows use this column, so the
partial unique index prevents any further exact-revision duplicates without a
destructive migration-time guess.
"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_documents_org_arxiv_id_live"
TRIGGER_NAME = "trg_documents_set_arxiv_id"
FUNCTION_NAME = "set_documents_arxiv_id_on_insert"


def upgrade() -> None:
    # R6-M9 guard: this revision runs after the r6h3_model_baseline
    # create_all on fresh databases, so the column may already exist.
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS arxiv_id VARCHAR(64)")
    # Rolling deployments overlap old and new pods. Old code omits the new
    # column, so post-migration inserts must still participate in uniqueness.
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {FUNCTION_NAME}() RETURNS trigger AS $$
        DECLARE
            candidate TEXT;
        BEGIN
            candidate := NULLIF(BTRIM(NEW.document_metadata->>'arxiv_id'), '');
            IF NEW.arxiv_id IS NULL OR BTRIM(NEW.arxiv_id) = '' THEN
                IF LENGTH(candidate) <= 64 AND (
                    candidate ~ '^[0-9]{{4}}[.][0-9]{{4,5}}(v[0-9]+)?$'
                    OR candidate ~ '^[A-Za-z][A-Za-z0-9.-]*/[0-9]{{7}}(v[0-9]+)?$'
                ) THEN
                    NEW.arxiv_id := candidate;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON documents;

        CREATE TRIGGER {TRIGGER_NAME}
        BEFORE INSERT ON documents
        FOR EACH ROW EXECUTE FUNCTION {FUNCTION_NAME}();
        """)
    op.execute(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
        ON documents (organization_id, arxiv_id)
        WHERE is_deleted = false AND arxiv_id IS NOT NULL
        """)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="documents")
    op.execute(f"DROP TRIGGER {TRIGGER_NAME} ON documents")
    op.execute(f"DROP FUNCTION {FUNCTION_NAME}()")
    op.drop_column("documents", "arxiv_id")
