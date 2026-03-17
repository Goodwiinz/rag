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
from langgraph.types import RetryPolicy, interrupt, Command

from src.core.config import get_settings
from src.services.agent.observability import track_node_execution
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
# Memory nodes
# ---------------------------------------------------------------------------


@track_node_execution("memory_retrieval_node")
async def memory_retrieval_node(state: AgentState, config: RunnableConfig) -> dict:
    """Retrieve relevant long-term memories before the LLM call."""
    configurable = config.get("configurable", {})
    current_user = configurable.get("current_user")

    if not current_user:
        return {"user_memories": []}

    try:
        from src.services.agent.memory import get_memory_store, search_memories

        store = await get_memory_store()
        if not store:
            return {"user_memories": []}

        # Find the last user message for memory search
        last_user_msg = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_user_msg = msg.content
                break

        if not last_user_msg:
            return {"user_memories": []}

        memories = await search_memories(
            store, str(current_user.id), last_user_msg, limit=5
        )
        return {"user_memories": memories}
    except Exception as e:
        logger.warning("Memory retrieval failed: %s", e)
        return {"user_memories": []}


@track_node_execution("memory_save_node")
async def memory_save_node(state: AgentState, config: RunnableConfig) -> dict:
    """Save relevant information from the conversation to long-term memory."""
    configurable = config.get("configurable", {})
    current_user = configurable.get("current_user")

    if not current_user:
        return {}

    try:
        from src.services.agent.memory import get_memory_store, save_memory

        store = await get_memory_store()
        if not store:
            return {}

        # Extract the last assistant message for memory
        last_ai_content = ""
        last_user_content = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content and not last_ai_content:
                last_ai_content = msg.content
            if isinstance(msg, HumanMessage) and not last_user_content:
                last_user_content = msg.content
            if last_ai_content and last_user_content:
                break

        if not last_user_content:
            return {}

        # Save a condensed memory of the interaction
        import hashlib

        mem_key = hashlib.md5(
            last_user_content[:100].encode(), usedforsecurity=False
        ).hexdigest()[:12]

        await save_memory(
            store,
            str(current_user.id),
            mem_key,
            {
                "query": last_user_content[:200],
                "intent": state.get("intent", "general"),
                "tools_used": [
                    te.get("tool_name", "")
                    for te in state.get("tool_executions", [])[-3:]
                ],
            },
        )
        return {}
    except Exception as e:
        logger.warning("Memory save failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


@track_node_execution("rag_node")
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


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

INTENT_KEYWORDS = {
    "research": {"search", "find", "arxiv", "paper", "papers", "look up", "discover", "ingest", "import"},
    "writing": {"write", "draft", "note", "summarize", "summary", "create note", "literature review", "export", "bibliography", "cite"},
    "knowledge_graph": {"entity", "entities", "knowledge graph", "relationship", "graph", "extract entities", "concept", "ontology"},
}


@track_node_execution("intent_classifier_node")
async def intent_classifier_node(state: AgentState, config: RunnableConfig) -> dict:
    """Classify user intent to route to specialized LLM prompts."""
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content.lower()
            break

    if not last_user_msg:
        return {"intent": "general"}

    # Simple keyword-based classification
    scores = {intent: 0 for intent in INTENT_KEYWORDS}
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in last_user_msg:
                scores[intent] += 1

    best_intent = max(scores, key=lambda k: scores[k])
    if scores[best_intent] == 0:
        best_intent = "general"

    logger.debug("Classified intent: %s (scores: %s)", best_intent, scores)
    return {"intent": best_intent}


def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate sub-graph based on classified intent."""
    intent = state.get("intent", "general")
    if intent == "research":
        return "research_subgraph"
    if intent == "writing":
        return "writing_subgraph"
    if intent == "knowledge_graph":
        return "data_subgraph"
    return "llm_node"


# ---------------------------------------------------------------------------
# Intent-specific tool subsets and prompt augmentations
# ---------------------------------------------------------------------------

RESEARCH_TOOLS_NAMES = {
    "search_arxiv", "ingest_arxiv_papers", "search_documents",
    "add_document_to_project", "list_project_documents",
}
WRITING_TOOLS_NAMES = {
    "create_draft", "create_project_note", "export_bibliography",
    "summarize_document", "compare_documents",
}
KG_TOOLS_NAMES = {
    "extract_entities", "search_knowledge_graph", "search_documents",
}

INTENT_PROMPTS = {
    "research": (
        "Focus on helping the user find, discover, and organize research papers. "
        "Prefer search_arxiv for finding papers, and search_documents for local documents."
    ),
    "writing": (
        "Focus on helping the user write, summarize, and synthesize content. "
        "Use summarize_document, compare_documents, create_draft, and export_bibliography."
    ),
    "knowledge_graph": (
        "Focus on extracting and exploring entities and relationships. "
        "Use extract_entities and search_knowledge_graph to help the user understand connections."
    ),
    "general": "Use any tools as appropriate to help the user.",
}


def _get_tools_for_intent(intent: str) -> list:
    """Return the tool subset for a given intent."""
    name_set = {
        "research": RESEARCH_TOOLS_NAMES,
        "writing": WRITING_TOOLS_NAMES,
        "knowledge_graph": KG_TOOLS_NAMES,
    }.get(intent)

    if name_set is None:
        return ALL_TOOLS

    return [t for t in ALL_TOOLS if t.name in name_set]


@track_node_execution("llm_node")
async def llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Call the LLM with system prompt, RAG context, and bound tools."""
    page_context = state.get("page_context", {})
    retrieved = state.get("retrieved_contexts", [])

    # Build system prompt with rich page context
    context_line = ""
    page_type = page_context.get("type", "unknown")
    project_id = page_context.get("project_id")
    project_name = page_context.get("project_name", "")
    page_label = page_context.get("label", "")
    page_metadata = page_context.get("metadata") or {}
    active_tab = page_metadata.get("activeTab", "")

    if page_type == "project" and project_id:
        context_line = f'The user is viewing the project "{project_name}" (ID: {project_id}).'
        if active_tab:
            context_line += f" They are currently on the {active_tab} tab."
        doc_count = page_metadata.get("documentCount")
        if doc_count is not None:
            context_line += f" The project has {doc_count} documents."
        description = page_metadata.get("description")
        if description:
            context_line += f' Project description: "{description}".'
        context_line += (
            "\nWhen the user refers to 'this project' or 'my project', use this project_id. "
            "Do NOT ask for the project ID — you already have it."
        )
    elif page_type != "unknown":
        context_line = f"The user is on the {page_label or page_type} page."

    system_text = (
        "You are an AI research agent for a RAG-powered academic research system.\n"
        "You help users search documents, manage research projects, find ArXiv papers, "
        "create notes, and analyze research.\n\n"
        "You have access to the following tools:\n"
        "- **search_arxiv**: Search arXiv for academic papers.\n"
        "- **ingest_arxiv_papers**: Ingest arXiv papers into the RAG system.\n"
        "- **search_documents**: Search the user's indexed documents.\n"
        "- **add_document_to_project**: Add an existing document to a project. "
        "IMPORTANT: document_id must be a UUID from `document_ids` in the ingest response, NOT an arXiv paper ID.\n"
        "- **create_project_note**: Create a markdown note in a project.\n"
        "- **list_project_documents**: List all documents in a project.\n"
        "- **summarize_document**: Summarize a document's content (requires document UUID).\n"
        "- **compare_documents**: Compare 2-5 documents to find similarities, differences, and themes.\n"
        "- **extract_entities**: Extract named entities (people, organizations, concepts) from a document.\n"
        "- **search_knowledge_graph**: Search the knowledge graph for entities and relationships.\n"
        "- **create_draft**: Generate a literature review draft from project documents around specific themes.\n"
        "- **export_bibliography**: Export bibliography for documents in bibtex, apa, ieee, or mla format.\n\n"
        f"{context_line}\n"
        "When the user is on a project page, the project_id is available from the "
        "page context and does not need to be asked for.\n\n"
        "CRITICAL: After ingesting papers, use the `document_ids` (UUIDs) from the ingest response "
        "when calling add_document_to_project — NOT the arXiv paper IDs.\n\n"
        "When answering questions, use retrieved document context when available.\n"
        "Cite sources using [Doc N] format inline.\n"
        "Be concise and action-oriented."
    )

    # Add intent-specific prompt augmentation
    intent = state.get("intent", "general")
    intent_guidance = INTENT_PROMPTS.get(intent, INTENT_PROMPTS["general"])
    system_text += f"\n\nCurrent intent: {intent}. {intent_guidance}"

    # Inject user memories if available
    user_memories = state.get("user_memories", [])
    if user_memories:
        mem_text = "\n".join(
            f"- {m.get('value', {}).get('query', '')}" for m in user_memories if m.get("value")
        )
        if mem_text.strip():
            system_text += f"\n\nRelevant past interactions:\n{mem_text}"

    if retrieved:
        context_text = "\n\n".join(
            f"[Doc {i + 1}] {ctx['title']}:\n{ctx['content']}"
            for i, ctx in enumerate(retrieved)
        )
        system_text += f"\n\nRetrieved context:\n{context_text}"

    # Build messages list: system + conversation messages
    # Sanitize: ensure every AIMessage with tool_calls has matching ToolMessages
    raw_messages = list(state["messages"])
    sanitized: list = []
    for msg in raw_messages:
        sanitized.append(msg)
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            # Collect tool_call IDs from this message
            expected_ids = {tc["id"] for tc in msg.tool_calls}
            # Look ahead for matching ToolMessages already in the list
            answered_ids: set = set()
            for future_msg in raw_messages[raw_messages.index(msg) + 1:]:
                if isinstance(future_msg, ToolMessage):
                    answered_ids.add(future_msg.tool_call_id)
                elif isinstance(future_msg, (AIMessage, HumanMessage)):
                    break
            # Add placeholder ToolMessages for any unanswered tool_calls
            for tc in msg.tool_calls:
                if tc["id"] not in answered_ids:
                    sanitized.append(
                        ToolMessage(
                            content='{"status": "skipped"}',
                            tool_call_id=tc["id"],
                        )
                    )

    messages = [SystemMessage(content=system_text)] + sanitized

    # Bind intent-specific tool subset
    intent_tools = _get_tools_for_intent(intent)

    llm = _build_llm()
    llm_with_tools = llm.bind_tools(intent_tools)
    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
        "tool_loop_count": state.get("tool_loop_count", 0) + 1,
    }


