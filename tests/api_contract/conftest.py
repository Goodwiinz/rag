"""
Comprehensive API Contract Test Suite for Multimodal Enterprise RAG System
Provides end-to-end API validation with contract testing, integration testing, and performance validation
"""

import pytest
import asyncio
import sys
import os
import tempfile
import uuid
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Generator, AsyncGenerator, List
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from fastapi.testclient import TestClient
from httpx import AsyncClient
import aiofiles
import websockets
from io import BytesIO

# Add backend directory to Python path
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
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["QDRANT_URL"] = "http://localhost:6333"

# Import backend modules
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Project imports
from src.core.database import Base, get_db
from src.main import app
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority
from src.core.security import create_access_token, create_refresh_token, verify_token

# Test configuration
API_BASE_URL = "http://localhost:8000"
API_V1_PREFIX = "/api/v1"

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "query_response_time_p95": 3.0,  # seconds
    "file_upload_processing": 300.0,  # 5 minutes
    "websocket_latency": 0.1,  # 100ms
    "concurrent_users": 50,
    "api_rate_limit": 100  # requests per minute
}

# File size limits for testing
FILE_SIZE_LIMITS = {
    "max_file_size_mb": 100,
    "max_text_file_mb": 50,
    "max_image_file_mb": 20,
    "max_audio_file_mb": 100,
    "max_video_file_mb": 500
}


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config():
    """Test configuration fixture"""
    return {
        "api_base_url": API_BASE_URL,
        "api_v1_prefix": API_V1_PREFIX,
        "performance_thresholds": PERFORMANCE_THRESHOLDS,
        "file_size_limits": FILE_SIZE_LIMITS
    }


@pytest.fixture(scope="function")
def test_database():
    """Create a fresh database for each test function"""
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

    yield session

    session.close()


@pytest.fixture(scope="function")
def test_client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture(scope="function")
async def async_client():
    """Create an async test client"""
    async with AsyncClient(app=app, base_url=API_BASE_URL) as client:
        yield client


@pytest.fixture
def mock_external_services():
    """Mock all external services (Qdrant, Neo4j, Redis)"""
    with patch('src.services.vector_search_service.qdrant_client') as mock_qdrant, \
         patch('src.services.hybrid_search_service.neo4j_driver') as mock_neo4j, \
         patch('src.core.database.redis_client') as mock_redis:

        # Configure Qdrant mock
        mock_qdrant.upsert.return_value = None
        mock_qdrant.search.return_value = []
        mock_qdrant.create_collection.return_value = None
        mock_qdrant.get_collection.return_value = Mock(vectors_count=0)

        # Configure Neo4j mock
        mock_neo4j.session.return_value.__enter__.return_value = Mock()
        mock_neo4j.session.return_value.__exit__.return_value = None

        # Configure Redis mock
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.delete.return_value = True

        yield {
            "qdrant": mock_qdrant,
            "neo4j": mock_neo4j,
            "redis": mock_redis
        }


@pytest.fixture
def test_user_data():
    """Sample user data for testing"""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
        "organization_name": "Test Organization"
    }


@pytest.fixture
def test_admin_user_data():
    """Sample admin user data for testing"""
    return {
        "email": "admin@example.com",
        "password": "AdminPassword123!",
        "first_name": "Admin",
        "last_name": "User",
        "organization_name": "Admin Organization",
        "role": "admin"
    }


