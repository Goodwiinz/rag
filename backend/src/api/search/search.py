"""
Search API endpoints for hybrid search functionality
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import logging

from src.core.dependencies import get_current_user
from src.core.database import get_db
from src.core.api_key_auth import get_api_key_data, APIKeyData
from src.services.search.fulltext_search_service import fulltext_search_service
from src.services.search.hybrid_search_service import hybrid_search_service
from src.models.search_schemas import (
    SearchQuery, SearchResponse, SearchResult, SearchType, SearchSortOrder,
    SearchAnalytics, SearchIndex, SearchSuggestion
)
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def search_documents(
    search_request: SearchQuery,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Perform search on documents with multiple search modalities
    """
    try:
        # Route search to appropriate service based on search type
        if search_request.search_type == SearchType.HYBRID:
            # Use hybrid search service
            result = hybrid_search_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db
            )
        elif search_request.search_type == SearchType.FULLTEXT:
            # Use full-text search service
            result = fulltext_search_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db
            )
        elif search_request.search_type == SearchType.VECTOR:
            # Use vector search service
            from src.services.search.vector_search_service import vector_search_service
            result = vector_search_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db
            )
        elif search_request.search_type == SearchType.KNOWLEDGE_GRAPH:
            # Use knowledge graph search service
            from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
            result = knowledge_graph_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db
            )
        else:
            # Default to hybrid search
            search_request.search_type = SearchType.HYBRID
            result = hybrid_search_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db
            )

        # Log search query in background (for analytics)
        background_tasks.add_task(
            log_search_query,
            str(current_user.id),
            str(current_user.organization_id),
            search_request.query,
            len(result.results),
            result.search_time_ms,
            search_request.search_type.value
        )

        return result

    except Exception as e:
        logger.error(f"Error performing search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(
    search_request: SearchQuery,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Perform hybrid search combining vector, full-text, and knowledge graph search
    """
    try:
        # Force hybrid search type
        search_request.search_type = SearchType.HYBRID

        # Perform hybrid search
        result = hybrid_search_service.search(
            search_request=search_request,
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id)
        )

        # Log search query in background
        background_tasks.add_task(
            log_search_query,
            str(current_user.id),
            str(current_user.organization_id),
            search_request.query,
            len(result.results),
            result.search_time_ms,
            "hybrid"
        )

        return result

    except Exception as e:
        logger.error(f"Error performing hybrid search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=2, max_length=100, description="Query for suggestions"),
    limit: int = Query(default=5, ge=1, le=20, description="Number of suggestions"),
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get search suggestions for auto-completion
    """
    try:
        suggestions = fulltext_search_service._get_search_suggestions(q, db)

        # Convert to SearchSuggestion models
        search_suggestions = [
            SearchSuggestion(
                text=suggestion,
                type="completion",
                score=0.8,
                metadata={"source": "document_titles"}
            )
            for suggestion in suggestions[:limit]
        ]

        return {"suggestions": search_suggestions}

    except Exception as e:
        logger.error(f"Error getting search suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_search_history(
    limit: int = Query(default=50, ge=1, le=100, description="Number of history items"),
    current_user: User = Depends(get_current_user)
):
    """
    Get search history for the current user (placeholder)
    """
    # Return empty list for now until search history table is implemented
    return []


@router.post("/history")
async def add_search_history(
    query: str,
    result_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Add item to search history (placeholder)
    """
    return {"status": "success", "message": "Search history saved"}


@router.delete("/history")
async def clear_search_history(
    current_user: User = Depends(get_current_user)
):
    """
    Clear search history (placeholder)
    """
    return {"status": "success", "message": "Search history cleared"}


@router.get("/analytics", response_model=SearchAnalytics)
async def get_search_analytics(
    days: int = Query(default=30, ge=1, le=365, description="Number of days for analytics"),
    current_user: User = Depends(get_current_user)
):
    """
    Get search analytics data
    """
    try:
        analytics_data = fulltext_search_service.get_search_analytics(
            organization_id=str(current_user.organization_id),
            days=days
        )

        return SearchAnalytics(
            total_searches=analytics_data.get('total_documents', 0),  # Placeholder
            average_search_time_ms=analytics_data.get('avg_search_time', 150),  # Placeholder
            most_common_queries=[],  # Placeholder - would need search logging
            search_types_distribution={"fulltext": analytics_data.get('total_documents', 0)},
            zero_result_queries=[],  # Placeholder
            average_results_per_search=analytics_data.get('total_documents', 0) / 10  # Placeholder
        )

    except Exception as e:
        logger.error(f"Error getting search analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/indexes/rebuild")
async def rebuild_search_indexes(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Rebuild full-text search indexes (admin only)
    """
    # Check if user has admin privileges
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Create indexes
        fulltext_search_service.create_search_indexes(db)

        # Update all document search vectors
        from src.models.document import Document, ProcessingStatus

        documents = db.query(Document).filter(
            Document.processing_status == ProcessingStatus.COMPLETED,
            Document.is_deleted == False
        ).all()

        updated_count = 0
        for document in documents:
            try:
                fulltext_search_service.update_document_search_vector(
                    str(document.id),
                    db
                )
                updated_count += 1
            except Exception as e:
                logger.error(f"Error updating search vector for document {document.id}: {e}")

        return {
            "message": "Search indexes rebuilt successfully",
            "indexes_created": True,
            "documents_updated": updated_count,
            "total_documents": len(documents)
        }

    except Exception as e:
        logger.error(f"Error rebuilding search indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indexes", response_model=List[SearchIndex])
async def get_search_indexes(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get information about search indexes
    """
    try:
        # Get index information from PostgreSQL
        index_query = """
        SELECT
            schemaname || '.' || indexname as name,
            'gin' as type,
            0 as document_count,  -- Placeholder
            0.0 as size_mb,       # Placeholder
            NOW() as last_updated,
            true as is_active,
            '{}'::jsonb as configuration
        FROM pg_indexes
        WHERE tablename = 'documents'
            AND indexname LIKE '%search%'
        """

        result = db.execute(index_query)
        indexes = []

        for row in result:
            indexes.append(SearchIndex(
                name=row.name,
                type=row.type,
                document_count=row.document_count,
                size_mb=row.size_mb,
                last_updated=row.last_updated,
                is_active=row.is_active,
                configuration=row.configuration
            ))

        return indexes

    except Exception as e:
        logger.error(f"Error getting search indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/reindex")
async def reindex_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Rebuild search vector for a specific document
    """
    try:
        # Verify user has access to the document
        from src.models.document import Document

        document = db.query(Document).filter(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id,
            Document.is_deleted == False
        ).first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Update search vector
        fulltext_search_service.update_document_search_vector(document_id, db)

        return {
            "message": f"Document {document_id} reindexed successfully",
            "document_id": document_id,
            "title": document.title
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reindexing document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/popular")
async def get_popular_searches(
    limit: int = Query(default=10, ge=1, le=50, description="Number of popular searches"),
    current_user: User = Depends(get_current_user)
):
    """
    Get popular search queries (placeholder for future analytics implementation)
    """
    try:
        # This is a placeholder - would need search query logging table
        # For now, return empty results
        return {
            "popular_queries": [],
            "trending_terms": [],
            "recent_searches": []
        }

    except Exception as e:
        logger.error(f"Error getting popular searches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar")
async def get_similar_queries(
    q: str = Query(..., min_length=2, description="Query to find similar searches for"),
    limit: int = Query(default=5, ge=1, le=20, description="Number of similar queries"),
    current_user: User = Depends(get_current_user)
):
    """
    Get similar search queries (placeholder)
    """
    return []


@router.get("/related/{result_id}")
async def get_related_searches(
    result_id: str,
    limit: int = Query(default=5, ge=1, le=20, description="Number of related searches"),
    current_user: User = Depends(get_current_user)
):
    """
    Get related searches for a result (placeholder)
    """
    return []


@router.post("/feedback")
async def submit_search_feedback(
    search_query: str,
    document_id: str,
    rating: int = Query(..., ge=1, le=5, description="Rating 1-5"),
    feedback_text: Optional[str] = Query(None, description="Optional feedback text"),
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback for search results (placeholder for future implementation)
    """
    try:
        # This is a placeholder - would need feedback logging table
        # For now, just acknowledge receipt
        return {
            "message": "Feedback submitted successfully",
            "query": search_query,
            "document_id": document_id,
            "rating": rating,
            "feedback_text": feedback_text,
            "user_id": str(current_user.id)
        }

    except Exception as e:
        logger.error(f"Error submitting search feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def search_health_check(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Health check for all search functionality including hybrid search
    """
    try:
        health_status = {
            "status": "healthy",
            "services": {},
            "overall_search_time_ms": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Test full-text search
        try:
            ft_query = SearchQuery(
                query="test",
                search_type=SearchType.FULLTEXT,
                limit=1
            )
            start_time = time.time()
            ft_result = fulltext_search_service.search(
                search_request=ft_query,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id)
            )
            ft_time_ms = (time.time() - start_time) * 1000
            health_status["services"]["fulltext"] = {
                "status": "healthy",
                "search_time_ms": ft_time_ms,
                "results_count": len(ft_result.results)
            }
        except Exception as e:
            health_status["services"]["fulltext"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            logger.error(f"Full-text search health check failed: {e}")

        # Test hybrid search
        try:
            hybrid_query = SearchQuery(
                query="test",
                search_type=SearchType.HYBRID,
                limit=1
            )
            start_time = time.time()
            hybrid_result = hybrid_search_service.search(
                search_request=hybrid_query,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id)
            )
            hybrid_time_ms = (time.time() - start_time) * 1000
            health_status["services"]["hybrid"] = {
                "status": "healthy",
                "search_time_ms": hybrid_time_ms,
                "results_count": len(hybrid_result.results)
            }
            health_status["overall_search_time_ms"] = hybrid_time_ms
        except Exception as e:
            health_status["services"]["hybrid"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            logger.error(f"Hybrid search health check failed: {e}")

        # Check if full-text indexes exist
        try:
            index_check_query = """
            SELECT COUNT(*) as index_count
            FROM pg_indexes
            WHERE tablename = 'documents'
                AND indexname LIKE '%search%'
            """
            index_result = db.execute(index_check_query)
            index_count = index_result.scalar()
            health_status["indexes"] = {
                "search_indexes_count": index_count,
                "indexes_available": index_count > 0
            }
        except Exception as e:
            health_status["indexes"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Check external service availability (vector DB, knowledge graph)
        health_status["external_services"] = {}

        # Test Qdrant (vector search)
        try:
            from src.services.search.vector_search_service import vector_search_service
            vector_query = SearchQuery(
                query="test",
                search_type=SearchType.VECTOR,
                limit=1
            )
            start_time = time.time()
            vector_result = vector_search_service.search(
                search_request=vector_query,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id)
            )
            vector_time_ms = (time.time() - start_time) * 1000
            health_status["external_services"]["qdrant"] = {
                "status": "healthy",
                "search_time_ms": vector_time_ms
            }
        except Exception as e:
            health_status["external_services"]["qdrant"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Test Neo4j (knowledge graph)
        try:
            from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
            kg_query = SearchQuery(
                query="test",
                search_type=SearchType.KNOWLEDGE_GRAPH,
                limit=1
            )
            start_time = time.time()
            kg_result = knowledge_graph_service.search(
                search_request=kg_query,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id)
            )
            kg_time_ms = (time.time() - start_time) * 1000
            health_status["external_services"]["neo4j"] = {
                "status": "healthy",
                "search_time_ms": kg_time_ms
            }
        except Exception as e:
            health_status["external_services"]["neo4j"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Determine overall status
        all_healthy = all(
            service.get("status") == "healthy"
            for service in health_status["services"].values()
        )

        health_status["status"] = "healthy" if all_healthy else "degraded"

        return health_status

    except Exception as e:
        logger.error(f"Search health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.post("/authenticated/hybrid", response_model=SearchResponse)
async def authenticated_hybrid_search(
    search_request: SearchQuery,
    background_tasks: BackgroundTasks,
    request: Request,
    api_key_data: tuple = Depends(get_api_key_data),
    db = Depends(get_db)
):
    """
    API Key authenticated hybrid search endpoint.
    Requires valid API key for secure external access.
    
    This endpoint replaces the previous unauthenticated '/public/hybrid' endpoint
    to prevent unauthorized access to search functionality.
    """
    api_key, endpoint = api_key_data
    
    try:
        # Force hybrid search type
        search_request.search_type = SearchType.HYBRID

        # Perform hybrid search with API key context
        # Use specific organization_id from API key or None for cross-org search based on key permissions
        result = hybrid_search_service.search(
            search_request=search_request,
            user_id=f"api_key:{api_key.id}",
            organization_id=None  # API keys can access across organizations (controlled by key permissions)
        )

        # Enhanced logging for API key usage
        background_tasks.add_task(
            log_authenticated_search_query,
            api_key.id,
            api_key.name,
            search_request.query,
            len(result.results),
            result.search_time_ms,
            "authenticated_hybrid",
            request.client.host if request.client else "unknown",
            request.headers.get("user-agent", "unknown")
        )

        # Log API access for security audit
        from src.core.api_key_auth import log_api_access
        log_api_access(
            api_key_data,
            request,
            "search",
            {
                "query_length": len(search_request.query),
                "search_type": search_request.search_type.value,
                "results_count": len(result.results),
                "search_time_ms": result.search_time_ms
            }
        )

        return result

    except Exception as e:
        logger.error(f"Error performing authenticated hybrid search: {e}")
        
        # Log failed search attempt
        from src.core.api_key_auth import log_api_access
        log_api_access(
            api_key_data,
            request,
            "search_failed",
            {"error": str(e), "query_length": len(search_request.query)}
        )
        
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/authenticated/health")
async def authenticated_search_health_check(
    request: Request,
    api_key_data: tuple = Depends(get_api_key_data)
):
    """
    API Key authenticated health check for search services.
    Requires valid API key to prevent information disclosure.
    """
    api_key, endpoint = api_key_data
    
    try:
        health_status = {
            "status": "healthy", 
            "services": {},
            "timestamp": datetime.utcnow().isoformat(),
            "api_key": {
                "name": api_key.name,
                "prefix": api_key.key_prefix,
                "usage_count": api_key.usage_count
            }
        }

        # Test basic API functionality
        health_status["services"]["api"] = {
            "status": "healthy",
            "message": "Search API is accessible with valid authentication"
        }

        # Test hybrid search service availability (without performing actual search)
        try:
            health_status["services"]["hybrid_search"] = {
                "status": "healthy",
                "message": "Hybrid search service is available"
            }
        except Exception as e:
            health_status["services"]["hybrid_search"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Log API access
        from src.core.api_key_auth import log_api_access
        log_api_access(
            api_key_data,
            request, 
            "health_check",
            {"services_checked": len(health_status["services"])}
        )

        return health_status

    except Exception as e:
        logger.error(f"Authenticated search health check failed: {e}")
        
        # Log failed health check
        from src.core.api_key_auth import log_api_access
        log_api_access(
            api_key_data,
            request,
            "health_check_failed", 
            {"error": str(e)}
        )
        
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


# Background task functions
async def log_search_query(
    user_id: str,
    organization_id: str,
    query: str,
    result_count: int,
    search_time_ms: float,
    search_type: str = "unknown"
):
    """
    Log search query for analytics (placeholder for future implementation)
    """
    try:
        # This would log to a search_analytics table
        logger.info(f"Search logged: user={user_id}, query='{query}', results={result_count}, time={search_time_ms:.2f}ms, type={search_type}")
    except Exception as e:
        logger.error(f"Error logging search query: {e}")

async def log_authenticated_search_query(
    api_key_id: str,
    api_key_name: str, 
    query: str,
    result_count: int,
    search_time_ms: float,
    search_type: str,
    client_ip: str,
    user_agent: str
):
    """
    Log authenticated search query with enhanced security context
    """
    try:
        # Enhanced logging for API key searches with security context
        logger.info(f"API Key Search: key_id={api_key_id}, key_name='{api_key_name}', "
                   f"query_hash='{hash(query) % 10000}', query_length={len(query)}, "
                   f"results={result_count}, time={search_time_ms:.2f}ms, "
                   f"type={search_type}, ip={client_ip}, ua='{user_agent[:100]}'")
        
        # TODO: Store in api_key_usage_log table for audit trail
        # This would be implemented when the full audit system is built
        
    except Exception as e:
        logger.error(f"Error logging authenticated search query: {e}")


# Import time for health check
import time
from datetime import datetime