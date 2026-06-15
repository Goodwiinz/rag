"""Multimodal (list-of-blocks) message content must not break classify/memory.

``HumanMessage.content`` is a ``list[dict]`` for multimodal turns. Before the
fix, ``_classify_core`` passed the raw list into the classifier (whose keyword
path calls ``.lower()/.split()``) and ``memory_save_node`` sliced/encoded it —
both raised ``AttributeError`` that was swallowed upstream, silently
defaulting the intent to "general" and dropping the saved memory. These tests
pin the ``_coerce_text`` coercion in both nodes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

MULTIMODAL_CONTENT = [
    {"type": "text", "text": "search for papers on attention"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxxx"}},
]


class TestClassifyCoercesMultimodal:
    async def test_classify_core_passes_flattened_text_to_classifier(self):
        from src.services.agent._nodes_classify import _classify_core
        from src.services.agent.classifier import ClassificationResult

        captured: dict = {}

        async def fake_classify(query, page_context, previous_turn="", prior_tool=None):
            captured["query"] = query
            captured["previous_turn"] = previous_turn
            return ClassificationResult(
                intent="research", confidence=0.9, reasoning="r", source="llm"
            )

        state = {
            "messages": [
                HumanMessage(content="earlier question"),
                AIMessage(content=MULTIMODAL_CONTENT),
                HumanMessage(content=MULTIMODAL_CONTENT),
            ],
        }

        with patch(
            "src.services.agent.classifier.classify_intent_with_fallback",
            side_effect=fake_classify,
        ):
            result = await _classify_core(state, {"configurable": {}})

        # The classifier received flattened strings, never raw block lists.
        assert isinstance(captured["query"], str)
        assert "search for papers on attention" in captured["query"]
        assert isinstance(captured["previous_turn"], str)
        # And the real intent survived instead of a swallowed-error default.
        assert result["intent"] == "research"


class TestMemorySaveCoercesMultimodal:
    async def test_memory_save_persists_coerced_text(self):
        from src.services.agent._nodes_memory import memory_save_node

        user = Mock()
        user.id = "user-mm-1"

        store = Mock()
        save_memory = AsyncMock()

        state = {
            "messages": [
                HumanMessage(content=MULTIMODAL_CONTENT),
                AIMessage(content=MULTIMODAL_CONTENT),
            ],
            "intent": "research",
            "tool_executions": [{"tool_name": "search_arxiv"}],
            "thread_id": "",
        }
        config = {"configurable": {"current_user": user, "thread_id": ""}}

        with patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=store),
        ), patch("src.services.agent.memory.save_memory", new=save_memory):
            result = await memory_save_node(state, config)

        # The save went through (was previously lost to a swallowed
        # AttributeError on list content) and stored the flattened text.
        assert result == {}
        save_memory.assert_awaited()
        saved_payload = save_memory.await_args_list[0].args[3]
        assert "search for papers on attention" in saved_payload["query"]
