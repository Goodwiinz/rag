"""
Integration Test Configuration
Sets up test environment, Docker containers, and mock services for comprehensive testing
"""

import os
import pytest
import asyncio
import uuid
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import asyncpg
import aioredis
import httpx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from testcontainers.core.waiting_utils import wait_for_logs
import docker
from fastapi.testclient import TestClient
import json
import logging
from tests.constants import TEST_JWT_SECRET

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test Configuration
TEST_CONFIG = {
    "database": {
        "host": "localhost",
        "port": 5432,
        "database": "test_analytics",
        "username": "test_user",
        "password": "test_password",
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 1
    },
    "api": {
        "base_url": "http://localhost:8000",
        "timeout": 30.0
    },
    "websocket": {
        "base_url": "ws://localhost:8000",
        "timeout": 10.0
    }
}

# Test Fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def postgres_container() -> AsyncGenerator[Dict[str, Any], None]:
    """Start PostgreSQL container for testing"""
    logger.info("Starting PostgreSQL test container...")

    postgres = PostgresContainer(
        image="postgres:15",
        username="test_user",
        password="test_password",
        database="test_analytics",
        port=5432
    )

    try:
        postgres.start()

        # Wait for database to be ready
        wait_for_logs(postgres, "database system is ready to accept connections", timeout=60)

        # Get connection details
        connection_params = postgres.get_connection_url()

        # Parse connection URL to get host and port
        import urllib.parse
        parsed = urllib.parse.urlparse(connection_params)

        TEST_CONFIG["database"].update({
            "host": postgres.get_container_host_ip(),
            "port": postgres.get_exposed_port(5432),
            "database": "test_analytics",
            "username": "test_user",
            "password": "test_password"
        })

        logger.info(f"PostgreSQL container started on {TEST_CONFIG['database']['host']}:{TEST_CONFIG['database']['port']}")

        yield TEST_CONFIG["database"]

    finally:
        postgres.stop()
        logger.info("PostgreSQL container stopped")

@pytest.fixture(scope="session")
async def redis_container() -> AsyncGenerator[Dict[str, Any], None]:
    """Start Redis container for testing"""
    logger.info("Starting Redis test container...")

    redis = RedisContainer(
        image="redis:7-alpine",
        port=6379
    )

    try:
        redis.start()

        TEST_CONFIG["redis"].update({
            "host": redis.get_container_host_ip(),
            "port": redis.get_exposed_port(6379),
            "db": 1
        })

        logger.info(f"Redis container started on {TEST_CONFIG['redis']['host']}:{TEST_CONFIG['redis']['port']}")

        yield TEST_CONFIG["redis"]

    finally:
        redis.stop()
        logger.info("Redis container stopped")

@pytest.fixture(scope="session")
async def test_database_engine(postgres_container):
    """Create async SQLAlchemy engine for test database"""
    from src.core.database import get_async_session
    from src.core.config import settings

    # Override settings for testing
    settings.DATABASE_URL = (
        f"postgresql+asyncpg://{TEST_CONFIG['database']['username']}:"
        f"{TEST_CONFIG['database']['password']}@{TEST_CONFIG['database']['host']}:"
        f"{TEST_CONFIG['database']['port']}/{TEST_CONFIG['database']['database']}"
    )

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "command_timeout": 60,
            "server_settings": {
                "application_name": "test_analytics"
            }
        }
    )

    try:
        # Run database migrations
        await setup_test_database(engine)
        yield engine
    finally:
        await engine.dispose()

@pytest.fixture(scope="session")
async def redis_client(redis_container):
    """Create Redis client for testing"""
    redis_url = (
        f"redis://{TEST_CONFIG['redis']['host']}:"
        f"{TEST_CONFIG['redis']['port']}/{TEST_CONFIG['redis']['db']}"
    )

    client = aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True
    )

    try:
        await client.ping()
        yield client
    finally:
        await client.close()

