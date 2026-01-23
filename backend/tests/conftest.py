"""
Unified Pytest Configuration for Backend Tests

This file provides comprehensive test fixtures and configuration for:
- Database mocking with SQLite
- External service mocking (Qdrant, Neo4j, Redis, Celery)
- AI client mocking
- Authentication fixtures
- Performance tracking

Usage:
    All fixtures are automatically available to tests via pytest's fixture discovery.
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path
from typing import AsyncGenerator, Generator, List, Optional
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set test environment variables before importing application code
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    # Test type markers
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external deps)")
    config.addinivalue_line("markers", "integration: Integration tests (may use containers)")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")

    # Feature/domain markers
    config.addinivalue_line("markers", "ai: AI-specific tests (mocked or real)")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line("markers", "auth: Authentication tests")
    config.addinivalue_line("markers", "search: Search functionality tests")
    config.addinivalue_line("markers", "documents: Document processing tests")

    # External dependency markers (for testcontainers)
    config.addinivalue_line(
        "markers",
        "requires_postgres: Tests requiring real PostgreSQL (via testcontainers)"
    )
    config.addinivalue_line(
        "markers",
        "requires_redis: Tests requiring real Redis (via testcontainers)"
    )
    config.addinivalue_line(
        "markers",
        "requires_neo4j: Tests requiring real Neo4j (via testcontainers)"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically add markers based on file/class names."""
    for item in items:
        # Add markers based on test file names
        test_path = str(item.fspath)
        if "test_auth" in test_path:
            item.add_marker(pytest.mark.auth)
        elif "test_search" in test_path:
            item.add_marker(pytest.mark.search)
        elif "test_document" in test_path:
            item.add_marker(pytest.mark.documents)

        if "integration" in test_path:
            item.add_marker(pytest.mark.integration)
        elif "performance" in test_path:
            item.add_marker(pytest.mark.performance)
        elif "e2e" in test_path:
            item.add_marker(pytest.mark.e2e)
        elif "unit" in test_path:
            item.add_marker(pytest.mark.unit)


# ============================================================================
# Event Loop Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_db_engine():
    """Create an in-memory SQLite engine for testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )

    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def mock_db_session(mock_db_engine):
    """Create a database session for testing."""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=mock_db_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ============================================================================
# External Service Mocks
# ============================================================================

@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for vector search tests."""
    import numpy as np

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
    """Mock Neo4j driver for knowledge graph tests."""
    driver = Mock()
    session = Mock()
    session.run = Mock(return_value=Mock())
    session.close = Mock(return_value=None)
    driver.session = Mock(return_value=session)
    driver.verify_connectivity = Mock(return_value=None)
    driver.close = Mock(return_value=None)

    return driver


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for caching tests."""
    client = Mock()
    client.get = Mock(return_value=None)
    client.set = Mock(return_value=True)
    client.delete = Mock(return_value=True)
    client.exists = Mock(return_value=False)
    client.ping = Mock(return_value=True)
    client.expire = Mock(return_value=True)

    return client


@pytest.fixture
def mock_celery_app():
    """Mock Celery app for background task testing."""
    app = Mock()
    app.send_task = Mock(return_value=Mock(id="test-task-id"))
    app.control = Mock()
    app.control.inspect = Mock()
    app.AsyncResult = Mock(return_value=Mock(state="PENDING", result=None))

    return app


# ============================================================================
# Embedding Service Mocks
# ============================================================================

@pytest.fixture
def mock_embeddings_service():
    """Mock embedding service for testing."""
    import numpy as np

    service = Mock()

    def mock_embed_query(text: str) -> List[float]:
        """Generate deterministic embeddings based on text hash."""
        np.random.seed(hash(text) % 2**32)
        return np.random.rand(384).tolist()

    service.embed_query = Mock(side_effect=mock_embed_query)
    service.embed_documents = Mock(
        side_effect=lambda texts: [mock_embed_query(text) for text in texts]
    )
    service.embed = AsyncMock(
        side_effect=lambda texts: [mock_embed_query(text) for text in texts]
    )

    return service


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Create a mock regular user."""
    user = Mock()
    user.id = "test-user-id-12345"
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.role = Mock(value="user")
    user.organization_id = "test-org-id"
    user.is_active = True
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()

    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = Mock()
    user.id = "test-admin-id-12345"
    user.email = "admin@example.com"
    user.first_name = "Admin"
    user.last_name = "User"
    user.role = Mock(value="admin")
    user.organization_id = "test-org-id"
    user.is_active = True
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()

    return user


@pytest.fixture
def mock_auth_headers(mock_user):
    """Generate mock JWT authentication headers."""
    import jwt

    payload = {
        "sub": mock_user.id,
        "email": mock_user.email,
        "role": mock_user.role.value,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow()
    }

    token = jwt.encode(payload, "test-secret-key-for-testing", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_documents_data():
    """Sample document data for testing."""
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
    """Sample search queries for testing."""
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
    """Sample search results for testing."""
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


# ============================================================================
# Performance Tracking
# ============================================================================

@pytest.fixture
def performance_tracker():
    """Track performance metrics for tests."""
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
                if times:
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

    # Print summary if metrics were recorded
    if tracker.metrics:
        print(f"\n Performance Summary:")
        for name, stats in tracker.get_summary().items():
            print(f"   {name}: {stats['average']:.3f}s avg ({stats['count']} runs)")


# ============================================================================
# Logging Configuration
# ============================================================================

@pytest.fixture(autouse=True)
def configure_test_logging():
    """Configure logging for tests to reduce noise."""
    import logging

    # Reduce noise from common loggers
    for logger_name in ["uvicorn", "fastapi", "sqlalchemy", "httpx", "qdrant", "neo4j"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    yield


# ============================================================================
# FastAPI Test Client Fixtures
# ============================================================================

@pytest.fixture
def test_app():
    """Create FastAPI test application."""
    try:
        from src.main import app
        # Clear any existing dependency overrides
        app.dependency_overrides = {}
        return app
    except ImportError:
        pytest.skip("FastAPI app not available")


@pytest.fixture
def test_client(test_app):
    """Create synchronous test client for FastAPI application."""
    from fastapi.testclient import TestClient

    with TestClient(test_app) as client:
        yield client


@pytest.fixture
async def async_test_client(test_app) -> AsyncGenerator:
    """Create async test client for FastAPI application."""
    from httpx import AsyncClient

    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


# ============================================================================
# Temporary File Fixtures
# ============================================================================

@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory."""
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_text_file(temp_upload_dir):
    """Create a sample text file for testing."""
    file_path = os.path.join(temp_upload_dir, "sample.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("""This is a sample text file for testing document processing.

It contains multiple paragraphs and various content types including:
- Regular text
- Some numbers like 123 and 4567
- Email addresses: test@example.com
- URLs: https://www.example.com
- Company names: Acme Corporation, Global Tech Inc

The quick brown fox jumps over the lazy dog.
""")
    return file_path


# ============================================================================
# Import Service Fixtures
# ============================================================================
# Import service-specific fixtures for automatic discovery
try:
    from tests.fixtures.service_fixtures import *
except ImportError:
    pass  # Service fixtures may not be available in all test contexts
