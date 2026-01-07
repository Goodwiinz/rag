"""
Integration tests for the search pipeline.

Tests the SearchOrchestrator with all components:
- ResultFusion
- SearchReranker
- SearchCache
- SearchMetrics
"""

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.search import (
    SearchOrchestrator,
    SearchQuery,
    SearchResult,
    SearchSource,
    ResultFusion,
    SearchReranker,
    SearchCache,
    SearchMetrics,
)
from src.services.search.base import SearchExecutor


# =============================================================================
# Test Fixtures
# =============================================================================

class MockVectorExecutor(SearchExecutor):
    """Mock vector search executor."""
    
    def __init__(self, results: List[SearchResult] = None, should_fail: bool = False):
        self._results = results or []
        self._should_fail = should_fail
    
    @property
    def source_name(self) -> SearchSource:
        return SearchSource.VECTOR
    
    async def execute(self, query: SearchQuery) -> List[SearchResult]:
        if self._should_fail:
            raise RuntimeError("Vector search failed")
        return self._results


class MockGraphExecutor(SearchExecutor):
    """Mock graph search executor."""
    
    def __init__(self, results: List[SearchResult] = None, should_fail: bool = False):
        self._results = results or []
        self._should_fail = should_fail
    
    @property
    def source_name(self) -> SearchSource:
        return SearchSource.GRAPH
    
    async def execute(self, query: SearchQuery) -> List[SearchResult]:
        if self._should_fail:
            raise RuntimeError("Graph search failed")
        return self._results


class MockKeywordExecutor(SearchExecutor):
    """Mock keyword search executor."""
    
    def __init__(self, results: List[SearchResult] = None, should_fail: bool = False):
        self._results = results or []
        self._should_fail = should_fail
    
    @property
    def source_name(self) -> SearchSource:
        return SearchSource.KEYWORD
    
    async def execute(self, query: SearchQuery) -> List[SearchResult]:
        if self._should_fail:
            raise RuntimeError("Keyword search failed")
        return self._results


def create_mock_result(
    doc_id: str,
    score: float,
    source: SearchSource,
    title: str = ""
) -> SearchResult:
    """Create a mock search result."""
    return SearchResult(
        document_id=doc_id,
        score=score,
        snippet=f"Snippet for {doc_id}",
        title=title or f"Document {doc_id}",
        source=source,
        metadata={"test": True}
    )


@pytest.fixture
def vector_results() -> List[SearchResult]:
    """Vector search results fixture."""
    return [
        create_mock_result("doc1", 0.95, SearchSource.VECTOR, "Machine Learning Basics"),
        create_mock_result("doc2", 0.85, SearchSource.VECTOR, "Deep Learning Guide"),
        create_mock_result("doc3", 0.75, SearchSource.VECTOR, "Neural Networks"),
    ]


@pytest.fixture
def graph_results() -> List[SearchResult]:
    """Graph search results fixture."""
    return [
        create_mock_result("doc1", 0.90, SearchSource.GRAPH, "Machine Learning Basics"),
        create_mock_result("doc4", 0.80, SearchSource.GRAPH, "AI Applications"),
        create_mock_result("doc5", 0.70, SearchSource.GRAPH, "Data Science"),
    ]


@pytest.fixture
def keyword_results() -> List[SearchResult]:
    """Keyword search results fixture."""
    return [
        create_mock_result("doc2", 0.88, SearchSource.KEYWORD, "Deep Learning Guide"),
        create_mock_result("doc6", 0.65, SearchSource.KEYWORD, "Python Tutorial"),
    ]


@pytest.fixture
def search_query() -> SearchQuery:
    """Basic search query fixture - uses unique text to avoid cache collisions."""
    import uuid
    return SearchQuery(
        text=f"machine learning {uuid.uuid4().hex[:8]}",
        limit=10,
        user_id="test-user",
        organization_id="test-org"
    )


@pytest.fixture
def fresh_cache() -> SearchCache:
    """Create a fresh cache instance for isolated tests."""
    return SearchCache()


# =============================================================================
# Integration Tests
# =============================================================================

