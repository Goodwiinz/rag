"""Research Agent sub-graph.

Specialized for paper discovery, search, and ingestion tasks.
Tools: search_arxiv, ingest_arxiv_papers, search_documents,
       add_document_to_project, list_project_documents
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.services.agent.state import AgentState
from src.services.agent.tools import (
    add_document_to_project,
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
    add_document_to_project,
    list_project_documents,
]

RESEARCH_SYSTEM_PROMPT = (
    "You are a specialized Research Agent focused on discovering, searching, "
    "and organizing academic papers and documents.\n\n"
    "Your tools:\n"
    "- search_arxiv: Find papers on arXiv\n"
    "- ingest_arxiv_papers: Import papers into the RAG system\n"
    "- search_documents: Search indexed documents\n"
    "- add_document_to_project: Organize documents into projects\n"
    "- list_project_documents: View project contents\n\n"
    "CRITICAL: After ingesting papers, use the document_ids (UUIDs) from the "
    "ingest response — NOT arXiv paper IDs.\n"
    "Be thorough in searching and systematic in organizing research."
)


async def research_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Research-specialized LLM node."""
    from src.services.agent.graph import _build_llm

    messages = [SystemMessage(content=RESEARCH_SYSTEM_PROMPT)] + list(state["messages"])

    llm = _build_llm()
    llm_with_tools = llm.bind_tools(RESEARCH_TOOLS)
    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
    }


def research_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in research sub-graph."""
    if state.get("error_count", 0) >= 3:
        return END
    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < 8
    ):
        return "research_tool_node"
    return END


def build_research_subgraph() -> StateGraph:
    """Build the research agent sub-graph."""
    from src.services.agent.graph import make_filtered_tool_node

    RESEARCH_TOOL_NAMES = {t.name for t in RESEARCH_TOOLS}
    filtered_tool = make_filtered_tool_node(RESEARCH_TOOL_NAMES)

    graph = StateGraph(AgentState)
    graph.add_node("research_llm_node", research_llm_node)
    graph.add_node("research_tool_node", filtered_tool)

    graph.set_entry_point("research_llm_node")
    graph.add_conditional_edges(
        "research_llm_node",
        research_should_continue,
        {"research_tool_node": "research_tool_node", END: END},
    )
    graph.add_edge("research_tool_node", "research_llm_node")

    return graph
