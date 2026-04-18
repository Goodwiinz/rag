"""Integration tests for agent graph execution."""

import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .conftest import (
    MockChatModel,
    make_ai_response,
    make_tool_call_response,
    make_initial_state,
    make_graph_config,
    make_mock_execute_tool,
    compile_graph_with_mocks,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_and_invoke(llm, tool_fn=None):
    """Compile a graph with the given mock LLM and tool function."""
    return compile_graph_with_mocks(llm, tool_fn or make_mock_execute_tool())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_simple_query_no_tools():
    """Simple 'Hello' query returns an AIMessage, intent='general', and no tool_executions."""
    llm = MockChatModel([make_ai_response("Hi there!")])
    graph = _build_and_invoke(llm)

    state = make_initial_state(message="Hello")
    config = make_graph_config()

    result = await graph.ainvoke(state, config=config)

    # Last message should be from the assistant
    last_msg = result["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert last_msg.content  # non-empty

    # Intent should be general for a greeting
    assert result["intent"] == "general"

    # No tool executions
    assert result["tool_executions"] == []


async def test_tool_call_flow():
    """LLM returns a search_arxiv tool_call, then a text response. Assert ToolMessage in messages."""
    tool_call_msg = make_tool_call_response(
        tool_name="search_arxiv",
        tool_args={"query": "graph neural networks"},
    )
    final_msg = make_ai_response("I found some papers on GNNs.")

    llm = MockChatModel([tool_call_msg, final_msg])
    tool_fn = make_mock_execute_tool(
        {"search_arxiv": {"results": [{"title": "GNN Survey"}]}}
    )
    graph = _build_and_invoke(llm, tool_fn)

    state = make_initial_state(message="Find arxiv papers on GNNs")
    config = make_graph_config()

    result = await graph.ainvoke(state, config=config)

    # Should contain a ToolMessage somewhere in the message history
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) >= 1


async def test_tool_loop_respects_max():
    """When the LLM always returns tool_calls, tool_loop_count must not exceed 10."""
    # Create an LLM that always returns tool calls (up to a large number)
    responses = [
        make_tool_call_response("search_arxiv", {"query": f"query_{i}"})
        for i in range(20)
    ]
    llm = MockChatModel(responses)
    tool_fn = make_mock_execute_tool()
    graph = _build_and_invoke(llm, tool_fn)

    state = make_initial_state(message="Search for everything about AI")
    config = make_graph_config()

    result = await graph.ainvoke(state, config=config)

    assert result["tool_loop_count"] <= 10


async def test_research_intent():
    """'Find arxiv papers on GNNs' should be classified with intent='research'."""
    llm = MockChatModel([make_ai_response("Here are papers on GNNs.")])
    graph = _build_and_invoke(llm)

    state = make_initial_state(message="Find arxiv papers on GNNs")
    config = make_graph_config()

    result = await graph.ainvoke(state, config=config)

    assert result["intent"] == "research"


async def test_writing_intent():
    """'Write a summary' should be classified with intent='writing'."""
    llm = MockChatModel([make_ai_response("Here is your summary.")])
    graph = _build_and_invoke(llm)

    state = make_initial_state(message="Write a summary")
    config = make_graph_config()

    result = await graph.ainvoke(state, config=config)

    assert result["intent"] == "writing"


async def test_knowledge_graph_intent():
    """'Extract entities' should be classified with intent='knowledge_graph'."""
    llm = MockChatModel([make_ai_response("Extracted entities: ...")])
    graph = _build_and_invoke(llm)

    state = make_initial_state(message="Extract entities from the document")
    config = make_graph_config()

    result = await graph.ainvoke(state, config=config)

    assert result["intent"] == "knowledge_graph"


async def test_general_intent():
    """'Hello what can you do' should be classified with intent='general'."""
    llm = MockChatModel([make_ai_response("I can help with research.")])
    graph = _build_and_invoke(llm)

    state = make_initial_state(message="Hello what can you do")
    config = make_graph_config()

    result = await graph.ainvoke(state, config=config)

    assert result["intent"] == "general"


async def test_v2_state_fields_present():
    """All v2 fields exist with correct types in the final state."""
    llm = MockChatModel([make_ai_response("Done.")])
    graph = _build_and_invoke(llm)

    state = make_initial_state(message="Hello")
    config = make_graph_config()

    result = await graph.ainvoke(state, config=config)

    # v2 fields
    assert "plan" in result
    assert isinstance(result["plan"], list)

    assert "reflection_count" in result
    assert isinstance(result["reflection_count"], int)

    assert "compaction_count" in result
    assert isinstance(result["compaction_count"], int)

    assert "intent_confidence" in result
    assert isinstance(result["intent_confidence"], float)

    assert "last_error_info" in result
    assert isinstance(result["last_error_info"], dict)

    # Core fields
    assert "intent" in result
    assert isinstance(result["intent"], str)

    assert "tool_loop_count" in result
    assert isinstance(result["tool_loop_count"], int)

    assert "error_count" in result
    assert isinstance(result["error_count"], int)
