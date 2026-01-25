"""
Integration Test Configuration

Sets up environment variables BEFORE importing the application to ensure
tests use SQLite in-memory database instead of PostgreSQL.

This prevents the 'database does not exist' error when running integration tests
without a PostgreSQL server running.
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# CRITICAL: Set environment variables BEFORE any application imports
# This prevents database.py from trying to connect to PostgreSQL
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ASYNC_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["TESTING"] = "true"
os.environ["DEBUG"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"

# Mock external service URLs (tests will mock these services)
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["QDRANT_URL"] = "http://localhost:6333"

# Mock API keys for testing
os.environ["SECRET_KEY"] = "test-secret-key-for-integration-tests"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"

import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.fixture(autouse=True)
def mock_external_services(request):
    """
    Auto-mock external services for integration tests that don't use testcontainers.

    Tests marked with @pytest.mark.requires_postgres or @pytest.mark.requires_redis
    will NOT have those services mocked - they use real containers instead.
    """
    # Check if test uses real containers
    markers = {m.name for m in request.node.iter_markers()}
    uses_postgres = "requires_postgres" in markers
    uses_redis = "requires_redis" in markers

    # Build context managers for services we need to mock
    patches = []

    if not uses_redis:
        patches.append(patch("redis.Redis"))
        patches.append(patch("redis.asyncio.Redis"))

    patches.append(patch("qdrant_client.QdrantClient"))
    patches.append(patch("neo4j.GraphDatabase.driver"))

    # Apply patches
    mocks = [p.start() for p in patches]

    # Configure mocks
    mock_idx = 0
    if not uses_redis:
        # Redis mock
        mock_redis = mocks[mock_idx]
        mock_redis_instance = Mock()
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis.return_value = mock_redis_instance
        mock_redis.from_url.return_value = mock_redis_instance
        mock_idx += 1

        # Async Redis mock
        mock_async_redis = mocks[mock_idx]
        mock_async_redis_instance = AsyncMock()
        mock_async_redis_instance.ping.return_value = True
        mock_async_redis_instance.get.return_value = None
        mock_async_redis_instance.set.return_value = True
        mock_async_redis.return_value = mock_async_redis_instance
        mock_async_redis.from_url.return_value = mock_async_redis_instance
        mock_idx += 1

    # Qdrant mock
    mock_qdrant = mocks[mock_idx]
    mock_qdrant_instance = Mock()
    mock_qdrant_instance.get_collections.return_value = Mock(collections=[])
    mock_qdrant.return_value = mock_qdrant_instance
    mock_idx += 1

    # Neo4j mock
    mock_neo4j = mocks[mock_idx]
    mock_neo4j_driver = Mock()
    mock_neo4j_driver.verify_connectivity.return_value = None
    mock_neo4j.return_value = mock_neo4j_driver

    yield

    # Stop all patches
    for p in patches:
        p.stop()


@pytest.fixture
def mock_celery_task():
    """Mock Celery task.delay() to prevent actual task queuing."""
    with patch("celery.Celery.send_task") as mock_send:
        mock_send.return_value = Mock(id="test-task-id")
        yield mock_send


# ============================================================================
# Testcontainers Integration (Optional)
# ============================================================================
# These fixtures require testcontainers to be installed:
#   pip install testcontainers[postgres,redis]
#
# They are useful for integration tests that need real database behavior.
# Use with @pytest.mark.requires_postgres or @pytest.mark.requires_redis

try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer
    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None
    RedisContainer = None


@pytest.fixture(scope="session")
def postgres_container():
    """
    Spin up PostgreSQL container for integration tests.

    This fixture provides a real PostgreSQL database for tests that need
    actual database behavior (transactions, constraints, etc.).

    Usage:
        @pytest.mark.requires_postgres
        def test_with_real_db(postgres_container):
            connection_url = postgres_container["url"]
            # Use connection_url for database operations

    Requires: pip install testcontainers[postgres]
    """
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed - run: pip install testcontainers[postgres]")

    with PostgresContainer("postgres:15-alpine") as postgres:
        yield {
            "url": postgres.get_connection_url(),
            "host": postgres.get_container_host_ip(),
            "port": postgres.get_exposed_port(5432),
            "user": postgres.username,
            "password": postgres.password,
            "database": postgres.dbname,
        }


@pytest.fixture(scope="session")
def redis_container():
    """
    Spin up Redis container for integration tests.

    This fixture provides a real Redis instance for tests that need
    actual caching behavior, pub/sub, or Redis data structures.

    Usage:
        @pytest.mark.requires_redis
        def test_with_real_redis(redis_container):
            redis_url = redis_container["url"]
            # Use redis_url for cache operations

    Requires: pip install testcontainers[redis]
    """
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed - run: pip install testcontainers[redis]")

    with RedisContainer("redis:7-alpine") as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        yield {
            "url": f"redis://{host}:{port}/0",
            "host": host,
            "port": port,
        }


@pytest.fixture(scope="function")
def postgres_session(postgres_container):
    """
    Create a SQLAlchemy session connected to the PostgreSQL container.

    This fixture creates tables and provides a session for database tests.
    Tables are dropped after each test for isolation.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(postgres_container["url"])

    # Import and create all tables
    # IMPORTANT: Import all models to ensure SQLAlchemy can resolve relationships
    try:
        from src.models import Base
        # Import ab_testing models to resolve User -> Experiment relationship
        from src.models import ab_testing  # noqa: F401
        Base.metadata.create_all(engine)
    except ImportError:
        pass  # Models may not be available

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # Clean up tables after test
        try:
            from src.models import Base
            from src.models import ab_testing  # noqa: F401
            Base.metadata.drop_all(engine)
        except ImportError:
            pass
        engine.dispose()


@pytest.fixture(scope="function")
def redis_client(redis_container):
    """
    Create a Redis client connected to the Redis container.

    The client is connected to a fresh Redis instance for each test session.
    """
    import redis

    client = redis.Redis.from_url(redis_container["url"])

    try:
        yield client
    finally:
        # Clean up all keys after test
        client.flushdb()
        client.close()


try:
    import pytest_asyncio

    @pytest_asyncio.fixture(scope="function")
    async def async_redis_client(redis_container):
        """
        Create an async Redis client connected to the Redis container.

        Use for testing async cache operations.
        """
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            redis_container["url"],
            encoding="utf-8",
            decode_responses=True,
        )

        try:
            yield client
        finally:
            await client.flushdb()
            await client.close()
except ImportError:
    # pytest_asyncio not installed
    pass
