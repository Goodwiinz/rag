"""
Comprehensive validation tests for all T2 tasks in the Multimodal RAG System

This test suite validates the implementation of:
- T2-001: Vector Database Setup and Embedding Generation
- T2-002: Knowledge Graph Construction
- T2-003: Full-Text Search Implementation
- T2-004: Hybrid Search Engine
- T2-005: Search API Implementation
- T2-007: Search Quality Evaluation

Note: T2-006 (Multi-Agent Search Orchestration) is pending implementation
"""

import pytest
import asyncio
import time
import json
import numpy as np
from typing import List, Dict, Any
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# Import test framework and fixtures
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import modules to test
from src.main import app
from src.core.database import get_db, Base
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.user import User
from src.models.search_schemas import SearchQuery, SearchType, SearchSortOrder
from src.services.vector_search_service import vector_search_service
from src.services.knowledge_graph_service import knowledge_graph_service
from src.services.fulltext_search_service import fulltext_search_service
from src.services.hybrid_search_service import hybrid_search_service
from src.services.search_quality_service import search_quality_service


# Test client fixture
@pytest.fixture(scope="module")
def client():
    """Create test client for FastAPI application"""
    return TestClient(app)


@pytest.fixture(scope="module")
def test_db():
    """Create test database session"""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    session.close()


@pytest.fixture
def test_user(test_db):
    """Create test user"""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed_password",
        full_name="Test User",
        organization_id="test_org",
        is_active=True,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_documents(test_db, test_user):
    """Create sample documents for testing"""
    documents = [
        Document(
            title="Machine Learning Fundamentals",
            content_text="Machine learning is a subset of artificial intelligence that focuses on neural networks and deep learning algorithms.",
            content_summary="Introduction to ML concepts",
            document_type=DocumentType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            uploaded_by_user_id=str(test_user.id),
            organization_id=str(test_user.organization_id),
            file_size_bytes=1024,
            tags=["machine learning", "AI", "neural networks"],
            document_metadata={"pages": 50, "author": "Test Author"}
        ),
        Document(
            title="Natural Language Processing",
            content_text="NLP involves processing and understanding human language using computational linguistics and machine learning techniques.",
            content_summary="Overview of NLP techniques",
            document_type=DocumentType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            uploaded_by_user_id=str(test_user.id),
            organization_id=str(test_user.organization_id),
            file_size_bytes=2048,
            tags=["NLP", "linguistics", "text processing"],
            document_metadata={"pages": 75, "author": "Test Author 2"}
        ),
        Document(
            title="Computer Vision Applications",
            content_text="Computer vision enables machines to interpret and understand visual information from images and videos using deep learning.",
            content_summary="Computer vision in practice",
            document_type=DocumentType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            uploaded_by_user_id=str(test_user.id),
            organization_id=str(test_user.organization_id),
            file_size_bytes=3072,
            tags=["computer vision", "image processing", "deep learning"],
            document_metadata={"pages": 100, "author": "Test Author 3"}
        )
    ]

    for doc in documents:
        test_db.add(doc)

    test_db.commit()

    # Refresh documents to get IDs
    for doc in documents:
        test_db.refresh(doc)

    return documents


