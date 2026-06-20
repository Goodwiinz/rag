"""Dedupe early-exit: when all tool calls in a batch are cache hits, tool_node
sets tools_all_deduped=True and route_after_tool_node bypasses the re-plan
loop (compactor_node → llm_node) going straight to force_synthesis_node.

Trace context: Azure p95 LLM round-trip is ~8 s. A fully-deduped batch
carries zero new information, so skipping that hop is pure latency saving
with no correctness impact. Scope: MAIN graph tool_node ONLY.
Subgraph filtered_tool_nodes are unaffected — marked as follow-up (GOO-XXX).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# ---------------------------------------------------------------------------
# route_after_tool_node — unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_route_after_tool_node_fully_deduped_routes_to_synthesis():
    """tools_all_deduped=True → force_synthesis_node, skipping re-plan loop."""
    from src.services.agent._builders import route_after_tool_node

    state = {"tools_all_deduped": True}
    assert route_after_tool_node(state) == "force_synthesis_node"


@pytest.mark.unit
def test_route_after_tool_node_false_routes_to_compactor():
    """tools_all_deduped=False → normal compactor_node path."""
    from src.services.agent._builders import route_after_tool_node

    state = {"tools_all_deduped": False}
    assert route_after_tool_node(state) == "compactor_node"


@pytest.mark.unit
def test_route_after_tool_node_absent_routes_to_compactor():
    """Missing tools_all_deduped key → normal path (falsy default)."""
    from src.services.agent._builders import route_after_tool_node

    assert route_after_tool_node({}) == "compactor_node"


@pytest.mark.unit
def test_route_after_tool_node_none_routes_to_compactor():
    """Explicitly None → normal path."""
    from src.services.agent._builders import route_after_tool_node

    state = {"tools_all_deduped": None}
    assert route_after_tool_node(state) == "compactor_node"


# ---------------------------------------------------------------------------
# tools_all_deduped flag in tool_node
# ---------------------------------------------------------------------------


def _make_state(tool_calls: list[dict]) -> dict:
    """Build a minimal AgentState dict with the given tool_calls on the last AIMessage."""
    return {
        "messages": [
            HumanMessage(content="search for papers"),
            AIMessage(content="", tool_calls=tool_calls),
        ],
        "tool_executions": [],
        "error_count": 0,
        "last_error": "",
        "last_error_info": {},
        "page_context": {},
        "tool_loop_count": 0,
    }


def _make_tool_calls(n: int = 2) -> list[dict]:
    return [
        {"id": f"call_{i}", "name": "search_arxiv", "args": {"query": f"topic_{i}"}}
        for i in range(n)
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_node_fully_cached_sets_flag_true():
    """When find_cached_tool_results returns all IDs, tools_all_deduped=True.

    The dedupe helpers are imported inside tool_node via `from ... import`, so
    we patch their origin module (tool_dedupe) rather than the _nodes_tools
    namespace.  _execute_single_tool is also guarded so no real I/O runs.
    """
    from src.services.agent._nodes_tools import tool_node

    tool_calls = _make_tool_calls(2)
    state = _make_state(tool_calls)

    # Every call is a cache hit
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
        # Guard against any accidental real tool execution
        patch(
            "src.services.agent._nodes_tools._execute_single_tool",
            side_effect=AssertionError(
                "should not execute fresh tools in full-cache case"
            ),
        ),
    ):
        result = await tool_node(state, {"configurable": {}})

    assert result["tools_all_deduped"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_node_no_cache_hits_sets_flag_false():
    """When no cache hits, tools_all_deduped=False (fresh calls run)."""
    from src.services.agent._nodes_tools import tool_node

    tool_calls = _make_tool_calls(1)
    state = _make_state(tool_calls)

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
        result = await tool_node(state, {"configurable": {}})

    assert result["tools_all_deduped"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_node_partial_cache_sets_flag_false():
    """One hit + one fresh call → tools_all_deduped=False (partial is not full)."""
    from src.services.agent._nodes_tools import tool_node

    tool_calls = _make_tool_calls(2)
    state = _make_state(tool_calls)

    # Only the first call is cached
    cached_map = {
        tool_calls[0]["id"]: {
            "id": tool_calls[0]["id"],
            "tool_name": tool_calls[0]["name"],
            "args": tool_calls[0]["args"],
            "status": "completed",
            "result": {"papers": []},
        }
    }

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
            side_effect=_fake_execute,
        ),
    ):
        result = await tool_node(state, {"configurable": {}})

    assert result["tools_all_deduped"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_node_empty_tool_calls_sets_flag_false():
    """No tool_calls at all → early return with tools_all_deduped absent/falsy."""
    from src.services.agent._nodes_tools import tool_node

    state = {
        "messages": [HumanMessage(content="hello"), AIMessage(content="hi")],
        "tool_executions": [],
        "error_count": 0,
        "last_error": "",
        "last_error_info": {},
        "page_context": {},
        "tool_loop_count": 0,
    }
    # No last AIMessage with tool_calls → early return
    result = await tool_node(state, {"configurable": {}})
    # The early-return branch doesn't set the flag; either absent or falsy is fine
    assert not result.get("tools_all_deduped")


# ---------------------------------------------------------------------------
# Graph wiring — conditional edge exists and routes correctly
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_graph_builds_with_conditional_edge():
    """build_agent_graph() must complete without error (imports + wiring pass)."""
    from src.services.agent._builders import build_agent_graph

    graph = build_agent_graph()
    assert graph is not None


@pytest.mark.unit
def test_route_after_tool_node_is_exported():
    """route_after_tool_node must appear in __all__ and be importable."""
    import src.services.agent._builders as builders

    assert "route_after_tool_node" in builders.__all__
    assert callable(builders.route_after_tool_node)


@pytest.mark.unit
def test_compiled_graph_has_force_synthesis_node():
    """The main compiled graph must include force_synthesis_node as a node."""
    from src.services.agent._builders import build_agent_graph

    compiled = build_agent_graph().compile()
    node_ids = set(compiled.get_graph().nodes.keys())
    assert (
        "force_synthesis_node" in node_ids
    ), "force_synthesis_node must be present so the dedupe fast-exit path exists"


@pytest.mark.unit
def test_compiled_graph_has_compactor_node():
    """The main compiled graph still has compactor_node for the normal path."""
    from src.services.agent._builders import build_agent_graph

    compiled = build_agent_graph().compile()
    node_ids = set(compiled.get_graph().nodes.keys())
    assert "compactor_node" in node_ids