class TestSearchOrchestrator:
    """Integration tests for SearchOrchestrator."""
    
    @pytest.mark.asyncio
    async def test_search_returns_fused_results(
        self,
        vector_results,
        graph_results,
        keyword_results,
        search_query
    ):
        """Test that search returns fused results from multiple sources."""
        # Setup executors
        vector_executor = MockVectorExecutor(vector_results)
        graph_executor = MockGraphExecutor(graph_results)
        keyword_executor = MockKeywordExecutor(keyword_results)
        
        # Create orchestrator
        orchestrator = SearchOrchestrator(
            executors=[vector_executor, graph_executor, keyword_executor],
            fusion=ResultFusion(),
            reranker=SearchReranker(),
            cache=SearchCache(),
            metrics=SearchMetrics()
        )
        
        # Execute search
        response = await orchestrator.search(search_query)
        
        # Assertions
        assert response.results is not None
        assert len(response.results) > 0
        assert response.total_count >= len(response.results)
        assert len(response.sources_used) >= 2  # At least 2 sources contributed
        
        # Check that results are fused
        for result in response.results:
            assert result.source == SearchSource.FUSED
            assert "fusion_sources" in result.metadata
    
    @pytest.mark.asyncio
    async def test_search_handles_source_failure(
        self,
        vector_results,
        search_query
    ):
        """Test graceful degradation when a source fails."""
        # Setup with one failing executor
        vector_executor = MockVectorExecutor(vector_results)
        failing_graph_executor = MockGraphExecutor(should_fail=True)
        
        # Disable caching for this test
        from src.services.search.orchestrator import OrchestratorConfig
        config = OrchestratorConfig(enable_cache=False)
        
        orchestrator = SearchOrchestrator(
            executors=[vector_executor, failing_graph_executor],
            fusion=ResultFusion(),
            metrics=SearchMetrics(),
            config=config
        )
        
        # Execute search - should still return results
        response = await orchestrator.search(search_query)
        
        assert response.results is not None
        assert len(response.results) > 0
        # Only vector source should have contributed
        assert SearchSource.VECTOR in response.sources_used
    
    @pytest.mark.asyncio
    async def test_search_returns_cached_results(self, search_query):
        """Test that cache is used for repeated queries."""
        cached_results = [
            create_mock_result("cached1", 0.99, SearchSource.FUSED)
        ]
        
        # Create cache and pre-populate
        cache = SearchCache()
        await cache.set(search_query, cached_results)
        
        orchestrator = SearchOrchestrator(
            executors=[],  # No executors - cache should be used
            cache=cache,
            metrics=SearchMetrics()
        )
        
        response = await orchestrator.search(search_query)
        
        assert response.cache_hit is True
        assert len(response.results) == 1
        assert response.results[0].document_id == "cached1"
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, vector_results, search_query):
        """Test search with source filters."""
        vector_executor = MockVectorExecutor(vector_results)
        graph_executor = MockGraphExecutor([])
        
        orchestrator = SearchOrchestrator(
            executors=[vector_executor, graph_executor],
            fusion=ResultFusion(),
            metrics=SearchMetrics()
        )
        
        # Only include vector source
        filtered_query = SearchQuery(
            text=search_query.text,
            include_sources=[SearchSource.VECTOR],
            limit=10
        )
        
        response = await orchestrator.search(filtered_query)
        
        assert SearchSource.VECTOR in response.sources_used
        assert SearchSource.GRAPH not in response.sources_used
    
    @pytest.mark.asyncio
    async def test_search_with_min_score(self, vector_results, search_query):
        """Test search with minimum score threshold."""
        vector_executor = MockVectorExecutor(vector_results)
        
        orchestrator = SearchOrchestrator(
            executors=[vector_executor],
            fusion=ResultFusion(),
            metrics=SearchMetrics()
        )
        
        # Set high min_score
        filtered_query = SearchQuery(
            text=search_query.text,
            min_score=0.5,  # RRF scores will be much lower
            limit=10
        )
        
        response = await orchestrator.search(filtered_query)
        
        # All results should be above min_score
        for result in response.results:
            assert result.score >= filtered_query.min_score
    
    @pytest.mark.asyncio
    async def test_health_check(self, vector_results):
        """Test orchestrator health check."""
        vector_executor = MockVectorExecutor(vector_results)
        
        orchestrator = SearchOrchestrator(
            executors=[vector_executor],
            fusion=ResultFusion(),
            metrics=SearchMetrics()
        )
        
        health = await orchestrator.health_check()
        
        assert "status" in health
        assert "executors" in health
        assert "vector" in health["executors"]
    
    @pytest.mark.asyncio
    async def test_get_stats(self, vector_results, search_query):
        """Test stats collection."""
        vector_executor = MockVectorExecutor(vector_results)
        
        orchestrator = SearchOrchestrator(
            executors=[vector_executor],
            fusion=ResultFusion(),
            metrics=SearchMetrics()
        )
        
        # Execute a search to generate stats
        await orchestrator.search(search_query)
        
        stats = orchestrator.get_stats()
        
        assert "metrics" in stats
        assert stats["metrics"]["total_searches"] == 1


