"""
Tests for Search Service
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient

from backend.src.services.search_service import app
from backend.src.shared.schemas import SearchType, QueryIntent


class TestSearchService:
    """Test Search Service functionality"""

    @pytest.fixture
    def client(self):
        """Create test client for Search Service"""
        return TestClient(app)

    @pytest.fixture
    async def http_client(self):
        """Create async HTTP client"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    @patch('backend.src.services.search_service.HybridSearchEngine.hybrid_search')
    async def test_hybrid_search_success(self, mock_hybrid_search, http_client, sample_organization):
        """Test successful hybrid search"""
        # Mock search results
        from backend.src.shared.schemas import SearchResponse, SearchResult, DocumentType
        mock_response = SearchResponse(
            query="test query",
            search_id=uuid.uuid4(),
            total_results=2,
            search_time_ms=150.5,
            results=[
                SearchResult(
                    document_id=uuid.uuid4(),
                    title="Test Document 1",
                    content_snippet="Test content snippet 1",
                    relevance_score=0.95,
                    document_type=DocumentType.PDF,
                    matched_content=[],
                    metadata={}
                ),
                SearchResult(
                    document_id=uuid.uuid4(),
                    title="Test Document 2",
                    content_snippet="Test content snippet 2",
                    relevance_score=0.87,
                    document_type=DocumentType.TEXT,
                    matched_content=[],
                    metadata={}
                )
            ],
            facets={},
            query_classification={
                "intent": QueryIntent.LOOKUP,
                "confidence": 0.8,
                "entities": []
            }
        )
        mock_hybrid_search.return_value = mock_response

        # Test search
        response = await http_client.post(
            "/search",
            json={
                "query": "test query",
                "search_type": SearchType.HYBRID.value,
                "limit": 10,
                "offset": 0,
                "include_metadata": True
            },
            params={"organization_id": str(sample_organization.id)}
        )

        assert response.status_code == 200

        data = response.json()
        assert data["query"] == "test query"
        assert data["total_results"] == 2
        assert len(data["results"]) == 2
        assert "search_time_ms" in data
        assert "query_classification" in data

    async def test_hybrid_search_invalid_query(self, http_client, sample_organization):
        """Test hybrid search with invalid query"""
        response = await http_client.post(
            "/search",
            json={
                "query": "",  # Empty query
                "search_type": SearchType.HYBRID.value,
                "limit": 10
            },
            params={"organization_id": str(sample_organization.id)}
        )

        assert response.status_code == 422

    async def test_hybrid_search_invalid_limit(self, http_client, sample_organization):
        """Test hybrid search with invalid limit"""
        response = await http_client.post(
            "/search",
            json={
                "query": "test query",
                "search_type": SearchType.HYBRID.value,
                "limit": 100  # Exceeds max limit
            },
            params={"organization_id": str(sample_organization.id)}
        )

        assert response.status_code == 422

    @patch('backend.src.services.search_service.cache')
    async def test_cached_search_results(self, mock_cache, http_client, sample_organization):
        """Test cached search results"""
        # Mock cache hit
        from backend.src.shared.schemas import SearchResponse
        cached_response = SearchResponse(
            query="cached query",
            search_id=uuid.uuid4(),
            total_results=1,
            search_time_ms=50.0,
            results=[],
            facets={},
            query_classification={
                "intent": QueryIntent.LOOKUP,
                "confidence": 0.9,
                "entities": []
            }
        )
        mock_cache.get.return_value = cached_response.dict()

        response = await http_client.post(
            "/search",
            json={
                "query": "cached query",
                "search_type": SearchType.HYBRID.value,
                "limit": 10
            },
            params={"organization_id": str(sample_organization.id)}
        )

        assert response.status_code == 200
        # Verify cache was checked
        mock_cache.get.assert_called_once()

    @patch('backend.src.services.search_service.cache')
    @patch('backend.src.services.search_service.HybridSearchEngine.hybrid_search')
    async def test_search_caching(self, mock_hybrid_search, mock_cache, http_client, sample_organization):
        """Test search result caching"""
        # Mock search response
        from backend.src.shared.schemas import SearchResponse
        mock_response = SearchResponse(
            query="test query",
            search_id=uuid.uuid4(),
            total_results=1,
            search_time_ms=100.0,
            results=[],
            facets={},
            query_classification={
                "intent": QueryIntent.LOOKUP,
                "confidence": 0.8,
                "entities": []
            }
        )
        mock_hybrid_search.return_value = mock_response
        mock_cache.get.return_value = None  # Cache miss

        response = await http_client.post(
            "/search",
            json={
                "query": "test query",
                "search_type": SearchType.HYBRID.value,
                "limit": 10
            },
            params={"organization_id": str(sample_organization.id)}
        )

        assert response.status_code == 200
        # Verify result was cached
        mock_cache.set.assert_called_once()

    async def test_search_suggestions(self, http_client, sample_organization):
        """Test search suggestions"""
        with patch('backend.src.services.search_service.cache') as mock_cache:
            # Mock cached suggestions
            from backend.src.shared.schemas import SearchSuggestion
            mock_suggestions = [
                SearchSuggestion(text="test document", type="autocomplete", score=0.9).dict(),
                SearchSuggestion(text="test query", type="completion", score=0.7).dict()
            ]
            mock_cache.get.return_value = mock_suggestions

            response = await http_client.get(
                "/suggestions",
                params={
                    "q": "test",
                    "limit": 5,
                    "organization_id": str(sample_organization.id)
                }
            )

            assert response.status_code == 200

            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["type"] == "autocomplete"

    async def test_search_suggestions_no_cache(self, http_client, sample_organization):
        """Test search suggestions with no cache"""
        with patch('backend.src.services.search_service.cache') as mock_cache:
            with patch('backend.src.services.search_service.select') as mock_select:
                # Mock database query
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = [
                    "Test Document 1",
                    "Test Document 2"
                ]
                mock_select.return_value.__aenter__.return_value = mock_result
                mock_cache.get.return_value = None

                response = await http_client.get(
                    "/suggestions",
                    params={
                        "q": "test",
                        "limit": 5,
                        "organization_id": str(sample_organization.id)
                    }
                )

                assert response.status_code == 200
                # Verify cache was set
                mock_cache.set.assert_called_once()

    async def test_search_history(self, http_client, sample_organization, sample_regular_user):
        """Test search history retrieval"""
        with patch('backend.src.services.search_service.select') as mock_select:
            # Mock search history
            mock_result = MagicMock()
            mock_search_query = MagicMock()
            mock_search_query.id = uuid.uuid4()
            mock_search_query.query = "test query"
            mock_search_query.search_type = "hybrid"
            mock_search_query.result_count = 5
            mock_search_query.search_time_ms = 150.0
            mock_search_query.created_at = "2024-01-01T00:00:00Z"

            mock_result.scalars.return_value.all.return_value = [mock_search_query]
            mock_select.return_value.__aenter__.return_value = mock_result

            response = await http_client.get(
                "/search/history",
                params={
                    "limit": 20,
                    "organization_id": str(sample_organization.id),
                    "user_id": str(sample_regular_user.id)
                }
            )

            assert response.status_code == 200

            data = response.json()
            assert "searches" in data
            assert isinstance(data["searches"], list)

    async def test_popular_searches(self, http_client, sample_organization):
        """Test popular searches retrieval"""
        response = await http_client.get(
            "/search/popular",
            params={
                "limit": 10,
                "organization_id": str(sample_organization.id),
                "days": 7
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "popular_searches" in data
        assert "time_period_days" in data
        assert "organization_id" in data

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "service" in data
        assert "timestamp" in data

    async def test_query_classification(self):
        """Test query classification logic"""
        from backend.src.services.search_service import HybridSearchEngine

        engine = HybridSearchEngine()

        # Test different query types
        queries = [
            ("what is machine learning", QueryIntent.LOOKUP),
            ("how does the algorithm work", QueryIntent.REASONING),
            ("compare python vs java", QueryIntent.COMPARISON),
            ("when was the system created", QueryIntent.TEMPORAL),
            ("what causes the error", QueryIntent.CAUSAL)
        ]

        for query, expected_intent in queries:
            classification = await engine.classify_query(query)
            assert classification.intent == expected_intent
            assert 0 <= classification.confidence <= 1
            assert isinstance(classification.entities, list)

    @patch('backend.src.services.search_service.make_http_request')
    async def test_query_embedding_generation(self, mock_request):
        """Test query embedding generation"""
        from backend.src.services.search_service import HybridSearchEngine

        engine = HybridSearchEngine()

        # Mock embedding service response
        mock_request.return_value = {"embedding": [0.1] * 768}

        embedding = await engine.get_query_embedding("test query")

        assert isinstance(embedding, list)
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)

    @patch('backend.src.services.search_service.qdrant_client')
    async def test_vector_search(self, mock_qdrant):
        """Test vector search functionality"""
        from backend.src.services.search_service import HybridSearchEngine
        from backend.src.shared.schemas import DocumentType

        engine = HybridSearchEngine()

        # Mock Qdrant search response
        mock_hit = MagicMock()
        mock_hit.score = 0.85
        mock_hit.payload = {
            "document_id": str(uuid.uuid4()),
            "title": "Test Document",
            "content_snippet": "Test content",
            "document_type": "text",
            "metadata": {}
        }

        mock_qdrant.search.return_value = [mock_hit]

        result = await engine.vector_search(
            query_embedding=[0.1] * 768,
            limit=10,
            organization_id=uuid.uuid4()
        )

        assert result.component_name == "vector_search"
        assert len(result.results) == 1
        assert result.results[0].relevance_score == 0.85
        assert result.results[0].document_type == DocumentType.TEXT

    @patch('backend.src.services.search_service.select')
    async def test_keyword_search(self, mock_select):
        """Test keyword search functionality"""
        from backend.src.services.search_service import HybridSearchEngine
        from backend.src.models.document import Document, DocumentType, ProcessingStatus
        from sqlalchemy.ext.asyncio import AsyncSession

        engine = HybridSearchEngine()

        # Mock database results
        mock_doc = MagicMock(spec=Document)
        mock_doc.id = uuid.uuid4()
        mock_doc.title = "Test Document"
        mock_doc.content_text = "Test content with keyword"
        mock_doc.document_type = DocumentType.TEXT
        mock_doc.created_at = "2024-01-01T00:00:00Z"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_doc]

        # Create mock session
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute.return_value.__aenter__.return_value = mock_result

        result = await engine.keyword_search(
            query="keyword",
            limit=10,
            organization_id=uuid.uuid4(),
            db=mock_session
        )

        assert result.component_name == "keyword_search"
        assert len(result.results) == 1
        assert "keyword" in result.results[0].title.lower() or "keyword" in result.results[0].content_snippet.lower()

    @patch('backend.src.services.search_service.neo4j_driver')
    async def test_graph_search(self, mock_neo4j):
        """Test knowledge graph search"""
        from backend.src.services.search_service import HybridSearchEngine

        engine = HybridSearchEngine()

        # Mock Neo4j response
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {
            "id": str(uuid.uuid4()),
            "title": "Graph Document",
            "content_preview": "Graph content preview",
            "document_type": "pdf",
            "entity_count": 3
        }.get(key)

        mock_session = MagicMock()
        mock_session.run.return_value.__aenter__.return_value = [mock_record]
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session

        result = await engine.graph_search(
            query="entity search",
            limit=10,
            organization_id=uuid.uuid4()
        )

        assert result.component_name == "graph_search"
        assert len(result.results) == 1
        assert result.results[0].metadata["entity_count"] == 3

    async def test_result_reranking(self):
        """Test search result reranking"""
        from backend.src.services.search_service import HybridSearchEngine
        from backend.src.shared.schemas import SearchResult, DocumentType

        engine = HybridSearchEngine()

        # Create test results
        results = [
            SearchResult(
                document_id=uuid.uuid4(),
                title="Document 1",
                content_snippet="Content 1",
                relevance_score=0.8,
                document_type=DocumentType.TEXT,
                matched_content=[],
                metadata={}
            ),
            SearchResult(
                document_id=uuid.uuid4(),
                title="Document 2",
                content_snippet="Content 2",
                relevance_score=0.6,
                document_type=DocumentType.PDF,
                matched_content=[],
                metadata={}
            )
        ]

        reranked = await engine.rerank_results("test query", results, limit=10)

        assert len(reranked) == 2
        # PDF should get boost
        assert reranked[0].document_type == DocumentType.PDF
        assert reranked[0].relevance_score >= reranked[1].relevance_score

    async def test_faceted_search(self, http_client, sample_organization):
        """Test faceted search with filters"""
        with patch('backend.src.services.search_service.HybridSearchEngine.hybrid_search') as mock_search:
            from backend.src.shared.schemas import SearchResponse

            mock_response = SearchResponse(
                query="test query",
                search_id=uuid.uuid4(),
                total_results=5,
                search_time_ms=120.0,
                results=[],
                facets={
                    "document_types": {
                        "pdf": 3,
                        "text": 2
                    }
                },
                query_classification={
                    "intent": QueryIntent.LOOKUP,
                    "confidence": 0.8,
                    "entities": []
                }
            )
            mock_search.return_value = mock_response

            response = await http_client.post(
                "/search",
                json={
                    "query": "test query",
                    "search_type": SearchType.HYBRID.value,
                    "filters": {
                        "document_types": [DocumentType.PDF.value],
                        "tags": ["important"],
                        "date_range": {
                            "start": "2024-01-01T00:00:00Z",
                            "end": "2024-12-31T23:59:59Z"
                        }
                    },
                    "limit": 10
                },
                params={"organization_id": str(sample_organization.id)}
            )

            assert response.status_code == 200
            data = response.json()
            assert "facets" in data
            assert "document_types" in data["facets"]

    async def test_search_analytics_storage(self):
        """Test search analytics storage"""
        from backend.src.services.search_service import store_search_analytics

        with patch('backend.src.services.search_service.event_logger') as mock_logger:
            await store_search_analytics(
                search_id=str(uuid.uuid4()),
                query="test query",
                organization_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                result_count=5,
                search_time_ms=150.0
            )

            # Should log analytics event
            mock_logger.log_event.assert_called_once()

    @patch('backend.src.services.search_service.qdrant_client')
    async def test_vector_search_error_handling(self, mock_qdrant):
        """Test vector search error handling"""
        from backend.src.services.search_service import HybridSearchEngine
        from backend.src.shared.exceptions import VectorStoreError

        engine = HybridSearchEngine()

        # Mock Qdrant error
        mock_qdrant.search.side_effect = Exception("Qdrant connection failed")

        with pytest.raises(Exception):
            await engine.vector_search(
                query_embedding=[0.1] * 768,
                limit=10,
                organization_id=uuid.uuid4()
            )

    @patch('backend.src.services.search_service.neo4j_driver')
    async def test_graph_search_error_handling(self, mock_neo4j):
        """Test graph search error handling"""
        from backend.src.services.search_service import HybridSearchEngine
        from backend.src.shared.exceptions import KnowledgeGraphError

        engine = HybridSearchEngine()

        # Mock Neo4j error
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j connection failed")
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session

        with pytest.raises(Exception):
            await engine.graph_search(
                query="test query",
                limit=10,
                organization_id=uuid.uuid4()
            )

    async def test_different_search_types(self, http_client, sample_organization):
        """Test different search types"""
        with patch('backend.src.services.search_service.HybridSearchEngine.hybrid_search') as mock_search:
            from backend.src.shared.schemas import SearchResponse

            mock_response = SearchResponse(
                query="test query",
                search_id=uuid.uuid4(),
                total_results=1,
                search_time_ms=100.0,
                results=[],
                facets={},
                query_classification={
                    "intent": QueryIntent.LOOKUP,
                    "confidence": 0.8,
                    "entities": []
                }
            )
            mock_search.return_value = mock_response

            search_types = [
                SearchType.HYBRID,
                SearchType.VECTOR,
                SearchType.KEYWORD,
                SearchType.GRAPH
            ]

            for search_type in search_types:
                response = await http_client.post(
                    "/search",
                    json={
                        "query": "test query",
                        "search_type": search_type.value,
                        "limit": 10
                    },
                    params={"organization_id": str(sample_organization.id)}
                )

                assert response.status_code == 200
                # Verify search type was passed correctly
                mock_search.assert_called()
                call_args = mock_search.call_args
                assert call_args[1]["request"].search_type == search_type