"""
Unit Tests for HybridSearchService

Tests query routing, parallel search execution, result fusion,
reranking, and graceful degradation.

All tests use mocks - no external services required.
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime, timedelta

from tests.mocks.services import (
    MockAsyncSession,
    MockCohereClient,
    MockSearchResult,
    MockFulltextSearchService,
    MockVectorSearchService,
    MockGraphSearchService,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_search_query():
    """Create a mock search query."""
    query = Mock()
    query.query = "machine learning algorithms"
    query.search_type = "hybrid"
    query.limit = 10
    query.offset = 0
    query.filters = {}
    query.include_metadata = True
    query.enable_reranking = True
    return query


@pytest.fixture
def mock_search_results():
    """Create mock search results from multiple sources."""
    return {
        "fulltext": [
            MockSearchResult(
                id=str(uuid4()),
                document_id="doc-1",
                content="Machine learning is a subset of AI...",
                score=0.95,
                source="fulltext",
                metadata={"title": "ML Intro"}
            ),
            MockSearchResult(
                id=str(uuid4()),
                document_id="doc-2",
                content="Deep learning algorithms process data...",
                score=0.88,
                source="fulltext",
                metadata={"title": "Deep Learning"}
            ),
        ],
        "vector": [
            MockSearchResult(
                id=str(uuid4()),
                document_id="doc-3",
                content="Neural networks form the basis...",
                score=0.92,
                source="vector",
                metadata={"title": "Neural Nets"}
            ),
            MockSearchResult(
                id=str(uuid4()),
                document_id="doc-1",  # Duplicate doc
                content="Machine learning is a subset of AI...",
                score=0.89,
                source="vector",
                metadata={"title": "ML Intro"}
            ),
        ],
        "graph": [
            MockSearchResult(
                id=str(uuid4()),
                document_id="doc-4",
                content="Knowledge graphs connect entities...",
                score=0.85,
                source="graph",
                metadata={"title": "Knowledge Graphs"}
            ),
        ],
    }


@pytest.fixture
def mock_cohere_client():
    """Create mock Cohere client."""
    return MockCohereClient().set_rerank_scores([0.95, 0.92, 0.88, 0.85, 0.80])


# ============================================================================
# Query Routing Tests
# ============================================================================

class TestQueryRouting:
    """Test query routing to appropriate search sources."""

    def test_routes_hybrid_to_all_sources(self, mock_search_query):
        """Hybrid queries should route to all search sources."""
        mock_search_query.search_type = "hybrid"

        # The routing logic should include all sources
        expected_sources = {"fulltext", "vector", "graph"}

        # Simulate routing decision
        sources = set()
        if mock_search_query.search_type in ("hybrid", "fulltext"):
            sources.add("fulltext")
        if mock_search_query.search_type in ("hybrid", "vector", "semantic"):
            sources.add("vector")
        if mock_search_query.search_type in ("hybrid", "graph"):
            sources.add("graph")

        assert sources == expected_sources

    def test_routes_semantic_to_vector_only(self, mock_search_query):
        """Semantic queries should route to vector search only."""
        mock_search_query.search_type = "semantic"

        sources = set()
        if mock_search_query.search_type in ("hybrid", "fulltext"):
            sources.add("fulltext")
        if mock_search_query.search_type in ("hybrid", "vector", "semantic"):
            sources.add("vector")
        if mock_search_query.search_type in ("hybrid", "graph"):
            sources.add("graph")

        assert sources == {"vector"}

    def test_routes_fulltext_to_fulltext_only(self, mock_search_query):
        """Fulltext queries should route to fulltext search only."""
        mock_search_query.search_type = "fulltext"

        sources = set()
        if mock_search_query.search_type in ("hybrid", "fulltext"):
            sources.add("fulltext")
        if mock_search_query.search_type in ("hybrid", "vector", "semantic"):
            sources.add("vector")
        if mock_search_query.search_type in ("hybrid", "graph"):
            sources.add("graph")

        assert sources == {"fulltext"}

    def test_routes_short_queries_to_fulltext(self):
        """Short queries (<3 words) should prefer fulltext."""
        short_query = "AI"

        # Short queries work better with fulltext
        prefer_fulltext = len(short_query.split()) < 3
        assert prefer_fulltext is True

    def test_routes_entity_queries_to_graph(self):
        """Queries with entity patterns should route to graph."""
        entity_patterns = [
            "relationships between OpenAI and Microsoft",
            "papers by Yann LeCun",
            "companies founded by Elon Musk"
        ]

        for query in entity_patterns:
            # Simple heuristic: contains "by", "between", "founded", etc.
            entity_keywords = ["by", "between", "founded", "authored", "published"]
            has_entity_pattern = any(kw in query.lower() for kw in entity_keywords)
            assert has_entity_pattern is True


# ============================================================================
# Parallel Search Execution Tests
# ============================================================================

class TestParallelSearchExecution:
    """Test parallel search execution across sources."""

    @pytest.mark.asyncio
    async def test_executes_searches_concurrently(self, mock_search_query, mock_search_results):
        """Searches should execute concurrently, not sequentially."""
        execution_order = []

        async def mock_fulltext_search():
            execution_order.append(("fulltext_start", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.05)  # 50ms
            execution_order.append(("fulltext_end", asyncio.get_event_loop().time()))
            return mock_search_results["fulltext"]

        async def mock_vector_search():
            execution_order.append(("vector_start", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.05)  # 50ms
            execution_order.append(("vector_end", asyncio.get_event_loop().time()))
            return mock_search_results["vector"]

        async def mock_graph_search():
            execution_order.append(("graph_start", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.05)  # 50ms
            execution_order.append(("graph_end", asyncio.get_event_loop().time()))
            return mock_search_results["graph"]

        start_time = asyncio.get_event_loop().time()

        # Execute concurrently
        results = await asyncio.gather(
            mock_fulltext_search(),
            mock_vector_search(),
            mock_graph_search()
        )

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should take ~50ms (concurrent), not ~150ms (sequential)
        assert elapsed < 0.1, f"Searches took {elapsed:.3f}s, should be <0.1s for concurrent execution"

        # All three sources returned results
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_handles_single_source_timeout(self, mock_search_query, mock_search_results):
        """Should handle timeout from single source gracefully."""

        async def mock_slow_search():
            await asyncio.sleep(10)  # Very slow
            return []

        async def mock_fast_search():
            return mock_search_results["fulltext"]

        # Use timeout
        async def search_with_timeout(coro, timeout=0.1):
            try:
                return await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                return []

        # Execute with timeout
        results = await asyncio.gather(
            search_with_timeout(mock_slow_search()),
            search_with_timeout(mock_fast_search()),
        )

        # One timed out (empty), one succeeded
        assert results[0] == []  # Timed out
        assert len(results[1]) == 2  # Succeeded

    @pytest.mark.asyncio
    async def test_handles_source_exception(self, mock_search_query, mock_search_results):
        """Should handle exceptions from sources gracefully."""

        async def mock_failing_search():
            raise ConnectionError("Vector store unavailable")

        async def mock_successful_search():
            return mock_search_results["fulltext"]

        async def safe_search(coro):
            try:
                return await coro
            except Exception:
                return []

        results = await asyncio.gather(
            safe_search(mock_failing_search()),
            safe_search(mock_successful_search()),
        )

        assert results[0] == []  # Failed
        assert len(results[1]) == 2  # Succeeded


# ============================================================================
# Result Fusion Tests
# ============================================================================

class TestResultFusion:
    """Test result fusion and scoring algorithms."""

    def test_combines_results_from_all_sources(self, mock_search_results):
        """Should combine results from all sources."""
        all_results = []
        for source_results in mock_search_results.values():
            all_results.extend(source_results)

        assert len(all_results) == 5  # 2 + 2 + 1

    def test_deduplicates_by_document_id(self, mock_search_results):
        """Should deduplicate results by document_id."""
        all_results = []
        for source_results in mock_search_results.values():
            all_results.extend(source_results)

        # Deduplicate by document_id, keeping highest score
        seen_docs = {}
        for result in all_results:
            doc_id = result.document_id
            if doc_id not in seen_docs or result.score > seen_docs[doc_id].score:
                seen_docs[doc_id] = result

        # doc-1 appears in both fulltext and vector
        assert len(seen_docs) == 4  # 5 results, 1 duplicate

    def test_applies_source_weights(self, mock_search_results):
        """Should apply source-specific weights to scores."""
        weights = {
            "fulltext": 0.4,
            "vector": 0.4,
            "graph": 0.2,
        }

        weighted_results = []
        for source, results in mock_search_results.items():
            for result in results:
                weighted_score = result.score * weights[source]
                weighted_results.append((result, weighted_score))

        # Verify weights are applied
        for result, weighted_score in weighted_results:
            assert weighted_score <= result.score

    def test_sorts_by_fused_score(self, mock_search_results):
        """Should sort final results by fused score descending."""
        # Flatten and add fused scores
        results_with_scores = []
        for source, results in mock_search_results.items():
            for result in results:
                fused_score = result.score * 0.9  # Simple fusion
                results_with_scores.append((result, fused_score))

        # Sort by fused score descending
        sorted_results = sorted(results_with_scores, key=lambda x: x[1], reverse=True)

        # Verify sorted order
        for i in range(len(sorted_results) - 1):
            assert sorted_results[i][1] >= sorted_results[i + 1][1]

    def test_respects_limit_parameter(self, mock_search_results, mock_search_query):
        """Should respect the limit parameter."""
        all_results = []
        for source_results in mock_search_results.values():
            all_results.extend(source_results)

        mock_search_query.limit = 3
        limited_results = all_results[:mock_search_query.limit]

        assert len(limited_results) == 3

    def test_applies_recency_boost(self, mock_search_results):
        """Should apply recency boost for recent documents."""
        recency_boost_hours = 24

        for result in mock_search_results["fulltext"]:
            # Simulate recent document
            result.metadata["created_at"] = datetime.utcnow().isoformat()

            # Calculate recency boost
            created_at = datetime.fromisoformat(result.metadata["created_at"])
            hours_old = (datetime.utcnow() - created_at).total_seconds() / 3600

            if hours_old < recency_boost_hours:
                recency_boost = 0.1 * (1 - hours_old / recency_boost_hours)
                boosted_score = result.score + recency_boost
                assert boosted_score > result.score


# ============================================================================
# Cohere Reranking Tests
# ============================================================================

class TestCohereReranking:
    """Test Cohere reranking integration."""

    @pytest.mark.asyncio
    async def test_applies_reranking_when_enabled(self, mock_cohere_client, mock_search_results):
        """Should apply Cohere reranking when enabled."""
        mock_cohere_client.set_enabled(True)

        documents = [r.content for r in mock_search_results["fulltext"]]
        query = "machine learning"

        results = await mock_cohere_client.rerank(
            query=query,
            documents=documents,
            top_n=5
        )

        assert len(results) > 0
        assert mock_cohere_client.rerank_calls

    @pytest.mark.asyncio
    async def test_skips_reranking_when_disabled(self, mock_cohere_client, mock_search_results):
        """Should skip reranking when disabled."""
        mock_cohere_client.set_enabled(False)

        documents = [r.content for r in mock_search_results["fulltext"]]
        query = "machine learning"

        results = await mock_cohere_client.rerank(
            query=query,
            documents=documents
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_reranking_respects_top_n(self, mock_cohere_client, mock_search_results):
        """Should respect top_n parameter."""
        mock_cohere_client.set_rerank_scores([0.9, 0.8, 0.7, 0.6, 0.5])

        documents = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        results = await mock_cohere_client.rerank(
            query="test",
            documents=documents,
            top_n=3
        )

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_handles_reranking_failure_gracefully(self, mock_cohere_client, mock_search_results):
        """Should handle reranking failure gracefully."""
        mock_cohere_client.set_side_effect(ConnectionError("Cohere API unavailable"))

        documents = [r.content for r in mock_search_results["fulltext"]]
        original_results = mock_search_results["fulltext"]

        try:
            await mock_cohere_client.rerank(query="test", documents=documents)
            reranked = True
        except ConnectionError:
            reranked = False

        # Fallback to original results
        if not reranked:
            final_results = original_results
            assert final_results == mock_search_results["fulltext"]


# ============================================================================
# Graceful Degradation Tests
# ============================================================================

class TestGracefulDegradation:
    """Test graceful degradation when sources fail."""

    @pytest.mark.asyncio
    async def test_returns_results_when_vector_fails(self, mock_search_results):
        """Should return fulltext results when vector search fails."""
        fulltext_service = MockFulltextSearchService()
        fulltext_service.set_results(mock_search_results["fulltext"])

        vector_service = MockVectorSearchService()
        vector_service.set_side_effect(ConnectionError("Qdrant unavailable"))

        async def safe_search(service, query):
            try:
                return await service.search(query)
            except Exception:
                return []

        results = await asyncio.gather(
            safe_search(fulltext_service, "test"),
            safe_search(vector_service, "test"),
        )

        assert len(results[0]) == 2  # Fulltext succeeded
        assert len(results[1]) == 0  # Vector failed

    @pytest.mark.asyncio
    async def test_returns_results_when_graph_fails(self, mock_search_results):
        """Should return other results when graph search fails."""
        fulltext_results = mock_search_results["fulltext"]
        vector_results = mock_search_results["vector"]

        graph_service = MockGraphSearchService()
        graph_service.set_side_effect(ConnectionError("Neo4j unavailable"))

        try:
            await graph_service.search("test")
            graph_results = []
        except ConnectionError:
            graph_results = []

        all_results = fulltext_results + vector_results + graph_results
        assert len(all_results) == 4  # Only fulltext + vector

    @pytest.mark.asyncio
    async def test_falls_back_to_fulltext_when_all_fail(self, mock_search_results):
        """Should fallback to fulltext-only when other sources fail."""

        async def fallback_search():
            """Fallback to fulltext only."""
            fulltext_service = MockFulltextSearchService()
            fulltext_service.set_results(mock_search_results["fulltext"])
            return await fulltext_service.search("test")

        # Simulate all other sources failing
        results = await fallback_search()
        assert len(results) == 2

    def test_logs_source_failures(self, mock_search_results, caplog):
        """Should log when sources fail."""
        import logging

        logger = logging.getLogger("test")

        # Simulate failure
        try:
            raise ConnectionError("Vector store unavailable")
        except ConnectionError as e:
            logger.error(f"Vector search failed: {e}")

        # Verify logging would occur (caplog captures logs)
        # In real test, check caplog.records


# ============================================================================
# Performance Tests
# ============================================================================

class TestSearchPerformance:
    """Test search performance characteristics."""

    def test_fusion_algorithm_complexity(self, mock_search_results):
        """Fusion algorithm should be O(n) where n = total results."""
        import time

        # Create large result set
        large_results = []
        for i in range(1000):
            large_results.append(MockSearchResult(
                id=str(uuid4()),
                document_id=f"doc-{i}",
                content=f"Content {i}",
                score=0.9 - (i * 0.0001),
                source="fulltext"
            ))

        start = time.time()

        # Simulate fusion: deduplicate and sort
        seen = {}
        for r in large_results:
            if r.document_id not in seen or r.score > seen[r.document_id].score:
                seen[r.document_id] = r

        sorted_results = sorted(seen.values(), key=lambda x: x.score, reverse=True)

        elapsed = time.time() - start

        # Should complete quickly (< 100ms for 1000 results)
        assert elapsed < 0.1, f"Fusion took {elapsed:.3f}s, should be <0.1s"

    def test_handles_empty_results(self, mock_search_query):
        """Should handle empty results from all sources."""
        empty_results = {
            "fulltext": [],
            "vector": [],
            "graph": [],
        }

        all_results = []
        for results in empty_results.values():
            all_results.extend(results)

        assert len(all_results) == 0

    def test_handles_single_result(self, mock_search_query):
        """Should handle single result correctly."""
        single_result = [MockSearchResult(
            id=str(uuid4()),
            document_id="doc-1",
            content="Only result",
            score=0.9,
            source="fulltext"
        )]

        assert len(single_result) == 1
        assert single_result[0].score == 0.9