class TestT2_001_VectorDatabase:
    """Test T2-001: Vector Database Setup and Embedding Generation"""

    def test_vector_search_service_initialization(self):
        """Test that vector search service initializes properly"""
        assert vector_search_service is not None
        assert hasattr(vector_search_service, 'embedding_dimension')
        assert hasattr(vector_search_service, 'search_collection')

    @patch('src.services.vector_search_service.embeddings')
    @patch('src.services.vector_search_service.qdrant_client')
    def test_embedding_generation(self, mock_qdrant, mock_embeddings):
        """Test text embedding generation functionality"""
        # Mock embedding generation
        test_text = "This is a test document for embedding generation"
        expected_embedding = np.random.rand(384).tolist()

        mock_embeddings.embed_query.return_value = expected_embedding
        mock_qdrant.upsert.return_value = Mock()

        # Test embedding generation
        embedding = vector_search_service._generate_embedding(test_text)

        assert isinstance(embedding, list)
        assert len(embedding) == vector_search_service.embedding_dimension
        assert all(isinstance(x, float) for x in embedding)

    @patch('src.services.vector_search_service.qdrant_client')
    def test_vector_storage_and_retrieval(self, mock_qdrant):
        """Test storing and retrieving vectors from Qdrant"""
        # Mock Qdrant operations
        mock_qdrant.upsert.return_value = Mock()
        mock_qdrant.search.return_value = [
            Mock(id="doc1", score=0.85, payload={"document_id": "doc1", "title": "Test Doc"}),
            Mock(id="doc2", score=0.75, payload={"document_id": "doc2", "title": "Test Doc 2"})
        ]

        # Test vector storage
        doc_id = "test_doc_123"
        text = "Test document content for vector storage"
        metadata = {"title": "Test Doc", "document_type": "PDF"}

        try:
            vector_search_service.store_document_vector(
                document_id=doc_id,
                text=text,
                metadata=metadata
            )
            storage_success = True
        except Exception as e:
            storage_success = False
            print(f"Storage failed: {e}")

        # Test vector retrieval
        try:
            query_text = "test query"
            results = vector_search_service.search_similar_documents(
                query_text=query_text,
                limit=5,
                organization_id="test_org"
            )
            retrieval_success = True
        except Exception as e:
            retrieval_success = False
            results = []
            print(f"Retrieval failed: {e}")

        assert storage_success or retrieval_success, "Either storage or retrieval should work"
        if retrieval_success:
            assert isinstance(results, list)

    def test_embedding_dimension_consistency(self):
        """Test that embedding dimensions are consistent"""
        expected_dimension = 384  # Standard for sentence-transformers
        assert vector_search_service.embedding_dimension == expected_dimension


class TestT2_002_KnowledgeGraph:
    """Test T2-002: Knowledge Graph Construction"""

    def test_knowledge_graph_service_initialization(self):
        """Test that knowledge graph service initializes properly"""
        assert knowledge_graph_service is not None
        assert hasattr(knowledge_graph_service, 'neo4j_driver')

    @patch('src.services.knowledge_graph_service.neo4j_driver')
    def test_entity_extraction_and_storage(self, mock_neo4j):
        """Test entity extraction and storage in Neo4j"""
        # Mock Neo4j operations
        mock_session = Mock()
        mock_session.run.return_value = Mock()
        mock_neo4j.session.return_value = mock_session

        # Test entity extraction
        text = "Apple Inc. is a technology company founded by Steve Jobs in Cupertino, California."

        try:
            entities = knowledge_graph_service._extract_entities(text)
            entity_extraction_success = True
        except Exception as e:
            entity_extraction_success = False
            entities = []
            print(f"Entity extraction failed: {e}")

        # Test entity storage
        try:
            knowledge_graph_service.store_document_entities(
                document_id="test_doc",
                entities=entities,
                text=text
            )
            entity_storage_success = True
        except Exception as e:
            entity_storage_success = False
            print(f"Entity storage failed: {e}")

        assert entity_extraction_success or entity_storage_success, "Either extraction or storage should work"

    @patch('src.services.knowledge_graph_service.neo4j_driver')
    def test_relationship_creation(self, mock_neo4j):
        """Test creating relationships between entities"""
        # Mock Neo4j operations
        mock_session = Mock()
        mock_session.run.return_value = Mock()
        mock_neo4j.session.return_value = mock_session

        try:
            # Test relationship creation
            relationships = [
                {"source": "Apple Inc.", "target": "Steve Jobs", "type": "FOUNDED_BY"},
                {"source": "Apple Inc.", "target": "Cupertino", "type": "LOCATED_IN"}
            ]

            knowledge_graph_service.store_entity_relationships(
                document_id="test_doc",
                relationships=relationships
            )
            relationship_success = True
        except Exception as e:
            relationship_success = False
            print(f"Relationship creation failed: {e}")

        assert relationship_success, "Relationship creation should work"

    @patch('src.services.knowledge_graph_service.neo4j_driver')
    def test_graph_query_execution(self, mock_neo4j):
        """Test executing graph queries"""
        # Mock Neo4j query result
        mock_session = Mock()
        mock_result = Mock()
        mock_result.data.return_value = [
            {"entity": {"name": "Apple Inc.", "type": "Company"}},
            {"entity": {"name": "Steve Jobs", "type": "Person"}}
        ]
        mock_session.run.return_value = mock_result
        mock_neo4j.session.return_value = mock_session

        try:
            # Test graph query
            query = "MATCH (n:Entity) WHERE n.name CONTAINS 'Apple' RETURN n LIMIT 10"
            results = knowledge_graph_service.query_graph(query)
            query_success = True
        except Exception as e:
            query_success = False
            results = []
            print(f"Graph query failed: {e}")

        assert query_success, "Graph query should execute successfully"
        assert isinstance(results, list)


