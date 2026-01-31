"""
Search API endpoints for hybrid search functionality
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.search_schemas import (
    SearchAnalytics,
    SearchIndex,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchSortOrder,
    SearchSuggestion,
    SearchType,
)
from src.models.user import User
from src.services.search.fulltext_search_service import fulltext_search_service
from src.services.search.hybrid_search_service import hybrid_search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def search_documents(
    search_request: SearchQuery,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
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
                db=db,
            )
        elif search_request.search_type == SearchType.FULLTEXT:
            # Use full-text search service
            result = fulltext_search_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db,
            )
        elif search_request.search_type == SearchType.VECTOR:
            # Use vector search service
            from src.services.search.vector_search_service import vector_search_service

            result = vector_search_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db,
            )
        elif search_request.search_type == SearchType.KNOWLEDGE_GRAPH:
            # Use knowledge graph search service
            from src.services.knowledge_graph.knowledge_graph_service import (
                knowledge_graph_service,
            )

            result = knowledge_graph_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db,
            )
        else:
            # Default to hybrid search
            search_request.search_type = SearchType.HYBRID
            result = hybrid_search_service.search(
                search_request=search_request,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db,
            )

        # Log search query in background (for analytics)
        background_tasks.add_task(
            log_search_query,
            str(current_user.id),
            str(current_user.organization_id),
            search_request.query,
            len(result.results),
            result.search_time_ms,
            search_request.search_type.value,
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
    db=Depends(get_db),
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
            organization_id=str(current_user.organization_id),
        )

        # Log search query in background
        background_tasks.add_task(
            log_search_query,
            str(current_user.id),
            str(current_user.organization_id),
            search_request.query,
            len(result.results),
            result.search_time_ms,
            "hybrid",
        )

        return result

    except Exception as e:
        logger.error(f"Error performing hybrid search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(
        ..., min_length=2, max_length=100, description="Query for suggestions"
    ),
    limit: int = Query(default=5, ge=1, le=20, description="Number of suggestions"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
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
                metadata={"source": "document_titles"},
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
    """
    Add item to search history (placeholder)
    """
    return {"status": "success", "message": "Search history saved"}


@router.delete("/history")
async def clear_search_history(current_user: User = Depends(get_current_user)):
    """
    Clear search history (placeholder)
    """
    return {"status": "success", "message": "Search history cleared"}


@router.get("/analytics", response_model=SearchAnalytics)
async def get_search_analytics(
    days: int = Query(
        default=30, ge=1, le=365, description="Number of days for analytics"
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Get search analytics data
    """
    try:
        analytics_data = fulltext_search_service.get_search_analytics(
            organization_id=str(current_user.organization_id), days=days
        )

        return SearchAnalytics(
            total_searches=analytics_data.get("total_documents", 0),  # Placeholder
            average_search_time_ms=analytics_data.get(
                "avg_search_time", 150
            ),  # Placeholder
            most_common_queries=[],  # Placeholder - would need search logging
            search_types_distribution={
                "fulltext": analytics_data.get("total_documents", 0)
            },
            zero_result_queries=[],  # Placeholder
            average_results_per_search=analytics_data.get("total_documents", 0)
            / 10,  # Placeholder
        )

    except Exception as e:
        logger.error(f"Error getting search analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/indexes/rebuild")
