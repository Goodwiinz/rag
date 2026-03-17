"""Data Agent sub-graph.

Specialized for entity extraction, knowledge graph exploration, and data analysis.
Tools: extract_entities, search_knowledge_graph, search_documents,
       list_project_documents
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.services.agent.state import AgentState
from src.services.agent.tools import (
    extract_entities,
    list_project_documents,
    search_documents,
    search_knowledge_graph,
)

logger = logging.getLogger(__name__)

DATA_TOOLS = [
    extract_entities,
    search_knowledge_graph,
    search_documents,
    list_project_documents,
]

DATA_SYSTEM_PROMPT = (
    "You are a specialized Data Agent focused on extracting entities, "
    "exploring knowledge graphs, and analyzing structured data from documents.\n\n"
    "Your tools:\n"
    "- extract_entities: Extract named entities from documents\n"
    "- search_knowledge_graph: Search entities and relationships\n"
    "- search_documents: Find documents to analyze\n"
    "- list_project_documents: View project contents\n\n"
    "Be analytical and thorough. Present findings in structured formats."
)


async def data_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Data-specialized LLM node."""
    from src.services.agent.graph import _build_llm

    messages = [SystemMessage(content=DATA_SYSTEM_PROMPT)] + list(state["messages"])

    llm = _build_llm()
    llm_with_tools = llm.bind_tools(DATA_TOOLS)
    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
        "tool_loop_count": state.get("tool_loop_count", 0) + 1,
    }


def data_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in data sub-graph."""
    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < 8
    ):
        return "data_tool_node"
    return END


def build_data_subgraph() -> StateGraph:
    """Build the data agent sub-graph."""
    from src.services.agent.graph import tool_node

    graph = StateGraph(AgentState)
    graph.add_node("data_llm_node", data_llm_node)
    graph.add_node("data_tool_node", tool_node)

    graph.set_entry_point("data_llm_node")
    graph.add_conditional_edges(
        "data_llm_node",
        data_should_continue,
        {"data_tool_node": "data_tool_node", END: END},
    )
    graph.add_edge("data_tool_node", "data_llm_node")

    return graph
