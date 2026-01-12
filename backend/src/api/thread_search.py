"""
Thread and Message Search API endpoints.

Provides full-text search functionality for threads and chat messages
with filtering, highlighting, and relevance ranking.
"""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status, BackgroundTasks
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.user import User
from ..models.thread import ThreadStatus
from ..models.chat_message import MessageRole
from ..services.thread_message_search_service import (
    thread_message_search_service,
    ThreadSearchRequest,
    ThreadSearchFilter,
    ThreadSearchSortOrder,
    ThreadSearchResponse,
    MessageSearchRequest,
    MessageSearchFilter,
    MessageSearchSortOrder,
    MessageSearchResponse,
    CombinedSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Thread & Message Search"])


# =============================================================================
# Thread Search Endpoints
# =============================================================================

@router.post("/threads", response_model=ThreadSearchResponse)
async def search_threads(
    request: ThreadSearchRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search threads using PostgreSQL full-text search.
    
    Searches thread titles and summaries, and optionally includes threads
    that have matching messages. Returns relevance-ranked results with
    highlighted snippets.
    
    **Features:**
    - Full-text search on thread titles and summaries
    - Filter by conversation, workspace, status, date range
    - Sort by relevance, date, message count, or last activity
    - Highlighted matching terms in results
    - Shows count of matching messages per thread
    """
    try:
        result = thread_message_search_service.search_threads(
            request=request,
            user_id=current_user.id,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Error in thread search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/threads", response_model=ThreadSearchResponse)
async def search_threads_get(
    query: str = Query(..., min_length=1, description="Search query"),
    conversation_id: Optional[UUID] = Query(None, description="Filter by conversation ID"),
    workspace_id: Optional[UUID] = Query(None, description="Filter by workspace ID"),
    status_filter: Optional[List[str]] = Query(None, description="Filter by thread status (active, resolved, archived)"),
    date_from: Optional[datetime] = Query(None, description="Filter threads created after this date"),
    date_to: Optional[datetime] = Query(None, description="Filter threads created before this date"),
    min_message_count: Optional[int] = Query(None, ge=0, description="Minimum message count"),
    sort_order: str = Query("relevance", description="Sort order: relevance, date_desc, date_asc, message_count, last_activity"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search threads using GET request with query parameters.
    
    A more RESTful alternative to POST for simple searches.
    """
    try:
        # Build filter object
        filters = ThreadSearchFilter(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            status=[ThreadStatus(s) for s in status_filter] if status_filter else None,
            date_from=date_from,
            date_to=date_to,
            min_message_count=min_message_count
        ) if any([conversation_id, workspace_id, status_filter, date_from, date_to, min_message_count]) else None
        
        # Map sort order string to enum
        sort_mapping = {
            "relevance": ThreadSearchSortOrder.RELEVANCE,
            "date_desc": ThreadSearchSortOrder.DATE_DESC,
            "date_asc": ThreadSearchSortOrder.DATE_ASC,
            "message_count": ThreadSearchSortOrder.MESSAGE_COUNT,
            "last_activity": ThreadSearchSortOrder.LAST_ACTIVITY,
        }
        sort_enum = sort_mapping.get(sort_order, ThreadSearchSortOrder.RELEVANCE)
        
        request = ThreadSearchRequest(
            query=query,
            filters=filters,
            sort_order=sort_enum,
            limit=limit,
            offset=offset
        )
        
        result = thread_message_search_service.search_threads(
            request=request,
            user_id=current_user.id,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Error in thread search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


# =============================================================================
# Message Search Endpoints
# =============================================================================

@router.post("/messages", response_model=MessageSearchResponse)
async def search_messages(
    request: MessageSearchRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search messages using PostgreSQL full-text search.
    
    Searches message content across all accessible threads.
    Returns relevance-ranked results with highlighted snippets
    and thread context.
    
    **Features:**
    - Full-text search on message content
    - Filter by thread, conversation, workspace, user, role
    - Filter by date range and citation presence
    - Sort by relevance or date
    - Highlighted matching terms in results
    - Thread context (title, conversation) in results
    """
    try:
        result = thread_message_search_service.search_messages(
            request=request,
            user_id=current_user.id,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Error in message search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/messages", response_model=MessageSearchResponse)
async def search_messages_get(
    query: str = Query(..., min_length=1, description="Search query"),
    thread_id: Optional[UUID] = Query(None, description="Filter by thread ID"),
    conversation_id: Optional[UUID] = Query(None, description="Filter by conversation ID"),
    workspace_id: Optional[UUID] = Query(None, description="Filter by workspace ID"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID (message author)"),
    roles: Optional[List[str]] = Query(None, description="Filter by message role (user, assistant, system, tool)"),
    date_from: Optional[datetime] = Query(None, description="Filter messages created after this date"),
    date_to: Optional[datetime] = Query(None, description="Filter messages created before this date"),
    has_citations: Optional[bool] = Query(None, description="Filter by citation presence"),
    sort_order: str = Query("relevance", description="Sort order: relevance, date_desc, date_asc"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search messages using GET request with query parameters.
    
    A more RESTful alternative to POST for simple searches.
    """
    try:
        # Build filter object
        filters = MessageSearchFilter(
            thread_id=thread_id,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            roles=[MessageRole(r) for r in roles] if roles else None,
            date_from=date_from,
            date_to=date_to,
            has_citations=has_citations
        ) if any([thread_id, conversation_id, workspace_id, user_id, roles, date_from, date_to, has_citations is not None]) else None
        
        # Map sort order string to enum
        sort_mapping = {
            "relevance": MessageSearchSortOrder.RELEVANCE,
            "date_desc": MessageSearchSortOrder.DATE_DESC,
            "date_asc": MessageSearchSortOrder.DATE_ASC,
        }
        sort_enum = sort_mapping.get(sort_order, MessageSearchSortOrder.RELEVANCE)
        
        request = MessageSearchRequest(
            query=query,
            filters=filters,
            sort_order=sort_enum,
            limit=limit,
            offset=offset
        )
        
        result = thread_message_search_service.search_messages(
            request=request,
            user_id=current_user.id,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Error in message search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


# =============================================================================
# Combined Search Endpoint
# =============================================================================

@router.get("/combined", response_model=CombinedSearchResponse)
async def combined_search(
    query: str = Query(..., min_length=1, description="Search query"),
    workspace_id: Optional[UUID] = Query(None, description="Filter by workspace ID"),
    conversation_id: Optional[UUID] = Query(None, description="Filter by conversation ID"),
    limit: int = Query(20, ge=1, le=50, description="Max results to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search across both threads and messages in a single query.
    
    Returns a combined list of results ranked by relevance.
    Thread results are given slightly higher weight than messages.
    
    **Use cases:**
    - Quick search across all content
    - Workspace-wide or conversation-wide search
    - Finding related threads and messages together
    """
    try:
        result = thread_message_search_service.combined_search(
            query=query,
            user_id=current_user.id,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            limit=limit,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Error in combined search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


# =============================================================================
# Search Suggestions Endpoint
# =============================================================================

@router.get("/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1, description="Partial search query"),
    workspace_id: Optional[UUID] = Query(None, description="Limit suggestions to workspace"),
    limit: int = Query(5, ge=1, le=10, description="Max suggestions to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get search suggestions based on thread titles and recent searches.
    
    Provides autocomplete functionality for the search input.
    """
    try:
        # Simple suggestion based on thread titles
        from sqlalchemy import text
        
        suggestion_sql = """
            SELECT DISTINCT t.title
            FROM threads t
            JOIN conversations c ON t.conversation_id = c.id
            JOIN workspaces w ON c.workspace_id = w.id
            WHERE t.is_deleted = false
                AND c.is_deleted = false
                AND w.is_deleted = false
                AND t.title IS NOT NULL
                AND LOWER(t.title) LIKE LOWER(:query_pattern)
        """
        
        params = {'query_pattern': f'%{query}%'}
        
        if workspace_id:
            suggestion_sql += " AND w.id = :workspace_id"
            params['workspace_id'] = str(workspace_id)
        
        suggestion_sql += " ORDER BY t.last_message_at DESC LIMIT :limit"
        params['limit'] = limit
        
        result = db.execute(text(suggestion_sql), params)
        suggestions = [row.title for row in result if row.title]
        
        return {
            "query": query,
            "suggestions": suggestions
        }
    except Exception as e:
        logger.error(f"Error getting search suggestions: {e}")
        return {"query": query, "suggestions": []}


# =============================================================================
# Search Health Check
# =============================================================================

@router.get("/health")
async def search_health_check(
    db: Session = Depends(get_db)
):
    """
    Check health of the thread/message search system.
    
    Verifies that full-text search indexes exist and are functional.
    """
    try:
        from sqlalchemy import text
        
        # Check if GIN indexes exist
        index_check_sql = """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename IN ('threads', 'chat_messages')
                AND indexdef LIKE '%GIN%'
        """
        
        result = db.execute(text(index_check_sql))
        indexes = [{"name": row.indexname, "definition": row.indexdef} for row in result]
        
        # Try a simple search to verify functionality
        test_search_sql = """
            SELECT COUNT(*) FROM threads 
            WHERE search_vector @@ plainto_tsquery('test')
        """
        
        try:
            db.execute(text(test_search_sql))
            search_functional = True
        except Exception:
            search_functional = False
        
        return {
            "status": "healthy" if search_functional else "degraded",
            "search_functional": search_functional,
            "gin_indexes": indexes,
            "index_count": len(indexes)
        }
    except Exception as e:
        logger.error(f"Search health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
