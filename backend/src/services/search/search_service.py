"""
Search Service - Port 8002
Handles hybrid search orchestration combining vector, graph, and keyword search with reranking
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
import redis.asyncio as redis
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue, Vector

    _QDRANT_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - environment dependent
    QdrantClient = None  # type: ignore[assignment]
    FieldCondition = Filter = MatchValue = Vector = None  # type: ignore[assignment]
    _QDRANT_IMPORT_ERROR = exc
from sqlalchemy import and_, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document
from src.models.document import DocumentType as DocType
from src.models.document import ProcessingStatus as ProcStatus
from src.models.search_schemas import SearchQuery
from src.models.search_schemas import SearchResult as SearchResultModel
from src.shared.exceptions import (
    BaseCustomException,
    KnowledgeGraphError,
    SearchError,
    ValidationError,
    VectorStoreError,
    handle_exceptions,
)
from src.shared.schemas import (
    BaseResponse,
    ErrorResponse,
    HealthCheckResponse,
    MatchedContent,
    QueryClassification,
    QueryIntent,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchSuggestion,
    SearchType,
)
from src.shared.utils import (
    AsyncCache,
    CorrelationIdMiddleware,
    EventLogger,
    HealthChecker,
    MetricsCollector,
    circuit_breaker,
    retry_async,
)

from .cohere_rerank_service import cohere_rerank_service

# Configuration
SEARCH_SERVICE_CONFIG = {
    "service_name": "search-service",
    "version": "1.0.0",
    "port": 8002,
    "host": "0.0.0.0",
    "default_search_limit": 10,
    "max_search_limit": 50,
    "rerank_top_k": 20,
    "embedding_dimension": 768,
    "cache_ttl_seconds": 300,  # 5 minutes
}

# Initialize FastAPI app
app = FastAPI(
    title="Search Service",
    version=SEARCH_SERVICE_CONFIG["version"],
    description="Hybrid search service combining vector, graph, and keyword search",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)

# Initialize components
event_logger = EventLogger(SEARCH_SERVICE_CONFIG["service_name"])
health_checker = HealthChecker(SEARCH_SERVICE_CONFIG["service_name"])
metrics = MetricsCollector(SEARCH_SERVICE_CONFIG["service_name"])
cache = AsyncCache(settings.REDIS_URL, SEARCH_SERVICE_CONFIG["cache_ttl_seconds"])

# Initialize external service clients
qdrant_client = (
    QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    if QdrantClient is not None
    else None
)
neo4j_driver = GraphDatabase.driver(
    settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)


@dataclass
class SearchComponentResult:
    """Result from a single search component"""

    results: List[SearchResult]
    component_name: str
    search_time_ms: float
    total_results: int


class HybridSearchEngine:
    """Hybrid search engine combining multiple search strategies"""

    def __init__(self):
        self.embedding_service_url = (
            "http://localhost:8006"  # Analytics service for embeddings
        )
        self.reranker_service_url = (
            "http://localhost:8004"  # Evaluation service for reranking
        )

    async def classify_query(self, query: str) -> QueryClassification:
        """Classify query intent and extract entities"""
        try:
            # Use simple heuristics for classification (in production, use NLP model)
            query_lower = query.lower()

            # Determine intent
            if any(word in query_lower for word in ["what is", "define", "explain"]):
                intent = QueryIntent.LOOKUP
            elif any(word in query_lower for word in ["how", "why", "process"]):
                intent = QueryIntent.REASONING
            elif any(word in query_lower for word in ["compare", "difference", "vs"]):
                intent = QueryIntent.COMPARISON
            elif any(word in query_lower for word in ["when", "timeline", "history"]):
                intent = QueryIntent.TEMPORAL
            elif any(word in query_lower for word in ["cause", "effect", "impact"]):
                intent = QueryIntent.CAUSAL
            else:
                intent = QueryIntent.LOOKUP

            # Extract simple entities (in production, use NER)
            words = query.split()
            entities = []
            for i, word in enumerate(words):
                if len(word) > 3 and word.isalpha():  # Simple entity extraction
                    entities.append(
                        {"text": word, "type": "unknown", "confidence": 0.5}
                    )

            return QueryClassification(
                intent=intent,
                confidence=0.7,  # Simplified confidence
                entities=entities[:5],  # Limit entities
            )

        except Exception as e:
            await event_logger.log_error(
                e, {"query": query, "operation": "classify_query"}
            )
            return QueryClassification(
                intent=QueryIntent.LOOKUP, confidence=0.5, entities=[]
            )

    @retry_async(max_attempts=3)
    async def get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for search query"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.embedding_service_url}/embeddings", json={"text": query}
                )
                response.raise_for_status()
                data = response.json()
                return data["embedding"]
        except Exception as e:
            await event_logger.log_error(
                e, {"query": query, "operation": "get_query_embedding"}
            )
            raise VectorStoreError("Failed to generate query embedding")

    @circuit_breaker(failure_threshold=5, recovery_timeout=30.0)
    async def vector_search(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        organization_id: Optional[uuid.UUID] = None,
    ) -> SearchComponentResult:
        """Perform vector similarity search"""
        start_time = time.time()

        try:
            if qdrant_client is None:
                await event_logger.log_event(
                    event_type="warning",
                    event_data={
                        "warning_type": "qdrant_client_unavailable",
                        "operation": "vector_search",
                        "reason": str(_QDRANT_IMPORT_ERROR),
                    },
                )
                return SearchComponentResult(
                    results=[],
                    component_name="vector_search",
                    search_time_ms=(time.time() - start_time) * 1000,
                    total_results=0,
                )

            # Build Qdrant filter
            qdrant_filter = None
            if filters or organization_id:
                filter_conditions = []

                if organization_id:
                    filter_conditions.append(
                        FieldCondition(
                            key="organization_id",
                            match=MatchValue(value=str(organization_id)),
                        )
                    )

                if filters and filters.document_types:
                    filter_conditions.append(
                        FieldCondition(
                            key="document_type",
                            match=MatchValue(value=filters.document_types[0].value),
                        )
                    )

                if filter_conditions:
                    qdrant_filter = Filter(must=filter_conditions)

            # Search in Qdrant
            search_result = qdrant_client.search(
                collection_name="documents",
                query_vector=Vector(query_embedding),
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

            # Convert to search results
            results = []
            for hit in search_result:
                payload = hit.payload
                results.append(
                    SearchResult(
                        document_id=uuid.UUID(payload["document_id"]),
                        title=payload.get("title", ""),
                        content_snippet=payload.get("content_snippet", ""),
                        relevance_score=hit.score,
                        document_type=DocumentType(
                            payload.get("document_type", "text")
                        ),
                        matched_content=[
                            MatchedContent(
                                content=payload.get("content_snippet", ""),
                                content_type="text",
                                relevance_score=hit.score,
                                source_reference=payload.get("document_id"),
                            )
                        ],
                        metadata=payload.get("metadata", {}),
                    )
                )

            search_time = (time.time() - start_time) * 1000

            return SearchComponentResult(
                results=results,
                component_name="vector_search",
                search_time_ms=search_time,
                total_results=len(results),
            )

        except Exception as e:
            await event_logger.log_error(e, {"operation": "vector_search"})
            raise VectorStoreError("Vector search failed")

    @circuit_breaker(failure_threshold=5, recovery_timeout=30.0)
    async def keyword_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        organization_id: Optional[uuid.UUID] = None,
        db: AsyncSession = None,
    ) -> SearchComponentResult:
        """Perform keyword search using database full-text search"""
        start_time = time.time()

        try:
            # Build database query
            db_query = select(Document).where(
                and_(
                    Document.is_deleted == False,
                    Document.processing_status == ProcStatus.COMPLETED,
                    Document.content_text.isnot(None),
                )
            )

            # Add organization filter
            if organization_id:
                db_query = db_query.where(Document.organization_id == organization_id)

            # Add full-text search
            search_terms = query.split()
            search_conditions = []
            for term in search_terms:
                search_condition = Document.title.ilike(f"%{term}%")
                search_condition = or_(
                    search_condition, Document.content_text.ilike(f"%{term}%")
                )
                search_conditions.append(search_condition)

            if search_conditions:
                db_query = db_query.where(or_(*search_conditions))

            # Add additional filters
            if filters and filters.document_types:
                db_query = db_query.where(
                    Document.document_type.in_(
                        [DocType(dt.value) for dt in filters.document_types]
                    )
                )

            # Order by relevance (simplified - would use proper ranking in production)
            db_query = db_query.order_by(
                desc(func.similarity(Document.title, query)), desc(Document.created_at)
            ).limit(limit)

            # Execute query
            result = await db.execute(db_query)
            documents = result.scalars().all()

            # Convert to search results
            results = []
            for doc in documents:
                # Calculate simple relevance score
                relevance_score = 0.5  # Base score
                for term in search_terms:
                    if term.lower() in doc.title.lower():
                        relevance_score += 0.2
                    if doc.content_text and term.lower() in doc.content_text.lower():
                        relevance_score += 0.1

                results.append(
                    SearchResult(
                        document_id=doc.id,
                        title=doc.title,
                        content_snippet=doc.get_content_preview(200),
                        relevance_score=min(relevance_score, 1.0),
                        document_type=DocumentType(doc.document_type.value),
                        matched_content=[
                            MatchedContent(
                                content=doc.get_content_preview(150),
                                content_type="text",
                                relevance_score=relevance_score,
                                source_reference=str(doc.id),
                            )
                        ],
                        metadata=doc.get_metadata(),
                    )
                )

            search_time = (time.time() - start_time) * 1000

            return SearchComponentResult(
                results=results,
                component_name="keyword_search",
                search_time_ms=search_time,
                total_results=len(results),
            )

        except Exception as e:
            await event_logger.log_error(e, {"operation": "keyword_search"})
            raise SearchError("Keyword search failed")

    @circuit_breaker(failure_threshold=5, recovery_timeout=30.0)
    async def graph_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        organization_id: Optional[uuid.UUID] = None,
    ) -> SearchComponentResult:
        """Perform knowledge graph search"""
        if not organization_id:
            raise ValueError("organization_id is required for graph search")

        start_time = time.time()

        try:
            with neo4j_driver.session() as session:
                # Extract entities from query (simplified)
                query_words = [word.lower() for word in query.split() if len(word) > 3]

                # Build Cypher query
                cypher_query = """
                MATCH (d:Document)
                WHERE d.organization_id = $org_id
                """

                # Build parameterized word conditions to prevent Cypher injection
                params = {
                    "org_id": str(organization_id) if organization_id else "",
                    "limit": limit,
                }

                if query_words:
                    word_conditions = []
                    for i, word in enumerate(query_words[:3]):
                        param_name = f"word{i}"
                        word_conditions.append(f"toLower(d.title) CONTAINS ${param_name}")
                        params[param_name] = word

                    if word_conditions:
                        cypher_query += " AND (" + " OR ".join(word_conditions) + ")"

                cypher_query += """
                OPTIONAL MATCH (d)-[:CONTAINS_ENTITY]->(e:Entity)
                WITH d, collect(e) as entities
                ORDER BY size(entities) DESC, d.created_at DESC
                LIMIT $limit
                RETURN d, entities
                """

                result = session.run(cypher_query, **params)

                # Convert to search results
                search_results = []
                for record in result:
                    doc_node = record["d"]
                    entities = record["entities"]

                    # Calculate relevance based on entity connections
                    entity_score = min(len(entities) / 10.0, 1.0)

                    search_results.append(
                        SearchResult(
                            document_id=uuid.UUID(doc_node["id"]),
                            title=doc_node.get("title", ""),
                            content_snippet=doc_node.get("content_preview", ""),
                            relevance_score=entity_score,
                            document_type=DocumentType(
                                doc_node.get("document_type", "text")
                            ),
                            matched_content=[
                                MatchedContent(
                                    content=doc_node.get("content_preview", ""),
                                    content_type="text",
                                    relevance_score=entity_score,
                                    source_reference=doc_node["id"],
                                )
                            ],
                            metadata={
                                "entity_count": len(entities),
                                "entities": [
                                    entity.get("name", "") for entity in entities[:5]
                                ],
                            },
                        )
                    )

                search_time = (time.time() - start_time) * 1000

                return SearchComponentResult(
                    results=search_results,
                    component_name="graph_search",
                    search_time_ms=search_time,
                    total_results=len(search_results),
                )

        except Exception as e:
            await event_logger.log_error(e, {"operation": "graph_search"})
            raise KnowledgeGraphError("Graph search failed")

    async def rerank_results(
        self, query: str, results: List[SearchResult], limit: int = 10
    ) -> List[SearchResult]:
        """Rerank search results using Cohere reranking API for improved precision"""
        if not results:
            return []

        try:
            # Use Cohere reranking if enabled
            if cohere_rerank_service.is_enabled:
                await event_logger.log_event(
                    event_type="rerank_start",
                    event_data={"query": query, "num_docs": len(results)},
                )

                reranked = await cohere_rerank_service.rerank_search_results(
                    query=query,
                    results=results,
                    top_n=limit,
                    content_field="content_snippet",
                )

                await event_logger.log_event(
                    event_type="rerank_complete",
                    event_data={"query": query, "num_results": len(reranked)},
                )

                return reranked

            # Fallback: simple heuristic-based reranking
            for result in results:
                base_score = result.relevance_score

                # Boost based on document type
                type_boost = {
                    DocumentType.PDF: 0.1,
                    DocumentType.TEXT: 0.05,
                    DocumentType.SPREADSHEET: 0.03,
                }.get(result.document_type, 0.0)

                # Boost based on content length
                content_length = len(result.content_snippet)
                length_boost = min(content_length / 1000.0, 0.1)

                result.relevance_score = min(
                    base_score + type_boost + length_boost, 1.0
                )

            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results[:limit]

        except Exception as e:
            await event_logger.log_error(
                e, {"operation": "rerank_results", "error": str(e)}
            )
            return results[:limit]

    async def hybrid_search(
        self,
        request: SearchRequest,
        organization_id: Optional[uuid.UUID] = None,
        db: AsyncSession = None,
    ) -> SearchResponse:
        """Perform hybrid search combining multiple strategies"""
        search_id = uuid.uuid4()
        start_time = time.time()

        try:
            # Classify query
            classification = await self.classify_query(request.query)

            # Initialize results
            all_results = []
            component_results = {}

            # Perform search based on requested type
            if request.search_type in [SearchType.HYBRID, SearchType.VECTOR]:
                try:
                    # Get query embedding for vector search
                    query_embedding = await self.get_query_embedding(request.query)

                    # Perform vector search
                    vector_result = await self.vector_search(
                        query_embedding=query_embedding,
                        filters=request.filters,
                        limit=request.limit * 2,  # Get more for reranking
                        organization_id=organization_id,
                    )
                    all_results.extend(vector_result.results)
                    component_results["vector_search"] = vector_result

                except VectorStoreError as e:
                    await event_logger.log_error(e, {"search_id": str(search_id)})
                    # Continue with other search types

            if request.search_type in [SearchType.HYBRID, SearchType.KEYWORD]:
                try:
                    # Perform keyword search
                    keyword_result = await self.keyword_search(
                        query=request.query,
                        filters=request.filters,
                        limit=request.limit * 2,
                        organization_id=organization_id,
                        db=db,
                    )
                    all_results.extend(keyword_result.results)
                    component_results["keyword_search"] = keyword_result

                except Exception as e:
                    await event_logger.log_error(e, {"search_id": str(search_id)})

            if request.search_type in [SearchType.HYBRID, SearchType.GRAPH]:
                try:
                    # Perform graph search
                    graph_result = await self.graph_search(
                        query=request.query,
                        filters=request.filters,
                        limit=request.limit * 2,
                        organization_id=organization_id,
                    )
                    all_results.extend(graph_result.results)
                    component_results["graph_search"] = graph_result

                except KnowledgeGraphError as e:
                    await event_logger.log_error(e, {"search_id": str(search_id)})

            # Remove duplicates and rerank
            seen_docs = set()
            unique_results = []
            for result in all_results:
                if result.document_id not in seen_docs:
                    seen_docs.add(result.document_id)
                    unique_results.append(result)

            # Rerank results
            final_results = await self.rerank_results(
                query=request.query, results=unique_results, limit=request.limit
            )

            # Calculate total search time
            total_time = (time.time() - start_time) * 1000

            # Generate facets (simplified)
            facets = {}
            document_types = {}
            for result in final_results:
                doc_type = result.document_type.value
                document_types[doc_type] = document_types.get(doc_type, 0) + 1
            facets["document_types"] = document_types

            # Log search event
            await event_logger.log_event(
                event_type="search_completed",
                event_data={
                    "search_id": str(search_id),
                    "query": request.query,
                    "search_type": request.search_type.value,
                    "total_results": len(final_results),
                    "search_time_ms": total_time,
                    "components": list(component_results.keys()),
                },
            )

            # Record metrics
            metrics.increment_counter(
                "searches_performed",
                labels={
                    "search_type": request.search_type.value,
                    "intent": classification.intent.value,
                },
            )
            metrics.record_histogram(
                "search_duration_ms",
                total_time,
                labels={"search_type": request.search_type.value},
            )

            return SearchResponse(
                query=request.query,
                search_id=search_id,
                total_results=len(final_results),
                search_time_ms=total_time,
                results=final_results,
                facets=facets,
                query_classification=classification,
            )

        except Exception as e:
            await event_logger.log_error(
                e, {"search_id": str(search_id), "query": request.query}
            )
            raise SearchError(f"Search failed: {str(e)}")


# Initialize search engine
search_engine = HybridSearchEngine()


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await event_logger.log_event(
        event_type="service_startup",
        event_data={"version": SEARCH_SERVICE_CONFIG["version"]},
    )

    # Add health checks
    health_checker.add_check("qdrant", lambda: True)  # Would check actual connection
    health_checker.add_check("neo4j", lambda: True)  # Would check actual connection
    health_checker.add_check("redis", lambda: True)  # Would check actual connection


@app.post("/search", response_model=SearchResponse)
@handle_exceptions
async def search(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    organization_id: uuid.UUID = Query(...),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Perform hybrid search"""
    # Validate request
    if not request.query.strip():
        raise ValidationError("Search query cannot be empty")

    if request.limit < 1 or request.limit > SEARCH_SERVICE_CONFIG["max_search_limit"]:
        raise ValidationError(
            f"Search limit must be between 1 and {SEARCH_SERVICE_CONFIG['max_search_limit']}"
        )

    # Check cache for identical searches
    cache_data = {
        "query": request.query,
        "search_type": request.search_type.value,
        "filters": request.filters.dict() if request.filters else None,
        "limit": request.limit,
        "organization_id": str(organization_id),
    }
    cache_key = f"search:{hash(json.dumps(cache_data, sort_keys=True))}"

    cached_result = await cache.get(cache_key)
    if cached_result:
        # Update cached result with new search ID
        cached_result["search_id"] = uuid.uuid4()
        await event_logger.log_event(
            event_type="search_cache_hit",
            event_data={"query": request.query, "cache_key": cache_key},
        )
        return SearchResponse(**cached_result)

    # Perform search
    search_result = await search_engine.hybrid_search(
        request=request, organization_id=organization_id, db=db
    )

    # Cache the result
    await cache.set(cache_key, search_result.dict())

    # Store search analytics in background
    background_tasks.add_task(
        store_search_analytics,
        str(search_result.search_id),
        request.query,
        organization_id,
        user_id,
        search_result.total_results,
        search_result.search_time_ms,
    )

    return search_result


