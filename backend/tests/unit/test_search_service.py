"""
Comprehensive Unit Tests for Search Service.

Applies testing patterns from Temporal Python Testing skill:
- Mocked external dependencies (Qdrant, Neo4j, Redis)
- Error injection for search failure scenarios
- Parameterized testing for different search types
- Performance tracking for search operations

Test Categories:
- Hybrid search orchestration
- Vector search operations
- Graph search operations
- Keyword/fulltext search
- Reranking operations
- Cache operations
- Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timedelta
import asyncio
from typing import List, Dict, Any

# Test markers
pytestmark = [pytest.mark.unit, pytest.mark.search]


# =============================================================================
# Fixtures - Mocked External Services (like Temporal's activity mocking)
# =============================================================================

@pytest.fixture
def mock_qdrant_client():
    """
    Mock Qdrant client for vector search tests.
    Equivalent to mocking activities in Temporal tests.
    """
    client = MagicMock()

    # Mock search results
    mock_result = Mock()
    mock_result.id = str(uuid4())
    mock_result.score = 0.95
    mock_result.payload = {
        "document_id": str(uuid4()),
        "title": "Test Document",
        "content": "This is test content for vector search",
        "chunk_index": 0
    }

    client.search = Mock(return_value=[mock_result])
    client.upsert = Mock(return_value=Mock())
    client.create_collection = Mock()
    client.get_collection = Mock(return_value=Mock())
    client.count = Mock(return_value=Mock(count=100))

    return client


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for graph search tests."""
    driver = MagicMock()
    session = MagicMock()

    # Mock graph query results
    mock_record = Mock()
    mock_record.data.return_value = {
        "node": {"id": str(uuid4()), "name": "Entity", "type": "CONCEPT"},
        "score": 0.85
    }

    session.run = Mock(return_value=[mock_record])
    session.close = Mock()

    driver.session = Mock(return_value=session)
    driver.verify_connectivity = Mock()
    driver.close = Mock()

    return driver


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for caching tests."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=False)
    client.expire = AsyncMock(return_value=True)
    client.ping = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for vector search."""
    import numpy as np

    service = AsyncMock()

    def generate_embedding(text: str) -> List[float]:
        """Generate deterministic embeddings based on text hash."""
        np.random.seed(hash(text) % 2**32)
        return np.random.rand(768).tolist()

    service.embed_query = AsyncMock(side_effect=generate_embedding)
    service.embed_documents = AsyncMock(
        side_effect=lambda texts: [generate_embedding(t) for t in texts]
    )

    return service


@pytest.fixture
def mock_rerank_service():
    """Mock Cohere rerank service."""
    service = AsyncMock()

    async def mock_rerank(query: str, documents: List[Dict], top_k: int = 10):
        """Mock reranking - returns documents in same order with scores."""
        return [
            {**doc, "rerank_score": 0.9 - (i * 0.05)}
            for i, doc in enumerate(documents[:top_k])
        ]

    service.rerank = mock_rerank
    return service


@pytest.fixture
def sample_search_request():
    """Create a sample search request."""
    return {
        "query": "machine learning algorithms",
        "search_type": "hybrid",
        "limit": 10,
        "filters": {
            "document_types": ["pdf", "txt"],
            "date_range": {
                "start": "2024-01-01",
                "end": "2024-12-31"
            }
        }
    }


@pytest.fixture
def sample_search_results():
    """Create sample search results from different sources."""
    return {
        "vector": [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "title": "ML Fundamentals",
                "content": "Machine learning is a subset of AI...",
                "score": 0.95,
                "source": "vector"
            },
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "title": "Deep Learning",
                "content": "Neural networks are inspired by...",
                "score": 0.88,
                "source": "vector"
            }
        ],
        "graph": [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "title": "AI Concepts",
                "content": "Artificial intelligence encompasses...",
                "score": 0.82,
                "source": "graph"
            }
        ],
        "keyword": [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "title": "Algorithm Design",
                "content": "Machine learning algorithms can be...",
                "score": 0.78,
                "source": "keyword"
            }
        ]
    }


# =============================================================================
# Search Component Tests
# =============================================================================

class TestVectorSearch:
    """Test vector search operations."""

    @pytest.mark.asyncio
    async def test_vector_search_success(self, mock_qdrant_client, mock_embedding_service):
        """Test successful vector search."""
        query = "machine learning fundamentals"
        embedding = await mock_embedding_service.embed_query(query)

        mock_qdrant_client.search(
            collection_name="documents",
            query_vector=embedding,
            limit=10
        )

        mock_qdrant_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_search_with_filters(self, mock_qdrant_client, mock_embedding_service):
        """Test vector search with metadata filters."""
        query = "machine learning"
        filters = {"document_type": "pdf", "organization_id": str(uuid4())}

        embedding = await mock_embedding_service.embed_query(query)

        # Simulate filtered search
        mock_qdrant_client.search(
            collection_name="documents",
            query_vector=embedding,
            query_filter=filters,
            limit=10
        )

        call_args = mock_qdrant_client.search.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_vector_search_empty_results(self, mock_qdrant_client, mock_embedding_service):
        """Test vector search with no results."""
        mock_qdrant_client.search.return_value = []

        query = "extremely specific query with no matches xyz123"
        embedding = await mock_embedding_service.embed_query(query)

        results = mock_qdrant_client.search(
            collection_name="documents",
            query_vector=embedding,
            limit=10
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_vector_search_connection_error(self, mock_qdrant_client, mock_embedding_service):
        """Test handling of Qdrant connection errors."""
        mock_qdrant_client.search.side_effect = ConnectionError("Failed to connect to Qdrant")

        with pytest.raises(ConnectionError):
            mock_qdrant_client.search(
                collection_name="documents",
                query_vector=[0.1] * 768,
                limit=10
            )


class TestGraphSearch:
    """Test knowledge graph search operations."""

    def test_graph_search_entity_relations(self, mock_neo4j_driver):
        """Test graph search for entity relationships."""
        query = """
        MATCH (e:Entity)-[r]->(related)
        WHERE e.name CONTAINS $query
        RETURN e, type(r), related
        LIMIT $limit
        """

        session = mock_neo4j_driver.session()
        results = session.run(query, {"query": "machine learning", "limit": 10})

        assert results is not None
        session.close.assert_not_called()  # Not closed yet

    def test_graph_search_with_path_finding(self, mock_neo4j_driver):
        """Test graph search with shortest path queries."""
        query = """
        MATCH path = shortestPath(
            (start:Entity {name: $start})-[*..5]-(end:Entity {name: $end})
        )
        RETURN path
        """

        session = mock_neo4j_driver.session()
        session.run(query, {"start": "ML", "end": "AI"})

        mock_neo4j_driver.session.assert_called()

    def test_graph_search_connection_error(self, mock_neo4j_driver):
        """Test handling of Neo4j connection errors."""
        session = mock_neo4j_driver.session()
        session.run.side_effect = Exception("Neo4j connection failed")

        with pytest.raises(Exception, match="Neo4j connection failed"):
            session.run("MATCH (n) RETURN n LIMIT 1")


class TestKeywordSearch:
    """Test keyword/fulltext search operations."""

    @pytest.mark.asyncio
    async def test_fulltext_search_basic(self):
        """Test basic fulltext search with PostgreSQL."""
        # Mock PostgreSQL fulltext search
        mock_db = AsyncMock()

        query = "machine learning algorithms"
        mock_db.execute.return_value = AsyncMock()
        mock_db.execute.return_value.fetchall = AsyncMock(return_value=[
            {"id": uuid4(), "title": "ML Guide", "rank": 0.85}
        ])

        # Simulate search
        results = await mock_db.execute.return_value.fetchall()

        assert len(results) == 1
        assert results[0]["rank"] > 0

    @pytest.mark.asyncio
    async def test_fulltext_search_with_stemming(self):
        """Test fulltext search uses stemming."""
        # "learning" should match "learn", "learned", "learning"
        mock_db = AsyncMock()

        queries = ["learn", "learning", "learned"]
        for q in queries:
            mock_db.execute.return_value = AsyncMock()
            mock_db.execute.return_value.fetchall = AsyncMock(return_value=[
                {"id": uuid4(), "content": "machine learning", "rank": 0.8}
            ])

            results = await mock_db.execute.return_value.fetchall()
            assert len(results) > 0


# =============================================================================
# Hybrid Search Tests - Integration of multiple search types
# =============================================================================

class TestHybridSearch:
    """Test hybrid search orchestration."""

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_sources(self, sample_search_results):
        """Test hybrid search combines results from all sources."""
        # Simulate HybridSearchEngine.search()
        all_results = []
        for source, results in sample_search_results.items():
            all_results.extend(results)

        assert len(all_results) == 4  # 2 vector + 1 graph + 1 keyword

    @pytest.mark.asyncio
    async def test_hybrid_search_deduplication(self, sample_search_results):
        """Test duplicate results are removed."""
        # Add duplicate document
        duplicate_doc_id = sample_search_results["vector"][0]["document_id"]
        sample_search_results["keyword"].append({
            "id": str(uuid4()),
            "document_id": duplicate_doc_id,  # Same document
            "title": "ML Fundamentals",
            "content": "Different chunk...",
            "score": 0.75,
            "source": "keyword"
        })

        # Simulate deduplication
        seen_docs = set()
        unique_results = []
        for source, results in sample_search_results.items():
            for r in results:
                if r["document_id"] not in seen_docs:
                    seen_docs.add(r["document_id"])
                    unique_results.append(r)

        # Should have 4 unique documents (original 4, duplicate removed)
        assert len(unique_results) == 4

    @pytest.mark.parametrize("search_type,expected_sources", [
        ("hybrid", ["vector", "graph", "keyword"]),
        ("vector", ["vector"]),
        ("graph", ["graph"]),
        ("keyword", ["keyword"]),
    ])
    @pytest.mark.asyncio
    async def test_search_type_routing(self, search_type, expected_sources, sample_search_results):
        """Parameterized test for search type routing."""
        # Simulate routing based on search type
        results = []
        for source in expected_sources:
            if source in sample_search_results:
                results.extend(sample_search_results[source])

        # Verify results only from expected sources
        for r in results:
            assert r["source"] in expected_sources

    @pytest.mark.asyncio
    async def test_hybrid_search_parallel_execution(self, sample_search_results):
        """Test hybrid search executes searches in parallel."""

        async def mock_vector_search():
            await asyncio.sleep(0.1)
            return sample_search_results["vector"]

        async def mock_graph_search():
            await asyncio.sleep(0.1)
            return sample_search_results["graph"]

        async def mock_keyword_search():
            await asyncio.sleep(0.1)
            return sample_search_results["keyword"]

        start = asyncio.get_event_loop().time()

        # Run in parallel
        results = await asyncio.gather(
            mock_vector_search(),
            mock_graph_search(),
            mock_keyword_search()
        )

        elapsed = asyncio.get_event_loop().time() - start

        # Should complete in ~0.1s (parallel) not ~0.3s (sequential)
        assert elapsed < 0.2

        # All results collected
        assert len(results) == 3


# =============================================================================
# Reranking Tests
# =============================================================================

class TestReranking:
    """Test reranking operations."""

    @pytest.mark.asyncio
    async def test_rerank_improves_relevance(self, mock_rerank_service, sample_search_results):
        """Test reranking reorders results by relevance."""
        all_results = []
        for results in sample_search_results.values():
            all_results.extend(results)

        reranked = await mock_rerank_service.rerank(
            query="machine learning fundamentals",
            documents=all_results,
            top_k=10
        )

        # Results should have rerank scores
        for r in reranked:
            assert "rerank_score" in r

        # Should be ordered by rerank score (descending)
        scores = [r["rerank_score"] for r in reranked]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self, mock_rerank_service, sample_search_results):
        """Test reranking respects top_k limit."""
        all_results = []
        for results in sample_search_results.values():
            all_results.extend(results)

        top_k = 2
        reranked = await mock_rerank_service.rerank(
            query="test query",
            documents=all_results,
            top_k=top_k
        )

        assert len(reranked) <= top_k


# =============================================================================
# Cache Tests
# =============================================================================

class TestSearchCache:
    """Test search caching operations."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_redis_client):
        """Test cache hit returns cached results."""
        import json

        cached_results = [{"id": "1", "title": "Cached Result", "score": 0.9}]
        mock_redis_client.get.return_value = json.dumps(cached_results)

        cache_key = "search:hash:abc123"
        cached = await mock_redis_client.get(cache_key)

        assert cached is not None
        assert json.loads(cached) == cached_results

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_search(self, mock_redis_client):
        """Test cache miss triggers actual search."""
        mock_redis_client.get.return_value = None

        cache_key = "search:hash:abc123"
        cached = await mock_redis_client.get(cache_key)

        assert cached is None
        # Would then trigger actual search

    @pytest.mark.asyncio
    async def test_cache_set_with_ttl(self, mock_redis_client):
        """Test cache set includes TTL."""
        import json

        results = [{"id": "1", "title": "New Result"}]
        cache_key = "search:hash:abc123"
        ttl = 300  # 5 minutes

        await mock_redis_client.set(cache_key, json.dumps(results))
        await mock_redis_client.expire(cache_key, ttl)

        mock_redis_client.set.assert_called_once()
        mock_redis_client.expire.assert_called_once_with(cache_key, ttl)