DESTRUCTIVE_TOOLS = {
    "ingest_arxiv_papers",
    "add_document_to_project",
    "create_project_note",
    "create_draft",
}


@track_node_execution("interrupt_node")
async def interrupt_node(state: AgentState, config: RunnableConfig) -> dict:
    """Check if pending tool calls are destructive and interrupt for confirmation."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {}

    destructive_calls = [
        tc for tc in last_message.tool_calls if tc["name"] in DESTRUCTIVE_TOOLS
    ]

    if not destructive_calls:
        return {"pending_confirmation": {}, "user_confirmed": True}

    confirmation_details = {
        "tools": [
            {"name": tc["name"], "args": tc["args"]} for tc in destructive_calls
        ],
        "message": f"The agent wants to execute {len(destructive_calls)} action(s) that modify your data. Please confirm.",
    }

    # LangGraph interrupt — pauses graph, saves state, returns to caller
    user_response = interrupt(confirmation_details)

    if user_response and user_response.get("confirmed"):
        return {"pending_confirmation": {}, "user_confirmed": True}

    # User denied — add a message explaining and skip tool execution
    return {
        "messages": [
            AIMessage(content="Action cancelled by user. Let me know if you'd like to proceed differently."),
        ],
        "pending_confirmation": {},
        "user_confirmed": False,
    }


TOOL_TIMEOUT_SECONDS = 30
_TOOL_SEMAPHORE = asyncio.Semaphore(3)


def _record_tool_metrics(tool_name: str, status: str):
    """Record tool call metrics if observability is available."""
    try:
        from src.services.agent.observability import record_tool_call

        record_tool_call(tool_name, status)
    except Exception:
        pass


async def _execute_single_tool(
    tc: dict,
    config: RunnableConfig,
    page_context: dict,
) -> dict:
    """Execute a single tool call with timeout and error handling."""
    from src.api.agent.execute import execute_tool

    tool_name = tc["name"]
    tool_args = dict(tc["args"])
    tool_call_id = tc["id"]

    # Auto-fill project_id from page context if not provided by LLM
    if (
        "project_id" not in tool_args
        and page_context.get("type") == "project"
        and page_context.get("project_id")
    ):
        tool_args["project_id"] = page_context["project_id"]

    t0 = time.monotonic()
    error_increment = 0
    error_text = ""

    async with _TOOL_SEMAPHORE:
        try:
            configurable = config.get("configurable", {})
            result = await asyncio.wait_for(
                execute_tool(
                    tool_name=tool_name,
                    args=tool_args,
                    user_id=str(configurable.get("current_user").id) if configurable.get("current_user") else "",
                    db=configurable.get("db"),
                    current_user=configurable.get("current_user"),
                ),
                timeout=TOOL_TIMEOUT_SECONDS,
            )
            result_content = json.dumps(result) if isinstance(result, dict) else str(result)
            status = "failed" if isinstance(result, dict) and "error" in result else "completed"
            if status == "failed":
                error_increment = 1
                error_text = result.get("error", "") if isinstance(result, dict) else ""
        except asyncio.TimeoutError:
            logger.warning("Tool %s timed out after %ds", tool_name, TOOL_TIMEOUT_SECONDS)
            result_content = json.dumps({"error": f"Tool {tool_name} timed out after {TOOL_TIMEOUT_SECONDS}s"})
            status = "failed"
            error_increment = 1
            error_text = f"Tool {tool_name} timed out"
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e, exc_info=True)
            result_content = json.dumps({"error": str(e)})
            status = "failed"
            error_increment = 1
            error_text = str(e)

    duration_ms = int((time.monotonic() - t0) * 1000)
    _record_tool_metrics(tool_name, status)

    return {
        "message": ToolMessage(content=result_content, tool_call_id=tool_call_id),
        "execution": {
            "id": tool_call_id,
            "tool_name": tool_name,
            "tool_display_name": tool_name.replace("_", " ").title(),
            "args": tool_args,
            "status": status,
            "result": json.loads(result_content),
            "duration_ms": duration_ms,
        },
        "error_increment": error_increment,
        "error_text": error_text,
    }


@track_node_execution("tool_node")
async def tool_node(state: AgentState, config: RunnableConfig) -> dict:
    """Execute tool calls from the last AIMessage in parallel."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": [], "tool_executions": []}

    tool_executions: List[dict] = list(state.get("tool_executions", []))
    error_count = state.get("error_count", 0)
    last_error = state.get("last_error", "")
    page_context = state.get("page_context", {})

    # Execute all tool calls concurrently with semaphore limiting
    tasks = [
        _execute_single_tool(tc, config, page_context)
        for tc in last_message.tool_calls
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    tool_messages: List[ToolMessage] = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Parallel tool execution error: %s", r)
            error_count += 1
            last_error = str(r)
            continue
        tool_messages.append(r["message"])
        tool_executions.append(r["execution"])
        error_count += r["error_increment"]
        if r["error_text"]:
            last_error = r["error_text"]

    return {
        "messages": tool_messages,
        "tool_executions": tool_executions,
        "error_count": error_count,
        "last_error": last_error,
    }


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------


MAX_ERRORS = 3


def should_continue(state: AgentState) -> str:
    """Decide whether to route to tool_node, interrupt_node, or memory_save_node (then END)."""
    # Bail out if too many errors have accumulated
    if state.get("error_count", 0) >= MAX_ERRORS:
        logger.warning(
            "Agent reached max error count (%d), stopping. Last error: %s",
            MAX_ERRORS,
            state.get("last_error", ""),
        )
        return "memory_save_node"

    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < MAX_TOOL_LOOPS
    ):
        # Check if any tool call is destructive — route through interrupt
        has_destructive = any(
            tc["name"] in DESTRUCTIVE_TOOLS for tc in last.tool_calls
        )
        if has_destructive:
            return "interrupt_node"
        return "tool_node"
    return "memory_save_node"


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def after_interrupt(state: AgentState) -> str:
    """Route after interrupt: proceed to tool_node if confirmed, else save memory and end."""
    if state.get("user_confirmed", False):
        return "tool_node"
    return "memory_save_node"