async def store_search_analytics(
    search_id: str,
    query: str,
    organization_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    result_count: int,
    search_time_ms: float,
    search_type: Optional[str] = None,
):
    """Store search analytics to DB and event log"""
    try:
        # Persist to search_analytics table
        from src.core.database import AsyncSessionLocal
        from src.models.search_analytics import SearchAnalyticsEvent

        async with AsyncSessionLocal() as db:
            event = SearchAnalyticsEvent(
                search_id=search_id,
                query=query,
                organization_id=organization_id,
                user_id=user_id,
                search_type=search_type,
                result_count=result_count,
                search_time_ms=search_time_ms,
            )
            db.add(event)
            await db.commit()
    except Exception as db_err:
        # DB persistence is best-effort; fall back to event log only
        logger.debug(f"Search analytics DB write failed (non-critical): {db_err}")

    try:
        await event_logger.log_event(
            event_type="search_analytics_stored",
            event_data={
                "search_id": search_id,
                "query": query,
                "result_count": result_count,
                "search_time_ms": search_time_ms,
            },
            user_id=str(user_id) if user_id else None,
            organization_id=str(organization_id),
        )
    except Exception as e:
        await event_logger.log_error(e, {"search_id": search_id})


@app.get("/suggestions", response_model=List[SearchSuggestion])
@handle_exceptions
async def get_search_suggestions(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get search suggestions"""
    try:
        suggestions = []

        # Get popular searches from cache/database
        cache_key = f"suggestions:{organization_id}:{q.lower()}"
        cached_suggestions = await cache.get(cache_key)

        if cached_suggestions:
            return [SearchSuggestion(**s) for s in cached_suggestions]

        # Generate suggestions based on document titles and content
        query_lower = q.lower()

        # Find matching document titles
        result = await db.execute(
            select(Document.title)
            .where(
                and_(
                    Document.organization_id == organization_id,
                    Document.is_deleted == False,
                    Document.processing_status == ProcStatus.COMPLETED,
                    Document.title.ilike(f"%{query_lower}%"),
                )
            )
            .limit(limit)
        )

        titles = [row[0] for row in result]

        # Generate suggestions
        for title in titles:
            if title.lower().startswith(query_lower):
                suggestions.append(
                    SearchSuggestion(text=title, type="autocomplete", score=0.9)
                )
            elif query_lower in title.lower():
                suggestions.append(
                    SearchSuggestion(text=title, type="completion", score=0.7)
                )

        # Add spelling correction suggestions (simplified)
        if not suggestions and len(q) > 3:
            # Would use proper spell checking in production
            suggestions.append(
                SearchSuggestion(
                    text=q, type="correction", score=0.5  # Return original as fallback
                )
            )

        # Cache suggestions
        await cache.set(cache_key, [s.dict() for s in suggestions])

        return suggestions[:limit]

    except Exception as e:
        await event_logger.log_error(e, {"query": q})
        return []


@app.get("/search/history")
@handle_exceptions
async def get_search_history(
    limit: int = Query(20, ge=1, le=100),
    organization_id: uuid.UUID = Query(...),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get search history for user or organization"""
    try:
        # Build query for search history
        query = select(SearchQuery).where(
            SearchQuery.organization_id == organization_id
        )

        if user_id:
            query = query.where(SearchQuery.user_id == user_id)

        query = query.order_by(desc(SearchQuery.created_at)).limit(limit)

        result = await db.execute(query)
        search_queries = result.scalars().all()

        return {
            "searches": [
                {
                    "id": str(search.id),
                    "query": search.query,
                    "search_type": search.search_type,
                    "result_count": search.result_count,
                    "search_time_ms": search.search_time_ms,
                    "created_at": search.created_at,
                }
                for search in search_queries
            ]
        }

    except Exception as e:
        await event_logger.log_error(e, {"user_id": str(user_id) if user_id else None})
        raise SearchError("Failed to retrieve search history")


@app.get("/search/popular")
@handle_exceptions
async def get_popular_searches(
    limit: int = Query(10, ge=1, le=50),
    organization_id: uuid.UUID = Query(...),
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Get popular searches in organization"""
    try:
        # This would aggregate from search analytics
        # For now, return empty placeholder
        return {
            "popular_searches": [],
            "time_period_days": days,
            "organization_id": str(organization_id),
        }

    except Exception as e:
        await event_logger.log_error(e, {"organization_id": str(organization_id)})
        raise SearchError("Failed to retrieve popular searches")


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Service health check"""
    health_data = await health_checker.check_health()

    return HealthCheckResponse(
        status=health_data["status"],
        version=SEARCH_SERVICE_CONFIG["version"],
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        services=health_data["checks"],
        uptime_seconds=0,  # Would track actual uptime
    )


@app.get("/metrics")
async def get_metrics():
    """Get search service metrics"""
    return metrics.get_metrics()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await cache.close()
    neo4j_driver.close()
    await event_logger.log_event(event_type="service_shutdown", event_data={})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.services.search_service:app",
        host=SEARCH_SERVICE_CONFIG["host"],
        port=SEARCH_SERVICE_CONFIG["port"],
        log_level=settings.LOG_LEVEL.lower(),
    )
