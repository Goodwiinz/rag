"""Unit tests for the persistent agent memory store.

Tests cover:
- save_memory: inserts a row via SQLAlchemy + indexes in Qdrant
- search_memories: semantic search via Qdrant + PostgreSQL hydration
- update_access: bumps last_accessed_at and access_count
- extract_insights: LLM-based insight extraction from conversation
"""

import sys
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest

# Ensure qdrant_client and qdrant_client.models are importable during the
# inline `from qdrant_client.models import PointStruct` calls inside
# memory_store.py, even when the real package isn't installed.
_QDC_SAVED = {k: sys.modules[k] for k in ("qdrant_client", "qdrant_client.models") if k in sys.modules}

if "qdrant_client" not in sys.modules or not hasattr(sys.modules["qdrant_client"], "__path__"):
    _qdc_models = ModuleType("qdrant_client.models")

    class _AnyKwargs:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    _qdc_models.PointStruct = _AnyKwargs
    _qdc_models.Filter = _AnyKwargs
    _qdc_models.FieldCondition = _AnyKwargs
    _qdc_models.MatchValue = _AnyKwargs

    _qdc_pkg = ModuleType("qdrant_client")
    _qdc_pkg.__path__ = []  # make it look like a package
    _qdc_pkg.models = _qdc_models

    sys.modules["qdrant_client"] = _qdc_pkg
    sys.modules["qdrant_client.models"] = _qdc_models

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Create a mock async DB session following the project pattern."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = Mock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_qdrant_client():
    """Create a mock Qdrant client."""
    client = MagicMock()
    client.upsert = MagicMock()
    client.search = MagicMock(return_value=[])
    client.get_collections = MagicMock()
    return client


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = AsyncMock()
    service.generate_embedding = AsyncMock(
        return_value=SimpleNamespace(embedding=[0.1] * 384, dimension=384)
    )
    return service


# ---------------------------------------------------------------------------
# test_save_memory_inserts_row
# ---------------------------------------------------------------------------


class TestSaveMemory:
    """Tests for save_memory function."""

    async def test_save_memory_inserts_row(self, mock_db, mock_embedding_service, mock_qdrant_client):
        """save_memory should insert a row into the database and index in Qdrant."""
        from src.services.agent.memory_store import save_memory

        user_id = uuid4()
        org_id = uuid4()
        content = "The user prefers concise responses."

        with patch(
            "src.services.agent.memory_store._get_embedding_service",
            return_value=mock_embedding_service,
        ), patch(
            "src.services.agent.memory_store._get_qdrant_client",
            return_value=mock_qdrant_client,
        ):
            result = await save_memory(
                db=mock_db,
                user_id=user_id,
                org_id=org_id,
                content=content,
                memory_type="insight",
            )

        # Should have added a row to the session
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()

        # Should have generated an embedding
        mock_embedding_service.generate_embedding.assert_awaited_once()

        # Should have indexed in Qdrant
        mock_qdrant_client.upsert.assert_called_once()

        # Should return the memory id
        assert result is not None

    async def test_save_memory_with_metadata(self, mock_db, mock_embedding_service, mock_qdrant_client):
        """save_memory should accept and store optional metadata."""
        from src.services.agent.memory_store import save_memory

        user_id = uuid4()
        org_id = uuid4()
        metadata = {"source": "conversation", "thread_id": str(uuid4())}

        with patch(
            "src.services.agent.memory_store._get_embedding_service",
            return_value=mock_embedding_service,
        ), patch(
            "src.services.agent.memory_store._get_qdrant_client",
            return_value=mock_qdrant_client,
        ):
            result = await save_memory(
                db=mock_db,
                user_id=user_id,
                org_id=org_id,
                content="User works on ML research.",
                memory_type="preference",
                metadata=metadata,
            )

        assert result is not None
        mock_db.add.assert_called_once()

    async def test_save_memory_graceful_qdrant_failure(self, mock_db, mock_embedding_service):
        """save_memory should still persist to DB even if Qdrant is unavailable."""
        from src.services.agent.memory_store import save_memory

        user_id = uuid4()
        org_id = uuid4()

        with patch(
            "src.services.agent.memory_store._get_embedding_service",
            return_value=mock_embedding_service,
        ), patch(
            "src.services.agent.memory_store._get_qdrant_client",
            return_value=None,
        ):
            result = await save_memory(
                db=mock_db,
                user_id=user_id,
                org_id=org_id,
                content="Some memory content.",
            )

        # Should still persist to DB
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        assert result is not None


# ---------------------------------------------------------------------------
# test_search_memories_returns_results
# ---------------------------------------------------------------------------


