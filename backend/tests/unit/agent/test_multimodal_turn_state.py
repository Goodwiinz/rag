"""Multimodal-content handling in the hot-path preprocessing/LLM/memory nodes.

Covers M4 and M5 from the 2026-08-16 agent audit round 1 (work item
``multimodal-turn-state``).

M1 from the same work item — "tool_executions never reset per turn" in
``preprocessing_node`` — was investigated and does NOT reproduce against this
checkout, so no fix or test for it is included here. Both graph entry points
(``agent_execution_service._run_agent_graph`` and ``streaming.py``'s SSE
handler) build a brand-new ``initial_state`` dict on every turn that already
sets ``"tool_executions": []`` explicitly. LangGraph applies that as an
ordinary last-value channel write — same as every other plain (non-Annotated)
``AgentState`` field — before ``preprocessing_node`` (the graph's sole entry
node, wired via ``set_entry_point``) ever runs, which overrides whatever the
checkpoint carried from the previous turn. Verified directly against the real
``AgentState`` + ``preprocessing_node`` (subtasks mocked) with an in-memory
checkpointer across two turns, via both ``ainvoke`` and ``astream_events``:
a non-empty ``tool_executions`` written during turn 1 does not survive into
turn 2's read of ``state.get("tool_executions")``. ``preprocessing_node``'s
per-turn reset dict omitting the key is therefore inert on both live call
paths, not a checkpoint-carryover bug.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

pytestmark = pytest.mark.unit


class _RecordingLLM:
    """Stand-in bound chat model — records every ``ainvoke`` call's messages."""

    def __init__(self) -> None:
        self.invoked_with: list[Any] = []

    def bind_tools(self, *_args: Any, **_kwargs: Any) -> "_RecordingLLM":
        return self

    async def ainvoke(self, messages: Any, *_args: Any, **_kwargs: Any) -> AIMessage:
        self.invoked_with.append(messages)
        return AIMessage(content="ok from model")


def _llm_state(messages: list) -> dict:
    """Minimal ``AgentState`` for a general-intent, no-retrieval turn."""
    return {
        "messages": messages,
        "intent": "general",
        "retrieved_contexts": [],
        "page_context": {},
        "user_memories": [],
        "project_memories": [],
        "project_skill_catalog": [],
        "plan": [],
        "model": "",
        "tool_loop_count": 0,
        "error_count": 0,
    }


class TestM4MultimodalGreetingFastPath:
    """An image-only turn must always reach the model, never a canned reply.

    Pre-fix, ``last_user_msg`` was filtered on ``isinstance(m.content, str)``,
    so it walked past a list-content (image) HumanMessage to the PREVIOUS
    turn's text. If that stale text was a bare greeting, the greeting
    fast-path fired and answered it instead of ever sending the image to the
    model.
    """

    async def test_image_only_turn_after_a_greeting_reaches_the_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.services.agent import graph as graph_mod
        from src.services.agent._nodes_llm import llm_node

        llm = _RecordingLLM()
        monkeypatch.setattr(graph_mod, "_build_llm", lambda **_k: llm)

        image_message = HumanMessage(
            content=[
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,AAAA"},
                },
            ]
        )
        messages = [
            HumanMessage(content="hi"),
            AIMessage(content="Hi — how can I help with your research today?"),
            image_message,
        ]

        result = await llm_node(_llm_state(messages), {})

        assert llm.invoked_with, (
            "the image-only turn never reached the model — last_user_msg "
            "resolved to the stale prior-turn 'hi' and the greeting "
            "fast-path answered that instead of the image"
        )
        sent_messages = llm.invoked_with[0]
        assert image_message in sent_messages, "the image content was dropped"
        assert result["messages"][0].content == "ok from model"

    async def test_bare_greeting_still_takes_the_fast_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Control: a genuine bare 'hi' must still skip the LLM round-trip."""
        from src.services.agent import graph as graph_mod
        from src.services.agent._nodes_llm import llm_node

        llm = _RecordingLLM()
        monkeypatch.setattr(graph_mod, "_build_llm", lambda **_k: llm)

        result = await llm_node(_llm_state([HumanMessage(content="hi")]), {})

        assert not llm.invoked_with, "a bare greeting should never reach the model"
        assert "Hi" in result["messages"][0].content


class TestM5MultimodalMemoryRecall:
    """A multimodal turn must not lose long-term memory recall.

    Pre-fix, ``last_user_msg`` was assigned raw ``msg.content`` (no
    coercion), and the ``is_conversational`` predicate call sat OUTSIDE the
    node's ``try`` block. For list content, ``is_conversational`` calls
    ``content.strip()`` and raises ``AttributeError``, which escapes
    ``memory_retrieval_node`` entirely and is silently swallowed two frames
    up by ``preprocessing_node``'s ``gather(return_exceptions=True)``.
    """

    async def test_list_content_message_does_not_raise_and_searches_coerced_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.services.agent._nodes_memory import memory_retrieval_node

        search_mock = AsyncMock(return_value=[])
        monkeypatch.setattr(
            "src.services.agent.memory.get_memory_store",
            AsyncMock(return_value=object()),
        )
        monkeypatch.setattr("src.services.agent.memory.search_memories", search_mock)

        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": "what does this chart show"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA"},
                    },
                ]
            ),
        ]
        state = {"messages": messages}
        config = {"configurable": {"user_id": "11111111-1111-1111-1111-111111111111"}}

        result = await memory_retrieval_node(state, config)  # must not raise

        assert result == {"user_memories": []}
        search_mock.assert_awaited_once()
        # search_memories(store, user_id, query, limit=...) — query is the
        # third positional argument.
        called_query = search_mock.await_args.args[2]
        assert called_query == "what does this chart show"

    async def test_image_only_message_coerces_to_empty_and_skips_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No text block at all -> coerces to "" -> conversational fast-path,
        cleanly, with no search call and no raise."""
        from src.services.agent._nodes_memory import memory_retrieval_node

        search_mock = AsyncMock(return_value=[])
        monkeypatch.setattr("src.services.agent.memory.search_memories", search_mock)

        messages = [
            HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA"},
                    },
                ]
            ),
        ]
        state = {"messages": messages}
        config = {"configurable": {"user_id": "11111111-1111-1111-1111-111111111111"}}

        result = await memory_retrieval_node(state, config)  # must not raise

        assert result == {"user_memories": []}
        search_mock.assert_not_awaited()