class TestResultFusion:
    """Integration tests for ResultFusion."""
    
    def test_fuse_deduplicates_results(
        self,
        vector_results,
        graph_results
    ):
        """Test that fusion deduplicates results by document_id."""
        fusion = ResultFusion()
        
        # Combine results (doc1 appears in both)
        all_results = vector_results + graph_results
        
        fused = fusion.fuse(all_results)
        
        # Count unique document IDs
        doc_ids = [r.document_id for r in fused]
        assert len(doc_ids) == len(set(doc_ids))
    
    def test_fuse_boosts_multi_source_results(
        self,
        vector_results,
        graph_results
    ):
        """Test that results from multiple sources get boosted."""
        fusion = ResultFusion()
        
        all_results = vector_results + graph_results
        fused = fusion.fuse(all_results)
        
        # doc1 appears in both sources - should have multi-source boost
        doc1_result = next(r for r in fused if r.document_id == "doc1")
        
        assert len(doc1_result.metadata["fusion_sources"]) == 2
        assert doc1_result.metadata["source_count"] == 2
    
    def test_fuse_with_empty_results(self):
        """Test fusion with empty input."""
        fusion = ResultFusion()
        
        fused = fusion.fuse([])
        
        assert fused == []
    
    def test_fusion_stats(self, vector_results, graph_results):
        """Test that fusion tracks statistics."""
        fusion = ResultFusion()
        
        # Perform multiple fusions
        fusion.fuse(vector_results)
        fusion.fuse(graph_results)
        
        stats = fusion.get_stats()
        
        assert stats["total_fusions"] == 2
        assert stats["avg_results_per_fusion"] > 0


class TestSearchReranker:
    """Integration tests for SearchReranker."""
    
    @pytest.mark.asyncio
    async def test_rerank_fallback(self, vector_results):
        """Test fallback reranking when Cohere is unavailable."""
        reranker = SearchReranker()  # No API key = fallback
        
        reranked = await reranker.rerank(
            "machine learning",
            vector_results,
            top_n=2
        )
        
        assert len(reranked) <= 2
        assert reranked[0].metadata.get("reranker") == "fallback"
    
    @pytest.mark.asyncio
    async def test_rerank_preserves_metadata(self, vector_results):
        """Test that reranking preserves original metadata."""
        reranker = SearchReranker()
        
        reranked = await reranker.rerank(
            "machine learning",
            vector_results
        )
        
        for result in reranked:
            assert "original_score" in result.metadata
    
    @pytest.mark.asyncio
    async def test_rerank_with_few_results(self):
        """Test reranking with fewer than minimum results."""
        reranker = SearchReranker()
        
        few_results = [
            create_mock_result("doc1", 0.9, SearchSource.VECTOR)
        ]
        
        reranked = await reranker.rerank("test", few_results)
        
        # Should return as-is without reranking
        assert len(reranked) == 1


