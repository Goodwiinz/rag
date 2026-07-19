"""LangSmith evaluation tests for the agent graph.

E2E tests that invoke the real agent graph with real LLM calls
and log results to LangSmith for evaluation and monitoring.

Heavy infrastructure (RAG search, memory store) is mocked so
tests can run without Qdrant/Neo4j/Redis. Only the LLM is real.

Requirements:
  - LANGCHAIN_API_KEY set in environment
  - AZURE_OPENAI_CHAT_ENDPOINT and AZURE_OPENAI_CHAT_API_KEY set
  - Run with: pytest tests/unit/services/test_agent_langsmith.py -m langsmith -v

These tests are skipped by default unless credentials are present.
"""

import os
import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

# Skip unless credentials available
_HAS_LANGSMITH = bool(os.environ.get("LANGCHAIN_API_KEY"))
_HAS_LLM = bool(
    os.environ.get("AZURE_OPENAI_CHAT_API_KEY")
    or os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT")
)

# LangSmith testing requires LANGSMITH_TRACING=true
if _HAS_LANGSMITH:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "rag-agent-tests")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.langsmith,
    pytest.mark.skipif(
        not (_HAS_LANGSMITH and _HAS_LLM),
        reason="Requires LANGCHAIN_API_KEY and Azure OpenAI credentials",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(user_msg: str) -> dict:
    return {
        "messages": [HumanMessage(content=user_msg)],
        "page_context": {"type": "unknown"},
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": "",
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "pending_confirmation": {},
        "user_confirmed": False,
        "intent": "",
        "user_memories": [],
    }


def _make_config(thread_id: str | None = None) -> dict:
    user = Mock(id=uuid4(), organization_id=uuid4())
    return {
        "configurable": {
            "thread_id": thread_id or str(uuid4()),
            "db": AsyncMock(),
            "current_user": user,
            "page_context": {"type": "unknown"},
        }
    }


def _extract_tool_calls(state: dict) -> list[str]:
    """Extract tool names from all AIMessages in state."""
    return [
        tc["name"]
        for msg in state.get("messages", [])
        if isinstance(msg, AIMessage)
        for tc in getattr(msg, "tool_calls", [])
    ]


def _extract_final_answer(state: dict) -> str:
    """Extract the last AI text message."""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return ""


def _mock_infra():
    """Context manager that mocks heavy infrastructure (RAG, memory, tools)
    while leaving the LLM real."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        with (
            # Mock RAG search (needs Qdrant/Neo4j)
            patch(
                "src.services.agent.graph.rag_node",
                new=AsyncMock(return_value={"retrieved_contexts": []}),
            ),
            # Mock memory retrieval (needs store)
            patch(
                "src.services.agent.graph.memory_retrieval_node",
                new=AsyncMock(return_value={"user_memories": []}),
            ),
            # Mock memory save (needs store)
            patch(
                "src.services.agent.graph.memory_save_node",
                new=AsyncMock(return_value={}),
            ),
            # Mock tool execution (needs DB, external APIs)
            patch(
                "src.api.agent.execute.execute_tool",
                new=AsyncMock(return_value={"results": [], "total": 0, "message": "Mocked tool result"}),
            ),
        ):
            yield

    return _ctx()


# ---------------------------------------------------------------------------
# E2E Tests with LangSmith logging
# ---------------------------------------------------------------------------


class TestAgentResearchFlow:
    """E2E: Agent should use search_arxiv for research queries."""

    async def test_arxiv_search_triggered(self):
        """Agent should call search_arxiv when asked to find papers."""
        from langsmith import testing as t

        from src.services.agent.graph import compile_agent_graph

        query = "Search arxiv for recent papers on retrieval augmented generation"
        t.log_inputs({"query": query})
        t.log_reference_outputs({"expected_tool": "search_arxiv"})

        with _mock_infra():
            graph = compile_agent_graph(checkpointer=MemorySaver())
            config = _make_config()
            result = await graph.ainvoke(_make_state(query), config=config)

        tool_calls = _extract_tool_calls(result)
        final_answer = _extract_final_answer(result)

        t.log_outputs({
            "tool_calls": tool_calls,
            "final_answer": final_answer[:500],
            "num_messages": len(result["messages"]),
        })
        t.log_feedback(key="num_steps", score=len(result["messages"]))

        assert "search_arxiv" in tool_calls, (
            f"Expected search_arxiv in tool calls, got: {tool_calls}"
        )
        assert final_answer, "Agent should produce a text response"


class TestAgentGeneralConversation:
    """E2E: Agent should respond to general queries without tool use."""

    async def test_no_tools_on_greeting(self):
        """Agent should NOT use tools for a simple greeting."""
        from langsmith import testing as t

        from src.services.agent.graph import compile_agent_graph

        query = "Hello! How are you?"
        t.log_inputs({"query": query})
        t.log_reference_outputs({"expected_tools": []})

        with _mock_infra():
            graph = compile_agent_graph(checkpointer=MemorySaver())
            config = _make_config()
            result = await graph.ainvoke(_make_state(query), config=config)

        tool_calls = _extract_tool_calls(result)
        final_answer = _extract_final_answer(result)

        t.log_outputs({
            "tool_calls": tool_calls,
            "final_answer": final_answer[:500],
        })

        assert len(tool_calls) == 0, (
            f"Expected no tool calls for greeting, got: {tool_calls}"
        )
        assert final_answer, "Agent should produce a greeting response"


class TestAgentIntentRouting:
    """E2E: Intent classification should route to correct subgraph."""

    async def test_research_intent_classification(self):
        """Research query should be classified with research intent."""
        from langsmith import testing as t

        from src.services.agent.graph import compile_agent_graph

        query = "Find papers about attention mechanisms in deep learning"
        t.log_inputs({"query": query})
        t.log_reference_outputs({"expected_intent": "research"})

        with _mock_infra():
            checkpointer = MemorySaver()
            graph = compile_agent_graph(checkpointer=checkpointer)
            config = _make_config()
            result = await graph.ainvoke(_make_state(query), config=config)
            snapshot = await graph.aget_state(config)

        intent = snapshot.values.get("intent", "")

        t.log_outputs({
            "actual_intent": intent,
            "tool_calls": _extract_tool_calls(result),
        })
        t.log_feedback(key="correct_intent", score=1.0 if intent == "research" else 0.0)

        assert intent == "research", f"Expected research intent, got: {intent}"

    async def test_writing_intent_classification(self):
        """Writing query should be classified with writing intent."""
        from langsmith import testing as t

        from src.services.agent.graph import compile_agent_graph

        query = "Write a draft literature review and summarize the main themes"
        t.log_inputs({"query": query})
        t.log_reference_outputs({"expected_intent": "writing"})

        with _mock_infra():
            checkpointer = MemorySaver()
            graph = compile_agent_graph(checkpointer=checkpointer)
            config = _make_config()
            result = await graph.ainvoke(_make_state(query), config=config)
            snapshot = await graph.aget_state(config)

        intent = snapshot.values.get("intent", "")

        t.log_outputs({"actual_intent": intent})
        t.log_feedback(key="correct_intent", score=1.0 if intent == "writing" else 0.0)

        assert intent == "writing", f"Expected writing intent, got: {intent}"


class TestAgentErrorResilience:
    """E2E: Agent should handle errors gracefully."""

    async def test_agent_handles_tool_error_gracefully(self):
        """Agent should produce a response even when tools fail."""
        from langsmith import testing as t

        from src.services.agent.graph import compile_agent_graph

        query = "Search arxiv for papers about quantum computing"
        t.log_inputs({"query": query})

        with (
            patch(
                "src.services.agent.graph.rag_node",
                new=AsyncMock(return_value={"retrieved_contexts": []}),
            ),
            patch(
                "src.services.agent.graph.memory_retrieval_node",
                new=AsyncMock(return_value={"user_memories": []}),
            ),
            patch(
                "src.services.agent.graph.memory_save_node",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "src.api.agent.execute.execute_tool",
                new=AsyncMock(side_effect=Exception("Service unavailable")),
            ),
        ):
            graph = compile_agent_graph(checkpointer=MemorySaver())
            config = _make_config()
            result = await graph.ainvoke(_make_state(query), config=config)

        final_answer = _extract_final_answer(result)
        error_count = result.get("error_count", 0)

        t.log_outputs({
            "final_answer": final_answer[:500],
            "error_count": error_count,
            "num_messages": len(result["messages"]),
        })
        t.log_feedback(key="graceful_error", score=1.0 if final_answer else 0.0)

        assert len(result["messages"]) > 1, "Agent should have multiple messages"


class TestAgentMaxLoopProtection:
    """E2E: Agent should respect MAX_TOOL_LOOPS limit."""

    async def test_agent_terminates_within_loop_limit(self):
        """Agent execution should not exceed MAX_TOOL_LOOPS."""
        from langsmith import testing as t

        from src.services.agent.graph import MAX_TOOL_LOOPS, compile_agent_graph

        query = "Search for papers on transformers and list all project documents"
        t.log_inputs({"query": query, "max_tool_loops": MAX_TOOL_LOOPS})

        with _mock_infra():
            graph = compile_agent_graph(checkpointer=MemorySaver())
            config = _make_config()
            result = await graph.ainvoke(_make_state(query), config=config)

        tool_loop_count = result.get("tool_loop_count", 0)
        tool_calls = _extract_tool_calls(result)

        t.log_outputs({
            "tool_loop_count": tool_loop_count,
            "tool_calls": tool_calls,
            "num_messages": len(result["messages"]),
        })
        t.log_feedback(
            key="within_loop_limit",
            score=1.0 if tool_loop_count <= MAX_TOOL_LOOPS else 0.0,
        )

        assert tool_loop_count <= MAX_TOOL_LOOPS, (
            f"tool_loop_count {tool_loop_count} exceeds MAX_TOOL_LOOPS {MAX_TOOL_LOOPS}"
        )
