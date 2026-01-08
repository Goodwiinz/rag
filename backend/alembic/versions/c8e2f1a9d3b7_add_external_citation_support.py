"""Add external citation support for arXiv and other non-database sources

Revision ID: c8e2f1a9d3b7
Revises: f931599b6b5b
Create Date: 2026-01-07 10:00:00.000000

This migration adds support for citations from external sources (like arXiv papers)
that don't have corresponding entries in the documents table.

Changes:
- Make document_id nullable in citations table
- Add external_reference_id column for non-UUID identifiers
- Add document_title column to store title for external refs
- Add document_type column to store type for external refs
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8e2f1a9d3b7'
down_revision = 'a1b2c3d4e5f6'  # After thread-centric chat schema
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make document_id nullable (was previously required)
    op.alter_column('citations', 'document_id',
                    existing_type=sa.dialects.postgresql.UUID(),
                    nullable=True)

    # Add external_reference_id column for non-UUID references (e.g., arXiv IDs like "2512.14313v1")
    op.add_column('citations', sa.Column('external_reference_id', sa.String(255), nullable=True))
    op.create_index('ix_citations_external_reference_id', 'citations', ['external_reference_id'], unique=False)

    # Add document_title to store title for external references
    op.add_column('citations', sa.Column('document_title', sa.String(500), nullable=True))

    # Add document_type to store type/source for external references
    op.add_column('citations', sa.Column('document_type', sa.String(100), nullable=True))


def downgrade() -> None:
    # Remove document_type column
    op.drop_column('citations', 'document_type')

    # Remove document_title column
    op.drop_column('citations', 'document_title')

    # Remove external_reference_id column and its index
    op.drop_index('ix_citations_external_reference_id', table_name='citations')
    op.drop_column('citations', 'external_reference_id')

    # Make document_id required again
    # Note: This will fail if there are rows with NULL document_id
    op.alter_column('citations', 'document_id',
                    existing_type=sa.dialects.postgresql.UUID(),
                    nullable=False)
