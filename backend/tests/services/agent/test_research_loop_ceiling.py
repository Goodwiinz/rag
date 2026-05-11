"""Phase 6 — research subgraph loop ceiling lowered 8 → 5.

Trace 019e18f0 showed a 4-round runaway tool fan-out (95s wall, 13+
search_arxiv calls). Cap at 5 to bound worst-case latency while still
allowing search → refine → ingest → list → confirm sequences.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent.subgraphs.research_agent import (
    MAX_RESEARCH_TOOL_LOOPS,
    research_should_continue,
)


@pytest.mark.unit
def test_constant_is_five():
    assert MAX_RESEARCH_TOOL_LOOPS == 5


def _state_with_pending_tool_calls(loop_count: int) -> dict:
    """Build a minimal state where the last AI message has a tool_call."""
    return {
        "messages": [
            HumanMessage(content="find papers"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "search_arxiv",
                        "args": {"query": "x"},
                    }
                ],
            ),
        ],
        "tool_loop_count": loop_count,
        "error_count": 0,
    }


@pytest.mark.unit
def test_continues_below_ceiling():
    state = _state_with_pending_tool_calls(loop_count=4)
    assert research_should_continue(state) == "research_tool_node"


@pytest.mark.unit
def test_routes_to_force_synthesis_at_ceiling():
    """At loop_count == 5 WITH unanswered tool_calls, route to forced
    synthesis so the final AIMessage has real content. Previously routed
    directly to reflection with empty content (trace 019e1903)."""
    state = _state_with_pending_tool_calls(loop_count=5)
    assert research_should_continue(state) == "research_force_synthesis_node"


@pytest.mark.unit
def test_routes_to_force_synthesis_above_ceiling():
    state = _state_with_pending_tool_calls(loop_count=10)
    assert research_should_continue(state) == "research_force_synthesis_node"


@pytest.mark.unit
def test_routes_to_reflection_when_no_pending_tool_calls():
    """No tool_calls on the last AI message → no synthesis needed, go to gate."""
    state = {
        "messages": [
            HumanMessage(content="find papers"),
            AIMessage(content="Here are the papers..."),  # no tool_calls
        ],
        "tool_loop_count": 5,
        "error_count": 0,
    }
    assert research_should_continue(state) == "research_reflection_gate"


@pytest.mark.unit
def test_error_count_short_circuits_regardless_of_loop():
    state = _state_with_pending_tool_calls(loop_count=0)
    state["error_count"] = 3
    assert research_should_continue(state) == "research_reflection_gate"


@pytest.mark.unit
def test_no_loop_back_into_force_synthesis_after_first_fire():
    """Defensive routing: if forced synthesis already ran and the response
    still carries tool_calls (defective model output), go to reflection
    rather than re-entering force-synthesis (would loop infinitely)."""
    state = _state_with_pending_tool_calls(loop_count=10)
    state["_force_synthesis_fired"] = True
    assert research_should_continue(state) == "research_reflection_gate"
