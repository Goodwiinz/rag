"""
Comprehensive test configuration for the Multimodal RAG FastAPI backend
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set test environment variables
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def configure_test_environment():
    """Setup test environment before running tests"""
    print("\n🧪 Setting up FastAPI Backend Test Environment")
    print("=" * 60)

    yield

    print("\n🏁 FastAPI Backend Tests Completed")
    print("=" * 60)

@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging for tests"""
    import logging

    # Set specific logger levels to reduce noise during tests
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("qdrant").setLevel(logging.WARNING)

# Database fixtures
@pytest.fixture
def mock_db_engine():
    """Mock database engine for testing"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    # Use in-memory SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    yield engine

    engine.dispose()

@pytest.fixture
def mock_db_session(mock_db_engine):
    """Mock database session for testing"""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=mock_db_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()

# Mock service fixtures
@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for vector search tests"""
    client = Mock()
    client.upsert = Mock(return_value=Mock())
    client.search = Mock(return_value=[])
    client.create_collection = Mock(return_value=Mock())
    client.get_collection = Mock(return_value=Mock())
    client.delete_collection = Mock(return_value=Mock())
    client.count = Mock(return_value=Mock(count=0))
    client.scroll = Mock(return_value=([], None))

    return client

@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for knowledge graph tests"""
    driver = Mock()
    session = MagicMock()
    session.run = Mock(return_value=Mock())
    session.close = Mock(return_value=None)
    session.__enter__.return_value = session
    session.__exit__.side_effect = lambda exc_type, exc, tb: session.close()
    driver.session = Mock(return_value=session)
    driver.verify_connectivity = Mock(return_value=None)
    driver.close = Mock(return_value=None)

    return driver

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for caching tests"""
    client = Mock()
    client.get = Mock(return_value=None)
    client.set = Mock(return_value=True)
    client.delete = Mock(return_value=True)
    client.exists = Mock(return_value=False)
    client.ping = Mock(return_value=True)

    return client

@pytest.fixture
def mock_celery_app():
    """Mock Celery app for background task testing"""
    app = Mock()
    app.send_task = Mock(return_value=Mock(id="test-task-id"))
    app.control = Mock()
    app.inspect = Mock()

    return app

@pytest.fixture
def mock_embeddings_service():
    """Mock embedding service for testing"""
    import numpy as np

    service = Mock()

    def mock_embed_query(text: str):
        # Create deterministic embeddings based on text hash
        np.random.seed(hash(text) % 2**32)
        return np.random.rand(384).tolist()

    service.embed_query = Mock(side_effect=mock_embed_query)
    service.embed_documents = Mock(side_effect=lambda texts: [mock_embed_query(text) for text in texts])

    return service

# FastAPI test client fixtures
@pytest.fixture
def test_app():
    """Create FastAPI test application"""
    from fastapi import FastAPI
    from src.main import app

    # Override dependencies for testing
    app.dependency_overrides = {}

    return app

@pytest.fixture
def test_client(test_app) -> Generator[TestClient, None, None]:
    """Create test client for FastAPI application"""
    with TestClient(test_app) as client:
        yield client

