"""Create project_memories table

Revision ID: w1x2y3z4a5b6
Revises: v0a1b2c3d4e5
Create Date: 2026-06-06 00:00:00.000000

Project-scoped persistent memory: short, durable facts the user saves for a
project (via the chat `/remember` command or the project UI). Every thread in
the project recalls them, so they are injected into the agent system prompt
when a chat is bound to the project.

Distinct from `project_notes` (long markdown documents the user reads); memories
are terse instructions/facts the agent honors and are never shown as notes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'w1x2y3z4a5b6'
down_revision = 'v0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'project_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('collections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('source', sa.String(32), nullable=False, server_default='manual'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('ix_project_memories_project_id', 'project_memories', ['project_id'])
    op.create_index('ix_project_memories_user_id', 'project_memories', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_project_memories_user_id', table_name='project_memories')
    op.drop_index('ix_project_memories_project_id', table_name='project_memories')
    op.drop_table('project_memories')
