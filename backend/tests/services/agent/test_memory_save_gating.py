"""Memory save-gate + provenance regression tests.

Trace 019e066b-2a35 (rag-agent-dev, 2026-05-08) showed memory_save_node
persisting a greeting ("hi") under key 49f68a5c8493. Trace 019e040b later
recalled that same useless memory for a technical query. Save must skip
greetings and conversational turns that produced no tool calls.

Provenance: every saved value must carry thread_id, turn_index, created_at
so downstream telemetry + TTL cleanup can reason about lifecycle.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent.graph import memory_save_node


def _config(thread_id: str = "thread-x") -> dict:
    user = MagicMock()
    user.id = "user-1"
    return {
        "configurable": {
            "current_user": user,
            "thread_id": thread_id,
        }
    }


def _state(
    *,
    intent: str = "general",
    tool_executions: list | None = None,
    messages: list | None = None,
) -> dict:
    return {
        "messages": messages
        or [
            HumanMessage(content="hi"),
            AIMessage(content="Hello!"),
        ],
        "intent": intent,
        "tool_executions": tool_executions or [],
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_skipped_for_greeting_general_intent():
    """Greeting with no tools → no save."""
    save_mock = AsyncMock(return_value=True)
    store = MagicMock()
    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock):
        out = await memory_save_node(_state(), _config())

    save_mock.assert_not_called()
    assert out == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_fires_when_tool_executions_present():
    """General intent + tool ran → save fires (information worth keeping)."""
    save_mock = AsyncMock(return_value=True)
    store = MagicMock()
    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock):
        await memory_save_node(
            _state(
                tool_executions=[{"tool_name": "search_arxiv", "status": "completed"}],
                messages=[
                    HumanMessage(content="find papers on transformers"),
                    AIMessage(content="Here are 5 papers..."),
                ],
            ),
            _config(),
        )

    save_mock.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_fires_for_research_intent_without_tool():
    """Specialised intent alone → save fires (intent commitment is signal)."""
    save_mock = AsyncMock(return_value=True)
    store = MagicMock()
    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock):
        await memory_save_node(
            _state(
                intent="research",
                messages=[
                    HumanMessage(content="search the kb for survival analysis"),
                    AIMessage(content="..."),
                ],
            ),
            _config(),
        )

    save_mock.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_saved_value_includes_provenance_fields():
    """Saved value must carry thread_id, turn_index, created_at."""
    save_mock = AsyncMock(return_value=True)
    store = MagicMock()
    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock):
        await memory_save_node(
            _state(
                intent="research",
                messages=[
                    HumanMessage(content="find papers on RLHF"),
                    AIMessage(content="..."),
                    HumanMessage(content="ingest 2401.12345"),
                    AIMessage(content="..."),
                ],
                tool_executions=[{"tool_name": "ingest_arxiv_papers"}],
            ),
            _config(thread_id="thread-abc"),
        )

    save_mock.assert_called_once()
    call_kwargs_or_args = save_mock.call_args
    # save_memory signature: (store, user_id, key, value)
    value = call_kwargs_or_args.args[3]
    assert value["thread_id"] == "thread-abc"
    assert value["turn_index"] == 2  # two HumanMessage entries
    assert "created_at" in value and "T" in value["created_at"]
    assert value["intent"] == "research"
    assert "ingest_arxiv_papers" in value["tools_used"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_saved_value_strips_pii_from_query():
    """save_memory writes a redacted query string, not the raw input."""
    save_mock = AsyncMock(return_value=True)
    store = MagicMock()
    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock):
        await memory_save_node(
            _state(
                intent="research",
                messages=[
                    HumanMessage(
                        content=(
                            "email me at jane@example.com about project "
                            "5ed25258-5ad2-4b06-9678-4a4abe5ecac1"
                        )
                    ),
                    AIMessage(content="..."),
                ],
                tool_executions=[{"tool_name": "search_arxiv"}],
            ),
            _config(),
        )
    save_mock.assert_called_once()
    value = save_mock.call_args.args[3]
    assert "jane@example.com" not in value["query"]
    assert "5ed25258" not in value["query"]
    assert "<email>" in value["query"]
    assert "<uuid>" in value["query"]
