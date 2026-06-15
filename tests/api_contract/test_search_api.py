"""
Search API Contract Tests
Comprehensive testing for search functionality including hybrid search, advanced search, and search history
"""

import pytest
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.contract
@pytest.mark.search
class TestSearchQueryAPI:
    """Test search query submission endpoints"""

    def test_hybrid_search_success(self, test_client: TestClient, auth_headers):
        """Test successful hybrid search query"""
        headers = auth_headers({"email": "search@example.com", "first_name": "Search", "last_name": "User"})

        search_data = {
            "query": "machine learning algorithms",
            "search_type": "hybrid",
            "max_results": 10,
            "include_metadata": True,
            "filters": {
                "document_types": ["pdf", "text"],
                "tags": ["machine learning", "algorithms"]
            },
            "rerank": True,
            "rerank_weights": {
                "semantic": 0.4,
                "keyword": 0.3,
                "graph": 0.3
            }
        }

        response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "query_id" in response_data
        assert "results" in response_data
        assert "total_results" in response_data
        assert "search_metadata" in response_data
        assert "execution_time_ms" in response_data

        # Verify results structure
        assert isinstance(response_data["results"], list)
        assert response_data["total_results"] >= 0

        if response_data["results"]:
            first_result = response_data["results"][0]
            assert "document_id" in first_result
            assert "title" in first_result
            assert "score" in first_result
            assert "content_preview" in first_result
            assert "highlights" in first_result
            assert "document_type" in first_result

    def test_fulltext_search_success(self, test_client: TestClient, auth_headers):
        """Test successful full-text search query"""
        headers = auth_headers({"email": "fulltext@example.com", "first_name": "Full", "last_name": "Text"})

        search_data = {
            "query": "natural language processing",
            "search_type": "fulltext",
            "max_results": 5,
            "include_metadata": False,
            "filters": {
                "document_types": ["pdf"]
            }
        }

        response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "query_id" in response_data
        assert "results" in response_data
        assert len(response_data["results"]) <= 5

    def test_vector_search_success(self, test_client: TestClient, auth_headers):
        """Test successful vector search query"""
        headers = auth_headers({"email": "vector@example.com", "first_name": "Vector", "last_name": "Search"})

        search_data = {
            "query": "deep learning neural networks",
            "search_type": "vector",
            "max_results": 8,
            "similarity_threshold": 0.7,
            "include_metadata": True
        }

        response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "query_id" in response_data
        assert "results" in response_data

        # Check that vector search results have similarity scores
        if response_data["results"]:
            for result in response_data["results"]:
                assert "similarity_score" in result
                assert 0 <= result["similarity_score"] <= 1

    def test_graph_search_success(self, test_client: TestClient, auth_headers):
        """Test successful knowledge graph search query"""
        headers = auth_headers({"email": "graph@example.com", "first_name": "Graph", "last_name": "Search"})

        search_data = {
            "query": "computer vision applications",
            "search_type": "graph",
            "max_results": 10,
            "include_metadata": True,
            "graph_filters": {
                "entity_types": ["person", "organization", "technology"],
                "relationship_types": ["uses", "mentions", "relates_to"]
            }
        }

        response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "query_id" in response_data
        assert "results" in response_data

        # Graph search results should include entity information
        if response_data["results"]:
            for result in response_data["results"]:
                assert "entities" in result
                assert "relationships" in result

    def test_search_query_validation_error(self, test_client: TestClient, auth_headers):
        """Test search query with validation errors"""
        headers = auth_headers({"email": "invalid@example.com", "first_name": "Invalid", "last_name": "Query"})

        # Invalid search data
        search_data = {
            "query": "",  # Empty query
            "search_type": "invalid_type",  # Invalid search type
            "max_results": -1  # Invalid max results
        }

        response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 422  # Validation error
        response_data = response.json()
        assert "detail" in response_data

    def test_search_query_unauthorized(self, test_client: TestClient):
        """Test search query without authentication"""
        search_data = {
            "query": "test query",
            "search_type": "hybrid",
            "max_results": 10
        }

        response = test_client.post("/api/v1/search/", json=search_data)

        assert response.status_code == 401

    def test_search_query_too_long(self, test_client: TestClient, auth_headers):
        """Test search query exceeding length limits"""
        headers = auth_headers({"email": "longquery@example.com", "first_name": "Long", "last_name": "Query"})

        # Very long query
        long_query = "test " * 1000
        search_data = {
            "query": long_query,
            "search_type": "hybrid",
            "max_results": 10
        }

        response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 400
        response_data = response.json()
        assert "too long" in response_data["error"]["message"].lower()

    def test_search_with_complex_filters(self, test_client: TestClient, auth_headers):
        """Test search with complex filtering criteria"""
        headers = auth_headers({"email": "filters@example.com", "first_name": "Complex", "last_name": "Filters"})

        search_data = {
            "query": "artificial intelligence",
            "search_type": "hybrid",
            "max_results": 20,
            "filters": {
                "document_types": ["pdf", "text", "video"],
                "tags": ["AI", "machine learning", "neural networks"],
                "date_range": {
                    "start_date": "2023-01-01",
                    "end_date": "2024-12-31"
                },
                "file_size_range": {
                    "min_mb": 1,
                    "max_mb": 100
                },
                "processing_status": ["completed"]
            },
            "sort_by": "relevance",
            "sort_order": "desc"
        }

        response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "query_id" in response_data
        assert "results" in response_data
        assert "search_metadata" in response_data


