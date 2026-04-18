"""
Enhanced Pytest Configuration for Multi-Agent Search System Testing
Provides comprehensive fixtures, mocks, and utilities for testing
"""

import pytest
import asyncio
import sys
import os
import json
import tempfile
import uuid
from datetime import datetime
from typing import Dict, Any, Generator, AsyncGenerator, List
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# Add backend src to path
backend_src = Path(__file__).parent / "src"
sys.path.insert(0, str(backend_src))

# Set test environment
from test_config import set_test_environment, TEST_AGENT_CONFIG, TEST_DATA_CONFIG
set_test_environment()

# Core imports
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import redis

# Project imports
from src.main import app
from src.core.database import Base, get_db
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority
from src.services.knowledge_graph import KnowledgeGraphService
from src.services.search import VectorSearchService, HybridSearchService

# Import agent classes
try:
    from src.agents.orchestrator import SearchOrchestrator
    from src.agents.retrieval_agent import RetrievalAgent
    from src.agents.graph_agent import GraphAgent
    from src.agents.vector_agent import VectorAgent
    from src.agents.qa_agent import QAAgent
    from src.agents.crew_manager import CrewManager
except ImportError:
    # Create mock classes if agents don't exist yet
    SearchOrchestrator = Mock
    RetrievalAgent = Mock
    GraphAgent = Mock
    VectorAgent = Mock
    QAAgent = Mock
    CrewManager = Mock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration"""
    from test_config import TEST_DATA_CONFIG, TEST_AGENT_CONFIG
    return {
        "data": TEST_DATA_CONFIG,
        "agents": TEST_AGENT_CONFIG
    }


# Database Fixtures
@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine"""
    from test_config import TEST_DATABASES

    # Use SQLite for fast testing
    engine = create_engine(
        TEST_DATABASES["sqlite"]["url"],
        **TEST_DATABASES["sqlite"]
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Clean up
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """Create a test database session"""
    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(test_db_session):
    """Create a FastAPI test client"""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# Async HTTP Client Fixture
@pytest.fixture
async def async_test_client(test_db_session):
    """Create an async HTTP client for testing"""
    async def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# User and Authentication Fixtures
@pytest.fixture
def test_user(test_db_session):
    """Create a test user"""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        role=UserRole.USER,
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture
def test_admin(test_db_session):
    """Create a test admin user"""
    admin = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="hashed_admin_password",
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db_session.add(admin)
    test_db_session.commit()
    test_db_session.refresh(admin)
    return admin


@pytest.fixture
def test_organization(test_db_session, test_admin):
    """Create a test organization"""
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug="test-org",
        description="Test organization for unit tests",
        is_active=True,
        created_by_id=test_admin.id,
        created_at=datetime.utcnow()
    )
    test_db_session.add(org)
    test_db_session.commit()
    test_db_session.refresh(org)
    return org


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for a test user"""
    from src.core.security import create_access_token

    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(test_admin):
    """Create authentication headers for an admin user"""
    from src.core.security import create_access_token

    token = create_access_token(data={"sub": str(test_admin.id)})
    return {"Authorization": f"Bearer {token}"}


# Document Fixtures
@pytest.fixture
def sample_documents(test_db_session, test_user):
    """Create sample documents for testing"""
    documents = []

    for i in range(10):
        doc = Document(
            id=uuid.uuid4(),
            title=f"Test Document {i+1}",
            content=f"This is test content for document {i+1}. " * 20,
            document_type=DocumentType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            owner_id=test_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={
                "page_count": i + 1,
                "word_count": (i + 1) * 100,
                "language": "en"
            }
        )
        documents.append(doc)
        test_db_session.add(doc)

    test_db_session.commit()

    for doc in documents:
        test_db_session.refresh(doc)

    return documents


@pytest.fixture
def sample_processing_jobs(test_db_session, sample_documents, test_user):
    """Create sample processing jobs"""
    jobs = []

    for doc in sample_documents:
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            job_type=JobType.EMBEDDING_GENERATION,
            status=JobStatus.COMPLETED,
            progress=100,
            owner_id=test_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            result_data={"embedding_id": str(uuid.uuid4())}
        )
        jobs.append(job)
        test_db_session.add(job)

    test_db_session.commit()

    for job in jobs:
        test_db_session.refresh(job)

    return jobs


# Mock Service Fixtures
@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for vector search tests"""
    mock_client = Mock(spec=QdrantClient)

    # Mock collection operations
    mock_client.get_collections.return_value = {
        "collections": [
            {"name": "documents", "points_count": 1000}
        ]
    }

    # Mock search results
    mock_client.search.return_value = [
        Mock(
            id=str(uuid.uuid4()),
            score=0.95,
            payload={"document_id": str(uuid.uuid4()), "content": "test content"}
        )
    ]

    # Mock upsert operation
    mock_client.upsert.return_value = Mock()

    return mock_client


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for graph database tests"""
    mock_driver = Mock(spec=GraphDatabase.driver)

    # Mock session
    mock_session = Mock()
    mock_session.run.return_value = Mock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    mock_driver.session.return_value = mock_session
    mock_driver.verify_connectivity.return_value = Mock()

    return mock_driver


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for caching tests"""
    mock_client = Mock(spec=redis.Redis)

    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1
    mock_client.exists.return_value = 0
    mock_client.flushdb.return_value = True

    return mock_client


