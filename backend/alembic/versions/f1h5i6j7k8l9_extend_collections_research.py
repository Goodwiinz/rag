"""Extend collections table for research projects (User Story 4)

Revision ID: f1h5i6j7k8l9
Revises: e0g4h5i6j7k8
Create Date: 2026-01-14 19:40:00.000000

This migration extends the collections table to support research project management.
Collections can now function as research projects with additional metadata.

Changes:
- Add project_type column (research, literature_review, thesis, paper)
- Add research_status column (active, paused, completed, archived)
- Add research_goals column (TEXT) for project objectives
- Add deadline column (TIMESTAMP) for project deadline
- Add tags column (JSONB array) for project categorization
- Add is_private column (BOOLEAN) - always TRUE for Phase 3
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'f1h5i6j7k8l9'
down_revision = 'e0g4h5i6j7k8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add research project columns
    op.add_column('collections', sa.Column('project_type', sa.String(50), nullable=False, server_default='research'))
    op.add_column('collections', sa.Column('research_status', sa.String(50), nullable=False, server_default='active'))
    op.add_column('collections', sa.Column('research_goals', sa.Text, nullable=True))
    op.add_column('collections', sa.Column('deadline', sa.DateTime(timezone=True), nullable=True))
    op.add_column('collections', sa.Column('tags', postgresql.JSONB, nullable=False, server_default='[]'))
    op.add_column('collections', sa.Column('is_private', sa.Boolean, nullable=False, server_default='true'))

    # Add index on research_status for filtering
    op.create_index('ix_collections_research_status', 'collections', ['research_status'])


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_collections_research_status', table_name='collections')

    # Drop columns
    op.drop_column('collections', 'is_private')
    op.drop_column('collections', 'tags')
    op.drop_column('collections', 'deadline')
    op.drop_column('collections', 'research_goals')
    op.drop_column('collections', 'research_status')
    op.drop_column('collections', 'project_type')
