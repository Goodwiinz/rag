"""
Base configuration and utilities for API contract tests
"""

import pytest
import asyncio
import sys
import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Generator, AsyncGenerator, List, Optional
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Add src directory to Python path
src_dir = Path(__file__).parent.parent.parent / "backend" / "src"
sys.path.insert(0, str(src_dir))

# Set test environment variables
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"

# Import after path setup
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import jwt

# Project imports
from src.core.database import Base, get_db
from src.core.config import settings
from src.main import app
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.evaluation import (
    EvaluationJob, EvaluationMetric, EvaluationReport,
    EvaluationType, EvaluationStatus, MetricType
)

# Import evaluation data generators
from tests.contract.evaluation.fixtures.data_generators import (
    EvaluationDataGenerator, JobDataGenerator, MetricDataGenerator
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def test_client(db_session):
    """Create a test client with database dependency override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Clean up dependency override
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_client(db_session):
    """Create an async test client with database dependency override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as client:
        yield client

    # Clean up dependency override
    app.dependency_overrides.clear()


@pytest.fixture
def test_organization(db_session):
    """Create a test organization"""
    org = Organization(
        name="Test Organization",
        description="Test organization for contract tests",
        plan="enterprise",
        settings={"max_users": 100, "max_storage_gb": 1000}
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_user(db_session, test_organization):
    """Create a test user"""
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role=UserRole.USER,
        organization_id=test_organization.id,
        is_active=True
    )
    # Set password hash (in real app this would be properly hashed)
    user.password_hash = "hashed_password"
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin_user(db_session, test_organization):
    """Create a test admin user"""
    admin = User(
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        organization_id=test_organization.id,
        is_active=True
    )
    admin.password_hash = "hashed_admin_password"
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def user_token(test_user):
    """Generate JWT token for test user"""
    payload = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "role": test_user.role.value,
        "organization_id": str(test_user.organization_id),
        "exp": datetime.utcnow().timestamp() + 3600,  # 1 hour
        "iat": datetime.utcnow().timestamp()
    }

    # Use same secret as in config
    secret = settings.SECRET_KEY if hasattr(settings, 'SECRET_KEY') else "test-secret-key"
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


@pytest.fixture
def admin_token(test_admin_user):
    """Generate JWT token for admin user"""
    payload = {
        "sub": str(test_admin_user.id),
        "email": test_admin_user.email,
        "role": test_admin_user.role.value,
        "organization_id": str(test_admin_user.organization_id),
        "exp": datetime.utcnow().timestamp() + 3600,
        "iat": datetime.utcnow().timestamp()
    }

    secret = settings.SECRET_KEY if hasattr(settings, 'SECRET_KEY') else "test-secret-key"
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