@pytest.mark.contract
@pytest.mark.search
class TestSearchResultsAPI:
    """Test search results retrieval endpoints"""

    def test_get_search_results_success(self, test_client: TestClient, auth_headers):
        """Test successful search results retrieval"""
        headers = auth_headers({"email": "results@example.com", "first_name": "Results", "last_name": "User"})

        # First submit a search
        search_data = {
            "query": "data science",
            "search_type": "hybrid",
            "max_results": 10
        }

        search_response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert search_response.status_code == 200
        query_id = search_response.json()["query_id"]

        # Get search results
        response = test_client.get(
            f"/api/v1/search/{query_id}",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "query_id" in response_data
        assert "query" in response_data
        assert "results" in response_data
        assert "total_results" in response_data
        assert "search_metadata" in response_data
        assert "status" in response_data

        # Status should be one of the expected values
        valid_statuses = ["processing", "completed", "failed", "expired"]
        assert response_data["status"] in valid_statuses

    def test_get_search_results_not_found(self, test_client: TestClient, auth_headers):
        """Test search results for non-existent query"""
        headers = auth_headers({"email": "notfound@example.com", "first_name": "Not", "last_name": "Found"})

        fake_query_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/search/{fake_query_id}",
            headers=headers
        )

        assert response.status_code == 404
        response_data = response.json()
        assert "not found" in response_data["error"]["message"].lower()

    def test_get_search_results_unauthorized(self, test_client: TestClient):
        """Test search results without authentication"""
        query_id = str(uuid.uuid4())
        response = test_client.get(f"/api/v1/search/{query_id}")

        assert response.status_code == 401

    def test_get_search_results_with_pagination(self, test_client: TestClient, auth_headers):
        """Test search results with pagination"""
        headers = auth_headers({"email": "paginate@example.com", "first_name": "Paginate", "last_name": "Results"})

        # Submit a search
        search_data = {
            "query": "machine learning",
            "search_type": "hybrid",
            "max_results": 50
        }

        search_response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        query_id = search_response.json()["query_id"]

        # Get paginated results
        response = test_client.get(
            f"/api/v1/search/{query_id}?page=1&page_size=5",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "pagination" in response_data
        assert response_data["pagination"]["page"] == 1
        assert response_data["pagination"]["page_size"] == 5
        assert len(response_data["results"]) <= 5

    def test_get_expired_search_results(self, test_client: TestClient, auth_headers):
        """Test retrieval of expired search results"""
        headers = auth_headers({"email": "expired@example.com", "first_name": "Expired", "last_name": "Results"})

        # This would require mocking expired results or using a test query that has expired
        # For now, test the structure
        fake_query_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/search/{fake_query_id}",
            headers=headers
        )

        # Should return 404 for expired queries
        assert response.status_code in [404, 410]  # Not Found or Gone


