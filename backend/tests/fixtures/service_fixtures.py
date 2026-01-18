"""
Service-specific Test Fixtures.

Applies Temporal Python Testing patterns:
- Reusable fixtures for service testing
- Mocked external dependencies
- Test data generators
- Performance tracking utilities

Usage:
    Import these fixtures in conftest.py for automatic availability.
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json


# =============================================================================
# Chat Service Fixtures
# =============================================================================

@pytest.fixture
def chat_service_fixtures():
    """Factory for creating ChatService test data."""

    class ChatServiceFixtures:
        @staticmethod
        def create_workspace(
            owner_id: Optional[str] = None,
            name: str = "Test Workspace",
            is_public: bool = False
        ) -> Mock:
            """Create a mock workspace."""
            workspace = Mock()
            workspace.id = uuid4()
            workspace.name = name
            workspace.description = f"{name} description"
            workspace.owner_id = uuid4() if owner_id is None else owner_id
            workspace.organization_id = uuid4()
            workspace.is_public = is_public
            workspace.is_archived = False
            workspace.is_deleted = False
            workspace.created_at = datetime.utcnow()
            workspace.updated_at = datetime.utcnow()
            workspace.members = []
            workspace.conversations = []

            # Access control methods
            workspace.is_member = Mock(return_value=True)
            workspace.can_user_edit = Mock(return_value=True)
            workspace.can_user_admin = Mock(return_value=True)

            return workspace

        @staticmethod
        def create_conversation(
            workspace: Mock,
            title: str = "Test Conversation"
        ) -> Mock:
            """Create a mock conversation."""
            conversation = Mock()
            conversation.id = uuid4()
            conversation.workspace_id = workspace.id
            conversation.workspace = workspace
            conversation.title = title
            conversation.description = f"{title} description"
            conversation.created_by_id = workspace.owner_id
            conversation.is_archived = False
            conversation.is_pinned = False
            conversation.is_deleted = False
            conversation.last_activity_at = datetime.utcnow()
            conversation.threads = []
            conversation.update_activity = Mock()
            return conversation

        @staticmethod
        def create_thread(
            conversation: Mock,
            title: str = "Test Thread",
            message_count: int = 0
        ) -> Mock:
            """Create a mock thread."""
            thread = Mock()
            thread.id = uuid4()
            thread.conversation_id = conversation.id
            thread.conversation = conversation
            thread.title = title
            thread.status = Mock(value="active")
            thread.created_by_id = conversation.created_by_id
            thread.message_count = message_count
            thread.token_count = message_count * 50  # Estimate
            thread.is_deleted = False
            thread.last_message_at = datetime.utcnow()
            thread.messages = []
            thread.summary = None
            return thread

        @staticmethod
        def create_message(
            thread: Mock,
            role: str = "user",
            content: str = "Test message"
        ) -> Mock:
            """Create a mock message."""
            message = Mock()
            message.id = uuid4()
            message.thread_id = thread.id
            message.thread = thread
            message.role = Mock(value=role)
            message.content = content
            message.user_id = thread.created_by_id if role == "user" else None
            message.token_count = len(content.split()) * 2  # Rough estimate
            message.is_deleted = False
            message.created_at = datetime.utcnow()
            message.citations = []
            message.attachments = []

            def to_llm_format():
                return {"role": role, "content": content}

            message.to_llm_format = to_llm_format
            return message

        @staticmethod
        def create_chat_hierarchy(
            workspace_count: int = 1,
            conversations_per_workspace: int = 2,
            threads_per_conversation: int = 3,
            messages_per_thread: int = 5
        ) -> Dict[str, List[Mock]]:
            """Create a complete chat hierarchy for testing."""
            fixtures = ChatServiceFixtures()
            result = {
                "workspaces": [],
                "conversations": [],
                "threads": [],
                "messages": []
            }

            for _ in range(workspace_count):
                workspace = fixtures.create_workspace()
                result["workspaces"].append(workspace)

                for _ in range(conversations_per_workspace):
                    conversation = fixtures.create_conversation(workspace)
                    result["conversations"].append(conversation)

                    for _ in range(threads_per_conversation):
                        thread = fixtures.create_thread(conversation)
                        result["threads"].append(thread)

                        for i in range(messages_per_thread):
                            role = "user" if i % 2 == 0 else "assistant"
                            message = fixtures.create_message(thread, role)
                            result["messages"].append(message)
                            thread.messages.append(message)

                        thread.message_count = len(thread.messages)

            return result

    return ChatServiceFixtures()


# =============================================================================
# Search Service Fixtures
# =============================================================================

@pytest.fixture
def search_service_fixtures():
    """Factory for creating SearchService test data."""

    class SearchServiceFixtures:
        @staticmethod
        def create_search_result(
            source: str = "vector",
            score: float = 0.9,
            document_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """Create a mock search result."""
            return {
                "id": str(uuid4()),
                "document_id": document_id or str(uuid4()),
                "title": f"Test Document ({source})",
                "content": "This is test content for the search result.",
                "score": score,
                "source": source,
                "chunk_index": 0,
                "metadata": {
                    "document_type": "pdf",
                    "created_at": datetime.utcnow().isoformat()
                }
            }

        @staticmethod
        def create_search_results(
            vector_count: int = 5,
            graph_count: int = 3,
            keyword_count: int = 2
        ) -> Dict[str, List[Dict]]:
            """Create mock search results from multiple sources."""
            fixtures = SearchServiceFixtures()
            return {
                "vector": [
                    fixtures.create_search_result("vector", 0.95 - (i * 0.05))
                    for i in range(vector_count)
                ],
                "graph": [
                    fixtures.create_search_result("graph", 0.85 - (i * 0.05))
                    for i in range(graph_count)
                ],
                "keyword": [
                    fixtures.create_search_result("keyword", 0.75 - (i * 0.05))
                    for i in range(keyword_count)
                ]
            }

        @staticmethod
        def create_embedding(dimension: int = 768) -> List[float]:
            """Create a mock embedding vector."""
            import random
            return [random.random() for _ in range(dimension)]

        @staticmethod
        def create_search_request(
            query: str = "machine learning",
            search_type: str = "hybrid",
            limit: int = 10,
            filters: Optional[Dict] = None
        ) -> Dict[str, Any]:
            """Create a search request payload."""
            return {
                "query": query,
                "search_type": search_type,
                "limit": limit,
                "filters": filters or {},
                "include_metadata": True,
                "enable_reranking": True
            }

    return SearchServiceFixtures()


# =============================================================================
# Database Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_db_session_factory():
    """Factory for creating configured mock database sessions."""

    def create_session(
        query_results: Optional[List] = None,
        count_result: int = 0,
        raise_on_commit: bool = False
    ) -> MagicMock:
        """Create a mock database session with configurable behavior."""
        session = MagicMock()

        # Chainable query methods
        session.query.return_value = session
        session.filter.return_value = session
        session.options.return_value = session
        session.join.return_value = session
        session.order_by.return_value = session
        session.offset.return_value = session
        session.limit.return_value = session

        # Results
        session.first.return_value = query_results[0] if query_results else None
        session.all.return_value = query_results or []
        session.count.return_value = count_result
        session.scalar.return_value = count_result

        # Mutations
        session.add = MagicMock()
        session.delete = MagicMock(return_value=1)
        session.rollback = MagicMock()
        session.begin_nested = MagicMock(return_value=MagicMock())

        if raise_on_commit:
            session.commit = MagicMock(side_effect=Exception("Database error"))
        else:
            session.commit = MagicMock()

        session.refresh = MagicMock()

        return session

    return create_session


# =============================================================================
# External Service Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_external_services():
    """Factory for creating mocked external services."""

    class ExternalServiceMocks:
        @staticmethod
        def create_qdrant_client(
            search_results: Optional[List] = None,
            raise_on_search: bool = False
        ) -> MagicMock:
            """Create a mock Qdrant client."""
            client = MagicMock()

            if raise_on_search:
                client.search = MagicMock(
                    side_effect=ConnectionError("Qdrant unavailable")
                )
            else:
                # Create mock search results
                mock_results = []
                for i, result in enumerate(search_results or []):
                    mock_point = Mock()
                    mock_point.id = result.get("id", str(uuid4()))
                    mock_point.score = result.get("score", 0.9 - (i * 0.05))
                    mock_point.payload = result.get("payload", {
                        "document_id": str(uuid4()),
                        "content": "Test content"
                    })
                    mock_results.append(mock_point)

                client.search = MagicMock(return_value=mock_results)

            client.upsert = MagicMock()
            client.create_collection = MagicMock()
            client.get_collection = MagicMock()
            client.count = MagicMock(return_value=Mock(count=100))

            return client

        @staticmethod
        def create_neo4j_driver(
            query_results: Optional[List] = None,
            raise_on_query: bool = False
        ) -> MagicMock:
            """Create a mock Neo4j driver."""
            driver = MagicMock()
            session = MagicMock()

            if raise_on_query:
                session.run = MagicMock(side_effect=Exception("Neo4j error"))
            else:
                mock_records = []
                for result in (query_results or []):
                    record = Mock()
                    record.data = Mock(return_value=result)
                    mock_records.append(record)

                session.run = MagicMock(return_value=mock_records)

            session.close = MagicMock()
            driver.session = MagicMock(return_value=session)
            driver.verify_connectivity = MagicMock()
            driver.close = MagicMock()

            return driver

        @staticmethod
        def create_redis_client(
            cache_data: Optional[Dict[str, str]] = None,
            raise_on_get: bool = False
        ) -> AsyncMock:
            """Create a mock Redis client."""
            client = AsyncMock()
            cache = cache_data or {}

            if raise_on_get:
                client.get = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
            else:
                async def mock_get(key):
                    return cache.get(key)

                client.get = AsyncMock(side_effect=mock_get)

            client.set = AsyncMock(return_value=True)
            client.delete = AsyncMock(return_value=1)
            client.exists = AsyncMock(return_value=False)
            client.expire = AsyncMock(return_value=True)
            client.ping = AsyncMock(return_value=True)

            return client

        @staticmethod
        def create_celery_app() -> MagicMock:
            """Create a mock Celery app."""
            app = MagicMock()
            app.send_task = MagicMock(return_value=Mock(id="task-" + str(uuid4())[:8]))
            app.control = MagicMock()
            app.control.inspect = MagicMock()
            app.AsyncResult = MagicMock(return_value=Mock(state="PENDING", result=None))
            return app

    return ExternalServiceMocks()


# =============================================================================
# Performance Tracking Fixtures
# =============================================================================

@pytest.fixture
def performance_tracker():
    """Track performance metrics for tests."""
    import time

    class PerformanceTracker:
        def __init__(self):
            self.metrics: Dict[str, List[float]] = {}
            self.start_times: Dict[str, float] = {}

        def start_timer(self, name: str) -> None:
            """Start a named timer."""
            self.start_times[name] = time.time()

        def end_timer(self, name: str) -> float:
            """End a named timer and record the duration."""
            if name not in self.start_times:
                return 0.0

            duration = time.time() - self.start_times[name]
            if name not in self.metrics:
                self.metrics[name] = []
            self.metrics[name].append(duration)
            return duration

        def get_average(self, name: str) -> float:
            """Get average duration for a metric."""
            if name not in self.metrics or not self.metrics[name]:
                return 0.0
            return sum(self.metrics[name]) / len(self.metrics[name])

        def get_summary(self) -> Dict[str, Dict[str, float]]:
            """Get summary of all metrics."""
            summary = {}
            for name, times in self.metrics.items():
                if times:
                    summary[name] = {
                        "count": len(times),
                        "total": sum(times),
                        "average": sum(times) / len(times),
                        "min": min(times),
                        "max": max(times),
                    }
            return summary

        def assert_under_threshold(self, name: str, threshold_ms: float) -> None:
            """Assert average time is under threshold."""
            avg = self.get_average(name)
            avg_ms = avg * 1000
            assert avg_ms < threshold_ms, (
                f"{name} average {avg_ms:.2f}ms exceeds threshold {threshold_ms}ms"
            )

    tracker = PerformanceTracker()
    yield tracker

    # Print summary after test
    if tracker.metrics:
        print("\nPerformance Summary:")
        for name, stats in tracker.get_summary().items():
            print(f"  {name}: {stats['average']*1000:.2f}ms avg ({stats['count']} runs)")


# =============================================================================
# Test Data Generators
# =============================================================================

@pytest.fixture
def test_data_generator():
    """Generate test data for various scenarios."""

    class TestDataGenerator:
        @staticmethod
        def generate_documents(count: int = 10) -> List[Dict[str, Any]]:
            """Generate sample document data."""
            doc_types = ["pdf", "txt", "docx", "md"]
            return [
                {
                    "id": str(uuid4()),
                    "title": f"Document {i}",
                    "content": f"This is the content of document {i}. " * 10,
                    "document_type": doc_types[i % len(doc_types)],
                    "tags": [f"tag{j}" for j in range(i % 3 + 1)],
                    "created_at": (datetime.utcnow() - timedelta(days=i)).isoformat(),
                    "metadata": {
                        "author": f"Author {i % 5}",
                        "pages": i * 10 + 5
                    }
                }
                for i in range(count)
            ]

        @staticmethod
        def generate_search_queries(count: int = 10) -> List[str]:
            """Generate sample search queries."""
            topics = [
                "machine learning", "natural language processing",
                "computer vision", "deep learning", "neural networks",
                "data science", "artificial intelligence", "reinforcement learning",
                "transformer models", "language models"
            ]
            return topics[:count]

        @staticmethod
        def generate_users(count: int = 5) -> List[Dict[str, Any]]:
            """Generate sample user data."""
            roles = ["user", "admin", "viewer"]
            return [
                {
                    "id": str(uuid4()),
                    "email": f"user{i}@example.com",
                    "full_name": f"Test User {i}",
                    "role": roles[i % len(roles)],
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat()
                }
                for i in range(count)
            ]

    return TestDataGenerator()