class TestSearchMemories:
    """Tests for search_memories function."""

    async def test_search_memories_returns_results(self, mock_db, mock_embedding_service, mock_qdrant_client):
        """search_memories should return ranked memory results from Qdrant + DB hydration."""
        from src.services.agent.memory_store import search_memories

        user_id = uuid4()
        memory_id = uuid4()

        # Mock Qdrant search results
        qdrant_hit = MagicMock()
        qdrant_hit.id = str(memory_id)
        qdrant_hit.score = 0.92
        qdrant_hit.payload = {"user_id": str(user_id), "content": "User likes ML papers."}
        mock_qdrant_client.search.return_value = [qdrant_hit]

        # Mock DB hydration result
        mock_row = MagicMock()
        mock_row.id = memory_id
        mock_row.content = "User likes ML papers."
        mock_row.memory_type = "insight"
        mock_row.access_count = 3
        mock_row.created_at = datetime.now(timezone.utc)
        mock_row.last_accessed_at = datetime.now(timezone.utc)
        mock_row.metadata_ = {}

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_row])))
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.services.agent.memory_store._get_embedding_service",
            return_value=mock_embedding_service,
        ), patch(
            "src.services.agent.memory_store._get_qdrant_client",
            return_value=mock_qdrant_client,
        ):
            results = await search_memories(
                db=mock_db,
                user_id=user_id,
                query="machine learning papers",
                limit=5,
            )

        assert len(results) == 1
        assert results[0]["content"] == "User likes ML papers."
        assert results[0]["score"] == 0.92

    async def test_search_memories_empty_when_qdrant_unavailable(self, mock_db, mock_embedding_service):
        """search_memories should return empty list if Qdrant is unavailable."""
        from src.services.agent.memory_store import search_memories

        with patch(
            "src.services.agent.memory_store._get_embedding_service",
            return_value=mock_embedding_service,
        ), patch(
            "src.services.agent.memory_store._get_qdrant_client",
            return_value=None,
        ):
            results = await search_memories(
                db=mock_db,
                user_id=uuid4(),
                query="anything",
                limit=5,
            )

        assert results == []


# ---------------------------------------------------------------------------
# test_update_access_bumps_count
# ---------------------------------------------------------------------------


class TestUpdateAccess:
    """Tests for update_access function."""

    async def test_update_access_bumps_count(self, mock_db):
        """update_access should increment access_count and update last_accessed_at."""
        from src.services.agent.memory_store import update_access

        memory_id = uuid4()

        mock_db.execute = AsyncMock(return_value=MagicMock())

        await update_access(db=mock_db, memory_id=memory_id)

        # Should have executed an UPDATE statement
        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# test_extract_insights_returns_list
# ---------------------------------------------------------------------------


class TestExtractInsights:
    """Tests for extract_insights function."""

    async def test_extract_insights_returns_list(self):
        """extract_insights should return a list of insight strings."""
        from src.services.agent.memory_store import extract_insights

        messages = [
            {"role": "user", "content": "I'm researching quantum computing applications in drug discovery."},
            {"role": "assistant", "content": "That's a fascinating area. Let me find relevant papers on quantum computing for molecular simulation."},
            {"role": "user", "content": "Focus on papers from 2024. I prefer concise summaries."},
        ]

        mock_response = MagicMock()
        mock_response.content = (
            "1. User is researching quantum computing applications in drug discovery\n"
            "2. User prefers concise summaries\n"
            "3. User is interested in papers from 2024"
        )

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "src.services.agent.memory_store._build_insights_llm",
            return_value=mock_llm,
        ):
            insights = await extract_insights(messages=messages, config={})

        assert isinstance(insights, list)
        assert len(insights) >= 1
        # Each insight should be a non-empty string
        for insight in insights:
            assert isinstance(insight, str)
            assert len(insight.strip()) > 0

    async def test_extract_insights_empty_on_failure(self):
        """extract_insights should return empty list on LLM failure."""
        from src.services.agent.memory_store import extract_insights

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        with patch(
            "src.services.agent.memory_store._build_insights_llm",
            return_value=mock_llm,
        ):
            insights = await extract_insights(messages=[], config={})

        assert insights == []


# ---------------------------------------------------------------------------
# test_cleanup_stale_memories
# ---------------------------------------------------------------------------


class TestCleanupStaleMemories:
    """Tests for cleanup_stale_memories function."""

    async def test_cleanup_stale_memories(self, mock_db):
        """cleanup_stale_memories should soft-delete memories not accessed in N days."""
        from src.services.agent.memory_store import cleanup_stale_memories

        mock_db.execute = AsyncMock(return_value=MagicMock(rowcount=5))

        count = await cleanup_stale_memories(db=mock_db, days=90)

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()
        assert count == 5
