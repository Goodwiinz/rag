"""Create citation_relationships table for citation graph (User Story 3)

Revision ID: e0g4h5i6j7k8
Revises: d9f3g4h5i6j7
Create Date: 2026-01-14 19:35:00.000000

This migration creates the citation_relationships table to store directed edges
in the citation graph (paper A cites paper B).

Changes:
- Create citation_relationships table with source/target citation IDs
- Add relationship_type column (cites, cited_by, related_to)
- Add citation_context column (where the citation appears in text)
- Add confidence column (extraction confidence score)
- Add unique constraint to prevent duplicate relationships
- Add check constraint to prevent self-referencing relationships
- Add indexes on source_citation_id and target_citation_id
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'e0g4h5i6j7k8'
down_revision = 'd9f3g4h5i6j7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create citation_relationships table
    op.create_table(
        'citation_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source_citation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('citations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_citation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('citations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False, server_default='cites'),
        sa.Column('citation_context', sa.Text, nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),

        # Prevent duplicate relationships
        sa.UniqueConstraint('source_citation_id', 'target_citation_id', name='uq_citation_relationship'),

        # Prevent self-referencing relationships
        sa.CheckConstraint('source_citation_id != target_citation_id', name='ck_citation_no_self_reference')
    )

    # Create indexes for fast lookups
    op.create_index('ix_citation_relationships_source', 'citation_relationships', ['source_citation_id'])
    op.create_index('ix_citation_relationships_target', 'citation_relationships', ['target_citation_id'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_citation_relationships_target', table_name='citation_relationships')
    op.drop_index('ix_citation_relationships_source', table_name='citation_relationships')

    # Drop table
    op.drop_table('citation_relationships')