# Service Fixtures
@pytest.fixture
def knowledge_graph_service(test_db_session, mock_neo4j_driver):
    """Knowledge graph service fixture with mocked dependencies"""
    with patch('src.services.knowledge_graph_service.GraphDatabase.driver', return_value=mock_neo4j_driver):
        service = KnowledgeGraphService()
        yield service


@pytest.fixture
def vector_search_service(test_db_session, mock_qdrant_client):
    """Vector search service fixture with mocked dependencies"""
    with patch('src.services.vector_search_service.QdrantClient', return_value=mock_qdrant_client):
        service = VectorSearchService()
        yield service


@pytest.fixture
def hybrid_search_service(test_db_session, vector_search_service, knowledge_graph_service):
    """Hybrid search service fixture"""
    service = HybridSearchService(
        vector_service=vector_search_service,
        graph_service=knowledge_graph_service
    )
    return service


# Multi-Agent Fixtures
@pytest.fixture
def mock_search_tools():
    """Mock search tools for agents"""
    return {
        "vector_search": AsyncMock(return_value=[]),
        "graph_search": AsyncMock(return_value=[]),
        "fulltext_search": AsyncMock(return_value=[]),
        "filter_tool": AsyncMock(return_value=[]),
        "embedding_tool": AsyncMock(return_value=[0.1] * 384),
        "synthesis_tool": AsyncMock(return_value="Synthesized answer"),
        "ranking_tool": AsyncMock(return_value=[])
    }


@pytest.fixture
def search_orchestrator(mock_search_tools):
    """Search orchestrator agent fixture"""
    with patch('src.agents.orchestrator.SearchOrchestrator.__init__', return_value=None):
        orchestrator = SearchOrchestrator()
        orchestrator.tools = mock_search_tools
        yield orchestrator


@pytest.fixture
def retrieval_agent(mock_search_tools):
    """Retrieval agent fixture"""
    with patch('src.agents.retrieval_agent.RetrievalAgent.__init__', return_value=None):
        agent = RetrievalAgent()
        agent.vector_search_tool = mock_search_tools["vector_search"]
        agent.fulltext_search_tool = mock_search_tools["fulltext_search"]
        yield agent


@pytest.fixture
def graph_agent(mock_search_tools):
    """Graph agent fixture"""
    with patch('src.agents.graph_agent.GraphAgent.__init__', return_value=None):
        agent = GraphAgent()
        agent.graph_search_tool = mock_search_tools["graph_search"]
        yield agent


@pytest.fixture
def vector_agent(mock_search_tools):
    """Vector agent fixture"""
    with patch('src.agents.vector_agent.VectorAgent.__init__', return_value=None):
        agent = VectorAgent()
        agent.vector_search_tool = mock_search_tools["vector_search"]
        agent.embedding_tool = mock_search_tools["embedding_tool"]
        yield agent