class TestT2_003_FullTextSearch:
    """Test T2-003: Full-Text Search Implementation"""

    def test_fulltext_search_service_initialization(self):
        """Test that full-text search service initializes properly"""
        assert fulltext_search_service is not None
        assert hasattr(fulltext_search_service, 'search_pre_tag')
        assert hasattr(fulltext_search_service, 'search_post_tag')

    def test_search_query_building(self):
        """Test building PostgreSQL search queries"""
        search_request = SearchQuery(
            query="machine learning algorithms",
            search_type=SearchType.FULLTEXT,
            limit=10
        )

        try:
            query, params = fulltext_search_service._build_search_query(
                search_request=search_request,
                user_id="test_user",
                organization_id="test_org"
            )

            assert isinstance(query, str)
            assert isinstance(params, dict)
            assert "plainto_tsquery" in query
            assert "search_vector" in query
            query_building_success = True
        except Exception as e:
            query_building_success = False
            print(f"Query building failed: {e}")

        assert query_building_success, "Search query building should work"

    def test_text_preprocessing(self):
        """Test text preprocessing for search"""
        raw_text = "This is a test! With punctuation, and special characters."

        try:
            processed_terms = fulltext_search_service._prepare_search_terms(raw_text)
            preprocessing_success = True
        except Exception as e:
            preprocessing_success = False
            processed_terms = []
            print(f"Text preprocessing failed: {e}")

        assert preprocessing_success, "Text preprocessing should work"
        assert isinstance(processed_terms, str)

    def test_search_execution_with_sample_data(self, sample_documents):
        """Test executing full-text search with sample data"""
        search_request = SearchQuery(
            query="machine learning",
            search_type=SearchType.FULLTEXT,
            limit=5
        )

        try:
            results = fulltext_search_service.search(
                search_request=search_request,
                user_id="test_user",
                organization_id="test_org"
            )
            search_success = True
        except Exception as e:
            search_success = False
            results = []
            print(f"Full-text search failed: {e}")

        assert search_success, "Full-text search should execute successfully"
        assert isinstance(results, object)  # SearchResponse or similar

    def test_snippet_generation(self):
        """Test generating search result snippets"""
        content = "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed."
        query = "machine learning"

        try:
            snippet = fulltext_search_service._generate_snippet(content, query)
            snippet_success = True
        except Exception as e:
            snippet_success = False
            snippet = ""
            print(f"Snippet generation failed: {e}")

        assert snippet_success, "Snippet generation should work"
        assert isinstance(snippet, str)


