"""Research Agent sub-graph.

Specialized for paper discovery, search, and ingestion tasks.
Tools: search_arxiv, ingest_arxiv_papers, search_documents,
       create_project, add_document_to_project, list_project_documents
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from src.services.agent.compactor import make_compactor_node
from src.services.agent.planner import make_planner_node
from src.services.agent.reflection import make_reflection_gate
from src.services.agent.state import AgentState
from src.services.agent.tools import (
    add_document_to_project,
    create_project,
    ingest_arxiv_papers,
    list_project_documents,
    search_arxiv,
    search_documents,
)

logger = logging.getLogger(__name__)

RESEARCH_TOOLS = [
    search_arxiv,
    ingest_arxiv_papers,
    search_documents,
    create_project,
    add_document_to_project,
    list_project_documents,
]

RESEARCH_TOOL_NAMES_LIST = [t.name for t in RESEARCH_TOOLS]

RESEARCH_SYSTEM_PROMPT = (
    "You are a specialized Research Agent focused on discovering, searching, "
    "and organizing academic papers and documents.\n\n"
    "Your tools:\n"
    "- search_arxiv: Find papers on arXiv\n"
    "- ingest_arxiv_papers: Import papers into the RAG system\n"
    "- search_documents: Search indexed documents\n"
    "- create_project: Create a new research project (folder). Requires a name; "
    "description/research_goals/tags are optional\n"
    "- add_document_to_project: Organize documents into projects\n"
    "- list_project_documents: View project contents\n\n"
    "CRITICAL: After ingesting papers, use the document_ids (UUIDs) from the "
    "ingest response — NOT arXiv paper IDs.\n"
    "Be thorough in searching and systematic in organizing research."
)


def _sanitize_messages(raw: list) -> list:
    """Ensure the message list is valid for LLM APIs.

    - Adds placeholder ToolMessages for AIMessages whose tool_calls are unanswered.
    - Merges consecutive HumanMessages into one so the LLM doesn't reject them.
    """
    # Pass 1: fill missing ToolMessages
    filled: list = []
    for i, msg in enumerate(raw):
        filled.append(msg)
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            expected = {tc["id"] for tc in msg.tool_calls}
            answered: set = set()
            for future in raw[i + 1:]:
                if isinstance(future, ToolMessage):
                    answered.add(future.tool_call_id)
                elif isinstance(future, (AIMessage, HumanMessage)):
                    break
            for tc in msg.tool_calls:
                if tc["id"] not in answered:
                    filled.append(ToolMessage(content='{"status": "skipped"}', tool_call_id=tc["id"]))

    # Pass 2: merge consecutive HumanMessages
    merged: list = []
    for msg in filled:
        if merged and isinstance(merged[-1], HumanMessage) and isinstance(msg, HumanMessage):
            combined = f"{merged[-1].content}\n{msg.content}"
            merged[-1] = HumanMessage(content=combined)
        else:
            merged.append(msg)

    return merged


RESEARCH_DESTRUCTIVE_TOOLS = {"ingest_arxiv_papers", "add_document_to_project", "create_project"}


async def research_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Research-specialized LLM node."""
    from src.services.agent.graph import _build_llm

    sanitized = _sanitize_messages(list(state["messages"]))
    messages = [SystemMessage(content=RESEARCH_SYSTEM_PROMPT)] + sanitized

    llm = _build_llm()
    llm_with_tools = llm.bind_tools(RESEARCH_TOOLS)
    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
    }


def research_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in research sub-graph."""
    if state.get("error_count", 0) >= 3:
        return "research_reflection_gate"
    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < 8
    ):
        if any(tc["name"] in RESEARCH_DESTRUCTIVE_TOOLS for tc in last.tool_calls):
            return "research_interrupt_node"
        return "research_tool_node"
    return "research_reflection_gate"


async def research_interrupt_node(state: AgentState, config: RunnableConfig) -> dict:
    """Pause for user confirmation before executing destructive research tools."""
    last = state["messages"][-1]
    tool_names = [tc["name"] for tc in last.tool_calls if tc["name"] in RESEARCH_DESTRUCTIVE_TOOLS]
    interrupt({"pending_tools": tool_names, "message": f"Confirm: {', '.join(tool_names)}?"})
    return {}


def research_after_interrupt(state: AgentState) -> str:
    if state.get("user_confirmed", False):
        return "research_tool_node"
    return "research_reflection_gate"


def _research_reflection_route(state: AgentState) -> str:
    """Route after reflection: revise loops back to LLM, proceed exits."""
    from src.services.agent.reflection import ReflectionResult

    result: ReflectionResult | None = state.get("_reflection_result")  # type: ignore[arg-type]
    if result is None or result.passed or result.severity == "minor":
        return END
    if result.severity == "major" and state.get("reflection_count", 0) < 2:
        return "research_llm_node"
    return END


def build_research_subgraph() -> StateGraph:
    """Build the research agent sub-graph.

    Flow:
      research_planner_node -> research_llm_node -> research_should_continue ->
        | research_tool_node -> research_compactor_node -> research_llm_node (loop)
        | research_reflection_gate -> END (or revise -> research_llm_node)
    """
    from src.services.agent.graph import make_filtered_tool_node

    RESEARCH_TOOL_NAMES = {t.name for t in RESEARCH_TOOLS}
    filtered_tool = make_filtered_tool_node(RESEARCH_TOOL_NAMES)

    # Create v2 nodes
    planner = make_planner_node(RESEARCH_TOOL_NAMES_LIST)
    compactor = make_compactor_node()
    reflection_node, _reflection_route = make_reflection_gate(
        intent_filter={"research"},
    )

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("research_planner_node", planner)
    graph.add_node("research_llm_node", research_llm_node)
    graph.add_node("research_tool_node", filtered_tool)
    graph.add_node("research_interrupt_node", research_interrupt_node)
    graph.add_node("research_compactor_node", compactor)
    graph.add_node("research_reflection_gate", reflection_node)

    # Edges
    graph.set_entry_point("research_planner_node")
    graph.add_edge("research_planner_node", "research_llm_node")

    graph.add_conditional_edges(
        "research_llm_node",
        research_should_continue,
        {
            "research_tool_node": "research_tool_node",
            "research_interrupt_node": "research_interrupt_node",
            "research_reflection_gate": "research_reflection_gate",
        },
    )

    graph.add_conditional_edges(
        "research_interrupt_node",
        research_after_interrupt,
        {
            "research_tool_node": "research_tool_node",
            "research_reflection_gate": "research_reflection_gate",
        },
    )

    graph.add_edge("research_tool_node", "research_compactor_node")
    graph.add_edge("research_compactor_node", "research_llm_node")

    graph.add_conditional_edges(
        "research_reflection_gate",
        _research_reflection_route,
        {
            END: END,
            "research_llm_node": "research_llm_node",
        },
    )

    return graph
