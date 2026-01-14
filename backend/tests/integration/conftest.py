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
def mock_external_services():
    """
    Auto-mock external services for all integration tests.

    This ensures tests don't try to connect to real Redis, Neo4j, Qdrant, etc.
    """
    with (
        patch("redis.Redis") as mock_redis,
        patch("redis.asyncio.Redis") as mock_async_redis,
        patch("qdrant_client.QdrantClient") as mock_qdrant,
        patch("neo4j.GraphDatabase.driver") as mock_neo4j,
    ):
        # Configure Redis mock
        mock_redis_instance = Mock()
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis.return_value = mock_redis_instance

        # Configure async Redis mock
        mock_async_redis_instance = AsyncMock()
        mock_async_redis_instance.ping.return_value = True
        mock_async_redis_instance.get.return_value = None
        mock_async_redis_instance.set.return_value = True
        mock_async_redis.return_value = mock_async_redis_instance

        # Configure Qdrant mock
        mock_qdrant_instance = Mock()
        mock_qdrant_instance.get_collections.return_value = Mock(collections=[])
        mock_qdrant.return_value = mock_qdrant_instance

        # Configure Neo4j mock
        mock_neo4j_driver = Mock()
        mock_neo4j_driver.verify_connectivity.return_value = None
        mock_neo4j.return_value = mock_neo4j_driver

        yield


@pytest.fixture
def mock_celery_task():
    """Mock Celery task.delay() to prevent actual task queuing."""
    with patch("celery.Celery.send_task") as mock_send:
        mock_send.return_value = Mock(id="test-task-id")
        yield mock_send