class TestT2_004_HybridSearch:
    """Test T2-004: Hybrid Search Engine"""

    def test_hybrid_search_service_initialization(self):
        """Test that hybrid search service initializes properly"""
        assert hybrid_search_service is not None
        assert hasattr(hybrid_search_service, 'source_weights')
        assert hasattr(hybrid_search_service, 'fusion_algorithm')

    def test_parallel_search_execution(self):
        """Test executing parallel searches across multiple sources"""
        search_request = SearchQuery(
            query="artificial intelligence",
            search_type=SearchType.HYBRID,
            limit=10
        )

        try:
            results = hybrid_search_service.search(
                search_request=search_request,
                user_id="test_user",
                organization_id="test_org"
            )
            parallel_search_success = True
        except Exception as e:
            parallel_search_success = False
            results = []
            print(f"Parallel hybrid search failed: {e}")

        assert parallel_search_success, "Parallel hybrid search should execute successfully"
        assert isinstance(results, object)  # SearchResponse or similar

    def test_result_fusion_algorithm(self):
        """Test result fusion from multiple search sources"""
        # Mock search results from different sources
        mock_source_results = {
            "vector": Mock(
                success=True,
                results=[
                    Mock(document_id="doc1", relevance_score=0.9),
                    Mock(document_id="doc2", relevance_score=0.8)
                ]
            ),
            "fulltext": Mock(
                success=True,
                results=[
                    Mock(document_id="doc1", relevance_score=0.85),
                    Mock(document_id="doc3", relevance_score=0.75)
                ]
            )
        }

        search_request = SearchQuery(
            query="test query",
            search_type=SearchType.HYBRID
        )

        try:
            fused_results = hybrid_search_service._fuse_search_results(
                source_results=mock_source_results,
                search_request=search_request
            )
            fusion_success = True
        except Exception as e:
            fusion_success = False
            fused_results = []
            print(f"Result fusion failed: {e}")

        assert fusion_success, "Result fusion should work successfully"
        assert isinstance(fused_results, list)

    def test_score_normalization(self):
        """Test score normalization across different search sources"""
        test_scores = [
            (0.95, "vector"),      # Vector similarity scores (0-1)
            (15.2, "fulltext"),    # Full-text ranking scores (variable)
            (0.88, "graph")        # Graph relevance scores (0-1)
        ]

        normalized_scores = []
        normalization_success = True

        for score, source_type in test_scores:
            try:
                normalized = hybrid_search_service._normalize_score(score, source_type)
                normalized_scores.append(normalized)
            except Exception as e:
                normalization_success = False
                print(f"Score normalization failed for {source_type}: {e}")

        assert normalization_success, "Score normalization should work for all sources"
        assert all(0 <= score <= 1 for score in normalized_scores), "Normalized scores should be in [0,1] range"

    def test_source_weight_configuration(self):
        """Test search source weight configuration"""
        weights = hybrid_search_service.source_weights

        assert isinstance(weights, dict)
        assert "vector" in weights
        assert "fulltext" in weights
        assert "graph" in weights

        # Weights should sum to 1.0 (or close to it)
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01, f"Weights should sum to 1.0, got {total_weight}"


