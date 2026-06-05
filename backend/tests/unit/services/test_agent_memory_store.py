"""Unit tests for the persistent agent memory store.

Tests cover:
- update_access: bumps last_accessed_at and access_count
- cleanup_stale_memories: soft-deletes memories not accessed in N days
- extract_insights: LLM-based insight extraction from conversation
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest.fixture(autouse=True)
def _clear_qdrant_cache():
    """Reset the module-level Qdrant client cache and fix stubbed qdrant_client.

    test_sandbox.py replaces qdrant_client in sys.modules with a bare ModuleType
    stub at collection time.  save_memory() does a deferred
    ``from qdrant_client.models import PointStruct`` which fails against the
    stub.  Re-import the real package here so that deferred import succeeds.
    """
    import importlib, sys
    from src.services.agent import memory_store

    memory_store._QDRANT_CLIENT = None

    _saved = {}
    for key in list(sys.modules):
        if key == "qdrant_client" or key.startswith("qdrant_client."):
            mod = sys.modules[key]
            if not getattr(mod, "__file__", None):
                _saved[key] = sys.modules.pop(key)

    if _saved:
        importlib.import_module("qdrant_client")

    yield

    memory_store._QDRANT_CLIENT = None


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

    async def test_extract_insights_empty_messages_skips_llm(self):
        """Empty messages must return [] WITHOUT building or invoking an LLM."""
        from src.services.agent.memory_store import extract_insights

        with patch(
            "src.services.agent.memory_store._build_insights_llm",
        ) as mock_build:
            insights = await extract_insights(messages=[], config={})

        assert insights == []
        assert mock_build.call_count == 0  # no LLM constructed, no ainvoke

    async def test_extract_insights_empty_on_llm_failure(self):
        """A real LLM failure (non-empty input) still returns []."""
        from src.services.agent.memory_store import extract_insights

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        with patch(
            "src.services.agent.memory_store._build_insights_llm",
            return_value=mock_llm,
        ):
            insights = await extract_insights(
                messages=[{"role": "user", "content": "hello"}], config={}
            )

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
