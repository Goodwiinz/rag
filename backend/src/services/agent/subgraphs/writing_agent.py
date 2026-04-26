"""Writing Agent sub-graph.

Specialized for content creation, summarization, and bibliography tasks.
Tools: create_draft, create_project_note, export_bibliography,
       summarize_document, compare_documents
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

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
    summarize_document,
)

logger = logging.getLogger(__name__)

WRITING_TOOLS = [
    create_draft,
    create_project_note,
    export_bibliography,
    summarize_document,
    compare_documents,
]

WRITING_TOOL_NAMES_LIST = [t.name for t in WRITING_TOOLS]

def _build_writing_system_prompt() -> str:
    """Construct the writing subgraph system prompt with shared rules embedded.

    Imported lazily to avoid circular imports with graph.py.
    """
    from src.services.agent.graph import SHARED_AGENT_RULES

    return (
        "You are a specialized Writing Agent focused on creating content, "
        "summarizing documents, and managing bibliographies.\n\n"
        "Your tools:\n"
        "- summarize_document: Create summaries of documents\n"
        "- compare_documents: Compare multiple documents\n"
        "- create_draft: Generate literature review drafts\n"
        "- create_project_note: Write notes in projects\n"
        "- export_bibliography: Export citations in various formats\n\n"
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
