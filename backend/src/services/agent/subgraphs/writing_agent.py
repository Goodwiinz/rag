"""Writing Agent sub-graph.

Specialized for content creation, summarization, and bibliography tasks.
Tools: create_draft, create_project_note, export_bibliography,
       summarize_document, compare_documents
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

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

WRITING_SYSTEM_PROMPT = (
    "You are a specialized Writing Agent focused on creating content, "
    "summarizing documents, and managing bibliographies.\n\n"
    "Your tools:\n"
    "- summarize_document: Create summaries of documents\n"
    "- compare_documents: Compare multiple documents\n"
    "- create_draft: Generate literature review drafts\n"
    "- create_project_note: Write notes in projects\n"
    "- export_bibliography: Export citations in various formats\n\n"
    "Write clearly and academically. Cite sources when available."
)


async def writing_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Writing-specialized LLM node."""
    from src.services.agent.graph import _build_llm

    messages = [SystemMessage(content=WRITING_SYSTEM_PROMPT)] + list(state["messages"])

    llm = _build_llm()
    llm_with_tools = llm.bind_tools(WRITING_TOOLS)
    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
    }


def writing_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in writing sub-graph."""
    if state.get("error_count", 0) >= 3:
        return END
    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < 8
    ):
        return "writing_tool_node"
    return END


def build_writing_subgraph() -> StateGraph:
    """Build the writing agent sub-graph."""
    from src.services.agent.graph import make_filtered_tool_node

    WRITING_TOOL_NAMES = {t.name for t in WRITING_TOOLS}
    filtered_tool = make_filtered_tool_node(WRITING_TOOL_NAMES)

    graph = StateGraph(AgentState)
    graph.add_node("writing_llm_node", writing_llm_node)
    graph.add_node("writing_tool_node", filtered_tool)

    graph.set_entry_point("writing_llm_node")
    graph.add_conditional_edges(
        "writing_llm_node",
        writing_should_continue,
        {"writing_tool_node": "writing_tool_node", END: END},
    )
    graph.add_edge("writing_tool_node", "writing_llm_node")

    return graph
