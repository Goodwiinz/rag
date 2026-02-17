"""
Hybrid Search Service that combines vector, graph, and full-text search results
"""

import asyncio
import logging
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.search_schemas import (
    SearchFilter,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchType,
)

from .cohere_rerank_service import cohere_rerank_service
from .fulltext_search_service import fulltext_search_service

logger = logging.getLogger(__name__)


class SearchSourceType(Enum):
    """Source types for search results"""

    FULLTEXT = "fulltext"
    VECTOR = "vector"
    KNOWLEDGE_GRAPH = "knowledge_graph"


@dataclass
class RawSearchResult:
    """Raw search result from a specific source"""

    document_id: str
    source_type: SearchSourceType
    relevance_score: float
    metadata: Dict[str, Any]
    search_result: Optional[SearchResult] = None


@dataclass
class SearchSourceResult:
    """Results from a specific search source"""

    source_type: SearchSourceType
    results: List[RawSearchResult]
    search_time_ms: float
    total_available: int
    success: bool
    error: Optional[str] = None


class HybridSearchService:
    """Service for combining multiple search modalities"""

    def __init__(self):
        self.fulltext_weight = 0.4
        self.vector_weight = 0.4
        self.knowledge_graph_weight = 0.2

        # Fusion parameters
        self.min_results_per_source = 3
        self.max_results_per_source = 20
        self.diversity_boost = 0.1
        self.recency_boost_hours = 24

        # Thread pool for parallel search execution
        self.executor = ThreadPoolExecutor(max_workers=3)

    def search(
        self,
        search_request: SearchQuery,
        user_id: str = None,
        organization_id: str = None,
        db: Session = None,
    ) -> SearchResponse:
        """
        Perform hybrid search combining multiple search modalities

        Args:
            search_request: Search query and parameters
            user_id: ID of user performing search
            organization_id: ID of organization for filtering
            db: Database session (optional, will create one if not provided)

        Returns:
            SearchResponse with fused results from all sources
        """
        start_time = time.time()

        try:
            # Route search query to appropriate sources
            search_sources = self._route_search_query(search_request)

            # Execute searches in parallel
            source_results = self._execute_parallel_searches(
                search_request, search_sources, user_id, organization_id, db
            )

            # Fuse and rank results
            fused_results = self._fuse_search_results(source_results, search_request)

            # Apply Cohere reranking if enabled (improves Precision@3/5)
            if cohere_rerank_service.is_enabled and fused_results:
                logger.info(
                    f"Applying Cohere reranking to {len(fused_results)} results"
                )
                reranked = self._apply_cohere_reranking(
                    search_request.query,
                    fused_results,
                    search_request.limit * 2,  # Get more for filtering
                )
                fused_results = reranked

            # Apply final filtering and pagination
            final_results = self._apply_final_filtering(
                fused_results, search_request, organization_id
            )

            # Create response
            search_time_ms = (time.time() - start_time) * 1000

            return SearchResponse(
                query=search_request.query,
                search_id=str(uuid.uuid4()),
                search_type=SearchType.HYBRID,
                results=final_results,
                total_results=len(final_results),
                returned_results=len(final_results),
                search_time_ms=search_time_ms,
                limit=search_request.limit,
                offset=search_request.offset,
                has_more=len(final_results) >= search_request.limit,
                suggestions=self._get_hybrid_suggestions(
                    search_request, source_results
                ),
            )

        except Exception as e:
            logger.error(f"Error performing hybrid search: {e}")
            # Fallback to full-text search if hybrid fails
            return self._fallback_to_fulltext(search_request, user_id, organization_id)

    def search_with_diagnostics(
        self,
        search_request: SearchQuery,
        user_id: str = None,
        organization_id: str = None,
        db: Session = None,
        weights_override: Optional[Dict[str, float]] = None,
    ) -> Tuple[SearchResponse, "RetrievalTrace"]:
        """
        Perform hybrid search with full diagnostic instrumentation.

        Same pipeline as search() but captures per-source timing, fusion stats,
        reranking deltas, and returns a RetrievalTrace alongside the response.

        Args:
            search_request: Search query and parameters
            user_id: ID of user performing search
            organization_id: ID of organization for filtering
            db: Database session
            weights_override: Optional dict of {fulltext, vector, knowledge_graph} weights
                              for experimentation. Must sum to 1.0.

        Returns:
            Tuple of (SearchResponse, RetrievalTrace)
        """
        from src.services.diagnostics.retrieval_diagnostics import (
            FusionDiagnostics,
            RerankDiagnostics,
            RetrievalTrace,
            SourceDiagnostics,
        )

        start_time = time.time()
        trace = RetrievalTrace(query=search_request.query, search_type=search_request.search_type or "hybrid")

        effective_weights = {
            "fulltext": self.fulltext_weight,
            "vector": self.vector_weight,
            "knowledge_graph": self.knowledge_graph_weight,
        }
        if weights_override:
            effective_weights = {
                "fulltext": weights_override.get("fulltext", self.fulltext_weight),
                "vector": weights_override.get("vector", self.vector_weight),
                "knowledge_graph": weights_override.get(
                    "knowledge_graph", self.knowledge_graph_weight
                ),
            }

        try:
            # Step 1: Route query
            search_sources = self._route_search_query(search_request)

            # Step 2: Execute parallel searches with per-source diagnostics
            source_results = self._execute_parallel_searches(
                search_request, search_sources, user_id, organization_id, db
            )

            for source_type, source_result in source_results.items():
                scores = [r.relevance_score for r in source_result.results]
                trace.sources.append(
                    SourceDiagnostics(
                        source_type=source_type.value,
                        search_time_ms=source_result.search_time_ms,
                        result_count=len(source_result.results),
                        total_available=source_result.total_available,
                        success=source_result.success,
                        error=source_result.error,
                        top_scores=sorted(scores, reverse=True)[:5],
                        avg_score=round(statistics.mean(scores), 4) if scores else 0.0,
                    )
                )

            # Step 3: Fuse results with diagnostics
            fusion_start = time.time()
            fused_results = self._fuse_search_results(
                source_results,
                search_request,
                source_weights=effective_weights,
            )
            fusion_time = (time.time() - fusion_start) * 1000

            # Count raw input docs and multi-source docs
            raw_input_count = sum(
                len(sr.results) for sr in source_results.values() if sr.success
            )
            # Count docs appearing in multiple sources
            doc_sources: Dict[str, int] = {}
            for sr in source_results.values():
                if sr.success:
                    for r in sr.results:
                        doc_sources[r.document_id] = doc_sources.get(r.document_id, 0) + 1
            multi_source_count = sum(1 for c in doc_sources.values() if c > 1)

            fused_scores = [r.relevance_score for r in fused_results]
            score_dist = {}
            if fused_scores:
                score_dist = {
                    "min": round(min(fused_scores), 4),
                    "max": round(max(fused_scores), 4),
                    "mean": round(statistics.mean(fused_scores), 4),
                    "median": round(statistics.median(fused_scores), 4),
                }

            trace.fusion = FusionDiagnostics(
                input_count=raw_input_count,
                output_count=len(fused_results),
                multi_source_count=multi_source_count,
                weights_used=effective_weights,
                score_distribution=score_dist,
                fusion_time_ms=round(fusion_time, 2),
            )

            # Step 4: Rerank with diagnostics
            if cohere_rerank_service.is_enabled and fused_results:
                rerank_start = time.time()
                pre_rerank_scores = {r.document_id: r.relevance_score for r in fused_results}

                try:
                    reranked = self._apply_cohere_reranking(
                        search_request.query,
                        fused_results,
                        search_request.limit * 2,
                    )
                    rerank_time = (time.time() - rerank_start) * 1000

                    score_deltas = []
                    for r in reranked:
                        before = pre_rerank_scores.get(r.document_id, 0.0)
                        after = r.relevance_score
                        score_deltas.append(
                            {
                                "doc_id": r.document_id,
                                "before": round(before, 4),
                                "after": round(after, 4),
                                "delta": round(after - before, 4),
                            }
                        )

                    trace.rerank = RerankDiagnostics(
                        enabled=True,
                        rerank_time_ms=round(rerank_time, 2),
                        input_count=len(fused_results),
                        output_count=len(reranked),
                        score_deltas=score_deltas,
                        fallback_used=False,
                    )
                    fused_results = reranked
                except Exception as e:
                    rerank_time = (time.time() - rerank_start) * 1000
                    trace.rerank = RerankDiagnostics(
                        enabled=True,
                        rerank_time_ms=round(rerank_time, 2),
                        input_count=len(fused_results),
                        output_count=len(fused_results),
                        fallback_used=True,
                        error=str(e),
                    )
            else:
                trace.rerank = RerankDiagnostics(enabled=False)

            # Step 5: Final filtering
            final_results = self._apply_final_filtering(
                fused_results, search_request, organization_id
            )

            search_time_ms = (time.time() - start_time) * 1000
            trace.total_time_ms = round(search_time_ms, 2)
            trace.final_result_count = len(final_results)

            response = SearchResponse(
                query=search_request.query,
                search_id=str(uuid.uuid4()),
                search_type=SearchType.HYBRID,
                results=final_results,
                total_results=len(final_results),
                returned_results=len(final_results),
                search_time_ms=search_time_ms,
                limit=search_request.limit,
                offset=search_request.offset,
                has_more=len(final_results) >= search_request.limit,
                suggestions=self._get_hybrid_suggestions(search_request, source_results),
            )

            return response, trace

        except Exception as e:
            logger.error(f"Error in search_with_diagnostics: {e}")
            trace.total_time_ms = round((time.time() - start_time) * 1000, 2)
            fallback = self._fallback_to_fulltext(search_request, user_id, organization_id)
            return fallback, trace

    def _route_search_query(
        self, search_request: SearchQuery
    ) -> List[SearchSourceType]:
        """
        Determine which search sources to use based on query characteristics

        Args:
            search_request: The search query

        Returns:
            List of search source types to use
        """
        sources = []

        # Always include full-text search for text queries
        if search_request.search_type in [SearchType.FULLTEXT, SearchType.HYBRID]:
            sources.append(SearchSourceType.FULLTEXT)

        # Include vector search for semantic similarity
        if search_request.search_type in [SearchType.SEMANTIC, SearchType.HYBRID]:
            sources.append(SearchSourceType.VECTOR)

        # Include knowledge graph search for entity-based queries
        if search_request.search_type in [SearchType.HYBRID]:
            # Check if query contains entities or relationship indicators
            query_lower = search_request.query.lower()
            entity_indicators = [
                "who",
                "what",
                "where",
                "when",
                "how",
                "relationship",
                "connected",
            ]
            if any(indicator in query_lower for indicator in entity_indicators):
                sources.append(SearchSourceType.KNOWLEDGE_GRAPH)

        # Default to all sources for hybrid search
        if search_request.search_type == SearchType.HYBRID and not sources:
            sources = [
                SearchSourceType.FULLTEXT,
                SearchSourceType.VECTOR,
                SearchSourceType.KNOWLEDGE_GRAPH,
            ]

        return sources

    def _execute_parallel_searches(
        self,
        search_request: SearchQuery,
        sources: List[SearchSourceType],
        user_id: str,
        organization_id: str,
        db: Session = None,
    ) -> Dict[SearchSourceType, SearchSourceResult]:
        """
        Execute searches from multiple sources in parallel

        Args:
            search_request: Search query
            sources: List of search source types
            user_id: User ID for access control
            organization_id: Organization ID for filtering

        Returns:
            Dictionary mapping source types to their results
        """
        results = {}

        # Create search tasks for each source
        search_tasks = []
        for source_type in sources:
            if source_type == SearchSourceType.FULLTEXT:
                search_tasks.append(
                    (
                        source_type,
                        self._execute_fulltext_search,
                        search_request,
                        user_id,
                        organization_id,
                        db,
                    )
                )
            elif source_type == SearchSourceType.VECTOR:
                search_tasks.append(
                    (
                        source_type,
                        self._execute_vector_search,
                        search_request,
                        user_id,
                        organization_id,
                        db,
                    )
                )
            elif source_type == SearchSourceType.KNOWLEDGE_GRAPH:
                search_tasks.append(
                    (
                        source_type,
                        self._execute_knowledge_graph_search,
                        search_request,
                        user_id,
                        organization_id,
                        db,
                    )
                )

        # Execute searches in parallel
        future_to_source = {
            self.executor.submit(search_func, *args): source_type
            for source_type, search_func, *args in search_tasks
        }

        # Collect results
        for future in future_to_source:
            source_type = future_to_source[future]
            try:
                results[source_type] = future.result(
                    timeout=10
                )  # 10 second timeout per source
            except Exception as e:
                logger.error(f"Error in {source_type.value} search: {e}")
                results[source_type] = SearchSourceResult(
                    source_type=source_type,
                    results=[],
                    search_time_ms=0,
                    total_available=0,
                    success=False,
                    error=str(e),
                )

        return results

    def _execute_fulltext_search(
        self,
        search_request: SearchQuery,
        user_id: str,
        organization_id: str,
        db: Session = None,
    ) -> SearchSourceResult:
        """Execute full-text search"""
        start_time = time.time()

        try:
            # Create full-text search query
            ft_search_request = SearchQuery(
                query=search_request.query,
                search_type=SearchType.FULLTEXT,
                limit=self.max_results_per_source,
                offset=0,
                filters=search_request.filters,
                include_snippets=search_request.include_snippets,
            )

            # Execute search
            ft_result = fulltext_search_service.search(
                search_request=ft_search_request,
                user_id=user_id,
                organization_id=organization_id,
                db=db,
            )

            # Convert to raw results
            raw_results = []
            for result in ft_result.results:
                raw_results.append(
                    RawSearchResult(
                        document_id=result.document_id,
                        source_type=SearchSourceType.FULLTEXT,
                        relevance_score=result.relevance_score,
                        metadata={
                            "original_score": result.relevance_score,
                            "source": "fulltext",
                            "snippets": result.snippets,
                        },
                        search_result=result,
                    )
                )

            search_time_ms = (time.time() - start_time) * 1000

            return SearchSourceResult(
                source_type=SearchSourceType.FULLTEXT,
                results=raw_results,
                search_time_ms=search_time_ms,
                total_available=ft_result.total_results,
                success=True,
            )

        except Exception as e:
            logger.error(f"Full-text search failed: {e}")
            return SearchSourceResult(
                source_type=SearchSourceType.FULLTEXT,
                results=[],
                search_time_ms=0,
                total_available=0,
                success=False,
                error=str(e),
            )

    def _execute_vector_search(
        self,
        search_request: SearchQuery,
        user_id: str,
        organization_id: str,
        db: Session = None,
    ) -> SearchSourceResult:
        """Execute vector similarity search"""
        start_time = time.time()

        try:
            # Import and use vector search service
            from .vector_search_service import vector_search_service

            # Execute search using the available interface
            vector_result = vector_search_service.search_documents(
                query=search_request.query,
                organization_id=organization_id,
                limit=self.max_results_per_source,
                score_threshold=0.2,  # Lowered to 0.2 for more results (P@3, P@5 calculation)
            )

            # Convert to raw results
            raw_results = []
            for result in vector_result.results:
                full_text = result.text or ""
                result_metadata = dict(result.metadata.additional_data or {})
                result_metadata.setdefault("full_text", full_text)
                result_metadata.setdefault("text", full_text)
                result_metadata.setdefault("source_type", "vector")

                # Create SearchResult from VectorSearchResult
                search_result = SearchResult(
                    document_id=result.metadata.document_id,
                    title=result.text[:100],  # Use text as title preview
                    document_type=DocumentType.TEXT,  # Default type
                    content_preview=full_text[:300],
                    snippets=[],
                    relevance_score=result.score,
                    file_size_bytes=0,
                    created_at=result.metadata.timestamp,
                    updated_at=result.metadata.timestamp,
                    processing_status=ProcessingStatus.COMPLETED,
                    tags=[],
                    is_public=False,
                    uploaded_by_user_id=user_id or "",
                    organization_id=result.metadata.organization_id
                    or organization_id
                    or "",
                    metadata=result_metadata,
                )

                raw_results.append(
                    RawSearchResult(
                        document_id=result.metadata.document_id,
                        source_type=SearchSourceType.VECTOR,
                        relevance_score=result.score,
                        metadata={
                            "original_score": result.score,
                            "source": "vector",
                            "similarity": result.score,
                        },
                        search_result=search_result,
                    )
                )

            search_time_ms = (time.time() - start_time) * 1000

            return SearchSourceResult(
                source_type=SearchSourceType.VECTOR,
                results=raw_results,
                search_time_ms=search_time_ms,
                total_available=vector_result.total_found,
                success=True,
            )

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return SearchSourceResult(
                source_type=SearchSourceType.VECTOR,
                results=[],
                search_time_ms=0,
                total_available=0,
                success=False,
                error=str(e),
            )

    def _execute_knowledge_graph_search(
        self,
        search_request: SearchQuery,
        user_id: str,
        organization_id: str,
        db: Session = None,
    ) -> SearchSourceResult:
        """Execute knowledge graph search"""
        start_time = time.time()

        try:
            # Import and use knowledge graph service
            from src.services.knowledge_graph import knowledge_graph_service

            # Execute search using the available interface
            kg_result = knowledge_graph_service.search_entities(
                query=search_request.query, limit=self.max_results_per_source
            )

            # Convert to raw results
            raw_results = []
            for result in kg_result.results if hasattr(kg_result, "results") else []:
                # Create SearchResult from knowledge graph result
                search_result = SearchResult(
                    document_id=str(result.id)
                    if hasattr(result, "id")
                    else str(uuid.uuid4()),
                    title=getattr(result, "name", "Entity"),
                    document_type=DocumentType.TEXT,
                    content_preview=getattr(result, "description", ""),
                    snippets=[],
                    relevance_score=0.8,  # Default score
                    file_size_bytes=0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    processing_status=ProcessingStatus.COMPLETED,
                    tags=[],
                    is_public=False,
                    uploaded_by_user_id=user_id or "",
                    organization_id=organization_id,
                    metadata={},
                )

                raw_results.append(
                    RawSearchResult(
                        document_id=search_result.document_id,
                        source_type=SearchSourceType.KNOWLEDGE_GRAPH,
                        relevance_score=search_result.relevance_score,
                        metadata={
                            "original_score": search_result.relevance_score,
                            "source": "knowledge_graph",
                            "entities": [],
                        },
                        search_result=search_result,
                    )
                )

            search_time_ms = (time.time() - start_time) * 1000

            return SearchSourceResult(
                source_type=SearchSourceType.KNOWLEDGE_GRAPH,
                results=raw_results,
                search_time_ms=search_time_ms,
                total_available=len(raw_results),  # KG service doesn't provide total
                success=True,
            )

        except Exception as e:
            logger.error(f"Knowledge graph search failed: {e}")
            return SearchSourceResult(
                source_type=SearchSourceType.KNOWLEDGE_GRAPH,
                results=[],
                search_time_ms=0,
                total_available=0,
                success=False,
                error=str(e),
            )

    def _fuse_search_results(
        self,
        source_results: Dict[SearchSourceType, SearchSourceResult],
        search_request: SearchQuery,
        source_weights: Optional[Dict[str, float]] = None,
    ) -> List[RawSearchResult]:
        """
        Fuse results from multiple search sources using weighted scoring

        Args:
            source_results: Results from each search source
            search_request: Original search request

        Returns:
            Fused and ranked list of raw results
        """
        # Collect all results with their document IDs
        all_results = {}

        # Process results from each source
        for source_type, source_result in source_results.items():
            if not source_result.success:
                continue

            for result in source_result.results:
                document_id = result.document_id

                if document_id not in all_results:
                    all_results[document_id] = {
                        "document_id": document_id,
                        "sources": {},
                        "search_result": result.search_result,
                        "boost_factors": {},
                    }

                # Add source-specific score
                weight = self._get_source_weight(source_type, source_weights=source_weights)
                normalized_score = self._normalize_score(
                    result.relevance_score, source_type
                )
                all_results[document_id]["sources"][source_type] = {
                    "score": result.relevance_score,
                    "normalized_score": normalized_score,
                    "weight": weight,
                    "metadata": result.metadata,
                }

        # Calculate fused scores for each document
        fused_results = []
        for document_id, doc_data in all_results.items():
            fused_score = 0.0
            source_count = len(doc_data["sources"])

            # Base score from weighted combination
            for source_type, source_data in doc_data["sources"].items():
                fused_score += source_data["normalized_score"] * source_data["weight"]

            # Apply diversity boost for documents from multiple sources
            if source_count > 1:
                diversity_boost = self.diversity_boost * (source_count - 1)
                fused_score += diversity_boost
                doc_data["boost_factors"]["diversity"] = diversity_boost

            # Apply recency boost
            if doc_data["search_result"]:
                recency_boost = self._calculate_recency_boost(doc_data["search_result"])
                if recency_boost > 0:
                    fused_score += recency_boost
                    doc_data["boost_factors"]["recency"] = recency_boost

            # Create fused result
            fused_result = RawSearchResult(
                document_id=document_id,
                source_type=SearchSourceType.FULLTEXT,  # Default for hybrid
                relevance_score=fused_score,
                metadata={
                    "fused_score": fused_score,
                    "sources": doc_data["sources"],
                    "source_count": source_count,
                    "boost_factors": doc_data["boost_factors"],
                    "original_sources": list(doc_data["sources"].keys()),
                },
                search_result=doc_data["search_result"],
            )

            fused_results.append(fused_result)

        # Sort by fused score
        fused_results.sort(key=lambda x: x.relevance_score, reverse=True)

        return fused_results

    def _get_source_weight(
        self,
        source_type: SearchSourceType,
        source_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Get weight for a specific search source"""
        if source_weights:
            return source_weights.get(source_type.value, 0.33)

        default_weights = {
            SearchSourceType.FULLTEXT: self.fulltext_weight,
            SearchSourceType.VECTOR: self.vector_weight,
            SearchSourceType.KNOWLEDGE_GRAPH: self.knowledge_graph_weight,
        }
        return default_weights.get(source_type, 0.33)

    def _normalize_score(self, score: float, source_type: SearchSourceType) -> float:
        """Normalize score to 0-1 range for fusion"""
        # Different sources have different score ranges
        if source_type == SearchSourceType.FULLTEXT:
            # Full-text search typically uses tf-idf scores
            return min(score / 50.0, 1.0)  # Normalize assuming max score of 50
        elif source_type == SearchSourceType.VECTOR:
            # Vector similarity is already 0-1
            return score
        elif source_type == SearchSourceType.KNOWLEDGE_GRAPH:
            # Knowledge graph scores vary widely
            return min(score / 10.0, 1.0)  # Normalize assuming max score of 10
        else:
            return min(score, 1.0)

    def _calculate_recency_boost(self, search_result: SearchResult) -> float:
        """Calculate recency boost for a search result"""
        if not search_result.created_at:
            return 0.0

        import datetime
        from datetime import timezone

        now = datetime.datetime.now(timezone.utc)

        # Ensure created_at is aware
        created_at = search_result.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        age_hours = (now - created_at).total_seconds() / 3600

        if age_hours < self.recency_boost_hours:
            # Linear decay from full boost to 0 over the period
            boost = (1.0 - age_hours / self.recency_boost_hours) * 0.1
            return boost

        return 0.0

    def _apply_cohere_reranking(
        self, query: str, fused_results: List[RawSearchResult], top_n: int
    ) -> List[RawSearchResult]:
        """
        Apply Cohere reranking to improve precision of results.

        Args:
            query: The search query
            fused_results: List of fused search results
            top_n: Number of results to return

        Returns:
            Reranked list of results
        """
        try:
            # Convert to format expected by reranking service
            documents = []
            for result in fused_results:
                content = ""
                if result.search_result:
                    metadata = result.search_result.metadata or {}
                    content = (
                        metadata.get("full_text")
                        or metadata.get("text")
                        or result.search_result.content_preview
                        or result.search_result.title
                        or ""
                    )

                documents.append(
                    {
                        "id": result.document_id,
                        "document_id": result.document_id,
                        "content": content,
                        "content_snippet": content[:500],
                        "relevance_score": result.relevance_score,
                    }
                )

            # Use sync version of reranking for sync context
            rerank_results = cohere_rerank_service.rerank_sync(query, documents, top_n)

            # Build reordered results
            result_map = {r.document_id: r for r in fused_results}
            reranked = []

            for rr in rerank_results:
                if rr.document_id in result_map:
                    original = result_map[rr.document_id]
                    # Update score with Cohere's relevance score
                    original.relevance_score = rr.relevance_score
                    original.metadata["cohere_score"] = rr.relevance_score
                    original.metadata["original_score"] = rr.original_score
                    reranked.append(original)

            fallback_info = cohere_rerank_service.last_failure
            if fallback_info:
                for result in reranked:
                    result.metadata["cohere_fallback_used"] = True
                    result.metadata["cohere_fallback_reason"] = fallback_info.get(
                        "reason"
                    )
                    if "status_code" in fallback_info:
                        result.metadata["cohere_status_code"] = fallback_info.get(
                            "status_code"
                        )
            else:
                for result in reranked:
                    result.metadata["cohere_fallback_used"] = False

            logger.info(
                f"Cohere reranking complete: {len(fused_results)} -> {len(reranked)} results"
            )
            return reranked

        except Exception as e:
            logger.error(f"Cohere reranking failed, using original order: {e}")
            return fused_results[:top_n]

    def _apply_final_filtering(
        self,
        fused_results: List[RawSearchResult],
        search_request: SearchQuery,
        organization_id: str,
    ) -> List[SearchResult]:
        """Apply final filtering and pagination to fused results"""
        # Apply offset and limit
        start_idx = search_request.offset
        end_idx = start_idx + search_request.limit

        paginated_results = fused_results[start_idx:end_idx]

        # Convert to SearchResult objects
        final_results = []
        for result in paginated_results:
            if result.search_result:
                # Update the search result with the fused score
                result.search_result.relevance_score = result.relevance_score
                result.search_result.metadata.update(result.metadata)
                final_results.append(result.search_result)

        return final_results

    def _get_hybrid_suggestions(
        self,
        search_request: SearchQuery,
        source_results: Dict[SearchSourceType, SearchSourceResult],
    ) -> List[str]:
        """Get suggestions from multiple sources"""
        suggestions = []

        # Collect suggestions from successful sources
        for source_type, source_result in source_results.items():
            if source_result.success and hasattr(source_result, "suggestions"):
                if hasattr(source_result, "suggestions") and source_result.suggestions:
                    suggestions.extend(source_result.suggestions)

        # Remove duplicates and limit
        unique_suggestions = list(set(suggestions))
        return unique_suggestions[:5]

    def _fallback_to_fulltext(
        self, search_request: SearchQuery, user_id: str, organization_id: str
    ) -> SearchResponse:
        """Fallback to full-text search if hybrid search fails"""
        logger.warning("Hybrid search failed, falling back to full-text search")

        try:
            ft_search_request = SearchQuery(
                query=search_request.query,
                search_type=SearchType.FULLTEXT,
                limit=search_request.limit,
                offset=search_request.offset,
                filters=search_request.filters,
                include_snippets=search_request.include_snippets,
            )

            return fulltext_search_service.search(
                search_request=ft_search_request,
                user_id=user_id,
                organization_id=organization_id,
            )
        except Exception as e:
            logger.error(f"Fallback full-text search also failed: {e}")
            return SearchResponse(
                query=search_request.query,
                search_id=str(uuid.uuid4()),
                search_type=SearchType.FULLTEXT,
                results=[],
                total_results=0,
                returned_results=0,
                search_time_ms=0,
                limit=search_request.limit,
                offset=search_request.offset,
                has_more=False,
                suggestions=[],
            )


# Global hybrid search service instance
hybrid_search_service = HybridSearchService()