_RETRY_POLICY = RetryPolicy(max_attempts=3)


def build_agent_graph() -> StateGraph:
    """Build the uncompiled agent state graph.

    Flow:
      START → rag_node → intent_classifier_node → memory_retrieval_node
        → [route_by_intent] → research_subgraph | writing_subgraph | data_subgraph | llm_node
      llm_node → [should_continue] → tool_node | interrupt_node | memory_save_node
      Sub-graphs handle their own tool loops internally, then → memory_save_node → END
    """
    from src.services.agent.subgraphs.data_agent import build_data_subgraph
    from src.services.agent.subgraphs.research_agent import build_research_subgraph
    from src.services.agent.subgraphs.writing_agent import build_writing_subgraph

    graph = StateGraph(AgentState)

    graph.add_node("rag_node", rag_node, retry=_RETRY_POLICY)
    graph.add_node("intent_classifier_node", intent_classifier_node)
    graph.add_node("memory_retrieval_node", memory_retrieval_node)
    graph.add_node("llm_node", llm_node, retry=_RETRY_POLICY)
    graph.add_node("tool_node", tool_node)
    graph.add_node("interrupt_node", interrupt_node)
    graph.add_node("memory_save_node", memory_save_node)

    # Sub-graphs compiled as nodes
    graph.add_node("research_subgraph", build_research_subgraph().compile())
    graph.add_node("writing_subgraph", build_writing_subgraph().compile())
    graph.add_node("data_subgraph", build_data_subgraph().compile())

    graph.set_entry_point("rag_node")
    graph.add_edge("rag_node", "intent_classifier_node")
    graph.add_edge("intent_classifier_node", "memory_retrieval_node")

    # Route by intent after memory retrieval
    graph.add_conditional_edges(
        "memory_retrieval_node",
        route_by_intent,
        {
            "research_subgraph": "research_subgraph",
            "writing_subgraph": "writing_subgraph",
            "data_subgraph": "data_subgraph",
            "llm_node": "llm_node",
        },
    )

    # Sub-graphs complete → save memory → END
    graph.add_edge("research_subgraph", "memory_save_node")
    graph.add_edge("writing_subgraph", "memory_save_node")
    graph.add_edge("data_subgraph", "memory_save_node")

    # General path: llm_node → conditional
    graph.add_conditional_edges(
        "llm_node",
        should_continue,
        {
            "tool_node": "tool_node",
            "interrupt_node": "interrupt_node",
            "memory_save_node": "memory_save_node",
        },
    )
    graph.add_conditional_edges(
        "interrupt_node",
        after_interrupt,
        {"tool_node": "tool_node", "memory_save_node": "memory_save_node"},
    )
    graph.add_edge("tool_node", "llm_node")
    graph.add_edge("memory_save_node", END)

    return graph


def compile_agent_graph(checkpointer=None):
    """Compile the agent graph, optionally with a checkpointer."""
    graph = build_agent_graph()
    return graph.compile(checkpointer=checkpointer)