@pytest.fixture
def auth_headers(user_token):
    """Authorization headers for API requests"""
    return {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def admin_auth_headers(admin_token):
    """Admin authorization headers for API requests"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def evaluation_data_generator():
    """Evaluation data generator fixture"""
    return EvaluationDataGenerator()


@pytest.fixture
def job_data_generator():
    """Job data generator fixture"""
    return JobDataGenerator()


@pytest.fixture
def metric_data_generator():
    """Metric data generator fixture"""
    return MetricDataGenerator()


# Mock external services
@pytest.fixture
def mock_rag_evaluation_service():
    """Mock RAG evaluation service"""
    with patch('src.api.evaluation.rag_evaluation_service') as mock_service:
        # Mock methods
        mock_service.create_evaluation_job = AsyncMock()
        mock_service.get_evaluation_summary = Mock(return_value={})
        mock_service.get_evaluation_metrics = Mock(return_value=[])

        # Configure return values
        mock_job = Mock()
        mock_job.id = uuid.uuid4()
        mock_job.name = "Test Evaluation Job"
        mock_job.status = EvaluationStatus.PENDING.value
        mock_job.created_at = datetime.utcnow()
        mock_service.create_evaluation_job.return_value = mock_job

        yield mock_service


@pytest.fixture
def mock_background_tasks():
    """Mock background tasks"""
    with patch('fastapi.BackgroundTasks') as mock_tasks:
        yield mock_tasks


@pytest.fixture
def mock_celery_tasks():
    """Mock Celery tasks"""
    with patch('src.api.evaluation.run_rag_triad_evaluation') as mock_task:
        mock_task.delay = Mock(return_value=Mock(id="test-task-id"))
        yield mock_task


# Contract validation utilities
@pytest.fixture
def contract_validator():
    """Contract validation utilities"""
    class ContractValidator:
        @staticmethod
        def validate_response_structure(response_data: Dict[str, Any], required_fields: List[str]) -> bool:
            """Validate that response contains all required fields"""
            for field in required_fields:
                if field not in response_data:
                    return False
            return True

        @staticmethod
        def validate_data_types(response_data: Dict[str, Any], field_types: Dict[str, type]) -> List[str]:
            """Validate data types in response"""
            errors = []
            for field, expected_type in field_types.items():
                if field in response_data:
                    value = response_data[field]
                    if not isinstance(value, expected_type):
                        errors.append(f"Field '{field}' expected {expected_type.__name__}, got {type(value).__name__}")
            return errors

        @staticmethod
        def validate_enum_values(response_data: Dict[str, Any], enum_fields: Dict[str, List[Any]]) -> List[str]:
            """Validate enum values in response"""
            errors = []
            for field, allowed_values in enum_fields.items():
                if field in response_data:
                    value = response_data[field]
                    if value not in allowed_values:
                        errors.append(f"Field '{field}' has invalid value '{value}'. Allowed: {allowed_values}")
            return errors

        @staticmethod
        def validate_error_response(response_data: Dict[str, Any]) -> bool:
            """Validate error response structure"""
            required_fields = ["error"]
            if not ContractValidator.validate_response_structure(response_data, required_fields):
                return False

            error_data = response_data["error"]
            if not isinstance(error_data, dict):
                return False

            error_fields = ["message", "status_code", "type"]
            return ContractValidator.validate_response_structure(error_data, error_fields)

    return ContractValidator()


# Performance tracking
@pytest.fixture
def performance_tracker():
    """Track performance metrics for contract tests"""
    import time

    class PerformanceTracker:
        def __init__(self):
            self.metrics = {}
            self.start_times = {}

        def start_timer(self, name):
            self.start_times[name] = time.time()

        def end_timer(self, name):
            if name in self.start_times:
                duration = time.time() - self.start_times[name]
                if name not in self.metrics:
                    self.metrics[name] = []
                self.metrics[name].append(duration)
                return duration
            return None

        def get_summary(self):
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
        print(f"\n⏱️ Contract Test Performance Summary:")
        for name, stats in tracker.get_summary().items():
            print(f"   {name}: {stats['average']:.3f}s avg ({stats['count']} runs)")


# Test markers for contract tests
def pytest_configure(config):
    """Configure custom pytest markers for contract tests"""
    config.addinivalue_line(
        "markers", "contract: API contract tests"
    )
    config.addinivalue_line(
        "markers", "evaluation_contract: Evaluation API contract tests"
    )
    config.addinivalue_line(
        "markers", "auth_contract: Authentication API contract tests"
    )
    config.addinivalue_line(
        "markers", "load_test: Load and performance tests"
    )
    config.addinivalue_line(
        "markers", "cors_test: CORS configuration tests"
    )
    config.addinivalue_line(
        "markers", "error_contract: Error response contract tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add markers based on test class names and file paths
        if "contract" in str(item.fspath):
            item.add_marker(pytest.mark.contract)

        if "evaluation_contract" in str(item.fspath) or "EvaluationContract" in item.cls.__name__:
            item.add_marker(pytest.mark.evaluation_contract)

        if "auth_contract" in str(item.fspath) or "AuthContract" in item.cls.__name__:
            item.add_marker(pytest.mark.auth_contract)

        if "load_test" in str(item.fspath) or "LoadTest" in item.cls.__name__:
            item.add_marker(pytest.mark.load_test)

        if "cors" in str(item.fspath) or "CORS" in item.cls.__name__:
            item.add_marker(pytest.mark.cors_test)

        if "error" in str(item.fspath) or "Error" in item.cls.__name__:
            item.add_marker(pytest.mark.error_contract)