@pytest.fixture
async def async_test_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client for FastAPI application"""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client

# Authentication fixtures
@pytest.fixture
def mock_user():
    """Mock user for authentication testing"""
    from src.models.user import User, UserRole

    user = Mock(spec=User)
    user.id = "test-user-id"
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.role = UserRole.USER
    user.organization_id = "test-org-id"
    user.is_active = True
    user.created_at = "2024-01-01T00:00:00Z"
    user.updated_at = "2024-01-01T00:00:00Z"

    return user

@pytest.fixture
def mock_admin_user():
    """Mock admin user for authorization testing"""
    from src.models.user import User, UserRole

    user = Mock(spec=User)
    user.id = "test-admin-id"
    user.email = "admin@example.com"
    user.first_name = "Admin"
    user.last_name = "User"
    user.role = UserRole.ADMIN
    user.organization_id = "test-org-id"
    user.is_active = True
    user.created_at = "2024-01-01T00:00:00Z"
    user.updated_at = "2024-01-01T00:00:00Z"

    return user

@pytest.fixture
def mock_auth_headers(mock_user):
    """Mock authentication headers"""
    import jwt
    from datetime import datetime, timedelta

    # Create mock JWT token
    payload = {
        "sub": mock_user.id,
        "email": mock_user.email,
        "role": mock_user.role.value,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow()
    }

    token = jwt.encode(payload, "test-secret", algorithm="HS256")

    return {"Authorization": f"Bearer {token}"}

# Test data fixtures
@pytest.fixture
def sample_documents_data():
    """Sample document data for testing"""
    return [
        {
            "id": "doc-1",
            "title": "Introduction to Machine Learning",
            "content": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
            "document_type": "pdf",
            "tags": ["machine learning", "AI", "algorithms"],
            "metadata": {"pages": 50, "author": "Test Author"},
            "created_at": "2024-01-01T00:00:00Z"
        },
        {
            "id": "doc-2",
            "title": "Natural Language Processing Fundamentals",
            "content": "NLP is a branch of artificial intelligence that helps computers understand, interpret and manipulate human language.",
            "document_type": "pdf",
            "tags": ["NLP", "linguistics", "text processing"],
            "metadata": {"pages": 75, "author": "Test Author 2"},
            "created_at": "2024-01-02T00:00:00Z"
        },
        {
            "id": "doc-3",
            "title": "Computer Vision and Image Recognition",
            "content": "Computer vision is an AI field that trains computers to interpret and understand the visual world from digital images or videos.",
            "document_type": "video",
            "tags": ["computer vision", "image processing", "deep learning"],
            "metadata": {"duration": 3600, "author": "Test Author 3"},
            "created_at": "2024-01-03T00:00:00Z"
        }
    ]

@pytest.fixture
def sample_search_queries():
    """Sample search queries for testing"""
    return [
        "machine learning algorithms",
        "natural language processing",
        "computer vision applications",
        "deep neural networks",
        "artificial intelligence ethics",
        "data preprocessing techniques",
        "model evaluation metrics",
        "feature engineering methods"
    ]

@pytest.fixture
def sample_search_results():
    """Sample search results for testing"""
    return [
        {
            "id": "result-1",
            "document_id": "doc-1",
            "title": "Introduction to Machine Learning",
            "content_snippet": "Machine learning is a subset of artificial intelligence...",
            "score": 0.95,
            "metadata": {"source": "vector", "model": "embedding-model-v1"}
        },
        {
            "id": "result-2",
            "document_id": "doc-2",
            "title": "Natural Language Processing Fundamentals",
            "content_snippet": "NLP is a branch of artificial intelligence...",
            "score": 0.87,
            "metadata": {"source": "fulltext", "index": "documents_index"}
        }
    ]

# Performance tracking fixture
@pytest.fixture
def performance_tracker():
    """Track performance metrics for tests"""
    import time

    class PerformanceTracker:
        def __init__(self):
            self.metrics = {}
            self.start_times = {}

        def start_timer(self, name: str):
            self.start_times[name] = time.time()

        def end_timer(self, name: str) -> float:
            if name in self.start_times:
                duration = time.time() - self.start_times[name]
                if name not in self.metrics:
                    self.metrics[name] = []
                self.metrics[name].append(duration)
                return duration
            return 0.0

        def get_average(self, name: str) -> float:
            if name in self.metrics and self.metrics[name]:
                return sum(self.metrics[name]) / len(self.metrics[name])
            return 0.0

        def get_summary(self) -> dict:
            summary = {}
            for name, times in self.metrics.items():
                summary[name] = {
                    'count': len(times),
                    'total': sum(times),
                    'average': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times)
                }
            return summary

    tracker = PerformanceTracker()
    yield tracker

    # Print performance summary after test
    if tracker.metrics:
        print(f"\n⏱️ Performance Summary:")
        for name, stats in tracker.get_summary().items():
            print(f"   {name}: {stats['average']:.3f}s avg ({stats['count']} runs)")

# Mock file fixtures
@pytest.fixture
def sample_text_file():
    """Create a sample text file for testing"""
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a sample text file for testing document processing.\n")
        f.write("It contains multiple lines of text to simulate a real document.\n")
        f.write("The content is used for testing ingestion and processing pipelines.\n")
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)

@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing"""
    import tempfile
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    temp_path = tempfile.mktemp(suffix='.pdf')

    c = canvas.Canvas(temp_path, pagesize=letter)
    c.drawString(100, 750, "Sample PDF Document")
    c.drawString(100, 700, "This is a test PDF document for processing.")
    c.drawString(100, 650, "It contains text content for extraction testing.")
    c.save()

    yield temp_path

    # Cleanup
    os.unlink(temp_path)

# Test markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "auth: Authentication tests")
    config.addinivalue_line("markers", "search: Search functionality tests")
    config.addinivalue_line("markers", "documents: Document processing tests")
    config.addinivalue_line("markers", "database: Database tests")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")

# Collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add markers based on test file names and classes
        if "test_auth" in str(item.fspath):
            item.add_marker(pytest.mark.auth)
        elif "test_search" in str(item.fspath):
            item.add_marker(pytest.mark.search)
        elif "test_documents" in str(item.fspath):
            item.add_marker(pytest.mark.documents)
        elif "test_database" in str(item.fspath):
            item.add_marker(pytest.mark.database)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)

        # Add unit/integration markers based on test class names
        if "UnitTest" in item.cls.__name__ if item.cls else False:
            item.add_marker(pytest.mark.unit)
        elif "IntegrationTest" in item.cls.__name__ if item.cls else False:
            item.add_marker(pytest.mark.integration)
        elif "E2ETest" in item.cls.__name__ if item.cls else False:
            item.add_marker(pytest.mark.e2e)
