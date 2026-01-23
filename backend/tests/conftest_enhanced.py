"""
Enhanced Pytest Configuration for Feature-Driven Development

Provides comprehensive fixtures, factories, and utilities for testing
new features with proper isolation and scalability pattern verification.
"""

import asyncio
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["LOG_LEVEL"] = "DEBUG"


# =============================================================================
# Event Loop Configuration
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the entire test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_database_url():
    """Get test database URL (in-memory SQLite for speed)."""
    return "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_async_database_url():
    """Get async test database URL."""
    return "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
def sync_engine(test_database_url):
    """Create synchronous test engine with fresh database per test."""
    from src.core.database import Base

    engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(sync_engine) -> Generator[Session, None, None]:
    """Create database session for each test."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=sync_engine,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
async def async_engine(test_async_database_url):
    """Create async test engine."""
    from src.core.database import Base

    engine = create_async_engine(
        test_async_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def async_db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for each test."""
    AsyncTestingSessionLocal = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with AsyncTestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


# =============================================================================
# FastAPI Test Client Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def test_app(db_session):
    """Create test FastAPI application with dependency overrides."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.core.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_app):
    """Create synchronous test client."""
    from fastapi.testclient import TestClient

    with TestClient(test_app) as client:
        yield client


@pytest.fixture(scope="function")
async def async_client(test_app):
    """Create async test client."""
    from httpx import AsyncClient

    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


# =============================================================================
# Authentication Fixtures
# =============================================================================


@pytest.fixture
def test_user_data():
    """Standard test user data."""
    return {
        "id": "test-user-123",
        "email": "test@example.com",
        "username": "testuser",
        "role": "user",
        "organization_id": "test-org-123",
    }


@pytest.fixture
def admin_user_data():
    """Admin test user data."""
    return {
        "id": "admin-user-123",
        "email": "admin@example.com",
        "username": "admin",
        "role": "admin",
        "organization_id": "test-org-123",
    }


@pytest.fixture
def auth_headers(test_user_data):
    """Generate authentication headers for test user."""
    from src.core.security import create_access_token

    token = create_access_token(data={"sub": test_user_data["id"]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user_data):
    """Generate authentication headers for admin user."""
    from src.core.security import create_access_token

    token = create_access_token(data={"sub": admin_user_data["id"]})
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Mock External Services
# =============================================================================


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.mget = AsyncMock(return_value=[])
    mock.scan = AsyncMock(return_value=(0, []))
    mock.publish = AsyncMock(return_value=1)
    mock.subscribe = AsyncMock()
    return mock


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant vector database client."""
    mock = MagicMock()
    mock.upsert = MagicMock(return_value=True)
    mock.search = MagicMock(return_value=[])
    mock.create_collection = MagicMock(return_value=True)
    mock.get_collection = MagicMock(return_value=MagicMock(points_count=0))
    mock.delete = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j driver."""
    mock_session = MagicMock()
    mock_session.run = MagicMock(return_value=MagicMock(data=lambda: []))
    mock_session.close = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock()

    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    mock_driver.close = MagicMock()
    return mock_driver


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    mock = MagicMock()

    # Chat completion
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(content="Mock response"),
            finish_reason="stop",
        )
    ]
    mock.chat.completions.create = MagicMock(return_value=mock_completion)

    # Embeddings
    mock_embedding = MagicMock()
    mock_embedding.data = [MagicMock(embedding=[0.1] * 1536)]
    mock.embeddings.create = MagicMock(return_value=mock_embedding)

    return mock


@pytest.fixture
def mock_embeddings():
    """Mock embedding service with deterministic outputs."""
    import hashlib

    mock = MagicMock()

    def deterministic_embed(text: str) -> List[float]:
        """Generate deterministic embeddings based on text hash."""
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Convert to list of floats between -1 and 1
        return [(b / 255.0 * 2 - 1) for b in hash_bytes[:384]]

    mock.embed_query = MagicMock(side_effect=deterministic_embed)
    mock.embed_documents = MagicMock(
        side_effect=lambda texts: [deterministic_embed(t) for t in texts]
    )
    return mock


# =============================================================================
# Resilience Testing Fixtures
# =============================================================================


@pytest.fixture
def reset_circuit_breakers():
    """Reset all circuit breakers before/after test."""
    from src.core.circuit_breaker import circuit_breakers

    for breaker in circuit_breakers.values():
        breaker.reset()
    yield
    for breaker in circuit_breakers.values():
        breaker.reset()


@pytest.fixture
def reset_bulkheads():
    """Reset all bulkheads before/after test."""
    from src.core.resilience import reset_all_bulkheads

    reset_all_bulkheads()
    yield
    reset_all_bulkheads()


@pytest.fixture
def mock_failing_service():
    """Mock that fails N times then succeeds."""

    def create_mock(fail_count: int = 2):
        call_count = 0

        async def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= fail_count:
                raise ConnectionError(f"Simulated failure {call_count}")
            return {"success": True, "attempt": call_count}

        return mock_call, lambda: call_count

    return create_mock


# =============================================================================
# Test Data Factories
# =============================================================================


class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def document(
        title: str = "Test Document",
        content: str = "Test content for document",
        doc_type: str = "pdf",
        **kwargs,
    ) -> Dict[str, Any]:
        """Create document test data."""
        return {
            "title": title,
            "content": content,
            "document_type": doc_type,
            "tags": kwargs.get("tags", ["test"]),
            "metadata": kwargs.get("metadata", {}),
            "created_at": kwargs.get("created_at", datetime.utcnow().isoformat()),
            **kwargs,
        }

    @staticmethod
    def search_query(
        query: str = "test query",
        limit: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create search query test data."""
        return {
            "query": query,
            "limit": limit,
            "offset": kwargs.get("offset", 0),
            "filters": kwargs.get("filters", {}),
            "search_type": kwargs.get("search_type", "hybrid"),
            **kwargs,
        }

    @staticmethod
    def user(
        email: str = "test@example.com",
        **kwargs,
    ) -> Dict[str, Any]:
        """Create user test data."""
        import uuid

        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "email": email,
            "username": kwargs.get("username", email.split("@")[0]),
            "role": kwargs.get("role", "user"),
            "organization_id": kwargs.get("organization_id", str(uuid.uuid4())),
            **kwargs,
        }

    @staticmethod
    def chat_message(
        content: str = "Test message",
        role: str = "user",
        **kwargs,
    ) -> Dict[str, Any]:
        """Create chat message test data."""
        import uuid

        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "content": content,
            "role": role,
            "thread_id": kwargs.get("thread_id", str(uuid.uuid4())),
            "created_at": kwargs.get("created_at", datetime.utcnow().isoformat()),
            **kwargs,
        }