@pytest.fixture
def create_test_user(test_database):
    """Create a test user in the database"""
    def _create_user(user_data: Dict[str, Any], is_admin: bool = False) -> User:
        # Create organization first
        org = Organization(
            id=str(uuid.uuid4()),
            name=user_data.get("organization_name", "Test Organization"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        test_database.add(org)

        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=user_data["email"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            organization_id=org.id,
            role=UserRole.ADMIN if is_admin else UserRole.USER,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        # Set password (would be hashed in real implementation)
        user.hashed_password = f"hashed_{user_data['password']}"

        test_database.add(user)
        test_database.commit()
        test_database.refresh(user)

        return user

    return _create_user


@pytest.fixture
def auth_headers(create_test_user):
    """Create authentication headers for API requests"""
    def _create_headers(user_data: Dict[str, Any], is_admin: bool = False) -> Dict[str, str]:
        user = create_test_user(user_data, is_admin)

        # Create tokens
        access_token = create_access_token(
            data={"sub": user.email, "user_id": str(user.id), "org_id": str(user.organization_id)}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.email, "user_id": str(user.id)}
        )

        return {
            "Authorization": f"Bearer {access_token}",
            "X-Refresh-Token": refresh_token,
            "X-User-ID": str(user.id),
            "X-Organization-ID": str(user.organization_id)
        }

    return _create_headers


@pytest.fixture
def sample_files():
    """Create sample files for testing upload functionality"""
    files = {}

    # Text file
    files["text"] = (
        "sample.txt",
        BytesIO(b"This is a sample text file for testing document upload functionality."),
        "text/plain"
    )

    # PDF file (simulated)
    files["pdf"] = (
        "sample.pdf",
        BytesIO(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"),
        "application/pdf"
    )

    # Image file
    files["image"] = (
        "sample.jpg",
        BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01"),  # JPEG header
        "image/jpeg"
    )

    # Audio file
    files["audio"] = (
        "sample.mp3",
        BytesIO(b"ID3\x04\x00\x00\x00\x00\x00\x00"),  # MP3 header
        "audio/mpeg"
    )

    # Video file
    files["video"] = (
        "sample.mp4",
        BytesIO(b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00"),  # MP4 header
        "video/mp4"
    )

    return files


@pytest.fixture
def performance_tracker():
    """Track performance metrics during tests"""
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
            return None

        def get_stats(self, name: str) -> Dict[str, float]:
            if name in self.metrics and self.metrics[name]:
                times = self.metrics[name]
                return {
                    "count": len(times),
                    "total": sum(times),
                    "average": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times)
                }
            return {}

        def check_threshold(self, name: str, threshold: float) -> bool:
            stats = self.get_stats(name)
            return stats.get("p95", stats.get("average", 0)) <= threshold

    tracker = PerformanceTracker()
    yield tracker

    # Print performance summary
    if tracker.metrics:
        print("\n⏱️ Performance Test Results:")
        for name, stats in tracker.metrics.items():
            avg = sum(stats) / len(stats)
            p95 = sorted(stats)[int(len(stats) * 0.95)] if len(stats) > 20 else max(stats)
            print(f"   {name}: {avg:.3f}s avg, {p95:.3f}s p95 ({len(stats)} samples)")


@pytest.fixture
def websocket_client():
    """Create a WebSocket client for testing real-time features"""
    class WebSocketClient:
        def __init__(self):
            self.connection = None
            self.messages = []

        async def connect(self, endpoint: str, token: str = None):
            """Connect to WebSocket endpoint"""
            uri = f"ws://localhost:8000{endpoint}"
            headers = {"Authorization": f"Bearer {token}"} if token else {}

            try:
                self.connection = await websockets.connect(uri, extra_headers=headers)
                return True
            except Exception as e:
                print(f"WebSocket connection failed: {e}")
                return False

        async def send_message(self, message: Dict[str, Any]):
            """Send message to WebSocket"""
            if self.connection:
                await self.connection.send(json.dumps(message))

        async def receive_message(self) -> Dict[str, Any]:
            """Receive message from WebSocket"""
            if self.connection:
                message = await self.connection.recv()
                self.messages.append(json.loads(message))
                return self.messages[-1]
            return None

        async def close(self):
            """Close WebSocket connection"""
            if self.connection:
                await self.connection.close()
                self.connection = None

    return WebSocketClient()


# Contract testing fixtures
@pytest.fixture
def api_contract_validator():
    """Validate API contracts against OpenAPI specification"""
    class APIContractValidator:
        def __init__(self):
            self.contract_violations = []

        def validate_response(self, response, expected_schema: Dict[str, Any], endpoint: str):
            """Validate response against expected schema"""
            try:
                response_data = response.json() if hasattr(response, 'json') else response

                # Basic structure validation
                if not isinstance(response_data, dict):
                    self.contract_violations.append({
                        "endpoint": endpoint,
                        "violation": "Response is not a JSON object",
                        "actual": str(response_data)[:100]
                    })
                    return False

                # Schema validation would be implemented here with Pydantic or jsonschema
                # For now, just check that response has expected structure
                return True

            except Exception as e:
                self.contract_violations.append({
                    "endpoint": endpoint,
                    "violation": f"Schema validation failed: {str(e)}",
                    "actual": str(response)[:100] if hasattr(response, 'text') else str(response)[:100]
                })
                return False

        def get_violations(self) -> List[Dict[str, Any]]:
            """Return all contract violations"""
            return self.contract_violations

        def clear_violations(self):
            """Clear all contract violations"""
            self.contract_violations = []

    return APIContractValidator()


# Test markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    markers = [
        ("contract", "API contract tests"),
        ("integration", "Integration tests"),
        ("performance", "Performance tests"),
        ("security", "Security tests"),
        ("documents", "Document management API tests"),
        ("search", "Search API tests"),
        ("auth", "Authentication API tests"),
        ("knowledge_graph", "Knowledge graph API tests"),
        ("websocket", "WebSocket tests"),
        ("load", "Load tests")
    ]

    for marker, description in markers:
        config.addinivalue_line("markers", f"{marker}: {description}")


# Performance testing collection hook
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers and sort tests"""
    # Sort tests by type: contract -> integration -> performance -> load
    priority_order = {
        "contract": 1,
        "integration": 2,
        "auth": 3,
        "documents": 4,
        "search": 5,
        "knowledge_graph": 6,
        "websocket": 7,
        "security": 8,
        "performance": 9,
        "load": 10
    }

    def get_priority(item):
        for marker in item.iter_markers():
            if marker.name in priority_order:
                return priority_order[marker.name]
        return 999

    items.sort(key=get_priority)


# Test reporting
def pytest_html_report_title(report):
    """Custom HTML report title"""
    report.title = "Multimodal Enterprise RAG System - API Contract Test Report"


def pytest_runtest_logreport(report):
    """Custom test logging with performance metrics"""
    if report.when == "call":
        if report.failed:
            print(f"\n❌ {report.nodeid}")
            if hasattr(report, 'longrepr'):
                print(f"   Error: {report.longrepr}")
        elif report.passed:
            print(f"✅ {report.nodeid}")

            # Log performance if available
            if hasattr(report, 'user_properties'):
                for name, value in report.user_properties:
                    if name.startswith('perf_'):
                        print(f"   ⏱️ {name}: {value:.3f}s")