@pytest.mark.contract
@pytest.mark.search
class TestSearchHistoryAPI:
    """Test search history endpoints"""

    def test_get_search_history_success(self, test_client: TestClient, auth_headers):
        """Test successful search history retrieval"""
        headers = auth_headers({"email": "history@example.com", "first_name": "History", "last_name": "User"})

        response = test_client.get(
            "/api/v1/search/history",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "searches" in response_data
        assert "pagination" in response_data
        assert isinstance(response_data["searches"], list)

        # Verify search history entry structure
        if response_data["searches"]:
            first_search = response_data["searches"][0]
            assert "query_id" in first_search
            assert "query" in first_search
            assert "search_type" in first_search
            assert "created_at" in first_search
            assert "total_results" in first_search
            assert "status" in first_search

    def test_get_search_history_with_date_filter(self, test_client: TestClient, auth_headers):
        """Test search history with date filtering"""
        headers = auth_headers({"email": "datefilter@example.com", "first_name": "Date", "last_name": "Filter"})

        # Get search history for last 7 days
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        response = test_client.get(
            f"/api/v1/search/history?start_date={seven_days_ago}",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "searches" in response_data
        assert "pagination" in response_data

        # All searches should be within the date range
        if response_data["searches"]:
            for search in response_data["searches"]:
                search_date = datetime.fromisoformat(search["created_at"])
                assert search_date >= datetime.fromisoformat(seven_days_ago)

    def test_get_search_history_with_pagination(self, test_client: TestClient, auth_headers):
        """Test search history with pagination"""
        headers = auth_headers({"email": "historypage@example.com", "first_name": "History", "last_name": "Page"})

        response = test_client.get(
            "/api/v1/search/history?page=1&page_size=5",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["pagination"]["page"] == 1
        assert response_data["pagination"]["page_size"] == 5
        assert len(response_data["searches"]) <= 5

    def test_get_search_history_unauthorized(self, test_client: TestClient):
        """Test search history without authentication"""
        response = test_client.get("/api/v1/search/history")

        assert response.status_code == 401

    def test_clear_search_history_success(self, test_client: TestClient, auth_headers):
        """Test successful search history clearing"""
        headers = auth_headers({"email": "clear@example.com", "first_name": "Clear", "last_name": "History"})

        response = test_client.delete(
            "/api/v1/search/history",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["message"] == "Search history cleared successfully"

    def test_clear_search_history_unauthorized(self, test_client: TestClient):
        """Test search history clearing without authentication"""
        response = test_client.delete("/api/v1/search/history")

        assert response.status_code == 401


@pytest.mark.contract
@pytest.mark.search
class TestAdvancedSearchAPI:
    """Test advanced search functionality"""

    def test_advanced_search_with_facets(self, test_client: TestClient, auth_headers):
        """Test advanced search with faceted results"""
        headers = auth_headers({"email": "facets@example.com", "first_name": "Advanced", "last_name": "Search"})

        search_data = {
            "query": "artificial intelligence",
            "search_type": "hybrid",
            "max_results": 10,
            "enable_facets": True,
            "facet_fields": ["document_type", "tags", "author", "date_range"],
            "filters": {
                "document_types": ["pdf", "text"]
            }
        }

        response = test_client.post(
            "/api/v1/search/advanced",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify faceted results structure
        assert "results" in response_data
        assert "facets" in response_data
        assert "query_id" in response_data

        # Verify facets structure
        if response_data["facets"]:
            for facet_field, facet_data in response_data["facets"].items():
                assert "buckets" in facet_data
                assert isinstance(facet_data["buckets"], list)

                for bucket in facet_data["buckets"]:
                    assert "value" in bucket
                    assert "count" in bucket

    def test_advanced_search_with_suggestions(self, test_client: TestClient, auth_headers):
        """Test advanced search with query suggestions"""
        headers = auth_headers({"email": "suggest@example.com", "first_name": "Suggest", "last_name": "Search"})

        search_data = {
            "query": "machine lerning",  # Intentional typo
            "search_type": "hybrid",
            "max_results": 10,
            "enable_suggestions": True,
            "suggestion_limit": 5
        }

        response = test_client.post(
            "/api/v1/search/advanced",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "results" in response_data
        assert "suggestions" in response_data

        # Verify suggestions structure
        if response_data["suggestions"]:
            assert isinstance(response_data["suggestions"], list)
            assert len(response_data["suggestions"]) <= 5

            for suggestion in response_data["suggestions"]:
                assert "suggestion" in suggestion
                assert "score" in suggestion
                assert "type" in suggestion

    def test_advanced_search_with_aggregations(self, test_client: TestClient, auth_headers):
        """Test advanced search with result aggregations"""
        headers = auth_headers({"email": "aggregate@example.com", "first_name": "Aggregate", "last_name": "Search"})

        search_data = {
            "query": "data analysis",
            "search_type": "hybrid",
            "max_results": 20,
            "enable_aggregations": True,
            "aggregations": {
                "document_type": {"type": "terms", "size": 10},
                "file_size": {"type": "histogram", "interval": 10},
                "date": {"type": "date_histogram", "interval": "month"}
            }
        }

        response = test_client.post(
            "/api/v1/search/advanced",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "results" in response_data
        assert "aggregations" in response_data

        # Verify aggregations structure
        if response_data["aggregations"]:
            for agg_name, agg_data in response_data["aggregations"].items():
                assert "buckets" in agg_data
                assert isinstance(agg_data["buckets"], list)

    def test_advanced_search_with_reranking(self, test_client: TestClient, auth_headers):
        """Test advanced search with custom reranking"""
        headers = auth_headers({"email": "rerank@example.com", "first_name": "Rerank", "last_name": "Search"})

        search_data = {
            "query": "deep learning frameworks",
            "search_type": "hybrid",
            "max_results": 15,
            "rerank": True,
            "rerank_strategy": "custom",
            "rerank_weights": {
                "semantic_similarity": 0.5,
                "keyword_match": 0.3,
                "freshness": 0.1,
                "popularity": 0.1
            },
            "rerank_params": {
                "boost_recent": True,
                "days_threshold": 30
            }
        }

        response = test_client.post(
            "/api/v1/search/advanced",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert "results" in response_data
        assert "search_metadata" in response_data

        # Verify reranking metadata
        if "reranking" in response_data["search_metadata"]:
            rerank_data = response_data["search_metadata"]["reranking"]
            assert "strategy" in rerank_data
            assert "weights" in rerank_data

        # Results should be ordered by final reranked score
        if len(response_data["results"]) > 1:
            for i in range(len(response_data["results"]) - 1):
                current_score = response_data["results"][i].get("final_score", 0)
                next_score = response_data["results"][i + 1].get("final_score", 0)
                assert current_score >= next_score

    def test_advanced_search_validation_errors(self, test_client: TestClient, auth_headers):
        """Test advanced search with various validation errors"""
        headers = auth_headers({"email": "validate@example.com", "first_name": "Validate", "last_name": "Search"})

        # Test invalid aggregation configuration
        search_data = {
            "query": "test query",
            "search_type": "hybrid",
            "max_results": 10,
            "enable_aggregations": True,
            "aggregations": {
                "invalid_field": {"type": "invalid_type", "size": 10}
            }
        }

        response = test_client.post(
            "/api/v1/search/advanced",
            json=search_data,
            headers=headers
        )

        assert response.status_code == 422

        # Test invalid facet configuration
        search_data = {
            "query": "test query",
            "search_type": "hybrid",
            "max_results": 10,
            "enable_facets": True,
            "facet_fields": ["invalid_field_1", "invalid_field_2"]
        }

        response = test_client.post(
            "/api/v1/search/advanced",
            json=search_data,
            headers=headers
        )

        # Should handle invalid fields gracefully
        assert response.status_code in [200, 422]


@pytest.mark.integration
@pytest.mark.search
@pytest.mark.performance
class TestSearchPerformance:
    """Performance tests for search functionality"""

    def test_simple_search_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test simple search query performance"""
        headers = auth_headers({"email": "perf_simple@example.com", "first_name": "Perf", "last_name": "Simple"})

        search_data = {
            "query": "machine learning",
            "search_type": "hybrid",
            "max_results": 10
        }

        performance_tracker.start_timer("simple_search")

        response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        duration = performance_tracker.end_timer("simple_search")

        assert response.status_code == 200
        assert duration < 3.0  # Should complete within 3 seconds (p95 requirement)

    def test_complex_search_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test complex search query performance"""
        headers = auth_headers({"email": "perf_complex@example.com", "first_name": "Perf", "last_name": "Complex"})

        search_data = {
            "query": "artificial intelligence neural networks deep learning",
            "search_type": "hybrid",
            "max_results": 50,
            "enable_facets": True,
            "enable_suggestions": True,
            "enable_aggregations": True,
            "rerank": True,
            "filters": {
                "document_types": ["pdf", "text", "video"],
                "tags": ["AI", "machine learning"],
                "date_range": {
                    "start_date": "2023-01-01",
                    "end_date": "2024-12-31"
                }
            },
            "facet_fields": ["document_type", "tags", "author"],
            "aggregations": {
                "document_type": {"type": "terms", "size": 10},
                "file_size": {"type": "histogram", "interval": 5}
            }
        }

        performance_tracker.start_timer("complex_search")

        response = test_client.post(
            "/api/v1/search/advanced",
            json=search_data,
            headers=headers
        )

        duration = performance_tracker.end_timer("complex_search")

        assert response.status_code == 200
        assert duration < 5.0  # Complex search should still be reasonably fast

    def test_concurrent_search_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test concurrent search query performance"""
        import threading
        import queue
        import time

        headers = auth_headers({"email": "perf_concurrent@example.com", "first_name": "Perf", "last_name": "Concurrent"})

        results = queue.Queue()
        search_queries = [
            "machine learning algorithms",
            "natural language processing",
            "computer vision",
            "data science",
            "artificial intelligence"
        ]

        def perform_search(query):
            """Perform a search in a separate thread"""
            search_data = {
                "query": query,
                "search_type": "hybrid",
                "max_results": 10
            }

            start_time = time.time()

            response = test_client.post(
                "/api/v1/search/",
                json=search_data,
                headers=headers
            )

            duration = time.time() - start_time
            results.put((response.status_code, duration, query))

        # Start concurrent searches
        threads = []
        performance_tracker.start_timer("concurrent_searches")

        for query in search_queries:
            thread = threading.Thread(target=perform_search, args=(query,))
            threads.append(thread)
            thread.start()

        # Wait for all searches to complete
        for thread in threads:
            thread.join()

        total_duration = performance_tracker.end_timer("concurrent_searches")

        # Collect results
        successful_searches = 0
        search_durations = []

        while not results.empty():
            status, duration, query = results.get()
            if status == 200:
                successful_searches += 1
                search_durations.append(duration)

        assert successful_searches >= 4  # At least 4 out of 5 should succeed
        assert len(search_durations) > 0

        avg_search_time = sum(search_durations) / len(search_durations)
        assert avg_search_time < 3.0  # Average search time should meet p95 requirement

    def test_search_memory_usage(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test search memory usage with large result sets"""
        import psutil
        import os

        headers = auth_headers({"email": "perf_memory@example.com", "first_name": "Perf", "last_name": "Memory"})

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform multiple searches with large result sets
        for i in range(10):
            search_data = {
                "query": f"test query {i}",
                "search_type": "hybrid",
                "max_results": 100,  # Large result set
                "include_metadata": True
            }

            response = test_client.post(
                "/api/v1/search/",
                json=search_data,
                headers=headers
            )

            assert response.status_code == 200

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for 10 searches)
        assert memory_increase < 100, f"Memory increased by {memory_increase:.2f}MB"

        print(f"Memory usage: {initial_memory:.2f}MB -> {final_memory:.2f}MB (increase: {memory_increase:.2f}MB)")


@pytest.mark.integration
@pytest.mark.search
class TestSearchIntegration:
    """Integration tests for search workflows"""

    def test_end_to_end_search_workflow(self, test_client: TestClient, auth_headers):
        """Test complete search workflow from query to results"""
        headers = auth_headers({"email": "workflow@example.com", "first_name": "Workflow", "last_name": "User"})

        # Step 1: Submit search query
        search_data = {
            "query": "machine learning algorithms",
            "search_type": "hybrid",
            "max_results": 5
        }

        search_response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert search_response.status_code == 200
        search_result = search_response.json()
        query_id = search_result["query_id"]

        # Step 2: Check search results
        results_response = test_client.get(
            f"/api/v1/search/{query_id}",
            headers=headers
        )

        assert results_response.status_code == 200
        results_data = results_response.json()

        # Step 3: Verify search is in history
        history_response = test_client.get(
            "/api/v1/search/history",
            headers=headers
        )

        assert history_response.status_code == 200
        history_data = history_response.json()

        # Find our search in history
        our_search = None
        for search in history_data["searches"]:
            if search["query_id"] == query_id:
                our_search = search
                break

        assert our_search is not None
        assert our_search["query"] == "machine learning algorithms"

        # Step 4: Test advanced search with same query
        advanced_data = {
            "query": "machine learning algorithms",
            "search_type": "hybrid",
            "max_results": 10,
            "enable_facets": True,
            "facet_fields": ["document_type", "tags"]
        }

        advanced_response = test_client.post(
            "/api/v1/search/advanced",
            json=advanced_data,
            headers=headers
        )

        assert advanced_response.status_code == 200
        advanced_result = advanced_response.json()

        # Advanced search should have facets
        assert "facets" in advanced_result

    def test_search_filter_combinations(self, test_client: TestClient, auth_headers):
        """Test various combinations of search filters"""
        headers = auth_headers({"email": "filters@example.com", "first_name": "Filter", "last_name": "Combo"})

        filter_combinations = [
            # Single filter
            {
                "query": "test",
                "filters": {"document_types": ["pdf"]}
            },
            # Multiple filters
            {
                "query": "test",
                "filters": {
                    "document_types": ["pdf", "text"],
                    "tags": ["test", "sample"]
                }
            },
            # Date range filter
            {
                "query": "test",
                "filters": {
                    "date_range": {
                        "start_date": "2023-01-01",
                        "end_date": "2024-12-31"
                    }
                }
            },
            # Complex filter combination
            {
                "query": "test",
                "filters": {
                    "document_types": ["pdf"],
                    "tags": ["research"],
                    "date_range": {
                        "start_date": "2023-06-01"
                    },
                    "processing_status": ["completed"]
                }
            }
        ]

        for i, search_data in enumerate(filter_combinations):
            search_data["search_type"] = "hybrid"
            search_data["max_results"] = 10

            response = test_client.post(
                "/api/v1/search/",
                json=search_data,
                headers=headers
            )

            assert response.status_code == 200, f"Filter combination {i+1} failed"
            response_data = response.json()

            assert "results" in response_data
            assert "query_id" in response_data