"""Unit tests for the specialist-subgraph factory.

Asserts the generated ``should_continue`` routers reproduce the historical
per-subgraph routing for the four state shapes that matter, and that data
(no destructive tools) can never route to an interrupt node.
"""

from typing import Any, cast

from langchain_core.messages import AIMessage

from src.services.agent.state import AgentState
from src.services.agent.subgraphs.data_agent import (
    MAX_DATA_TOOL_LOOPS,
    data_should_continue,
)
from src.services.agent.subgraphs.research_agent import (
    MAX_RESEARCH_TOOL_LOOPS,
    RESEARCH_DESTRUCTIVE_TOOLS,
    research_should_continue,
)
from src.services.agent.subgraphs.writing_agent import (
    MAX_WRITING_TOOL_LOOPS,
    WRITING_DESTRUCTIVE_TOOLS,
    writing_should_continue,
)


def _state_with_tool_call(
    tool_name: str, *, loops: int = 0, **extra: Any
) -> AgentState:
    return cast(
        AgentState,
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"id": "tc1", "name": tool_name, "args": {}}],
                )
            ],
            "tool_loop_count": loops,
            **extra,
        },
    )


class TestUnderCeiling:
    def test_research_routes_to_tool_node(self) -> None:
        state = _state_with_tool_call("search_arxiv")
        assert research_should_continue(state) == "research_tool_node"

    def test_writing_routes_to_tool_node(self) -> None:
        state = _state_with_tool_call("summarize_document")
        assert writing_should_continue(state) == "writing_tool_node"

    def test_data_routes_to_tool_node(self) -> None:
        state = _state_with_tool_call("search_knowledge_graph")
        assert data_should_continue(state) == "data_tool_node"


class TestDestructiveInterrupt:
    def test_research_destructive_routes_to_interrupt(self) -> None:
        assert RESEARCH_DESTRUCTIVE_TOOLS, "registry lost research destructive tools"
        tool = next(iter(RESEARCH_DESTRUCTIVE_TOOLS))
        state = _state_with_tool_call(tool)
        assert research_should_continue(state) == "research_interrupt_node"

    def test_writing_destructive_routes_to_interrupt(self) -> None:
        assert WRITING_DESTRUCTIVE_TOOLS, "registry lost writing destructive tools"
        tool = next(iter(WRITING_DESTRUCTIVE_TOOLS))
        state = _state_with_tool_call(tool)
        assert writing_should_continue(state) == "writing_interrupt_node"

    def test_data_never_routes_to_interrupt(self) -> None:
        # Data has no interrupt node at all; even a hypothetically
        # destructive-named call must go to the tool node.
        for tool in ("create_draft", "ingest_arxiv_papers", "extract_entities"):
            state = _state_with_tool_call(tool)
            assert data_should_continue(state) == "data_tool_node"


class TestOverCeiling:
    def test_research_over_ceiling_forces_synthesis(self) -> None:
        state = _state_with_tool_call("search_arxiv", loops=MAX_RESEARCH_TOOL_LOOPS)
        assert research_should_continue(state) == "research_force_synthesis_node"

    def test_writing_over_ceiling_forces_synthesis(self) -> None:
        state = _state_with_tool_call(
            "summarize_document", loops=MAX_WRITING_TOOL_LOOPS
        )
        assert writing_should_continue(state) == "writing_force_synthesis_node"

    def test_data_over_ceiling_forces_synthesis(self) -> None:
        state = _state_with_tool_call(
            "search_knowledge_graph", loops=MAX_DATA_TOOL_LOOPS
        )
        assert data_should_continue(state) == "data_force_synthesis_node"


class TestSynthesisAlreadyFired:
    def test_research_routes_to_reflection(self) -> None:
        state = _state_with_tool_call(
            "search_arxiv",
            loops=MAX_RESEARCH_TOOL_LOOPS + 1,
            _force_synthesis_fired=True,
        )
        assert research_should_continue(state) == "research_reflection_gate"

    def test_data_routes_to_reflection(self) -> None:
        state = _state_with_tool_call(
            "search_knowledge_graph",
            loops=MAX_DATA_TOOL_LOOPS + 1,
            _force_synthesis_fired=True,
        )
        assert data_should_continue(state) == "data_reflection_gate"


class TestTerminalShapes:
    def test_error_ceiling_routes_to_reflection(self) -> None:
        state = _state_with_tool_call("search_arxiv", error_count=3)
        assert research_should_continue(state) == "research_reflection_gate"

    def test_plain_answer_routes_to_reflection(self) -> None:
        state = cast(
            AgentState,
            {"messages": [AIMessage(content="done")], "tool_loop_count": 0},
        )
        assert writing_should_continue(state) == "writing_reflection_gate"


class TestGeneratedNames:
    """Closure-identity insurance: generated fns carry the historical names."""

    def test_names(self) -> None:
        assert research_should_continue.__name__ == "research_should_continue"
        assert writing_should_continue.__name__ == "writing_should_continue"
        assert data_should_continue.__name__ == "data_should_continue"
