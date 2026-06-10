"""Writing/data subgraph loop-ceiling routing.

The research subgraph gained a forced-synthesis node after trace 019e1903
(loop ceiling tripped with unanswered tool_calls → AIMessage/ToolMessage
pairing violation + empty final answer). Writing and data had the same
exit path but no synthesis node — these tests pin the parity fix.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent.subgraphs.data_agent import (
    MAX_DATA_TOOL_LOOPS,
    data_should_continue,
)
from src.services.agent.subgraphs.writing_agent import (
    MAX_WRITING_TOOL_LOOPS,
    writing_should_continue,
)


def _state_with_pending_tool_calls(tool_name: str, loop_count: int) -> dict:
    """Build a minimal state where the last AI message has a tool_call."""
    return {
        "messages": [
            HumanMessage(content="do the thing"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": tool_name,
                        "args": {},
                    }
                ],
            ),
        ],
        "tool_loop_count": loop_count,
        "error_count": 0,
    }


# ---------------------------------------------------------------------------
# Writing subgraph
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_writing_continues_below_ceiling():
    state = _state_with_pending_tool_calls(
        "summarize_document", MAX_WRITING_TOOL_LOOPS - 1
    )
    assert writing_should_continue(state) == "writing_tool_node"


@pytest.mark.unit
def test_writing_destructive_routes_to_interrupt_below_ceiling():
    state = _state_with_pending_tool_calls(
        "create_draft", MAX_WRITING_TOOL_LOOPS - 1
    )
    assert writing_should_continue(state) == "writing_interrupt_node"


@pytest.mark.unit
def test_writing_routes_to_force_synthesis_at_ceiling():
    """At the ceiling WITH unanswered tool_calls, route to forced synthesis
    instead of exiting with a dangling tool-call AIMessage."""
    state = _state_with_pending_tool_calls(
        "summarize_document", MAX_WRITING_TOOL_LOOPS
    )
    assert writing_should_continue(state) == "writing_force_synthesis_node"


@pytest.mark.unit
def test_writing_no_loop_back_into_force_synthesis_after_first_fire():
    state = _state_with_pending_tool_calls(
        "summarize_document", MAX_WRITING_TOOL_LOOPS + 2
    )
    state["_force_synthesis_fired"] = True
    assert writing_should_continue(state) == "writing_reflection_gate"


@pytest.mark.unit
def test_writing_routes_to_reflection_when_no_pending_tool_calls():
    state = {
        "messages": [
            HumanMessage(content="summarize"),
            AIMessage(content="Here is the summary..."),
        ],
        "tool_loop_count": MAX_WRITING_TOOL_LOOPS,
        "error_count": 0,
    }
    assert writing_should_continue(state) == "writing_reflection_gate"


@pytest.mark.unit
def test_writing_error_count_short_circuits():
    state = _state_with_pending_tool_calls("summarize_document", 0)
    state["error_count"] = 3
    assert writing_should_continue(state) == "writing_reflection_gate"


# ---------------------------------------------------------------------------
# Data subgraph
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_data_continues_below_ceiling():
    state = _state_with_pending_tool_calls(
        "search_knowledge_graph", MAX_DATA_TOOL_LOOPS - 1
    )
    assert data_should_continue(state) == "data_tool_node"


@pytest.mark.unit
def test_data_routes_to_force_synthesis_at_ceiling():
    state = _state_with_pending_tool_calls(
        "search_knowledge_graph", MAX_DATA_TOOL_LOOPS
    )
    assert data_should_continue(state) == "data_force_synthesis_node"


@pytest.mark.unit
def test_data_no_loop_back_into_force_synthesis_after_first_fire():
    state = _state_with_pending_tool_calls(
        "search_knowledge_graph", MAX_DATA_TOOL_LOOPS + 2
    )
    state["_force_synthesis_fired"] = True
    assert data_should_continue(state) == "data_reflection_gate"


@pytest.mark.unit
def test_data_routes_to_reflection_when_no_pending_tool_calls():
    state = {
        "messages": [
            HumanMessage(content="show entities"),
            AIMessage(content="Here are the entities..."),
        ],
        "tool_loop_count": MAX_DATA_TOOL_LOOPS,
        "error_count": 0,
    }
    assert data_should_continue(state) == "data_reflection_gate"


@pytest.mark.unit
def test_data_error_count_short_circuits():
    state = _state_with_pending_tool_calls("search_knowledge_graph", 0)
    state["error_count"] = 3
    assert data_should_continue(state) == "data_reflection_gate"


# ---------------------------------------------------------------------------
# Graph wiring — synthesis nodes exist and exit through reflection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_writing_graph_has_force_synthesis_node():
    from src.services.agent.subgraphs.writing_agent import build_writing_subgraph

    compiled = build_writing_subgraph().compile()
    assert "writing_force_synthesis_node" in compiled.get_graph().nodes


@pytest.mark.unit
def test_data_graph_has_force_synthesis_node():
    from src.services.agent.subgraphs.data_agent import build_data_subgraph

    compiled = build_data_subgraph().compile()
    assert "data_force_synthesis_node" in compiled.get_graph().nodes
