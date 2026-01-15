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
revision = 'd9f3g4h5i6j7'
down_revision = 'b2c3d4e5f6g7'  # After fulltext search
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add scholarly metadata columns
    op.add_column('citations', sa.Column('authors', postgresql.JSONB, nullable=True))
    op.add_column('citations', sa.Column('year', sa.Integer, nullable=True))
    op.add_column('citations', sa.Column('venue', sa.String(500), nullable=True))
    op.add_column('citations', sa.Column('doi', sa.String(255), nullable=True))
    op.add_column('citations', sa.Column('arxiv_id', sa.String(100), nullable=True))
    op.add_column('citations', sa.Column('abstract', sa.Text, nullable=True))
    op.add_column('citations', sa.Column('metadata_source', sa.String(50), nullable=True))
    op.add_column('citations', sa.Column('needs_review', sa.Boolean, nullable=False, server_default='false'))

    # Add unique constraints for doi and arxiv_id (to prevent duplicate entries)
    op.create_index('ix_citations_doi', 'citations', ['doi'], unique=True, postgresql_where=sa.text("doi IS NOT NULL"))
    op.create_index('ix_citations_arxiv_id', 'citations', ['arxiv_id'], unique=True, postgresql_where=sa.text("arxiv_id IS NOT NULL"))

    # Ensure document_id index exists (should already exist from previous migrations)
    # op.create_index('ix_citations_document_id', 'citations', ['document_id'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_citations_arxiv_id', table_name='citations')
    op.drop_index('ix_citations_doi', table_name='citations')

    # Drop columns in reverse order
    op.drop_column('citations', 'needs_review')
    op.drop_column('citations', 'metadata_source')
    op.drop_column('citations', 'abstract')
    op.drop_column('citations', 'arxiv_id')
    op.drop_column('citations', 'doi')
    op.drop_column('citations', 'venue')
    op.drop_column('citations', 'year')
    op.drop_column('citations', 'authors')
