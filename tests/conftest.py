"""
Comprehensive Pytest Configuration and Fixtures
Provides shared test utilities, fixtures, and configuration for document upload testing
"""

import pytest
import asyncio
import sys
import os
import tempfile
import uuid
import json
import random
from datetime import datetime
from typing import Dict, Any, Generator, AsyncGenerator, List
from unittest.mock import Mock, AsyncMock
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Add src directory to Python path
src_dir = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(src_dir))

# Set test environment variables
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"

# Import after path setup
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

# Test factory imports
from tests.factories.document_factory import DocumentFactory, DocumentConfig


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before running tests"""
    print("\n🧪 Setting up T2 Validation Test Environment")
    print("=" * 60)

    # Print test configuration
    print(f"📋 Test Configuration:")
    print(f"   - Environment: {os.getenv('ENVIRONMENT', 'testing')}")
    print(f"   - Debug: {os.getenv('DEBUG', 'false')}")
    print(f"   - Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
    print(f"   - Python Path: {sys.path[:3]}...")  # Show first 3 entries

    yield

    print("\n🏁 T2 Validation Tests Completed")
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


# Mock fixtures for external services
@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for vector search tests"""
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.upsert.return_value = Mock()
    mock_client.search.return_value = []
    mock_client.create_collection.return_value = Mock()
    mock_client.get_collection.return_value = Mock()

    return mock_client


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for knowledge graph tests"""
    from unittest.mock import Mock

    mock_driver = Mock()
    mock_session = Mock()
    mock_session.run.return_value = Mock()
    mock_session.close.return_value = None
    mock_driver.session.return_value = mock_session
    mock_driver.close.return_value = None

    return mock_driver


@pytest.fixture
def mock_embeddings():
    """Mock embedding service"""
    from unittest.mock import Mock
    import numpy as np

    mock_service = Mock()
    # Generate consistent mock embeddings
    def mock_embed_query(text):
        # Create deterministic embeddings based on text hash
        np.random.seed(hash(text) % 2**32)
        return np.random.rand(384).tolist()

    mock_service.embed_query.side_effect = mock_embed_query
    mock_service.embed_documents.side_effect = lambda texts: [mock_embed_query(text) for text in texts]

    return mock_service


# Performance tracking fixture
@pytest.fixture
def performance_tracker():
    """Track performance metrics for tests"""
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

        def get_average(self, name):
            if name in self.metrics and self.metrics[name]:
                return sum(self.metrics[name]) / len(self.metrics[name])
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
        print(f"\n⏱️ Performance Summary:")
        for name, stats in tracker.get_summary().items():
            print(f"   {name}: {stats['average']:.3f}s avg ({stats['count']} runs)")


# Test data generators
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
def sample_documents_data():
    """Sample document data for testing"""
    return [
        {
            "title": "Introduction to Machine Learning",
            "content": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
            "document_type": "pdf",
            "tags": ["machine learning", "AI", "algorithms"],
            "metadata": {"pages": 50, "author": "Test Author"}
        },
        {
            "title": "Natural Language Processing Fundamentals",
            "content": "NLP is a branch of artificial intelligence that helps computers understand, interpret and manipulate human language.",
            "document_type": "pdf",
            "tags": ["NLP", "linguistics", "text processing"],
            "metadata": {"pages": 75, "author": "Test Author 2"}
        },
        {
            "title": "Computer Vision and Image Recognition",
            "content": "Computer vision is an AI field that trains computers to interpret and understand the visual world from digital images or videos.",
            "document_type": "video",
            "tags": ["computer vision", "image processing", "deep learning"],
            "metadata": {"duration": 3600, "author": "Test Author 3"}
        }
    ]


# Test markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "t2_001: Tests for T2-001 Vector Database Setup"
    )
    config.addinivalue_line(
        "markers", "t2_002: Tests for T2-002 Knowledge Graph Construction"
    )
    config.addinivalue_line(
        "markers", "t2_003: Tests for T2-003 Full-Text Search Implementation"
    )
    config.addinivalue_line(
        "markers", "t2_004: Tests for T2-004 Hybrid Search Engine"
    )
    config.addinivalue_line(
        "markers", "t2_005: Tests for T2-005 Search API Implementation"
    )
    config.addinivalue_line(
        "markers", "t2_006: Tests for T2-006 Multi-Agent Search Orchestration"
    )
    config.addinivalue_line(
        "markers", "t2_007: Tests for T2-007 Search Quality Evaluation"
    )


# Test collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add markers based on test class names
        if "TestT2_001" in item.cls.__name__:
            item.add_marker(pytest.mark.t2_001)
        elif "TestT2_002" in item.cls.__name__:
            item.add_marker(pytest.mark.t2_002)
        elif "TestT2_003" in item.cls.__name__:
            item.add_marker(pytest.mark.t2_003)
        elif "TestT2_004" in item.cls.__name__:
            item.add_marker(pytest.mark.t2_004)
        elif "TestT2_005" in item.cls.__name__:
            item.add_marker(pytest.mark.t2_005)
        elif "TestT2_006" in item.cls.__name__:
            item.add_marker(pytest.mark.t2_006)
        elif "TestT2_007" in item.cls.__name__:
            item.add_marker(pytest.mark.t2_007)
        elif "TestT2_Integration" in item.cls.__name__:
            item.add_marker(pytest.mark.integration)


# Test reporting
def pytest_html_report_title(report):
    """Custom HTML report title"""
    report.title = "T2 Validation Test Report"


def pytest_runtest_logreport(report):
    """Custom test logging"""
    if report.when == "call" and report.failed:
        print(f"\n❌ Test failed: {report.nodeid}")
        if hasattr(report, "longrepr"):
            print(f"   Error: {report.longrepr}")
    elif report.when == "call" and report.passed:
        print(f"✅ Test passed: {report.nodeid}")