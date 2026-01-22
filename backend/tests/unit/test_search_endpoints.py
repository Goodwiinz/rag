"""
Unit tests for Search API endpoints
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
import json
from typing import List, Dict, Any

from conftest_fastapi import *


class TestSearchEndpoints:
    """Test class for search endpoints"""

    @pytest.fixture
    def search_service_mock(self):
        """Mock search service"""
        service = Mock()
        service.search = AsyncMock()
        service.get_search_suggestions = AsyncMock()
        service.get_search_analytics = AsyncMock()
        return service

    @pytest.fixture
    def hybrid_search_service_mock(self):
        """Mock hybrid search service"""
        service = Mock()
        service.search = AsyncMock()
        return service

    @pytest.fixture
    def fulltext_search_service_mock(self):
        """Mock fulltext search service"""
        service = Mock()
        service.search = AsyncMock()
        return service

    @pytest.fixture
    def override_search_dependencies(self, test_app, search_service_mock, hybrid_search_service_mock, fulltext_search_service_mock):
        """Override search service dependencies"""
        from src.services.search.hybrid_search_service import hybrid_search_service
        from src.services.search.fulltext_search_service import fulltext_search_service

        # Override services with mocks
        original_hybrid = hybrid_search_service.search
        original_fulltext = fulltext_search_service.search

        hybrid_search_service.search = hybrid_search_service_mock.search
        fulltext_search_service.search = fulltext_search_service_mock.search

        yield

        # Restore original methods
        hybrid_search_service.search = original_hybrid
        fulltext_search_service.search = original_fulltext

    @pytest.mark.unit
    @pytest.mark.search
    def test_hybrid_search_success(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers, override_search_dependencies):
        """Test successful hybrid search"""
        # Setup mock response
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results),
            "search_metadata": {
                "search_type": "hybrid",
                "query": "machine learning",
                "execution_time_ms": 150,
                "sources_used": ["vector", "fulltext", "graph"]
            }
        }

        # Test data
        search_data = {
            "query": "machine learning",
            "search_type": "hybrid",
            "limit": 10,
            "offset": 0,
            "filters": {
                "document_types": ["pdf", "txt"],
                "tags": ["AI", "machine learning"]
            }
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert "search_metadata" in data
        assert len(data["results"]) == len(sample_search_results)
        assert data["search_metadata"]["search_type"] == "hybrid"

        # Verify service calls
        hybrid_search_service_mock.search.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.search
    def test_fulltext_search_success(self, test_client: TestClient, fulltext_search_service_mock, sample_search_results, mock_auth_headers, override_search_dependencies):
        """Test successful fulltext search"""
        # Setup mock response
        fulltext_search_service_mock.search.return_value = {
            "results": sample_search_results[:1],  # Return only one result
            "total": 1,
            "search_metadata": {
                "search_type": "fulltext",
                "query": "natural language processing",
                "execution_time_ms": 80,
                "index_used": "documents_index"
            }
        }

        # Test data
        search_data = {
            "query": "natural language processing",
            "search_type": "fulltext",
            "limit": 5,
            "offset": 0
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["search_metadata"]["search_type"] == "fulltext"

        # Verify service calls
        fulltext_search_service_mock.search.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.search
    def test_vector_search_success(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers, override_search_dependencies):
        """Test successful vector search"""
        # Setup mock response
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results),
            "search_metadata": {
                "search_type": "vector",
                "query": "computer vision",
                "execution_time_ms": 120,
                "similarity_threshold": 0.7,
                "embedding_model": "text-embedding-ada-002"
            }
        }

        # Test data
        search_data = {
            "query": "computer vision",
            "search_type": "vector",
            "limit": 10,
            "similarity_threshold": 0.7
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["search_metadata"]["search_type"] == "vector"
        assert data["search_metadata"]["similarity_threshold"] == 0.7

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_with_filters(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers, override_search_dependencies):
        """Test search with filters applied"""
        # Setup mock response
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results),
            "search_metadata": {
                "search_type": "hybrid",
                "query": "AI",
                "filters_applied": ["document_type", "date_range", "tags"]
            }
        }

        # Test data with complex filters
        search_data = {
            "query": "AI",
            "search_type": "hybrid",
            "filters": {
                "document_types": ["pdf", "video"],
                "tags": ["artificial intelligence", "machine learning"],
                "date_range": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31"
                },
                "authors": ["Test Author"],
                "min_score": 0.5
            },
            "sort_by": "relevance",
            "sort_order": "desc"
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "filters_applied" in data["search_metadata"]

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_validation_error(self, test_client: TestClient, mock_auth_headers):
        """Test search with invalid request data"""
        # Test data with missing required field
        search_data = {
            "search_type": "hybrid",
            # Missing "query" field
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "validation_error"

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_unauthorized(self, test_client: TestClient):
        """Test search without authentication"""
        search_data = {
            "query": "test query",
            "search_type": "hybrid"
        }

        # Make request without auth headers
        response = test_client.post("/api/v1/search/", json=search_data)

        # Assertions
        assert response.status_code == 401

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_empty_query(self, test_client: TestClient, hybrid_search_service_mock, mock_auth_headers, override_search_dependencies):
        """Test search with empty query"""
        # Setup mock response
        hybrid_search_service_mock.search.return_value = {
            "results": [],
            "total": 0,
            "search_metadata": {
                "search_type": "hybrid",
                "query": "",
                "execution_time_ms": 50
            }
        }

        search_data = {
            "query": "",
            "search_type": "hybrid"
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 0
        assert data["total"] == 0

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_pagination(self, test_client: TestClient, hybrid_search_service_mock, mock_auth_headers, override_search_dependencies):
        """Test search pagination"""
        # Setup mock response with pagination
        paginated_results = [{"id": f"result-{i}"} for i in range(10)]
        hybrid_search_service_mock.search.return_value = {
            "results": paginated_results,
            "total": 100,
            "search_metadata": {
                "search_type": "hybrid",
                "query": "test",
                "limit": 10,
                "offset": 0,
                "page": 1,
                "total_pages": 10
            }
        }

        search_data = {
            "query": "test",
            "search_type": "hybrid",
            "limit": 10,
            "offset": 0
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 10
        assert data["total"] == 100
        assert data["search_metadata"]["page"] == 1
        assert data["search_metadata"]["total_pages"] == 10

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_suggestions(self, test_client: TestClient, search_service_mock, mock_auth_headers):
        """Test search suggestions endpoint"""
        # Setup mock response
        suggestions = [
            "machine learning algorithms",
            "machine learning models",
            "machine learning frameworks"
        ]
        search_service_mock.get_search_suggestions.return_value = {
            "suggestions": suggestions,
            "query": "machine le",
            "total": len(suggestions)
        }

        # Make request
        response = test_client.get(
            "/api/v1/search/suggestions",
            params={"q": "machine le", "limit": 5},
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 3
        assert all("machine le" in suggestion.lower() for suggestion in data["suggestions"])

        # Verify service calls
        search_service_mock.get_search_suggestions.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_analytics(self, test_client: TestClient, search_service_mock, mock_auth_headers):
        """Test search analytics endpoint"""
        # Setup mock response
        analytics_data = {
            "total_searches": 1000,
            "popular_queries": [
                {"query": "machine learning", "count": 150},
                {"query": "AI", "count": 120},
                {"query": "data science", "count": 100}
            ],
            "average_results_per_search": 8.5,
            "average_search_time_ms": 150,
            "search_types_distribution": {
                "hybrid": 0.6,
                "vector": 0.3,
                "fulltext": 0.1
            }
        }
        search_service_mock.get_search_analytics.return_value = analytics_data

        # Make request
        response = test_client.get(
            "/api/v1/search/analytics",
            params={"period": "7d"},
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "total_searches" in data
        assert "popular_queries" in data
        assert "average_results_per_search" in data
        assert len(data["popular_queries"]) == 3

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_history(self, test_client: TestClient, mock_auth_headers):
        """Test search history endpoint"""
        # This would typically require database integration
        # For unit test, we'll mock the response

        with patch('src.services.search_service.SearchService.get_user_search_history') as mock_history:
            mock_history.return_value = [
                {
                    "id": "search-1",
                    "query": "machine learning",
                    "search_type": "hybrid",
                    "results_count": 10,
                    "timestamp": "2024-01-01T10:00:00Z"
                },
                {
                    "id": "search-2",
                    "query": "natural language processing",
                    "search_type": "vector",
                    "results_count": 5,
                    "timestamp": "2024-01-01T09:30:00Z"
                }
            ]

            # Make request
            response = test_client.get("/api/v1/search/history", headers=mock_auth_headers)

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["query"] == "machine learning"

    @pytest.mark.unit
    @pytest.mark.search
    def test_saved_searches(self, test_client: TestClient, mock_auth_headers):
        """Test saved searches management"""
        # Test saving a search
        search_data = {
            "name": "AI Research",
            "query": "artificial intelligence",
            "search_type": "hybrid",
            "filters": {"tags": ["AI", "research"]}
        }

        with patch('src.services.search_service.SearchService.save_search') as mock_save:
            mock_save.return_value = {
                "id": "saved-search-1",
                "name": "AI Research",
                "created_at": "2024-01-01T10:00:00Z"
            }

            response = test_client.post("/api/v1/search/saved", json=search_data, headers=mock_auth_headers)

            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "saved-search-1"
            assert data["name"] == "AI Research"

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_error_handling(self, test_client: TestClient, hybrid_search_service_mock, mock_auth_headers, override_search_dependencies):
        """Test search error handling"""
        # Setup mock to raise exception
        hybrid_search_service_mock.search.side_effect = Exception("Search service unavailable")

        search_data = {
            "query": "test query",
            "search_type": "hybrid"
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 500
        data = response.json()
        assert "error" in data

    @pytest.mark.unit
    @pytest.mark.search
    @pytest.mark.parametrize("search_type", ["hybrid", "vector", "fulltext", "graph"])
    def test_different_search_types(self, test_client: TestClient, hybrid_search_service_mock, mock_auth_headers, override_search_dependencies, search_type):
        """Test different search types"""
        # Setup mock response
        hybrid_search_service_mock.search.return_value = {
            "results": [{"id": "result-1"}],
            "total": 1,
            "search_metadata": {"search_type": search_type}
        }

        search_data = {
            "query": "test query",
            "search_type": search_type
        }

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["search_metadata"]["search_type"] == search_type

    @pytest.mark.unit
    @pytest.mark.search
    def test_search_performance_tracking(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers, performance_tracker, override_search_dependencies):
        """Test search with performance tracking"""
        # Setup mock response with delay
        async def mock_search_with_delay(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.1)  # Simulate processing time
            return {
                "results": sample_search_results,
                "total": len(sample_search_results),
                "search_metadata": {
                    "search_type": "hybrid",
                    "execution_time_ms": 100
                }
            }

        hybrid_search_service_mock.search.side_effect = mock_search_with_delay

        search_data = {
            "query": "test query",
            "search_type": "hybrid"
        }

        # Start timer
        performance_tracker.start_timer("search_request")

        # Make request
        response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)

        # End timer
        performance_tracker.end_timer("search_request")

        # Assertions
        assert response.status_code == 200

        # Check performance
        avg_time = performance_tracker.get_average("search_request")
        assert avg_time > 0.1  # Should be at least 100ms due to mock delay