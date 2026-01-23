"""Create generated_drafts and draft_citations tables (User Story 5)

Revision ID: h3j7k8l9m0n1
Revises: g2i6j7k8l9m0
Create Date: 2026-01-14 19:50:00.000000

This migration creates tables for AI-generated literature review drafts
with version management and citation tracking.

Changes:
- Create generated_drafts table with versioning support
- Create draft_citations table to link drafts to documents/citations
- Add version retention trigger (max 10 versions per project)
- Add indexes for fast version lookups
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'h3j7k8l9m0n1'
down_revision = 'g2i6j7k8l9m0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create generated_drafts table
    op.create_table(
        'generated_drafts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('collections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('themes', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('word_count', sa.Integer, nullable=True),
        sa.Column('citation_count', sa.Integer, nullable=True),
        sa.Column('generation_params', postgresql.JSONB, nullable=True),
        sa.Column('generation_time_ms', sa.Integer, nullable=True),
        sa.Column('is_current', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),

        # Unique constraint for version per project
        sa.UniqueConstraint('project_id', 'version', name='uq_draft_version')
    )

    # Create indexes
    op.create_index('ix_generated_drafts_project_id', 'generated_drafts', ['project_id'])
    op.create_index('ix_generated_drafts_is_current', 'generated_drafts', ['is_current'])

    # Create draft_citations table
    op.create_table(
        'draft_citations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('generated_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('citation_index', sa.Integer, nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('citation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('citations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('snippet', sa.Text, nullable=True),
        sa.Column('context', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # Create indexes for draft_citations
    op.create_index('ix_draft_citations_draft_id', 'draft_citations', ['draft_id'])
    op.create_index('ix_draft_citations_document_id', 'draft_citations', ['document_id'])

    # Create trigger function for version retention (max 10 versions)
    op.execute("""
        CREATE OR REPLACE FUNCTION maintain_draft_versions()
        RETURNS TRIGGER AS $$
        DECLARE
            version_count INTEGER;
            oldest_draft_id UUID;
        BEGIN
            -- Count versions for this project
            SELECT COUNT(*) INTO version_count
            FROM generated_drafts
            WHERE project_id = NEW.project_id;

            -- If we have more than 10 versions, delete the oldest
            IF version_count > 10 THEN
                SELECT id INTO oldest_draft_id
                FROM generated_drafts
                WHERE project_id = NEW.project_id
                ORDER BY version ASC
                LIMIT 1;

                DELETE FROM generated_drafts WHERE id = oldest_draft_id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger
    op.execute("""
        CREATE TRIGGER trigger_maintain_draft_versions
        AFTER INSERT ON generated_drafts
        FOR EACH ROW
        EXECUTE FUNCTION maintain_draft_versions();
    """)


def downgrade() -> None:
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trigger_maintain_draft_versions ON generated_drafts;")
    op.execute("DROP FUNCTION IF EXISTS maintain_draft_versions();")

    # Drop draft_citations indexes and table
    op.drop_index('ix_draft_citations_document_id', table_name='draft_citations')
    op.drop_index('ix_draft_citations_draft_id', table_name='draft_citations')
    op.drop_table('draft_citations')

    # Drop generated_drafts indexes and table
    op.drop_index('ix_generated_drafts_is_current', table_name='generated_drafts')
    op.drop_index('ix_generated_drafts_project_id', table_name='generated_drafts')
    op.drop_table('generated_drafts')
