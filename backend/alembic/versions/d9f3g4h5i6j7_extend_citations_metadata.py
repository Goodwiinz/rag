"""Extend citations table with scholarly metadata fields for Research Assistant

Revision ID: d9f3g4h5i6j7
Revises: b2c3d4e5f6g7
Create Date: 2026-01-14 19:30:00.000000

This migration extends the citations table to support full scholarly metadata
for citation extraction and bibliography generation (User Story 2).

Changes:
- Add authors column (JSONB array) for all authors
- Add year column (Integer) for publication year
- Add venue column (String) for journal/conference name
- Add doi column (String) with unique constraint for Digital Object Identifier
- Add arxiv_id column (String) with unique constraint for arXiv identifier
- Add abstract column (Text) for paper abstract
- Add metadata_source column (String) to track extraction source
- Add needs_review column (Boolean) flag for incomplete metadata
- Add indexes on arxiv_id, doi, and document_id for fast lookups
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d9f3g4h5i6j7"
down_revision = "b2c3d4e5f6g7"  # After fulltext search
branch_labels = None
depends_on = None


def upgrade() -> None:
    # R6-M9 guard: the model baseline creates the current citations schema,
    # so every column here may already exist. Idempotent ADD COLUMN keeps
    # both provisioning worlds alive.
    for stmt in (
        "ALTER TABLE citations ADD COLUMN IF NOT EXISTS authors JSONB",
        "ALTER TABLE citations ADD COLUMN IF NOT EXISTS year INTEGER",
        "ALTER TABLE citations ADD COLUMN IF NOT EXISTS venue VARCHAR(500)",
        "ALTER TABLE citations ADD COLUMN IF NOT EXISTS doi VARCHAR(255)",
        "ALTER TABLE citations ADD COLUMN IF NOT EXISTS arxiv_id VARCHAR(100)",
        "ALTER TABLE citations ADD COLUMN IF NOT EXISTS abstract TEXT",
        "ALTER TABLE citations ADD COLUMN IF NOT EXISTS metadata_source VARCHAR(50)",
        "ALTER TABLE citations ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT false",
    ):
        op.execute(stmt)

    # NOTE: intentionally NOT unique — global DOI/arXiv uniqueness was a
    # cross-tenant collision bug removed by o2r3s4t5u6v7; keep that outcome
    # for databases walking the chain fresh.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_citations_doi "
        "ON citations (doi) WHERE doi IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_citations_arxiv_id "
        "ON citations (arxiv_id) WHERE arxiv_id IS NOT NULL"
    )

    # Ensure document_id index exists (should already exist from previous migrations)
    # op.create_index('ix_citations_document_id', 'citations', ['document_id'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS ix_citations_arxiv_id")
    op.execute("DROP INDEX IF EXISTS ix_citations_doi")

    # Drop columns in reverse order
    op.execute("ALTER TABLE citations DROP COLUMN IF EXISTS needs_review")
    op.execute("ALTER TABLE citations DROP COLUMN IF EXISTS metadata_source")
    op.execute("ALTER TABLE citations DROP COLUMN IF EXISTS abstract")
    op.execute("ALTER TABLE citations DROP COLUMN IF EXISTS arxiv_id")
    op.execute("ALTER TABLE citations DROP COLUMN IF EXISTS doi")
    op.execute("ALTER TABLE citations DROP COLUMN IF EXISTS venue")
    op.execute("ALTER TABLE citations DROP COLUMN IF EXISTS year")
    op.execute("ALTER TABLE citations DROP COLUMN IF EXISTS authors")