@pytest.fixture
def factory():
    """Provide test data factory."""
    return TestDataFactory()


# =============================================================================
# Performance Testing Fixtures
# =============================================================================


class PerformanceTracker:
    """Track performance metrics during tests."""

    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self._start_times: Dict[str, float] = {}

    def start(self, name: str):
        """Start timing an operation."""
        import time

        self._start_times[name] = time.perf_counter()

    def stop(self, name: str) -> float:
        """Stop timing and record duration."""
        import time

        if name not in self._start_times:
            return 0.0

        duration = time.perf_counter() - self._start_times[name]
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(duration)
        del self._start_times[name]
        return duration

    @asynccontextmanager
    async def measure(self, name: str):
        """Context manager for measuring async operations."""
        self.start(name)
        try:
            yield
        finally:
            self.stop(name)

    def get_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for a metric."""
        if name not in self.metrics or not self.metrics[name]:
            return {}

        values = self.metrics[name]
        return {
            "count": len(values),
            "total": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "p50": sorted(values)[len(values) // 2],
            "p95": sorted(values)[int(len(values) * 0.95)] if len(values) >= 20 else max(values),
        }

    def summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary of all metrics."""
        return {name: self.get_stats(name) for name in self.metrics}


@pytest.fixture
def perf_tracker():
    """Provide performance tracker."""
    tracker = PerformanceTracker()
    yield tracker

    # Print summary if any metrics were collected
    if tracker.metrics:
        print("\n📊 Performance Summary:")
        for name, stats in tracker.summary().items():
            print(f"   {name}: {stats['avg']*1000:.2f}ms avg ({stats['count']} calls)")


# =============================================================================
# Feature Testing Utilities
# =============================================================================


@pytest.fixture
def feature_flag_override():
    """Override feature flags for testing."""
    original_flags = {}

    def override(flag_name: str, value: bool):
        # Store original if not already stored
        if flag_name not in original_flags:
            original_flags[flag_name] = os.environ.get(f"FEATURE_{flag_name.upper()}")
        os.environ[f"FEATURE_{flag_name.upper()}"] = str(value).lower()

    yield override

    # Restore original values
    for flag_name, original_value in original_flags.items():
        env_key = f"FEATURE_{flag_name.upper()}"
        if original_value is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = original_value


# =============================================================================
# Test Markers Configuration
# =============================================================================


def pytest_configure(config):
    """Configure custom pytest markers."""
    markers = [
        "unit: Unit tests (fast, no external dependencies)",
        "integration: Integration tests (may use external services)",
        "e2e: End-to-end tests (full system)",
        "slow: Slow tests (skipped in quick runs)",
        "resilience: Tests for resilience patterns",
        "scalability: Tests for scalability patterns",
        "feature: Feature-specific tests",
        "regression: Regression tests",
        "smoke: Smoke tests for quick validation",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)


# =============================================================================
# Test Hooks
# =============================================================================


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Setup hook for each test."""
    # Skip slow tests unless explicitly requested
    if "slow" in item.keywords and not item.config.getoption("--run-slow", default=False):
        pytest.skip("Skipping slow test (use --run-slow to run)")


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests",
    )
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests requiring external services",
    )
