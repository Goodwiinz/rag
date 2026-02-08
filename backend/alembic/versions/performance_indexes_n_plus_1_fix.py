"""Add performance indexes for N+1 query optimization

Revision ID: perf_indexes_n1
Revises: 
Create Date: 2024-02-08 06:30:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'perf_indexes_n1'
down_revision = None  # Replace with latest revision ID
branch_labels = None
depends_on = None

def upgrade():
    """Add performance indexes to optimize N+1 queries"""
    
    # User table indexes
    op.create_index('idx_user_email_active', 'users', ['email', 'is_active'])
    op.create_index('idx_user_org_role', 'users', ['organization_id', 'role'])
    op.create_index('idx_user_org_active', 'users', ['organization_id', 'is_active'])
    op.create_index('idx_user_last_login_active', 'users', ['last_login', 'is_active'])
    op.create_index('idx_user_role_active', 'users', ['role', 'is_active'])
    
    # Document table indexes
    op.create_index('idx_document_org_user', 'documents', ['organization_id', 'uploaded_by_user_id'])
    op.create_index('idx_document_user_created', 'documents', ['uploaded_by_user_id', 'created_at'])
    op.create_index('idx_document_org_status', 'documents', ['organization_id', 'processing_status'])
    op.create_index('idx_document_org_type', 'documents', ['organization_id', 'document_type'])
    op.create_index('idx_document_status_created', 'documents', ['processing_status', 'created_at'])
    op.create_index('idx_document_embedded_indexed', 'documents', ['is_embedded', 'is_indexed'])
    op.create_index('idx_document_org_public', 'documents', ['organization_id', 'is_public'])
    
    # RAG Queries additional indexes
    op.create_index('idx_rag_queries_user_created', 'rag_queries', ['user_id', 'created_at'])
    op.create_index('idx_rag_queries_org_created', 'rag_queries', ['organization_id', 'created_at'])
    op.create_index('idx_rag_queries_rating_helpful', 'rag_queries', ['user_rating', 'was_helpful'])
    op.create_index('idx_rag_queries_confidence_type', 'rag_queries', ['answer_confidence', 'answer_type'])
    op.create_index('idx_rag_queries_performance', 'rag_queries', ['total_duration_ms', 'cache_hit'])
    
    # Search Sessions additional indexes
    op.create_index('idx_search_sessions_user_start', 'search_sessions', ['user_id', 'start_time'])
    op.create_index('idx_search_sessions_duration', 'search_sessions', ['session_duration', 'search_count'])
    op.create_index('idx_search_sessions_org_start', 'search_sessions', ['organization_id', 'start_time'])
    
    # Search Events additional indexes
    op.create_index('idx_search_events_user_created', 'search_events', ['user_id', 'created_at'])
    op.create_index('idx_search_events_rating_response', 'search_events', ['user_rating', 'response_time'])
    op.create_index('idx_search_events_results_clicks', 'search_events', ['results_count', 'clicked_results'])
    op.create_index('idx_search_events_session_created', 'search_events', ['session_id', 'created_at'])
    
    # Conversation table indexes
    op.create_index('idx_conversation_workspace_activity', 'conversations', ['workspace_id', 'last_activity_at'])
    op.create_index('idx_conversation_creator_created', 'conversations', ['created_by_id', 'created_at'])
    op.create_index('idx_conversation_workspace_archived', 'conversations', ['workspace_id', 'is_archived'])
    op.create_index('idx_conversation_pinned_activity', 'conversations', ['is_pinned', 'last_activity_at'])
    op.create_index('idx_conversation_title_search', 'conversations', ['title'])


def downgrade():
    """Remove performance indexes"""
    
    # User table indexes
    op.drop_index('idx_user_email_active')
    op.drop_index('idx_user_org_role')
    op.drop_index('idx_user_org_active')
    op.drop_index('idx_user_last_login_active')
    op.drop_index('idx_user_role_active')
    
    # Document table indexes
    op.drop_index('idx_document_org_user')
    op.drop_index('idx_document_user_created')
    op.drop_index('idx_document_org_status')
    op.drop_index('idx_document_org_type')
    op.drop_index('idx_document_status_created')
    op.drop_index('idx_document_embedded_indexed')
    op.drop_index('idx_document_org_public')
    
    # RAG Queries additional indexes
    op.drop_index('idx_rag_queries_user_created')
    op.drop_index('idx_rag_queries_org_created')
    op.drop_index('idx_rag_queries_rating_helpful')
    op.drop_index('idx_rag_queries_confidence_type')
    op.drop_index('idx_rag_queries_performance')
    
    # Search Sessions additional indexes
    op.drop_index('idx_search_sessions_user_start')
    op.drop_index('idx_search_sessions_duration')
    op.drop_index('idx_search_sessions_org_start')
    
    # Search Events additional indexes
    op.drop_index('idx_search_events_user_created')
    op.drop_index('idx_search_events_rating_response')
    op.drop_index('idx_search_events_results_clicks')
    op.drop_index('idx_search_events_session_created')
    
    # Conversation table indexes
    op.drop_index('idx_conversation_workspace_activity')
    op.drop_index('idx_conversation_creator_created')
    op.drop_index('idx_conversation_workspace_archived')
    op.drop_index('idx_conversation_pinned_activity')
    op.drop_index('idx_conversation_title_search')