"""LangGraph agent graph definition.

Builds a ``StateGraph`` that chains:
  START -> rag_node -> llm_node -> [conditional] -> tool_node -> llm_node (loop) | END
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.core.config import get_settings
from src.services.agent.state import AgentState
from src.services.agent.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

MAX_TOOL_LOOPS = 10


# ---------------------------------------------------------------------------
# LLM construction
# ---------------------------------------------------------------------------


def _is_openai_compatible(endpoint: str) -> bool:
    """Mirror the check used by the existing AzureOpenAIService."""
    return "/v1" in endpoint or "services.ai.azure.com" in endpoint


def _build_llm():
    """Build a LangChain chat model from the existing Azure/OpenAI config."""
    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = (
        settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    )
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )
    deployment = (
        settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
        or settings.AZURE_OPENAI_DEPLOYMENT_NAME
        or "gpt-4o"
    )

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    if _is_openai_compatible(endpoint):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=deployment,
            api_key=api_key,
            base_url=endpoint,
            temperature=0.7,
            max_tokens=2048,
        )
    else:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment=deployment,
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            temperature=0.7,
            max_tokens=2048,
        )


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


async def rag_node(state: AgentState, config: RunnableConfig) -> dict:
    """Retrieve relevant documents via hybrid search and store in state."""
    configurable = config.get("configurable", {})
    current_user = configurable.get("current_user")

    # Find the last user message to use as search query
    last_user_msg: Optional[str] = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    if not last_user_msg or not current_user:
        return {"retrieved_contexts": []}

    try:
        from src.models.search_schemas import SearchQuery
        from src.services.search.hybrid_search_service import hybrid_search_service

        search_request = SearchQuery(
            query=last_user_msg,
            limit=5,
            search_type="hybrid",
        )

        loop = asyncio.get_running_loop()
        org_id = (
            str(current_user.organization_id)
            if current_user.organization_id
            else None
        )
        uid = str(current_user.id)

        search_response = await loop.run_in_executor(
            None,
            lambda: hybrid_search_service.search(
                search_request=search_request,
                user_id=uid,
                organization_id=org_id,
            ),
        )

        contexts: List[dict] = []
        for i, result in enumerate(search_response.results[:5]):
            doc_id = getattr(result, "document_id", None)
            title = getattr(result, "title", "Untitled") or f"Document {i + 1}"

            metadata = getattr(result, "metadata", {}) or {}
            content = metadata.get("full_text") or metadata.get("text", "")
            if not content:
                content = getattr(result, "content_preview", None)
            if not content:
                content = getattr(result, "content", "")
            if content is None:
                content = ""

            score = getattr(result, "relevance_score", 0.0)
            contexts.append(
                {
                    "document_id": str(doc_id) if doc_id else None,
                    "title": title,
                    "content": content[:3000],
                    "score": float(score),
                }
            )

        return {"retrieved_contexts": contexts}

    except Exception as e:
        logger.warning("RAG retrieval failed, proceeding without context", exc_info=e)
        return {"retrieved_contexts": []}


async def llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Call the LLM with system prompt, RAG context, and bound tools."""
    page_context = state.get("page_context", {})
    retrieved = state.get("retrieved_contexts", [])

    # Build system prompt
    context_line = ""
    page_type = page_context.get("type", "unknown")
    project_id = page_context.get("project_id")
    if page_type == "project" and project_id:
        context_line = f"The user is viewing a project (ID: {project_id})."
    elif page_type != "unknown":
        context_line = f"The user is on the {page_type} page."

    system_text = (
        "You are an AI research agent for a RAG-powered academic research system.\n"
        "You help users search documents, manage research projects, find ArXiv papers, "
        "create notes, and analyze research.\n\n"
        "You have access to the following tools:\n"
        "- **search_arxiv**: Search arXiv for academic papers.\n"
        "- **ingest_arxiv_papers**: Ingest arXiv papers into the RAG system.\n"
        "- **search_documents**: Search the user's indexed documents.\n"
        "- **add_document_to_project**: Add an existing document to a project.\n"
        "- **create_project_note**: Create a markdown note in a project.\n"
        "- **list_project_documents**: List all documents in a project.\n\n"
        f"{context_line}\n"
        "When the user is on a project page, the project_id is available from the "
        "page context and does not need to be asked for.\n\n"
        "When answering questions, use retrieved document context when available.\n"
        "Cite sources using [Doc N] format inline.\n"
        "Be concise and action-oriented."
    )

    if retrieved:
        context_text = "\n\n".join(
            f"[Doc {i + 1}] {ctx['title']}:\n{ctx['content']}"
            for i, ctx in enumerate(retrieved)
        )
        system_text += f"\n\nRetrieved context:\n{context_text}"

    # Build messages list: system + conversation messages
    messages = [SystemMessage(content=system_text)] + list(state["messages"])

    llm = _build_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
        "tool_loop_count": state.get("tool_loop_count", 0) + 1,
    }


async def tool_node(state: AgentState, config: RunnableConfig) -> dict:
    """Execute tool calls from the last AIMessage."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": [], "tool_executions": []}

    tools_by_name = {t.name: t for t in ALL_TOOLS}
    tool_messages: List[ToolMessage] = []
    tool_executions: List[dict] = list(state.get("tool_executions", []))

    for tc in last_message.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_call_id = tc["id"]

        t0 = time.monotonic()
        try:
            tool_fn = tools_by_name.get(tool_name)
            if not tool_fn:
                result_content = json.dumps({"error": f"Unknown tool: {tool_name}"})
                status = "failed"
            else:
                result = await tool_fn.ainvoke(tool_args, config=config)
                result_content = (
                    json.dumps(result) if isinstance(result, dict) else str(result)
                )
                status = "failed" if isinstance(result, dict) and "error" in result else "completed"
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e, exc_info=True)
            result_content = json.dumps({"error": str(e)})
            status = "failed"

        duration_ms = int((time.monotonic() - t0) * 1000)

        tool_messages.append(
            ToolMessage(content=result_content, tool_call_id=tool_call_id)
        )
        tool_executions.append(
            {
                "id": tool_call_id,
                "tool_name": tool_name,
                "tool_display_name": tool_name.replace("_", " ").title(),
                "args": tool_args,
                "status": status,
                "result": json.loads(result_content),
                "duration_ms": duration_ms,
            }
        )

    return {"messages": tool_messages, "tool_executions": tool_executions}


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------


def should_continue(state: AgentState) -> str:
    """Decide whether to route to tool_node or end."""
    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < MAX_TOOL_LOOPS
    ):
        return "tool_node"
    return END


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def build_agent_graph() -> StateGraph:
    """Build the uncompiled agent state graph."""
    graph = StateGraph(AgentState)

    graph.add_node("rag_node", rag_node)
    graph.add_node("llm_node", llm_node)
    graph.add_node("tool_node", tool_node)

    graph.set_entry_point("rag_node")
    graph.add_edge("rag_node", "llm_node")
    graph.add_conditional_edges("llm_node", should_continue, {"tool_node": "tool_node", END: END})
    graph.add_edge("tool_node", "llm_node")

    return graph


def compile_agent_graph(checkpointer=None):
    """Compile the agent graph, optionally with a checkpointer."""
    graph = build_agent_graph()
    return graph.compile(checkpointer=checkpointer)
