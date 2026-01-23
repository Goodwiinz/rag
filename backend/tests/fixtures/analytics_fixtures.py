"""
Pytest configuration and fixtures for T3 analytics services testing
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
import os

# When pytest runs with pythonpath = ., /app is in the path
# We can import directly from src
from src.main import app
from src.core.database import get_db, Base
from src.core.config import settings
from src.models.user import User
from src.models.organization import Organization


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db_session(test_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(test_db_session) -> TestClient:
    """Create a test client with test database."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_organization(test_db_session):
    """Create a mock organization for testing."""
    org = Organization(
        id="test-org-id",
        name="Test Organization",
        description="Test organization for analytics",
        settings={"max_users": 100, "features": ["analytics"]},
        created_by="system",
        is_deleted=False
    )
    test_db_session.add(org)
    test_db_session.commit()
    test_db_session.refresh(org)
    return org


@pytest.fixture
def mock_user(test_db_session, mock_organization):
    """Create a mock user for testing."""
    user = User(
        id="test-user-id",
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        organization_id=mock_organization.id,
        is_active=True,
        is_verified=True,
        settings={"theme": "light", "notifications": True},
        created_by="system",
        is_deleted=False
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture
def mock_current_user(mock_user):
    """Mock current user dependency."""
    return mock_user


@pytest.fixture
def mock_quality_metrics_data():
    """Mock quality metrics data for testing."""
    return {
        "search_accuracy": 0.94,
        "response_time_ms": 245,
        "relevance_score": 0.89,
        "user_satisfaction": 4.6,
        "error_rate": 0.015,
        "success_rate": 0.985,
        "total_searches": 1234,
        "unique_queries": 567,
        "click_through_rate": 0.45,
        "zero_results_rate": 0.08
    }


@pytest.fixture
def mock_user_behavior_data():
    """Mock user behavior data for testing."""
    return {
        "session_id": "test-session-123",
        "user_id": "test-user-id",
        "query": "test search query",
        "search_type": "hybrid",
        "results_count": 15,
        "response_time": 245.5,
        "clicked_results": [1, 3, 5],
        "filters_applied": {"date_range": "last_30_days"},
        "page_number": 1,
        "sort_order": "relevance",
        "user_agent": "Mozilla/5.0...",
        "ip_address": "192.168.1.100"
    }


@pytest.fixture
def mock_performance_data():
    """Mock performance metrics data for testing."""
    return {
        "cpu_usage": 45.2,
        "memory_usage": 67.8,
        "disk_usage": 34.1,
        "network_io": 1024.5,
        "response_time_p50": 200,
        "response_time_p95": 500,
        "response_time_p99": 800,
        "requests_per_second": 45.6,
        "error_rate": 0.015,
        "uptime_percentage": 99.9,
        "active_connections": 156
    }


@pytest.fixture
def mock_recommendations_data():
    """Mock quality recommendations data for testing."""
    return [
        {
            "id": "rec-001",
            "category": "content",
            "priority": "high",
            "title": "Improve Document Quality",
            "description": "Update outdated content and enhance metadata",
            "impact_assessment": "High impact on search accuracy",
            "effort_required": "Medium",
            "actionable_steps": ["Audit documents", "Update metadata", "Implement scoring"],
            "expected_outcome": "15-20% improvement in relevance",
            "estimated_improvement": 18,
            "status": "pending",
            "due_date": "2025-11-01T00:00:00Z",
            "assigned_to": "content-team",
            "created_at": "2025-10-09T21:41:00Z"
        },
        {
            "id": "rec-002",
            "category": "search_algorithm",
            "priority": "critical",
            "title": "Optimize Vector Search Parameters",
            "description": "Fine-tune embedding similarity thresholds",
            "impact_assessment": "Critical impact on result quality",
            "effort_required": "Low",
            "actionable_steps": ["Analyze thresholds", "A/B test", "Deploy changes"],
            "expected_outcome": "10-15% improvement in relevance",
            "estimated_improvement": 12,
            "status": "in_progress",
            "due_date": "2025-10-15T00:00:00Z",
            "assigned_to": "search-team",
            "created_at": "2025-10-09T20:30:00Z"
        }
    ]


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    client = AsyncMock()
    client.get.return_value = None
    client.set.return_value = True
    client.delete.return_value = 1
    client.exists.return_value = False
    client.expire.return_value = True
    return client


@pytest.fixture
def mock_psutil():
    """Mock psutil module for testing."""
    psutil_mock = Mock()

    # Mock CPU usage
    psutil_mock.cpu_percent.return_value = 45.2

    # Mock memory usage
    memory_mock = Mock()
    memory_mock.percent = 67.8
    memory_mock.used = 8 * 1024 * 1024 * 1024  # 8GB
    memory_mock.total = 16 * 1024 * 1024 * 1024  # 16GB
    psutil_mock.virtual_memory.return_value = memory_mock

    # Mock disk usage
    disk_mock = Mock()
    disk_mock.percent = 34.1
    disk_mock.used = 100 * 1024 * 1024 * 1024  # 100GB
    disk_mock.total = 300 * 1024 * 1024 * 1024  # 300GB
    psutil_mock.disk_usage.return_value = disk_mock

    # Mock network I/O
    network_mock = Mock()
    network_mock.bytes_sent = 1024 * 1024 * 100  # 100MB
    network_mock.bytes_recv = 1024 * 1024 * 500  # 500MB
    psutil_mock.net_io_counters.return_value = network_mock

    return psutil_mock


@pytest.fixture
def sample_time_series_data():
    """Sample time series data for testing."""
    import datetime
    base_time = datetime.datetime.utcnow()

    return [
        {
            "timestamp": (base_time - datetime.timedelta(hours=i)).isoformat(),
            "search_accuracy": 0.94 + (i * 0.01),
            "response_time": 245 + (i * 5),
            "user_satisfaction": 4.6 + (i * 0.1),
            "error_rate": 0.015 + (i * 0.002)
        }
        for i in range(24)
    ]


@pytest.fixture
def mock_alert_data():
    """Mock alert data for testing."""
    return [
        {
            "id": "alert-001",
            "type": "performance",
            "severity": "warning",
            "title": "High Response Time Detected",
            "message": "Average response time exceeded threshold",
            "threshold": 500,
            "current_value": 650,
            "timestamp": "2025-10-09T21:41:00Z",
            "resolved": False,
            "acknowledged_by": None
        },
        {
            "id": "alert-002",
            "type": "quality",
            "severity": "critical",
            "title": "Search Quality Degradation",
            "message": "Search accuracy dropped below threshold",
            "threshold": 0.85,
            "current_value": 0.78,
            "timestamp": "2025-10-09T20:30:00Z",
            "resolved": True,
            "acknowledged_by": "admin-user"
        }
    ]


# Override settings for testing
@pytest.fixture(autouse=True)
def override_settings():
    """Override settings for testing environment."""
    original_settings = {}

    # Store original settings
    for key in ['DATABASE_URL', 'REDIS_URL', 'ENVIRONMENT', 'DEBUG']:
        if hasattr(settings, key):
            original_settings[key] = getattr(settings, key)

    # Override with test settings
    settings.DATABASE_URL = TEST_DATABASE_URL
    settings.ENVIRONMENT = "testing"
    settings.DEBUG = True
    settings.REDIS_URL = "redis://localhost:6379/1"  # Test DB

    yield

    # Restore original settings
    for key, value in original_settings.items():
        setattr(settings, key, value)


# Async test fixtures
@pytest.fixture
async def async_test_client():
    """Create an async test client."""
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# Mock service fixtures
@pytest.fixture
def mock_quality_metrics_service():
    """Mock quality metrics service."""
    service = AsyncMock()
    service.collect_metrics.return_value = {"accuracy": 0.94}
    service.get_metrics_summary.return_value = {"total_metrics": 10}
    service.create_alert.return_value = {"id": "alert-123", "status": "created"}
    return service


@pytest.fixture
def mock_user_behavior_service():
    """Mock user behavior service."""
    service = AsyncMock()
    service.track_search_event.return_value = {"id": "event-123", "status": "tracked"}
    service.get_behavior_patterns.return_value = {"patterns": ["power_user", "researcher"]}
    service.get_session_analysis.return_value = {"duration": 300, "actions": 15}
    return service


@pytest.fixture
def mock_performance_dashboard_service():
    """Mock performance dashboard service."""
    service = AsyncMock()
    service.get_system_health.return_value = {"status": "healthy", "cpu": 45.2}
    service.get_dashboard_overview.return_value = {"metrics": 25, "alerts": 2}
    service.get_widget_data.return_value = {"type": "chart", "data": []}
    return service


@pytest.fixture
def mock_quality_recommendations_service():
    """Mock quality recommendations service."""
    service = AsyncMock()
    service.generate_recommendations.return_value = {"recommendations": [], "total": 0}
    service.analyze_quality_insights.return_value = {"insights": [], "gaps": []}
    service.track_recommendation_progress.return_value = {"status": "updated"}
    return service