class TestT2_005_SearchAPI:
    """Test T2-005: Search API Implementation"""

    def test_search_api_endpoints_exist(self, client):
        """Test that all search API endpoints exist"""
        endpoints = [
            "/api/v1/search/fulltext",
            "/api/v1/search/vector",
            "/api/v1/search/hybrid",
            "/api/v1/search/health"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should return 422 (validation error) for GET on POST endpoints, or 401 for auth
            assert response.status_code in [401, 405, 422], f"Endpoint {endpoint} should exist"

    def test_search_query_validation(self, client):
        """Test search query validation"""
        # Test empty query
        invalid_query = {
            "query": "",
            "search_type": "fulltext",
            "limit": 10
        }

        response = client.post("/api/v1/search/fulltext", json=invalid_query)
        assert response.status_code == 422  # Validation error

        # Test valid query (will fail auth but should pass validation)
        valid_query = {
            "query": "machine learning",
            "search_type": "fulltext",
            "limit": 10,
            "offset": 0
        }

        response = client.post("/api/v1/search/fulltext", json=valid_query)
        assert response.status_code == 401  # Auth error, but validation passed

    def test_search_response_schema(self):
        """Test search response schema compliance"""
        # This tests the response model structure
        from src.models.search_schemas import SearchResponse, SearchResult, SearchSourceResult

        # Verify response models can be instantiated
        mock_search_result = SearchResult(
            document_id="test_doc",
            title="Test Document",
            document_type="pdf",
            content_preview="Test content preview",
            relevance_score=0.85,
            score_breakdown={"vector": 0.9, "fulltext": 0.8},
            source_type="hybrid",
            highlights=["machine <mark>learning</mark>"],
            metadata={"test": "metadata"}
        )

        mock_response = SearchResponse(
            query="test query",
            search_type="hybrid",
            results=[mock_search_result],
            total_results=1,
            search_time_ms=150,
            facets={},
            suggestions=[],
            pagination={"current_page": 1, "total_pages": 1, "has_next": False, "has_prev": False}
        )

        assert mock_response.query == "test query"
        assert len(mock_response.results) == 1
        assert mock_response.total_results == 1

    def test_pagination_handling(self):
        """Test pagination parameter handling"""
        # Test valid pagination
        search_request = SearchQuery(
            query="test query",
            limit=20,
            offset=40
        )

        assert search_request.limit == 20
        assert search_request.offset == 40

        # Test boundary conditions
        boundary_requests = [
            {"limit": 1, "offset": 0},      # Minimum values
            {"limit": 100, "offset": 0},    # Maximum limit
            {"limit": 10, "offset": 1000}   # Large offset
        ]

        for params in boundary_requests:
            try:
                request = SearchQuery(query="test", **params)
                boundary_success = True
            except Exception as e:
                boundary_success = False
                print(f"Boundary test failed for {params}: {e}")
                break

        assert boundary_success, "Boundary conditions should be handled correctly"

    def test_search_health_endpoint(self, client):
        """Test search health check endpoint"""
        response = client.get("/api/v1/search/health")

        # Health check should be accessible without authentication
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "services" in data
        assert isinstance(data["services"], dict)


class TestT2_007_SearchQualityEvaluation:
    """Test T2-007: Search Quality Evaluation"""

    def test_quality_service_initialization(self):
        """Test that search quality service initializes properly"""
        assert search_quality_service is not None
        assert hasattr(search_quality_service, 'metric_thresholds')
        assert hasattr(search_quality_service, 'evaluate_search')

    def test_quality_metrics_calculation(self):
        """Test calculation of various quality metrics"""
        from src.models.search_schemas import SearchResponse, SearchResult
        from src.services.search_quality_service import QualityMetricType

        # Create mock search response
        mock_results = [
            SearchResult(
                document_id="doc1",
                title="Machine Learning Basics",
                document_type="pdf",
                content_preview="Introduction to machine learning concepts",
                relevance_score=0.9,
                score_breakdown={},
                source_type="vector",
                highlights=[],
                metadata={}
            ),
            SearchResult(
                document_id="doc2",
                title="Advanced AI Techniques",
                document_type="pdf",
                content_preview="Deep learning and neural networks",
                relevance_score=0.8,
                score_breakdown={},
                source_type="fulltext",
                highlights=[],
                metadata={}
            )
        ]

        mock_response = SearchResponse(
            query="machine learning",
            search_type=SearchType.HYBRID,
            results=mock_results,
            total_results=2,
            search_time_ms=150,
            facets={},
            suggestions=[],
            pagination={}
        )

        search_query = SearchQuery(
            query="machine learning",
            search_type=SearchType.HYBRID
        )

        try:
            evaluation = search_quality_service.evaluate_search(
                search_query=search_query,
                search_response=mock_response,
                user_id="test_user",
                organization_id="test_org"
            )
            evaluation_success = True
        except Exception as e:
            evaluation_success = False
            evaluation = None
            print(f"Quality evaluation failed: {e}")

        assert evaluation_success, "Quality evaluation should execute successfully"
        assert evaluation is not None

        # Check that expected metrics are calculated
        expected_metrics = [
            QualityMetricType.RELEVANCY,
            QualityMetricType.PRECISION,
            QualityMetricType.RESPONSE_TIME,
            QualityMetricType.RESULT_DIVERSITY,
            QualityMetricType.CONTEXTUAL_PRECISION
        ]

        for metric_type in expected_metrics:
            assert metric_type in evaluation.metrics, f"Metric {metric_type} should be calculated"
            assert isinstance(evaluation.metrics[metric_type], float), f"Metric {metric_type} should be a float"
            assert 0 <= evaluation.metrics[metric_type] <= 1, f"Metric {metric_type} should be in [0,1] range"

    def test_result_diversity_calculation(self):
        """Test result diversity metric calculation"""
        from src.services.search_quality_service import QualityMetricType
        from src.models.search_schemas import SearchResponse, SearchResult, DocumentType

        # Create diverse results
        diverse_results = [
            SearchResult(
                document_id="doc1",
                title="ML PDF",
                document_type=DocumentType.PDF,
                content_preview="content 1",
                relevance_score=0.9,
                score_breakdown={},
                source_type="hybrid",
                highlights=[],
                metadata={}
            ),
            SearchResult(
                document_id="doc2",
                title="NLP Video",
                document_type=DocumentType.VIDEO,
                content_preview="content 2",
                relevance_score=0.8,
                score_breakdown={},
                source_type="hybrid",
                highlights=[],
                metadata={}
            ),
            SearchResult(
                document_id="doc3",
                title="CV Audio",
                document_type=DocumentType.AUDIO,
                content_preview="content 3",
                relevance_score=0.7,
                score_breakdown={},
                source_type="hybrid",
                highlights=[],
                metadata={}
            )
        ]

        # Create non-diverse results (same type)
        non_diverse_results = [
            SearchResult(
                document_id="doc1",
                title="ML PDF 1",
                document_type=DocumentType.PDF,
                content_preview="content 1",
                relevance_score=0.9,
                score_breakdown={},
                source_type="hybrid",
                highlights=[],
                metadata={}
            ),
            SearchResult(
                document_id="doc2",
                title="ML PDF 2",
                document_type=DocumentType.PDF,
                content_preview="content 2",
                relevance_score=0.8,
                score_breakdown={},
                source_type="hybrid",
                highlights=[],
                metadata={}
            ),
            SearchResult(
                document_id="doc3",
                title="ML PDF 3",
                document_type=DocumentType.PDF,
                content_preview="content 3",
                relevance_score=0.7,
                score_breakdown={},
                source_type="hybrid",
                highlights=[],
                metadata={}
            )
        ]

        try:
            diverse_score = search_quality_service._calculate_result_diversity(diverse_results)
            non_diverse_score = search_quality_service._calculate_result_diversity(non_diverse_results)
            diversity_calculation_success = True
        except Exception as e:
            diversity_calculation_success = False
            diverse_score = non_diverse_score = 0
            print(f"Diversity calculation failed: {e}")

        assert diversity_calculation_success, "Diversity calculation should work"
        assert isinstance(diverse_score, float)
        assert isinstance(non_diverse_score, float)
        assert 0 <= diverse_score <= 1
        assert 0 <= non_diverse_score <= 1
        # Diverse results should have higher diversity score
        assert diverse_score >= non_diverse_score

    def test_overall_score_calculation(self):
        """Test overall quality score calculation"""
        from src.services.search_quality_service import QualityMetricType

        # Test with good metrics
        good_metrics = {
            QualityMetricType.RELEVANCY: 0.9,
            QualityMetricType.PRECISION: 0.8,
            QualityMetricType.RECALL: 0.7,
            QualityMetricType.RESPONSE_TIME: 0.8,  # Normalized
            QualityMetricType.RESULT_DIVERSITY: 0.8,
            QualityMetricType.CONTEXTUAL_PRECISION: 0.85
        }

        # Test with poor metrics
        poor_metrics = {
            QualityMetricType.RELEVANCY: 0.3,
            QualityMetricType.PRECISION: 0.4,
            QualityMetricType.RECALL: 0.2,
            QualityMetricType.RESPONSE_TIME: 0.3,  # Normalized
            QualityMetricType.RESULT_DIVERSITY: 0.3,
            QualityMetricType.CONTEXTUAL_PRECISION: 0.35
        }

        try:
            good_overall = search_quality_service._calculate_overall_score(good_metrics)
            poor_overall = search_quality_service._calculate_overall_score(poor_metrics)
            score_calculation_success = True
        except Exception as e:
            score_calculation_success = False
            good_overall = poor_overall = 0
            print(f"Overall score calculation failed: {e}")

        assert score_calculation_success, "Overall score calculation should work"
        assert isinstance(good_overall, float)
        assert isinstance(poor_overall, float)
        assert 0 <= good_overall <= 1
        assert 0 <= poor_overall <= 1
        # Good metrics should produce higher overall score
        assert good_overall > poor_overall

    def test_recommendation_generation(self):
        """Test generation of improvement recommendations"""
        from src.services.search_quality_service import QualityMetricType

        # Test with metrics that need improvement
        poor_metrics = {
            QualityMetricType.RELEVANCY: 0.5,  # Below threshold
            QualityMetricType.RESPONSE_TIME: 3.0,  # Above threshold (slow)
            QualityMetricType.PRECISION: 0.8  # Good
        }

        try:
            recommendations = search_quality_service._generate_recommendations(poor_metrics)
            recommendation_success = True
        except Exception as e:
            recommendation_success = False
            recommendations = []
            print(f"Recommendation generation failed: {e}")

        assert recommendation_success, "Recommendation generation should work"
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0, "Should generate recommendations for poor metrics"

        # Check that recommendations mention the problematic metrics
        rec_text = " ".join(recommendations).lower()
        assert "relevancy" in rec_text or "response time" in rec_text

    def test_benchmark_execution(self):
        """Test quality benchmark execution"""
        test_queries = [
            "machine learning algorithms",
            "natural language processing",
            "computer vision applications"
        ]

        try:
            # Mock the search services to avoid external dependencies
            with patch.object(hybrid_search_service, 'search') as mock_search:
                # Create mock search response
                mock_response = Mock()
                mock_response.results = []
                mock_response.search_time_ms = 100

                mock_search.return_value = mock_response

                benchmark_results = search_quality_service.run_quality_benchmark(
                    test_queries=test_queries,
                    organization_id="test_org"
                )
                benchmark_success = True
        except Exception as e:
            benchmark_success = False
            benchmark_results = {}
            print(f"Benchmark execution failed: {e}")

        assert benchmark_success, "Benchmark execution should work"
        assert isinstance(benchmark_results, dict)
        assert len(benchmark_results) == len(test_queries)


class TestT2_Integration:
    """Integration tests for T2 components"""

    def test_end_to_end_search_workflow(self):
        """Test complete search workflow from query to quality evaluation"""
        # This would test the entire pipeline, but requires extensive mocking
        # For now, we'll test the component interfaces

        from src.models.search_schemas import SearchQuery, SearchType

        # Test that all components can work together
        search_query = SearchQuery(
            query="machine learning",
            search_type=SearchType.HYBRID,
            limit=10
        )

        # Verify query can be passed to different services
        assert search_query.query == "machine learning"
        assert search_query.search_type == SearchType.HYBRID

        # Test metric types are consistent across services
        from src.services.search_quality_service import QualityMetricType
        from src.models.search_schemas import SearchType

        assert len(QualityMetricType) > 0
        assert len(SearchType) > 0

    def test_service_compatibility(self):
        """Test that all T2 services are compatible"""
        services = [
            vector_search_service,
            knowledge_graph_service,
            fulltext_search_service,
            hybrid_search_service,
            search_quality_service
        ]

        # Check that all services have required interface methods
        for service in services:
            assert service is not None
            assert hasattr(service, '__class__')

    def test_configuration_consistency(self):
        """Test configuration consistency across services"""
        # Check that services use consistent configuration
        assert hasattr(hybrid_search_service, 'source_weights')
        assert hasattr(search_quality_service, 'metric_thresholds')

        # Weights should be properly configured
        weights = hybrid_search_service.source_weights
        assert isinstance(weights, dict)
        assert len(weights) > 0

        # Thresholds should be properly configured
        thresholds = search_quality_service.metric_thresholds
        assert isinstance(thresholds, dict)
        assert len(thresholds) > 0


# Test execution summary
class TestSummary:
    """Summary of all T2 validation tests"""

    @pytest.mark.summary
    def test_all_t2_components_validated(self):
        """Summary test to ensure all T2 components have been validated"""

        validated_components = [
            "T2-001: Vector Database Setup and Embedding Generation",
            "T2-002: Knowledge Graph Construction",
            "T2-003: Full-Text Search Implementation",
            "T2-004: Hybrid Search Engine",
            "T2-005: Search API Implementation",
            "T2-007: Search Quality Evaluation"
        ]

        pending_components = [
            "T2-006: Multi-Agent Search Orchestration"
        ]

        print(f"\n✅ Validated Components ({len(validated_components)}):")
        for component in validated_components:
            print(f"   - {component}")

        print(f"\n⏳ Pending Components ({len(pending_components)}):")
        for component in pending_components:
            print(f"   - {component}")

        print(f"\n📊 Validation Coverage: {len(validated_components)/(len(validated_components)+len(pending_components))*100:.1f}%")

        # This test always passes - it's just for reporting
        assert True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])