@pytest.fixture(scope="function")
async def test_db_session(test_database_engine):
    """Create database session for each test function"""
    from src.models.base import Base

    async_session = sessionmaker(
        test_database_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Begin transaction
        transaction = await session.begin()

        try:
            yield session
        finally:
            # Rollback transaction to ensure clean state
            await transaction.rollback()
            await session.close()

@pytest.fixture(scope="session")
async def api_client():
    """Create HTTP client for API testing"""
    async with AsyncClient(
        base_url=TEST_CONFIG["api"]["base_url"],
        timeout=TEST_CONFIG["api"]["timeout"]
    ) as client:
        yield client

@pytest.fixture(scope="session")
def mock_fastapi_app():
    """Create FastAPI test application"""
    from src.ui.api_server import app

    # Override dependencies for testing
    from src.core.auth import get_current_user
    from src.core.database import get_async_session

    async def mock_get_current_user():
        return {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "organization_id": uuid.uuid4(),
            "is_active": True,
            "roles": ["admin", "analyst"]
        }

    app.dependency_overrides[get_current_user] = mock_get_current_user

    yield TestClient(app)

    # Clean up overrides
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
async def websocket_client():
    """Create WebSocket client for testing"""
    import websockets

    # This will be used for individual WebSocket connections in tests
    class WebSocketTestClient:
        def __init__(self):
            self.base_url = TEST_CONFIG["websocket"]["base_url"]
            self.timeout = TEST_CONFIG["websocket"]["timeout"]

        async def connect(self, path: str, **kwargs):
            uri = f"{self.base_url}{path}"
            return await websockets.connect(uri, timeout=self.timeout, **kwargs)

    yield WebSocketTestClient()

# Test Data Fixtures
@pytest.fixture
def sample_organization():
    """Create sample organization for testing"""
    return {
        "id": uuid.uuid4(),
        "name": "Test Organization",
        "domain": "test.example.com",
        "settings": {
            "timezone": "UTC",
            "data_retention_days": 365
        }
    }

@pytest.fixture
def sample_user(sample_organization):
    """Create sample user for testing"""
    return {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "name": "Test User",
        "organization_id": sample_organization["id"],
        "roles": ["admin", "analyst"],
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }

@pytest.fixture
def sample_dashboard(sample_organization, sample_user):
    """Create sample dashboard for testing"""
    return {
        "id": uuid.uuid4(),
        "organization_id": sample_organization["id"],
        "user_id": sample_user["id"],
        "config_name": "Test Dashboard",
        "config_type": "user",
        "is_default": False,
        "is_active": True,
        "layout": {
            "rows": 3,
            "columns": 4
        },
        "widgets": [
            {
                "id": uuid.uuid4(),
                "type": "metric_card",
                "title": "Total Entities",
                "position": {"row": 0, "col": 0, "width": 1, "height": 1},
                "config": {
                    "metric_id": "total_entities",
                    "refresh_interval": 30
                }
            }
        ],
        "filters": {
            "date_range": "7d",
            "entity_types": ["person", "organization"]
        },
        "auto_refresh_enabled": True,
        "auto_refresh_interval_seconds": 300,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

@pytest.fixture
def sample_report(sample_organization, sample_user):
    """Create sample report for testing"""
    return {
        "id": uuid.uuid4(),
        "organization_id": sample_organization["id"],
        "created_by_user_id": sample_user["id"],
        "report_name": "Knowledge Graph Analysis Report",
        "report_description": "Comprehensive analysis of knowledge graph metrics",
        "report_category": "graph_analysis",
        "report_definition": {
            "metrics": ["entity_count", "relationship_count", "graph_density"],
            "filters": {
                "time_range": "30d",
                "entity_types": ["person", "organization", "document"]
            },
            "visualizations": [
                {
                    "type": "line_chart",
                    "data_source": "time_series_metrics",
                    "config": {
                        "x_axis": "timestamp",
                        "y_axis": "value",
                        "group_by": "metric_type"
                    }
                }
            ]
        },
        "data_sources": ["entity_analytics", "relationship_analytics"],
        "visualizations": [],
        "schedule_config": {
            "enabled": False,
            "frequency": "weekly",
            "day_of_week": "monday",
            "time": "09:00"
        },
        "auto_generate": False,
        "output_formats": ["pdf", "json"],
        "delivery_methods": ["email", "download"],
        "recipients": ["test@example.com"],
        "is_public": False,
        "share_with_roles": ["admin"],
        "share_with_users": [],
        "version": 1,
        "is_template": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

@pytest.fixture
def sample_alert(sample_organization):
    """Create sample alert for testing"""
    return {
        "id": uuid.uuid4(),
        "organization_id": sample_organization["id"],
        "alert_name": "High Entity Growth Alert",
        "alert_type": "metric_threshold",
        "alert_condition": {
            "metric": "new_entities_per_hour",
            "operator": "greater_than",
            "threshold": 100,
            "time_window": "1h"
        },
        "threshold_values": {
            "warning": 50,
            "critical": 100
        },
        "status": "active",
        "severity": "warning",
        "notification_channels": ["email", "dashboard"],
        "notification_cooldown_minutes": 60,
        "alert_details": {
            "description": "Alert when entity creation rate exceeds threshold",
            "recommended_actions": ["Check data sources", "Verify ingestion pipeline"]
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

@pytest.fixture
def sample_metrics_data():
    """Create sample metrics data for testing"""
    now = datetime.now(timezone.utc)
    return [
        {
            "metric_id": "total_entities",
            "metric_name": "Total Entities",
            "channel": "entity_metrics",
            "current_value": 1500,
            "previous_value": 1450,
            "change_percentage": 3.45,
            "timestamp": now,
            "time_window": "1h",
            "aggregation_type": "sum",
            "sample_count": 100,
            "data_quality_score": 0.95,
            "dimensions": {
                "entity_types": {"person": 800, "organization": 500, "document": 200}
            },
            "tags": ["knowledge_graph", "entities"],
            "is_anomaly": False,
            "alert_threshold_min": 1000,
            "alert_threshold_max": 2000,
            "source": "entity_analytics_service",
            "confidence": 0.98
        },
        {
            "metric_id": "relationship_count",
            "metric_name": "Total Relationships",
            "channel": "relationship_metrics",
            "current_value": 3200,
            "previous_value": 3100,
            "change_percentage": 3.23,
            "timestamp": now - timedelta(minutes=5),
            "time_window": "1h",
            "aggregation_type": "sum",
            "sample_count": 150,
            "data_quality_score": 0.92,
            "dimensions": {
                "relationship_types": {"works_for": 500, "located_in": 800, "related_to": 1900}
            },
            "tags": ["knowledge_graph", "relationships"],
            "is_anomaly": False,
            "alert_threshold_min": 2500,
            "alert_threshold_max": 4000,
            "source": "relationship_analytics_service",
            "confidence": 0.96
        }
    ]

# Utility Functions
async def setup_test_database(engine):
    """Set up test database with required tables and sample data"""
    from src.models.base import Base

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Load test data
    await load_test_fixtures(engine)

async def load_test_fixtures(engine):
    """Load test data into database"""
    from src.models.analytics.realtime_models import (
        WebSocketConnection, RealtimeSubscription, LiveMetric, EventStream
    )

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Add sample fixtures if needed
        await session.commit()

@asynccontextmanager
async def create_test_user_session(organization_id: uuid.UUID, roles: list = None):
    """Create a test user session for authentication testing"""
    if roles is None:
        roles = ["analyst"]

    test_user = {
        "id": uuid.uuid4(),
        "organization_id": organization_id,
        "email": "test@example.com",
        "name": "Test User",
        "roles": roles,
        "is_active": True
    }

    # Create JWT token for test user
    import jwt
    token = jwt.encode(
        {
            "sub": str(test_user["id"]),
            "email": test_user["email"],
            "organization_id": str(test_user["organization_id"]),
            "roles": test_user["roles"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        },
        TEST_JWT_SECRET,
        algorithm="HS256"
    )

    yield test_user, token

def create_auth_headers(token: str) -> Dict[str, str]:
    """Create authentication headers for API requests"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# Pytest Configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "api_contract: mark test as API contract test"
    )
    config.addinivalue_line(
        "markers", "websocket: mark test as WebSocket test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "auth: mark test as authentication test"
    )
    config.addinivalue_line(
        "markers", "multitenant: mark test as multi-tenant test"
    )

# Custom assertions for testing
class APIAssertions:
    """Custom assertion helpers for API testing"""

    @staticmethod
    def assert_valid_response(response, expected_status: int = 200):
        """Assert valid API response"""
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"

        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "success" in data or "data" in data or "error" in data, f"Invalid response structure: {data}"
            return data
        return response

    @staticmethod
    def assert_openapi_schema_compliance(response_data: dict, expected_schema: dict):
        """Assert response complies with OpenAPI schema"""
        # Basic schema compliance checks
        required_fields = expected_schema.get("required", [])
        for field in required_fields:
            assert field in response_data, f"Missing required field: {field}"

        # Type checking
        properties = expected_schema.get("properties", {})
        for field, schema in properties.items():
            if field in response_data:
                expected_type = schema.get("type")
                if expected_type == "string" and schema.get("format") == "uuid":
                    try:
                        uuid.UUID(response_data[field])
                    except ValueError:
                        raise AssertionError(f"Field {field} is not a valid UUID")
                elif expected_type == "integer":
                    assert isinstance(response_data[field], int), f"Field {field} is not an integer"
                elif expected_type == "number":
                    assert isinstance(response_data[field], (int, float)), f"Field {field} is not a number"
                elif expected_type == "boolean":
                    assert isinstance(response_data[field], bool), f"Field {field} is not a boolean"
                elif expected_type == "array":
                    assert isinstance(response_data[field], list), f"Field {field} is not an array"
                elif expected_type == "object":
                    assert isinstance(response_data[field], dict), f"Field {field} is not an object"

# Test utilities
async def wait_for_condition(condition_func, timeout: float = 10.0, interval: float = 0.1):
    """Wait for a condition to become true"""
    start_time = asyncio.get_event_loop().time()

    while (asyncio.get_event_loop().time() - start_time) < timeout:
        if await condition_func():
            return True
        await asyncio.sleep(interval)

    raise TimeoutError(f"Condition not met within {timeout} seconds")

def generate_test_file(size_mb: int = 1) -> bytes:
    """Generate test file data"""
    return b"x" * (size_mb * 1024 * 1024)