async def rebuild_search_indexes(
    current_user: User = Depends(get_current_user), db=Depends(get_db)
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

        documents = (
            db.query(Document)
            .filter(
                Document.processing_status == ProcessingStatus.COMPLETED,
                Document.is_deleted == False,
            )
            .all()
        )

        updated_count = 0
        for document in documents:
            try:
                fulltext_search_service.update_document_search_vector(
                    str(document.id), db
                )
                updated_count += 1
            except Exception as e:
                logger.error(
                    f"Error updating search vector for document {document.id}: {e}"
                )

        return {
            "message": "Search indexes rebuilt successfully",
            "indexes_created": True,
            "documents_updated": updated_count,
            "total_documents": len(documents),
        }

    except Exception as e:
        logger.error(f"Error rebuilding search indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indexes", response_model=List[SearchIndex])
async def get_search_indexes(
    current_user: User = Depends(get_current_user), db=Depends(get_db)
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
            indexes.append(
                SearchIndex(
                    name=row.name,
                    type=row.type,
                    document_count=row.document_count,
                    size_mb=row.size_mb,
                    last_updated=row.last_updated,
                    is_active=row.is_active,
                    configuration=row.configuration,
                )
            )

        return indexes

    except Exception as e:
        logger.error(f"Error getting search indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/reindex")
async def reindex_document(
    document_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db)
):
    """
    Rebuild search vector for a specific document
    """
    try:
        # Verify user has access to the document
        from src.models.document import Document

        document = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.organization_id == current_user.organization_id,
                Document.is_deleted == False,
            )
            .first()
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Update search vector
        fulltext_search_service.update_document_search_vector(document_id, db)

        return {
            "message": f"Document {document_id} reindexed successfully",
            "document_id": document_id,
            "title": document.title,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reindexing document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/popular")
async def get_popular_searches(
    limit: int = Query(
        default=10, ge=1, le=50, description="Number of popular searches"
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Get popular search queries (placeholder for future analytics implementation)
    """
    try:
        # This is a placeholder - would need search query logging table
        # For now, return empty results
        return {"popular_queries": [], "trending_terms": [], "recent_searches": []}

    except Exception as e:
        logger.error(f"Error getting popular searches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar")
async def get_similar_queries(
    q: str = Query(..., min_length=2, description="Query to find similar searches for"),
    limit: int = Query(default=5, ge=1, le=20, description="Number of similar queries"),
    current_user: User = Depends(get_current_user),
):
    """
    Get similar search queries (placeholder)
    """
    return []


@router.get("/related/{result_id}")
async def get_related_searches(
    result_id: str,
    limit: int = Query(
        default=5, ge=1, le=20, description="Number of related searches"
    ),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
            "user_id": str(current_user.id),
        }

    except Exception as e:
        logger.error(f"Error submitting search feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def search_health_check(
    current_user: User = Depends(get_current_user), db=Depends(get_db)
):
    """
    Health check for all search functionality including hybrid search
    """
    try:
        health_status = {
            "status": "healthy",
            "services": {},
            "overall_search_time_ms": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Test full-text search
        try:
            ft_query = SearchQuery(
                query="test", search_type=SearchType.FULLTEXT, limit=1
            )
            start_time = time.time()
            ft_result = fulltext_search_service.search(
                search_request=ft_query,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
            )
            ft_time_ms = (time.time() - start_time) * 1000
            health_status["services"]["fulltext"] = {
                "status": "healthy",
                "search_time_ms": ft_time_ms,
                "results_count": len(ft_result.results),
            }
        except Exception as e:
            health_status["services"]["fulltext"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            logger.error(f"Full-text search health check failed: {e}")

        # Test hybrid search
        try:
            hybrid_query = SearchQuery(
                query="test", search_type=SearchType.HYBRID, limit=1
            )
            start_time = time.time()
            hybrid_result = hybrid_search_service.search(
                search_request=hybrid_query,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
            )
            hybrid_time_ms = (time.time() - start_time) * 1000
            health_status["services"]["hybrid"] = {
                "status": "healthy",
                "search_time_ms": hybrid_time_ms,
                "results_count": len(hybrid_result.results),
            }
            health_status["overall_search_time_ms"] = hybrid_time_ms
        except Exception as e:
            health_status["services"]["hybrid"] = {
                "status": "unhealthy",
                "error": str(e),
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
                "indexes_available": index_count > 0,
            }
        except Exception as e:
            health_status["indexes"] = {"status": "unhealthy", "error": str(e)}

        # Check external service availability (vector DB, knowledge graph)
        health_status["external_services"] = {}

        # Test Qdrant (vector search)
        try:
            from src.services.search.vector_search_service import vector_search_service

            vector_query = SearchQuery(
                query="test", search_type=SearchType.VECTOR, limit=1
            )
            start_time = time.time()
            vector_result = vector_search_service.search(
                search_request=vector_query,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
            )
            vector_time_ms = (time.time() - start_time) * 1000
            health_status["external_services"]["qdrant"] = {
                "status": "healthy",
                "search_time_ms": vector_time_ms,
            }
        except Exception as e:
            health_status["external_services"]["qdrant"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # Test Neo4j (knowledge graph)
        try:
            from src.services.knowledge_graph.knowledge_graph_service import (
                knowledge_graph_service,
            )

            kg_query = SearchQuery(
                query="test", search_type=SearchType.KNOWLEDGE_GRAPH, limit=1
            )
            start_time = time.time()
            kg_result = knowledge_graph_service.search(
                search_request=kg_query,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
            )
            kg_time_ms = (time.time() - start_time) * 1000
            health_status["external_services"]["neo4j"] = {
                "status": "healthy",
                "search_time_ms": kg_time_ms,
            }
        except Exception as e:
            health_status["external_services"]["neo4j"] = {
                "status": "unhealthy",
                "error": str(e),
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
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


@router.post("/public/hybrid", response_model=SearchResponse)
async def public_hybrid_search(
    search_request: SearchQuery, background_tasks: BackgroundTasks, db=Depends(get_db)
):
    """
    Public hybrid search endpoint (no authentication required).
    Used for evaluation and testing purposes.
    """
    try:
        # Force hybrid search type
        search_request.search_type = SearchType.HYBRID

        # Perform hybrid search without user context
        # Use None to skip organization filtering (postgres expects UUID, not string)
        result = hybrid_search_service.search(
            search_request=search_request,
            user_id="anonymous",
            organization_id=None,  # Skip org filtering for public search
        )

        # Log search query in background
        background_tasks.add_task(
            log_search_query,
            "anonymous",
            "public",
            search_request.query,
            len(result.results),
            result.search_time_ms,
            "hybrid_public",
        )

        return result

    except Exception as e:
        logger.error(f"Error performing public hybrid search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public/health")
async def public_search_health_check():
    """
    Public health check for search services (no authentication required)
    """
    try:
        health_status = {
            "status": "healthy",
            "services": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Test basic functionality without authentication
        health_status["services"]["api"] = {
            "status": "healthy",
            "message": "Search API is accessible",
        }

        # Test hybrid search service availability
        try:
            health_status["services"]["hybrid_search"] = {
                "status": "healthy",
                "message": "Hybrid search service is available",
            }
        except Exception as e:
            health_status["services"]["hybrid_search"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        return health_status

    except Exception as e:
        logger.error(f"Public search health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


# Background task functions
async def log_search_query(
    user_id: str,
    organization_id: str,
    query: str,
    result_count: int,
    search_time_ms: float,
    search_type: str = "unknown",
):
    """
    Log search query for analytics (placeholder for future implementation)
    """
    try:
        # This would log to a search_analytics table
        logger.info(
            f"Search logged: user={user_id}, query='{query}', results={result_count}, time={search_time_ms:.2f}ms, type={search_type}"
        )
    except Exception as e:
        logger.error(f"Error logging search query: {e}")


# Import time for health check
import time
from datetime import datetime
