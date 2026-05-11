"""Research Agent sub-graph.

Specialized for paper discovery, search, and ingestion tasks.
Tools: search_arxiv, ingest_arxiv_papers, search_documents,
       create_project, add_document_to_project, list_project_documents
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
    add_document_to_project,
    create_project,
    do_kb_retrieve,
    ingest_arxiv_papers,
    list_project_documents,
    list_projects,
    search_arxiv,
    search_documents,
)

logger = logging.getLogger(__name__)

RESEARCH_TOOLS = [
    search_arxiv,
    ingest_arxiv_papers,
    search_documents,
    do_kb_retrieve,
    create_project,
    list_projects,
    add_document_to_project,
    list_project_documents,
]

RESEARCH_TOOL_NAMES_LIST = [t.name for t in RESEARCH_TOOLS]

# Lowered from 8 after trace 019e18f0 showed a 4-round runaway tool fan-out
# (13+ search_arxiv calls, 95s wall). Five iterations is enough for a search →
# refine → ingest → list → confirm sequence; anything more is the agent
# refining queries the user did not ask for.
MAX_RESEARCH_TOOL_LOOPS = 5


def _build_research_system_prompt() -> str:
    """Construct the research subgraph system prompt with shared rules embedded.

    Imported lazily to avoid circular imports with graph.py.
    """
    from src.services.agent.graph import SHARED_AGENT_RULES

    return (
        "You are a research assistant focused on discovering, searching, "
        "and organizing academic papers and documents.\n\n"
        "Your tools:\n"
        "- search_arxiv: Find papers on arXiv\n"
        "- ingest_arxiv_papers: Import papers into the platform\n"
        "- search_documents: Search indexed documents by title/filename\n"
        "- do_kb_retrieve: Semantic retrieval over the org's knowledge base "
        "(use for content-level questions across documents)\n"
        "- create_project: Create a new research project (folder). Requires a name; "
        "description/research_goals/tags are optional\n"
        "- add_document_to_project: Organize documents into projects\n"
        "- list_project_documents: View project contents\n\n"
        "Important: After importing papers, use the document_ids (UUIDs) from the "
        "response — not arXiv paper IDs.\n\n"
        f"{SHARED_AGENT_RULES}\n\n"
        "Be thorough in searching and systematic in organizing research."
    )


RESEARCH_DESTRUCTIVE_TOOLS = {
    "ingest_arxiv_papers",
    "add_document_to_project",
    "create_project",
    "execute_code",
}


async def research_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Research-specialized LLM node."""
    from src.core.config import get_settings
    from src.services.agent.graph import _build_llm

    sanitized = _sanitize_messages(list(state["messages"]))
    messages = [SystemMessage(content=_build_research_system_prompt())] + sanitized

    llm = _build_llm()
    # See graph.llm_node for rationale on parallel_tool_calls=False.
    llm_with_tools = llm.bind_tools(
        RESEARCH_TOOLS,
        parallel_tool_calls=get_settings().AGENT_PARALLEL_TOOL_CALLS,
    )
    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
    }


def research_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in research sub-graph."""
    if state.get("error_count", 0) >= 3:
        return "research_reflection_gate"
    last = state["messages"][-1] if state["messages"] else None
    if isinstance(last, AIMessage) and last.tool_calls:
        if state.get("tool_loop_count", 0) < MAX_RESEARCH_TOOL_LOOPS:
            if any(tc["name"] in RESEARCH_DESTRUCTIVE_TOOLS for tc in last.tool_calls):
                return "research_interrupt_node"
            return "research_tool_node"
        # Loop ceiling tripped while the model still wants more tools. Route
        # to a forced-synthesis turn so the final AIMessage has real content
        # — otherwise reflection sees empty content + unanswered tool_calls
        # and flags a "no response" major issue (trace 019e1903).
        return "research_force_synthesis_node"
    return "research_reflection_gate"


async def research_force_synthesis_node(
    state: AgentState, config: RunnableConfig
) -> dict:
    """Final-answer LLM call when the tool-loop ceiling was hit.

    The model has fired ``MAX_RESEARCH_TOOL_LOOPS`` tool calls and still
    wants more. We strip the unanswered tool_calls, append a directive
    to synthesize from prior tool results, and re-invoke the LLM with NO
    tools bound so it must produce text. This guarantees a non-empty
    final AIMessage even when the model would otherwise spin.
    """
    from src.services.agent.graph import _build_llm

    messages = list(state["messages"])

    # Drop the trailing AIMessage with unanswered tool_calls so the model
    # sees a clean conversational head when synthesizing.
    while messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        messages.pop()

    sanitized = _sanitize_messages(messages)
    directive = SystemMessage(
        content=(
            f"You ran {state.get('tool_loop_count', 0)} tool calls and reached "
            "the per-turn search budget. Do NOT request more tools. Synthesize "
            "the final answer from the tool results already in the conversation "
            "above — list the most relevant papers (id, title, year, one-line "
            "summary) and end with a clear next-step suggestion."
        )
    )
    full = [SystemMessage(content=_build_research_system_prompt()), directive] + sanitized

    llm = _build_llm()
    # No bind_tools — force a pure text response.
    response = await llm.ainvoke(full, config=config)

    return {"messages": [response]}


async def research_interrupt_node(state: AgentState, config: RunnableConfig) -> dict:
    """Pause for user confirmation before executing destructive research tools."""
    last = state["messages"][-1] if state.get("messages") else None
    if not isinstance(last, AIMessage) or not getattr(last, "tool_calls", None):
        # Defensive guard — should_continue routes here only when the
        # last message is an AIMessage with tool_calls, but a stale
        # checkpoint or an out-of-order edge could violate that contract.
        return {"pending_confirmation": {}, "user_confirmed": False}
    destructive_calls = [
        tc for tc in last.tool_calls if tc["name"] in RESEARCH_DESTRUCTIVE_TOOLS
    ]
    tool_names = [tc["name"] for tc in destructive_calls]

    confirmation_details = {
        "pending_tools": tool_names,
        "tools": [{"name": tc["name"], "args": tc["args"]} for tc in destructive_calls],
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
    graph.add_node("research_force_synthesis_node", research_force_synthesis_node)
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
            "research_force_synthesis_node": "research_force_synthesis_node",
            "research_reflection_gate": "research_reflection_gate",
        },
    )

    # Forced synthesis always goes to reflection (it produced a final answer).
    graph.add_edge("research_force_synthesis_node", "research_reflection_gate")

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