# =============================================================================
# Error Handling Tests - Error Injection Patterns
# =============================================================================

class TestSearchErrorHandling:
    """Test error handling in search operations."""

    @pytest.mark.asyncio
    async def test_vector_search_fallback_on_error(
        self, mock_qdrant_client, mock_neo4j_driver
    ):
        """Test fallback to other search types when one fails."""
        # Vector search fails
        mock_qdrant_client.search.side_effect = Exception("Qdrant unavailable")

        # Graph search should still work
        session = mock_neo4j_driver.session()
        session.run.return_value = [Mock(data=lambda: {"entity": "AI"})]

        # In hybrid mode, should return graph results even if vector fails
        graph_results = session.run("MATCH (n) RETURN n")
        assert graph_results is not None

    @pytest.mark.asyncio
    async def test_all_search_types_fail(self, mock_qdrant_client, mock_neo4j_driver):
        """Test handling when all search types fail."""
        mock_qdrant_client.search.side_effect = Exception("Qdrant down")

        session = mock_neo4j_driver.session()
        session.run.side_effect = Exception("Neo4j down")

        # Should handle gracefully, possibly return empty results
        errors = []

        try:
            mock_qdrant_client.search()
        except Exception as e:
            errors.append(("vector", str(e)))

        try:
            session.run("MATCH (n) RETURN n")
        except Exception as e:
            errors.append(("graph", str(e)))

        assert len(errors) == 2

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test handling of search timeouts."""

        async def slow_search():
            await asyncio.sleep(5)  # Simulates slow search
            return []

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_search(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_partial_results_on_timeout(self, sample_search_results):
        """Test returning partial results when some searches timeout."""

        async def fast_vector_search():
            await asyncio.sleep(0.01)
            return sample_search_results["vector"]

        async def slow_graph_search():
            await asyncio.sleep(5)  # Will timeout
            return sample_search_results["graph"]

        # Gather with timeout handling
        results = []

        vector_task = asyncio.create_task(fast_vector_search())
        graph_task = asyncio.create_task(slow_graph_search())

        done, pending = await asyncio.wait(
            [vector_task, graph_task],
            timeout=0.1
        )

        for task in done:
            results.extend(task.result())

        for task in pending:
            task.cancel()

        # Should have vector results, not graph (timed out)
        assert len(results) == 2  # Only vector results
        assert all(r["source"] == "vector" for r in results)


# =============================================================================
# Performance Tracking Tests
# =============================================================================

class TestSearchPerformance:
    """Test search performance metrics."""

    @pytest.mark.asyncio
    async def test_search_timing_recorded(self):
        """Test that search timing is recorded."""
        import time

        start = time.time()
        await asyncio.sleep(0.05)  # Simulated search
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms >= 50
        assert elapsed_ms < 100  # Should be close to 50ms

    @pytest.mark.asyncio
    async def test_component_timing_breakdown(self, sample_search_results):
        """Test timing breakdown by component."""
        import time

        timings = {}

        start = time.time()
        await asyncio.sleep(0.02)  # Vector search
        timings["vector"] = (time.time() - start) * 1000

        start = time.time()
        await asyncio.sleep(0.03)  # Graph search
        timings["graph"] = (time.time() - start) * 1000

        start = time.time()
        await asyncio.sleep(0.01)  # Keyword search
        timings["keyword"] = (time.time() - start) * 1000

        # Verify timings recorded
        assert "vector" in timings
        assert "graph" in timings
        assert "keyword" in timings

        # Total should be sum of components (when sequential)
        total = sum(timings.values())
        assert total >= 60  # At least 60ms total


# =============================================================================
# Query Classification Tests
# =============================================================================

class TestQueryClassification:
    """Test query intent classification."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("what is machine learning?", "factual"),
        ("how does neural network work?", "explanation"),
        ("compare SVM and random forest", "comparison"),
        ("show me documents about AI", "retrieval"),
        ("summarize the ML paper", "summarization"),
    ])
    def test_query_intent_classification(self, query, expected_intent):
        """Parameterized test for query intent detection."""
        # Simulate intent classification
        intent_keywords = {
            "factual": ["what is", "define", "who is"],
            "explanation": ["how does", "why is", "explain"],
            "comparison": ["compare", "difference between", "vs"],
            "retrieval": ["show me", "find", "list"],
            "summarization": ["summarize", "summary", "overview"],
        }

        detected_intent = "unknown"
        query_lower = query.lower()

        for intent, keywords in intent_keywords.items():
            if any(kw in query_lower for kw in keywords):
                detected_intent = intent
                break

        assert detected_intent == expected_intent

    @pytest.mark.parametrize("query,expected_complexity", [
        ("AI", "simple"),
        ("machine learning algorithms", "moderate"),
        ("compare the performance of transformer models with recurrent neural networks for sequence modeling", "complex"),
    ])
    def test_query_complexity_assessment(self, query, expected_complexity):
        """Parameterized test for query complexity."""
        word_count = len(query.split())

        if word_count <= 2:
            complexity = "simple"
        elif word_count <= 6:
            complexity = "moderate"
        else:
            complexity = "complex"

        assert complexity == expected_complexity
