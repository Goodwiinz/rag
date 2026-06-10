"""CancelledError must propagate out of reflection and compaction.

Both wrap their LLM calls in broad ``except Exception`` fallbacks (reflection
returns a silent "passed", compaction leaves the message intact). A user
abort raises ``asyncio.CancelledError``, which those fallbacks must NOT
swallow — the house pattern (see classifier) re-raises it explicitly. These
tests pin the re-raise so a future refactor merging the except clauses
cannot silently absorb aborts.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestReflectionCancellation:
    async def test_cancelled_error_propagates_out_of_reflection_node(self):
        from src.services.agent.reflection import make_reflection_gate

        reflection_node, _route = make_reflection_gate(intent_filter={"research"})

        state = {
            "intent": "research",
            "reflection_count": 0,
            "messages": [
                HumanMessage(content="find papers on attention"),
                AIMessage(content="Here are the papers I found..." * 10),
            ],
            "tool_executions": [{"tool_name": "search_arxiv"}],
        }

        with patch(
            "src.services.agent.reflection._detect_ingest_success_lie",
            return_value=None,
        ), patch(
            "src.services.agent.reflection._should_skip_reflection",
            return_value=(False, ""),
        ), patch(
            "src.services.agent.reflection.reflect_on_response",
            new=AsyncMock(side_effect=asyncio.CancelledError()),
        ):
            with pytest.raises(asyncio.CancelledError):
                await reflection_node(state, {"configurable": {}})


class TestCompactionCancellation:
    async def test_cancelled_error_propagates_out_of_compact_messages(self):
        from src.services.agent import compactor

        llm = AsyncMock()
        llm.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())

        candidate = ToolMessage(
            content="long tool output " * 50,
            tool_call_id="tc-1",
            id="msg-1",
        )

        with patch.object(compactor, "_build_compactor_llm", return_value=llm):
            with pytest.raises(asyncio.CancelledError):
                await compactor.compact_messages([candidate], {"configurable": {}})
