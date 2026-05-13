"""memory_save_node runs extract_insights every N turns when enabled."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent._nodes_memory import memory_save_node


def _state_with_n_humans(n: int) -> dict:
    msgs: list = []
    for i in range(n):
        msgs.append(HumanMessage(content=f"user msg {i}"))
        msgs.append(AIMessage(content=f"reply {i}"))
    return {
        "messages": msgs,
        "intent": "research",
        "tool_executions": [{"tool_name": "search_arxiv"}],
    }


def _config() -> dict:
    user = MagicMock()
    user.id = "user-1"
    return {"configurable": {"current_user": user, "thread_id": "t-1"}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_insights_extracted_on_5th_turn():
    save_mock = AsyncMock(return_value=True)
    insights_mock = AsyncMock(return_value=["user prefers IEEE citations"])
    store = MagicMock()

    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock), \
       patch(
        "src.services.agent.memory_store.extract_insights",
        new=insights_mock,
    ):
        await memory_save_node(_state_with_n_humans(5), _config())

    # Two saves: one for the raw turn, one per insight emitted.
    assert save_mock.await_count == 2
    insights_mock.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_insights_skipped_on_non_multiple_turn():
    save_mock = AsyncMock(return_value=True)
    insights_mock = AsyncMock(return_value=["nope"])
    store = MagicMock()

    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock), \
       patch(
        "src.services.agent.memory_store.extract_insights",
        new=insights_mock,
    ):
        await memory_save_node(_state_with_n_humans(3), _config())

    assert save_mock.await_count == 1
    insights_mock.assert_not_awaited()
