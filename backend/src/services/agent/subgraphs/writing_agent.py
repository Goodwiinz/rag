"""Writing Agent sub-graph.

Specialized for content creation, summarization, and bibliography tasks.
Tools: create_draft, create_project_note, export_bibliography,
       summarize_document, compare_documents
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from src.services.agent.compactor import make_compactor_node
from src.services.agent.graph import _sanitize_messages
from src.services.agent.planner import make_planner_node
from src.services.agent.reflection import make_reflection_gate
from src.services.agent.state import AgentState
from src.services.agent.tools import (
    compare_documents,
    create_draft,
    create_project_note,
    export_bibliography,
    ingest_arxiv_papers,
    summarize_document,
)

logger = logging.getLogger(__name__)

WRITING_TOOLS = [
    create_draft,
    create_project_note,
    export_bibliography,
    summarize_document,
    compare_documents,
    # ingest_arxiv_papers is exposed here ONLY as a recovery path for
    # summarize_document / compare_documents when they return
    # error_type="recoverable" with suggestion="ingest_arxiv_papers"
    # (see _build_writing_system_prompt). Without it the LLM hits a
    # dead end on "Summarize arxiv 2201.00978" because the source paper
    # isn't ingested yet. Destructive — gated through the HITL interrupt.
    ingest_arxiv_papers,
]

WRITING_TOOL_NAMES_LIST = [t.name for t in WRITING_TOOLS]

# Destructive tools written by the writing subgraph. The main graph's
# DESTRUCTIVE_TOOLS gate only fires from the top-level interrupt_node and
# is bypassed once intent routes us into a subgraph, so the subgraph has
# to enforce HITL itself for any tool that mutates user data.
WRITING_DESTRUCTIVE_TOOLS = {
    "create_project_note",
    "create_draft",
    "ingest_arxiv_papers",
}

def _build_writing_system_prompt() -> str:
    """Construct the writing subgraph system prompt with shared rules embedded.

    Driver protocol sourced from ``AGENTS_writing.md`` — see
    ``agents_md_loader``. Inline fallback for missing-file safety.

    Imported lazily to avoid circular imports with graph.py.
    """
    from src.services.agent.graph import SHARED_AGENT_RULES
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    driver_protocol = load_agents_md("writing")
    if driver_protocol:
        return f"{driver_protocol}\n\n{SHARED_AGENT_RULES}"

    return (
        "You are a specialized Writing Agent focused on creating content, "
        "summarizing documents, and managing bibliographies.\n\n"
        f"{SHARED_AGENT_RULES}\n\n"
        "Write clearly and academically. Cite sources when available."
    )


async def writing_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Writing-specialized LLM node."""
    from src.services.agent.graph import _build_llm

    messages = [SystemMessage(content=_build_writing_system_prompt())] + _sanitize_messages(list(state["messages"]))

    llm = _build_llm()
    llm_with_tools = llm.bind_tools(WRITING_TOOLS)
    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
    }


def writing_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in writing sub-graph."""
    if state.get("error_count", 0) >= 3:
        return "writing_reflection_gate"
    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < 8
    ):
        if any(tc["name"] in WRITING_DESTRUCTIVE_TOOLS for tc in last.tool_calls):
            return "writing_interrupt_node"
        return "writing_tool_node"
    return "writing_reflection_gate"


async def writing_interrupt_node(state: AgentState, config: RunnableConfig) -> dict:
    """Pause for user confirmation before executing destructive writing tools."""
    last = state["messages"][-1] if state.get("messages") else None
    if not isinstance(last, AIMessage) or not getattr(last, "tool_calls", None):
        # Defensive guard — see ``research_interrupt_node`` for rationale.
        return {"pending_confirmation": {}, "user_confirmed": False}
    destructive_calls = [
        tc for tc in last.tool_calls if tc["name"] in WRITING_DESTRUCTIVE_TOOLS
    ]
    tool_names = [tc["name"] for tc in destructive_calls]

    confirmation_details = {
        "pending_tools": tool_names,
        "tools": [
            {"name": tc["name"], "args": tc["args"]} for tc in destructive_calls
        ],
        "message": f"Confirm: {', '.join(tool_names)}?",
    }
    user_response = interrupt(confirmation_details)

    if user_response and user_response.get("confirmed"):
        return {"pending_confirmation": {}, "user_confirmed": True}

    return {
        "messages": [
            AIMessage(
                content=(
                    "Action cancelled by user. Let me know if you'd like to "
                    "proceed differently."
                ),
            ),
        ],
        "pending_confirmation": {},
        "user_confirmed": False,
    }


def writing_after_interrupt(state: AgentState) -> str:
    if state.get("user_confirmed", False):
        return "writing_tool_node"
    return "writing_reflection_gate"


def _writing_reflection_route(state: AgentState) -> str:
    """Route after reflection: revise loops back to LLM, proceed exits."""
    from src.services.agent.reflection import ReflectionResult

    result: ReflectionResult | None = state.get("_reflection_result")  # type: ignore[arg-type]
    if result is None or result.passed or result.severity == "minor":
        return END
    if result.severity == "major" and state.get("reflection_count", 0) < 2:
        return "writing_llm_node"
    return END


def build_writing_subgraph() -> StateGraph:
    """Build the writing agent sub-graph.

    Flow:
      writing_planner_node -> writing_llm_node -> writing_should_continue ->
        | writing_interrupt_node -> writing_after_interrupt -> writing_tool_node
        | writing_tool_node -> writing_compactor_node -> writing_llm_node (loop)
        | writing_reflection_gate -> END (or revise -> writing_llm_node)
    """
    from src.services.agent.graph import make_filtered_tool_node

    WRITING_TOOL_NAMES = {t.name for t in WRITING_TOOLS}
    filtered_tool = make_filtered_tool_node(WRITING_TOOL_NAMES)

    # Create v2 nodes
    planner = make_planner_node(WRITING_TOOL_NAMES_LIST)
    compactor = make_compactor_node()
    reflection_node, _reflection_route = make_reflection_gate(
        intent_filter={"writing"},
    )

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("writing_planner_node", planner)
    graph.add_node("writing_llm_node", writing_llm_node)
    graph.add_node("writing_tool_node", filtered_tool)
    graph.add_node("writing_interrupt_node", writing_interrupt_node)
    graph.add_node("writing_compactor_node", compactor)
    graph.add_node("writing_reflection_gate", reflection_node)

    # Edges
    graph.set_entry_point("writing_planner_node")
    graph.add_edge("writing_planner_node", "writing_llm_node")

    graph.add_conditional_edges(
        "writing_llm_node",
        writing_should_continue,
        {
            "writing_tool_node": "writing_tool_node",
            "writing_interrupt_node": "writing_interrupt_node",
            "writing_reflection_gate": "writing_reflection_gate",
        },
    )

    graph.add_conditional_edges(
        "writing_interrupt_node",
        writing_after_interrupt,
        {
            "writing_tool_node": "writing_tool_node",
            "writing_reflection_gate": "writing_reflection_gate",
        },
    )

    graph.add_edge("writing_tool_node", "writing_compactor_node")
    graph.add_edge("writing_compactor_node", "writing_llm_node")

    graph.add_conditional_edges(
        "writing_reflection_gate",
        _writing_reflection_route,
        {
            END: END,
            "writing_llm_node": "writing_llm_node",
        },
    )

    return graph
