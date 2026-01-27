"""add project thread integration

Revision ID: i4k8l9m0n1o2
Revises: h3j7k8l9m0n1
Create Date: 2026-01-27 12:00:00.000000

This migration enables integration between Research Projects and Chat systems by:
1. Creating project_threads junction table for many-to-many relationships
2. Adding optional source_project_id to threads for quick project lookup
3. Adding rag_document_scope JSONB column to threads for RAG filtering
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'i4k8l9m0n1o2'
down_revision = 'h3j7k8l9m0n1'
branch_labels = None
depends_on = None


def upgrade():
    # Create project_threads junction table
    op.create_table(
        'project_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('thread_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('link_type', sa.String(length=50), nullable=False, server_default='manual'),
        sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('linked_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('context_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['thread_id'], ['threads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_by_id'], ['users.id']),
        sa.UniqueConstraint('project_id', 'thread_id', name='uq_project_thread'),
        comment='Junction table linking research projects to chat threads'
    )

    # Create indexes for efficient queries
    op.create_index('idx_project_threads_project_id', 'project_threads', ['project_id'])
    op.create_index('idx_project_threads_thread_id', 'project_threads', ['thread_id'])
    op.create_index('idx_project_threads_linked_by', 'project_threads', ['linked_by_id'])

    # Add optional source_project_id to threads table
    op.add_column(
        'threads',
        sa.Column(
            'source_project_id',
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment='Project that originated this thread (if started from project)'
        )
    )
    op.create_index('idx_threads_source_project', 'threads', ['source_project_id'])
    op.create_foreign_key(
        'fk_threads_source_project',
        'threads',
        'collections',
        ['source_project_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add rag_document_scope JSONB column to threads
    op.add_column(
        'threads',
        sa.Column(
            'rag_document_scope',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Document IDs for RAG filtering. Format: {"document_ids": ["uuid1", "uuid2"]}'
        )
    )


def downgrade():
    # Remove threads columns
    op.drop_constraint('fk_threads_source_project', 'threads', type_='foreignkey')
    op.drop_index('idx_threads_source_project', 'threads')
    op.drop_column('threads', 'rag_document_scope')
    op.drop_column('threads', 'source_project_id')

    # Drop project_threads table and indexes
    op.drop_index('idx_project_threads_linked_by', 'project_threads')
    op.drop_index('idx_project_threads_thread_id', 'project_threads')
    op.drop_index('idx_project_threads_project_id', 'project_threads')
    op.drop_table('project_threads')
