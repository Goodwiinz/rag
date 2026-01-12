"""Add full-text search for threads and messages

Revision ID: b2c3d4e5f6g7
Revises: c8e2f1a9d3b7
Create Date: 2026-01-12 02:30:00.000000

This migration adds PostgreSQL full-text search capability for threads and chat messages:
- Adds search_vector columns (tsvector) to threads and chat_messages tables
- Creates GIN indexes for fast full-text search
- Creates a trigger to automatically update search vectors on insert/update
- Adds combined search view for unified thread+message search
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'c8e2f1a9d3b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add search_vector column to threads table
    op.add_column(
        'threads',
        sa.Column('search_vector', postgresql.TSVECTOR, nullable=True)
    )
    
    # Add search_vector column to chat_messages table
    op.add_column(
        'chat_messages',
        sa.Column('search_vector', postgresql.TSVECTOR, nullable=True)
    )
    
    # Create GIN indexes for full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_threads_search_vector
        ON threads USING GIN (search_vector)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_search_vector
        ON chat_messages USING GIN (search_vector)
    """)
    
    # Create additional indexes for search performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_threads_title_gin
        ON threads USING GIN (to_tsvector('english', COALESCE(title, '')))
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_content_gin
        ON chat_messages USING GIN (to_tsvector('english', COALESCE(content, '')))
    """)
    
    # Create index on threads.conversation_id for joins
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_threads_conversation_status
        ON threads (conversation_id, status)
    """)
    
    # Create index on chat_messages.thread_id for joins
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_role
        ON chat_messages (thread_id, role)
    """)
    
    # Create function to update thread search vector
    op.execute("""
        CREATE OR REPLACE FUNCTION update_thread_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.summary, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for thread search vector updates
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_update_thread_search_vector ON threads;
        CREATE TRIGGER trigger_update_thread_search_vector
        BEFORE INSERT OR UPDATE OF title, summary ON threads
        FOR EACH ROW
        EXECUTE FUNCTION update_thread_search_vector();
    """)
    
    # Create function to update chat_message search vector
    op.execute("""
        CREATE OR REPLACE FUNCTION update_chat_message_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.content, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for chat_message search vector updates
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_update_chat_message_search_vector ON chat_messages;
        CREATE TRIGGER trigger_update_chat_message_search_vector
        BEFORE INSERT OR UPDATE OF content ON chat_messages
        FOR EACH ROW
        EXECUTE FUNCTION update_chat_message_search_vector();
    """)
    
    # Backfill existing threads with search vectors
    op.execute("""
        UPDATE threads
        SET search_vector = 
            setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(summary, '')), 'B')
        WHERE search_vector IS NULL
    """)
    
    # Backfill existing chat_messages with search vectors
    op.execute("""
        UPDATE chat_messages
        SET search_vector = to_tsvector('english', COALESCE(content, ''))
        WHERE search_vector IS NULL
    """)
    
    # Add index on citations for snippet search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_citations_snippet_gin
        ON citations USING GIN (to_tsvector('english', COALESCE(snippet, '')))
    """)


def downgrade() -> None:
    # Drop citation index
    op.execute("DROP INDEX IF EXISTS idx_citations_snippet_gin")
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trigger_update_chat_message_search_vector ON chat_messages")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_thread_search_vector ON threads")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS update_chat_message_search_vector()")
    op.execute("DROP FUNCTION IF EXISTS update_thread_search_vector()")
    
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_chat_messages_thread_role")
    op.execute("DROP INDEX IF EXISTS idx_threads_conversation_status")
    op.execute("DROP INDEX IF EXISTS idx_chat_messages_content_gin")
    op.execute("DROP INDEX IF EXISTS idx_threads_title_gin")
    op.execute("DROP INDEX IF EXISTS idx_chat_messages_search_vector")
    op.execute("DROP INDEX IF EXISTS idx_threads_search_vector")
    
    # Drop columns
    op.drop_column('chat_messages', 'search_vector')
    op.drop_column('threads', 'search_vector')