@pytest.fixture
def qa_agent(mock_search_tools):
    """QA agent fixture"""
    with patch('src.agents.qa_agent.QAAgent.__init__', return_value=None):
        agent = QAAgent()
        agent.synthesis_tool = mock_search_tools["synthesis_tool"]
        agent.ranking_tool = mock_search_tools["ranking_tool"]
        yield agent


@pytest.fixture
def crew_manager(search_orchestrator, retrieval_agent, graph_agent, vector_agent, qa_agent):
    """Crew manager fixture with all agents"""
    with patch('src.agents.crew_manager.CrewManager.__init__', return_value=None):
        manager = CrewManager()
        manager.orchestrator = search_orchestrator
        manager.retrieval_agent = retrieval_agent
        manager.graph_agent = graph_agent
        manager.vector_agent = vector_agent
        manager.qa_agent = qa_agent
        yield manager


# Test Data Fixtures
@pytest.fixture
def sample_search_queries():
    """Sample search queries for testing"""
    return [
        "What is machine learning?",
        "Find documents about quantum computing",
        "Climate change research papers",
        "Natural language processing techniques",
        "Deep learning architectures"
    ]


@pytest.fixture
def sample_embeddings():
    """Sample embedding vectors for testing"""
    import numpy as np
    return [
        np.random.rand(384).tolist() for _ in range(10)
    ]


@pytest.fixture
def sample_knowledge_graph_data():
    """Sample knowledge graph data for testing"""
    return {
        "entities": [
            {"id": "entity1", "type": "Person", "name": "Albert Einstein"},
            {"id": "entity2", "type": "Concept", "name": "Relativity"},
            {"id": "entity3", "type": "Document", "name": "Relativity Paper"}
        ],
        "relationships": [
            {"from": "entity1", "to": "entity2", "type": "AUTHORED"},
            {"from": "entity2", "to": "entity3", "type": "DESCRIBES_IN"}
        ]
    }


# Performance Testing Fixtures
@pytest.fixture
def performance_metrics():
    """Collect performance metrics during tests"""
    import time
    from dataclasses import dataclass
    from typing import List

    @dataclass
    class Metric:
        name: str
        start_time: float
        end_time: float
        duration: float

    metrics = []

    def record_metric(name: str, start_time: float, end_time: float = None):
        if end_time is None:
            end_time = time.time()
        metrics.append(Metric(name, start_time, end_time, end_time - start_time))

    yield record_metric

    # Print summary
    if metrics:
        print("\n=== Performance Metrics ===")
        for metric in metrics:
            print(f"{metric.name}: {metric.duration:.4f}s")


# WebSocket Testing Fixture
@pytest.fixture
async def websocket_client():
    """WebSocket client for testing real-time features"""
    import websockets
    import asyncio

    # Connect to test WebSocket endpoint
    uri = "ws://localhost:8000/api/v2/ws/connect?token=test-token"

    try:
        async with websockets.connect(uri) as websocket:
            yield websocket
    except Exception as e:
        pytest.skip(f"WebSocket not available for testing: {e}")


# Cleanup Fixture
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup resources after each test"""
    yield

    # Clean up any temporary files
    import tempfile
    import shutil

    temp_dir = tempfile.gettempdir()
    for item in os.listdir(temp_dir):
        if item.startswith("test_"):
            item_path = os.path.join(temp_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except:
                pass


# Marker registration
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers",
        "agent: mark test as agent-related test"
    )
    config.addinivalue_line(
        "markers",
        "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers",
        "websocket: mark test as WebSocket test"
    )


# Custom assertion helpers
@pytest.fixture
def assert_valid_search_result():
    """Assert that a search result has valid structure"""
    def _assert(result):
        assert isinstance(result, dict)
        assert "id" in result
        assert "title" in result
        assert "content" in result
        assert "score" in result
        assert isinstance(result["score"], (int, float))
        assert 0 <= result["score"] <= 1
        return True

    return _assert


@pytest.fixture
def assert_valid_agent_response():
    """Assert that an agent response has valid structure"""
    def _assert(response):
        assert isinstance(response, dict)
        assert "answer" in response or "result" in response
        assert "confidence" in response or "sources" in response
        if "confidence" in response:
            assert isinstance(response["confidence"], (int, float))
            assert 0 <= response["confidence"] <= 1
        return True

    return _assert