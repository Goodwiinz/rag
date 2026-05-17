"""forget_memory deletes the closest semantic match from the user's store."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent.memory import delete_memory_by_query


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_memory_returns_deleted_count():
    store = MagicMock()
    matched_item = MagicMock(key="abc123", score=0.92)
    matched_item.value = {"query": "find papers on transformers"}
    store.asearch = AsyncMock(return_value=[matched_item])
    store.adelete = AsyncMock(return_value=None)

    out = await delete_memory_by_query(
        store, user_id="user-1", query="papers on transformers", limit=3
    )

    assert out["deleted"] == 1
    assert out["matches"][0]["key"] == "abc123"
    store.adelete.assert_awaited_once_with(("user", "user-1"), "abc123")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_memory_skips_low_score_match():
    """A match with score < 0.6 is reported but NOT deleted (avoid accidents)."""
    store = MagicMock()
    weak = MagicMock(key="xyz", score=0.4)
    weak.value = {"query": "something else"}
    store.asearch = AsyncMock(return_value=[weak])
    store.adelete = AsyncMock(return_value=None)

    out = await delete_memory_by_query(
        store, user_id="user-1", query="papers", limit=3
    )

    assert out["deleted"] == 0
    assert out["matches"][0]["score"] == 0.4
    store.adelete.assert_not_awaited()


@pytest.mark.unit
def test_forget_memory_is_destructive_tool():
    from src.services.agent._nodes_tools import DESTRUCTIVE_TOOLS

    assert "forget_memory" in DESTRUCTIVE_TOOLS


@pytest.mark.unit
def test_forget_memory_tool_registered():
    from src.services.agent.tools import ALL_TOOLS

    assert any(t.name == "forget_memory" for t in ALL_TOOLS), (
        "forget_memory must be registered in ALL_TOOLS so subgraphs can bind it"
    )