class TestSearchCache:
    """Integration tests for SearchCache."""
    
    @pytest.mark.asyncio
    async def test_cache_hit(self, search_query, vector_results, fresh_cache):
        """Test cache hit scenario."""
        cache = fresh_cache
        
        # Set cache
        await cache.set(search_query, vector_results)
        
        # Get from cache
        cached = await cache.get(search_query)
        
        assert cached is not None
        assert len(cached) == len(vector_results)
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, fresh_cache):
        """Test cache miss scenario."""
        cache = fresh_cache
        
        # Create a unique query that was never cached
        unique_query = SearchQuery(
            text="definitely never cached query 12345",
            limit=10
        )
        
        cached = await cache.get(unique_query)
        
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_cache_key_varies_by_filters(self, fresh_cache):
        """Test that different filters produce different cache keys."""
        cache = fresh_cache
        
        query1 = SearchQuery(text="test", filters={"type": "pdf"})
        query2 = SearchQuery(text="test", filters={"type": "doc"})
        
        results = [create_mock_result("doc1", 0.9, SearchSource.VECTOR)]
        
        await cache.set(query1, results)
        
        # Different filter should be a cache miss
        cached = await cache.get(query2)
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, search_query, vector_results, fresh_cache):
        """Test cache invalidation."""
        cache = fresh_cache
        
        await cache.set(search_query, vector_results)
        await cache.invalidate(search_query)
        
        cached = await cache.get(search_query)
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, vector_results):
        """Test cache statistics."""
        # Create a fresh cache with Redis disabled to test memory cache only
        from src.services.search.cache import CacheConfig
        config = CacheConfig(use_redis=False)
        cache = SearchCache(config=config)
        
        # Create a unique query for this test
        import uuid
        unique_query = SearchQuery(
            text=f"unique stats test query {uuid.uuid4().hex}",
            limit=10
        )
        
        # Miss
        await cache.get(unique_query)
        
        # Set and hit
        await cache.set(unique_query, vector_results)
        await cache.get(unique_query)
        
        stats = cache.get_stats()
        
        assert stats["memory"]["hits"] >= 1
        assert stats["memory"]["misses"] >= 1


class TestSearchMetrics:
    """Integration tests for SearchMetrics."""
    
    def test_record_search(self, search_query, vector_results):
        """Test recording a search."""
        metrics = SearchMetrics()
        
        metrics.record_search(
            query=search_query,
            results=vector_results,
            execution_time_ms=150.0,
            sources_used=[SearchSource.VECTOR]
        )
        
        summary = metrics.get_summary()
        
        assert summary["total_searches"] == 1
        assert summary["avg_latency_ms"] == 150.0
    
    def test_quality_metrics(self, search_query, vector_results):
        """Test quality metrics calculation."""
        metrics = SearchMetrics()
        
        metrics.record_search(
            query=search_query,
            results=vector_results,
            execution_time_ms=100.0,
            sources_used=[SearchSource.VECTOR]
        )
        
        quality = metrics.get_quality_metrics()
        
        assert "avg_result_score" in quality
        assert "avg_top_score" in quality
    
    def test_latency_buckets(self, search_query, vector_results):
        """Test latency bucket distribution."""
        metrics = SearchMetrics()
        
        # Record searches with different latencies
        for latency in [50, 150, 750, 1500, 2500]:
            metrics.record_search(
                query=search_query,
                results=vector_results,
                execution_time_ms=latency,
                sources_used=[SearchSource.VECTOR]
            )
        
        summary = metrics.get_summary()
        
        assert summary["latency_distribution"]["<100ms"] >= 1
        assert summary["latency_distribution"]["100-500ms"] >= 1
        assert summary["latency_distribution"][">2000ms"] >= 1


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreakerIntegration:
    """Tests for circuit breaker behavior in search pipeline."""
    
    @pytest.mark.asyncio
    async def test_continues_with_failing_source(self, vector_results):
        """Test that search continues when one source fails repeatedly."""
        vector_executor = MockVectorExecutor(vector_results)
        failing_executor = MockGraphExecutor(should_fail=True)
        
        # Disable cache to ensure fresh searches
        from src.services.search.orchestrator import OrchestratorConfig
        config = OrchestratorConfig(enable_cache=False)
        
        orchestrator = SearchOrchestrator(
            executors=[vector_executor, failing_executor],
            metrics=SearchMetrics(),
            config=config
        )
        
        # Multiple searches should still work despite one source failing
        import uuid
        for i in range(5):
            query = SearchQuery(
                text=f"test query {uuid.uuid4().hex}",
                limit=10
            )
            response = await orchestrator.search(query)
            # Should still get results from the working source
            assert response.results is not None
            assert len(response.results) > 0
        
        # Check that searches completed successfully
        stats = orchestrator.get_stats()
        assert stats["metrics"]["total_searches"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
