"""Dedupe early-exit for the 3 LangGraph subgraphs (research/writing/data).

When a filtered_tool_node batch is FULLY deduped (every allowed tool call was
already executed this turn with identical args → zero fresh calls),
re-planning via the LLM is wasted (no new info). The subgraph route functions
short-circuit to *_force_synthesis_node instead of *_compactor_node, saving
~8 s Azure p95.

Scope: filtered_tool_node flag + 3 route fns + 3 graph smoke-compiles.
Mirrors test_tool_dedupe_early_exit.py (main graph), which covers tool_node.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(tool_calls: list[dict]) -> dict:
    """Minimal AgentState dict with the given tool_calls on the last AIMessage."""
    return {
        "messages": [
            HumanMessage(content="find papers on transformers"),
            AIMessage(content="", tool_calls=tool_calls),
        ],
        "tool_executions": [],
        "error_count": 0,
        "last_error": "",
        "last_error_info": {},
        "page_context": {},
        "tool_loop_count": 0,
    }


def _make_tool_calls(n: int = 2, name: str = "search_arxiv") -> list[dict]:
    return [
        {"id": f"call_{i}", "name": name, "args": {"query": f"topic_{i}"}}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# route_after_research_tool_node
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_route_after_research_tool_node_fully_deduped_routes_to_synthesis():
    """tools_all_deduped=True → research_force_synthesis_node."""
    from src.services.agent.subgraphs.research_agent import (
        route_after_research_tool_node,
    )

    assert route_after_research_tool_node({"tools_all_deduped": True}) == (
        "research_force_synthesis_node"
    )


@pytest.mark.unit
def test_route_after_research_tool_node_false_routes_to_compactor():
    """tools_all_deduped=False → research_compactor_node (normal path)."""
    from src.services.agent.subgraphs.research_agent import (
        route_after_research_tool_node,
    )

    assert route_after_research_tool_node({"tools_all_deduped": False}) == (
        "research_compactor_node"
    )


@pytest.mark.unit
def test_route_after_research_tool_node_absent_routes_to_compactor():
    """Missing tools_all_deduped → normal compactor path."""
    from src.services.agent.subgraphs.research_agent import (
        route_after_research_tool_node,
    )

    assert route_after_research_tool_node({}) == "research_compactor_node"


# ---------------------------------------------------------------------------
# route_after_writing_tool_node
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_route_after_writing_tool_node_fully_deduped_routes_to_synthesis():
    """tools_all_deduped=True → writing_force_synthesis_node."""
    from src.services.agent.subgraphs.writing_agent import (
        route_after_writing_tool_node,
    )

    assert route_after_writing_tool_node({"tools_all_deduped": True}) == (
        "writing_force_synthesis_node"
    )


@pytest.mark.unit
def test_route_after_writing_tool_node_false_routes_to_compactor():
    """tools_all_deduped=False → writing_compactor_node (normal path)."""
    from src.services.agent.subgraphs.writing_agent import (
        route_after_writing_tool_node,
    )

    assert route_after_writing_tool_node({"tools_all_deduped": False}) == (
        "writing_compactor_node"
    )


@pytest.mark.unit
def test_route_after_writing_tool_node_absent_routes_to_compactor():
    """Missing tools_all_deduped → normal compactor path."""
    from src.services.agent.subgraphs.writing_agent import (
        route_after_writing_tool_node,
    )

    assert route_after_writing_tool_node({}) == "writing_compactor_node"


# ---------------------------------------------------------------------------
# route_after_data_tool_node
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_route_after_data_tool_node_fully_deduped_routes_to_synthesis():
    """tools_all_deduped=True → data_force_synthesis_node."""
    from src.services.agent.subgraphs.data_agent import route_after_data_tool_node

    assert route_after_data_tool_node({"tools_all_deduped": True}) == (
        "data_force_synthesis_node"
    )


@pytest.mark.unit
def test_route_after_data_tool_node_false_routes_to_compactor():
    """tools_all_deduped=False → data_compactor_node (normal path)."""
    from src.services.agent.subgraphs.data_agent import route_after_data_tool_node

    assert route_after_data_tool_node({"tools_all_deduped": False}) == (
        "data_compactor_node"
    )


@pytest.mark.unit
def test_route_after_data_tool_node_absent_routes_to_compactor():
    """Missing tools_all_deduped → normal compactor path."""
    from src.services.agent.subgraphs.data_agent import route_after_data_tool_node

    assert route_after_data_tool_node({}) == "data_compactor_node"


# ---------------------------------------------------------------------------
# filtered_tool_node sets tools_all_deduped
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_filtered_tool_node_fully_cached_sets_flag_true():
    """When all allowed calls are cache hits, filtered_tool_node sets tools_all_deduped=True.

    Patches find_cached_tool_results to return all IDs so no fresh tools run,
    and guards _execute_single_tool so no real I/O is attempted.
    """
    from src.services.agent._nodes_tools import make_filtered_tool_node

    tool_calls = _make_tool_calls(2)
    state = _make_state(tool_calls)

    filtered_tool_node = make_filtered_tool_node({"search_arxiv"})

    cached_map = {
        tc["id"]: {
            "id": tc["id"],
            "tool_name": tc["name"],
            "args": tc["args"],
            "status": "completed",
            "result": {"papers": []},
        }
        for tc in tool_calls
    }

    with (
        patch(
            "src.services.agent.tool_dedupe.find_cached_tool_results",
            return_value=cached_map,
        ),
        patch(
            "src.services.agent.tool_dedupe.build_deduped_tool_message",
            side_effect=lambda tid, _prior: ToolMessage(
                content="[deduped]", tool_call_id=tid
            ),
        ),
        patch(
            "src.services.agent.tool_dedupe.build_deduped_execution_entry",
            return_value={},
        ),
        patch(
            "src.services.agent._nodes_tools._execute_single_tool",
            side_effect=AssertionError(
                "should not execute fresh tools in full-cache case"
            ),
        ),
    ):
        result = await filtered_tool_node(state, {"configurable": {}})

    assert result["tools_all_deduped"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_filtered_tool_node_no_cache_sets_flag_false():
    """When no calls are cached, filtered_tool_node sets tools_all_deduped=False."""
    from src.services.agent._nodes_tools import make_filtered_tool_node

    tool_calls = _make_tool_calls(1)
    state = _make_state(tool_calls)

    filtered_tool_node = make_filtered_tool_node({"search_arxiv"})

    async def _fake_execute(tc, config, page_ctx):
        return {
            "message": ToolMessage(content='{"results":[]}', tool_call_id=tc["id"]),
            "execution": {
                "id": tc["id"],
                "tool_name": tc["name"],
                "tool_display_name": tc["name"].replace("_", " ").title(),
                "args": tc["args"],
                "status": "completed",
                "result": {"results": []},
                "duration_ms": 50,
            },
            "error_increment": 0,
            "error_text": "",
            "error_info": {},
        }

    with (
        patch(
            "src.services.agent.tool_dedupe.find_cached_tool_results",
            return_value={},  # no cache hits
        ),
        patch(
            "src.services.agent._nodes_tools._execute_single_tool",
            side_effect=_fake_execute,
        ),
    ):
        result = await filtered_tool_node(state, {"configurable": {}})

    assert result["tools_all_deduped"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_filtered_tool_node_no_allowed_calls_flag_absent():
    """When no tool calls are in the allowed set, the early-return path omits the flag."""
    from src.services.agent._nodes_tools import make_filtered_tool_node

    # Allowed set does NOT include the tool being called
    filtered_tool_node = make_filtered_tool_node({"some_other_tool"})
    tool_calls = _make_tool_calls(1)
    state = _make_state(tool_calls)

    result = await filtered_tool_node(state, {"configurable": {}})

    # Early-return branch doesn't set the flag — falsy is correct
    assert not result.get("tools_all_deduped")


# ---------------------------------------------------------------------------
# Graph smoke-compile: all 3 subgraphs must compile with the new conditional edge
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_research_subgraph_compiles():
    """build_research_subgraph().compile() must not raise."""
    from src.services.agent.subgraphs.research_agent import build_research_subgraph

    compiled = build_research_subgraph().compile()
    node_ids = set(compiled.get_graph().nodes.keys())
    assert "research_force_synthesis_node" in node_ids
    assert "research_compactor_node" in node_ids


@pytest.mark.unit
def test_writing_subgraph_compiles():
    """build_writing_subgraph().compile() must not raise."""
    from src.services.agent.subgraphs.writing_agent import build_writing_subgraph

    compiled = build_writing_subgraph().compile()
    node_ids = set(compiled.get_graph().nodes.keys())
    assert "writing_force_synthesis_node" in node_ids
    assert "writing_compactor_node" in node_ids


@pytest.mark.unit
def test_data_subgraph_compiles():
    """build_data_subgraph().compile() must not raise."""
    from src.services.agent.subgraphs.data_agent import build_data_subgraph

    compiled = build_data_subgraph().compile()
    node_ids = set(compiled.get_graph().nodes.keys())
    assert "data_force_synthesis_node" in node_ids
    assert "data_compactor_node" in node_ids
