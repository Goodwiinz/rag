"""Create project_notes table (User Story 4)

Revision ID: g2i6j7k8l9m0
Revises: f1h5i6j7k8l9
Create Date: 2026-01-14 19:45:00.000000

This migration creates the project_notes table for storing markdown notes
within research projects.

Changes:
- Create project_notes table with project_id and user_id foreign keys
- Add title and content (markdown) columns
- Add linked_document_ids (JSONB array) to link notes to specific documents
- Add tags (JSONB array) for note organization
- Add is_pinned boolean flag for pinning important notes
- Add indexes on project_id and user_id for fast lookups
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'g2i6j7k8l9m0'
down_revision = 'f1h5i6j7k8l9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create project_notes table
    op.create_table(
        'project_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('collections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('linked_document_ids', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('tags', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('is_pinned', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # Create indexes for fast lookups
    op.create_index('ix_project_notes_project_id', 'project_notes', ['project_id'])
    op.create_index('ix_project_notes_user_id', 'project_notes', ['user_id'])
    op.create_index('ix_project_notes_is_pinned', 'project_notes', ['is_pinned'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_project_notes_is_pinned', table_name='project_notes')
    op.drop_index('ix_project_notes_user_id', table_name='project_notes')
    op.drop_index('ix_project_notes_project_id', table_name='project_notes')

    # Drop table
    op.drop_table('project_notes')
