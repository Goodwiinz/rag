# LangGraph Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the manual tool-calling loop in the agent endpoint with a LangGraph StateGraph that supports multi-step reasoning, conditional routing, PostgreSQL checkpointing, and async job execution.

**Architecture:** LangGraph `StateGraph` with 3 nodes (rag_node, llm_node, tool_node) and conditional edges. Async job system via in-memory dict with background tasks. Tools repackaged as `@tool` decorated functions. AzureChatOpenAI for LLM.

**Tech Stack:** LangGraph 0.4+, langchain-openai, langchain-core, langgraph-checkpoint-postgres, FastAPI BackgroundTasks

**Design doc:** `docs/plans/2026-03-16-langgraph-agent-design.md`

---

## Task 1: Install Dependencies

**Files:**

- Modify: `backend/requirements.txt`

**Step 1: Add LangGraph packages**

Append to `backend/requirements.txt`:

```
# LangGraph agent
langgraph>=0.4,<2.0
langchain-openai>=0.3,<1.0
langchain-core>=0.3,<1.0
langgraph-checkpoint-postgres>=0.1,<1.0
```

**Step 2: Install in Docker**

Run: `docker compose -f docker-compose.development.yml build backend`
Then: `docker compose -f docker-compose.development.yml up -d backend`
Verify: `docker exec rag_system-backend-1 pip show langgraph` shows version

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add langgraph, langchain-openai, langchain-core, langgraph-checkpoint-postgres"
```

---

## Task 2: Create Agent State Schema

**Files:**

- Create: `backend/src/services/agent/__init__.py`
- Create: `backend/src/services/agent/state.py`

**Step 1: Create module init**

```python
# backend/src/services/agent/__init__.py
"""LangGraph agent service."""
```

**Step 2: Create state schema**

```python
# backend/src/services/agent/state.py
"""Agent state schema for LangGraph."""

from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """State that flows through the agent graph."""
    # LangGraph message accumulator — automatically merges message lists
    messages: Annotated[list, add_messages]
    # Page context from the frontend (type, project_id, etc.)
    page_context: dict
    # RAG retrieved contexts for citations
    retrieved_contexts: list
    # Tool execution records for frontend display
    tool_executions: list
    # Active thread ID for persistence
    thread_id: str
    # Loop counter to prevent infinite tool loops
    tool_loop_count: int
```

**Step 3: Commit**

```bash
git add backend/src/services/agent/
git commit -m "feat(langgraph): add AgentState schema"
```

---

## Task 3: Repackage Tools for LangGraph

**Files:**

- Create: `backend/src/services/agent/tools.py`

**Step 1: Create tool wrappers**

Each tool is a `@tool` decorated async function that reads `db` and `current_user` from `RunnableConfig`. The actual logic delegates to the existing `_tool_*` functions in `execute.py`.

```python
# backend/src/services/agent/tools.py
"""Agent tools wrapped for LangGraph."""

import logging
from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_context(config: RunnableConfig):
    """Extract db, current_user, and page_context from RunnableConfig."""
    configurable = config.get("configurable", {})
    return (
        configurable.get("db"),
        configurable.get("current_user"),
        configurable.get("page_context", {}),
    )


@tool
async def search_arxiv(
    query: str,
    max_results: int = 5,
    categories: Optional[list[str]] = None,
    config: RunnableConfig = None,
) -> dict:
    """Search arXiv for academic papers. Use when the user asks to find research papers or scientific articles."""
    from src.api.agent.execute import _tool_search_arxiv
    return await _tool_search_arxiv({
        "query": query,
        "max_results": max_results,
        "categories": categories,
    })


@tool
async def ingest_arxiv_papers(
    paper_ids: list[str],
    config: RunnableConfig = None,
) -> dict:
    """Ingest arXiv papers into the RAG system. Use when the user wants to download and index specific arXiv papers."""
    from src.api.agent.execute import _tool_ingest_arxiv
    db, current_user, _ = _get_context(config)
    user_id = str(current_user.id) if current_user else ""
    return await _tool_ingest_arxiv(
        {"paper_ids": paper_ids}, user_id, db, current_user
    )


@tool
async def search_documents(
    query: str,
    max_results: int = 10,
    config: RunnableConfig = None,
) -> dict:
    """Search the user's indexed documents by title or content. Use when the user wants to find documents they already have."""
    from src.api.agent.execute import _tool_search_documents
    db, current_user, _ = _get_context(config)
    return await _tool_search_documents(
        {"query": query, "max_results": max_results}, db, current_user
    )


@tool
async def add_document_to_project(
    document_id: str,
    project_id: str = "",
    config: RunnableConfig = None,
) -> dict:
    """Add an existing document to a research project. Uses current project from page context if project_id not provided."""
    from src.api.agent.execute import _tool_add_document_to_project
    db, current_user, page_ctx = _get_context(config)
    if not project_id and page_ctx.get("type") == "project":
        project_id = page_ctx.get("project_id", "")
    return await _tool_add_document_to_project(
        {"document_id": document_id, "project_id": project_id}, db, current_user
    )


@tool
async def create_project_note(
    title: str,
    content: str,
    project_id: str = "",
    tags: Optional[list[str]] = None,
    config: RunnableConfig = None,
) -> dict:
    """Create a markdown note in a research project. Use when the user wants to save notes, summaries, or observations."""
    from src.api.agent.execute import _tool_create_project_note
    db, current_user, page_ctx = _get_context(config)
    if not project_id and page_ctx.get("type") == "project":
        project_id = page_ctx.get("project_id", "")
    return await _tool_create_project_note(
        {"title": title, "content": content, "project_id": project_id, "tags": tags or []},
        db, current_user,
    )


@tool
async def list_project_documents(
    project_id: str = "",
    config: RunnableConfig = None,
) -> dict:
    """List all documents in a research project. Use when the user wants to see project contents."""
    from src.api.agent.execute import _tool_list_project_documents
    db, current_user, page_ctx = _get_context(config)
    if not project_id and page_ctx.get("type") == "project":
        project_id = page_ctx.get("project_id", "")
    return await _tool_list_project_documents(
        {"project_id": project_id}, db, current_user
    )


# All tools list for graph binding
ALL_TOOLS = [
    search_arxiv,
    ingest_arxiv_papers,
    search_documents,
    add_document_to_project,
    create_project_note,
    list_project_documents,
]
```

**Step 2: Commit**

```bash
git add backend/src/services/agent/tools.py
git commit -m "feat(langgraph): repackage 6 tools as @tool decorated functions"
```

---

## Task 4: Create LangGraph Graph

**Files:**

- Create: `backend/src/services/agent/graph.py`

**Step 1: Build the StateGraph**

```python
# backend/src/services/agent/graph.py
"""LangGraph agent graph definition."""

import json
import logging
import time
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, START, END

from src.core.config import get_settings
from src.services.agent.state import AgentState
from src.services.agent.tools import ALL_TOOLS

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_TOOL_LOOPS = 10


def _build_llm() -> AzureChatOpenAI:
    """Build AzureChatOpenAI from existing settings."""
    endpoint = settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY
    api_version = settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    deployment = settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME or settings.AZURE_OPENAI_DEPLOYMENT_NAME

    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
        azure_deployment=deployment,
        temperature=0.7,
        max_tokens=2048,
    )


def _build_system_prompt(state: AgentState) -> str:
    """Build system prompt with page context and RAG context."""
    page_ctx = state.get("page_context", {})
    context_line = ""
    if page_ctx.get("type") == "project" and page_ctx.get("project_id"):
        context_line = f"The user is viewing a project (ID: {page_ctx['project_id']})."
    elif page_ctx.get("type", "unknown") != "unknown":
        context_line = f"The user is on the {page_ctx['type']} page."

    rag_context = ""
    if state.get("retrieved_contexts"):
        rag_context = "\n\nRetrieved context:\n" + "\n\n".join(
            f"[Doc {i+1}] {ctx['title']}:\n{ctx['content']}"
            for i, ctx in enumerate(state["retrieved_contexts"])
        )

    return f"""You are an AI research agent for a RAG-powered academic research system.
You help users search documents, manage research projects, find ArXiv papers, create notes, and analyze research.

You have access to these tools:
- search_arxiv: Search arXiv for academic papers
- ingest_arxiv_papers: Download and index arXiv papers into the system
- search_documents: Search the user's indexed documents
- add_document_to_project: Add a document to a research project
- create_project_note: Create a markdown note in a project
- list_project_documents: List documents in a project

{context_line}
When on a project page, project_id is available automatically — do not ask the user for it.

When answering questions, use retrieved document context when available.
Cite sources using [Doc N] format inline.
Be concise and action-oriented.{rag_context}"""


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

async def rag_node(state: AgentState, config) -> dict:
    """Retrieve relevant documents via hybrid search."""
    # Extract the last user message for RAG query
    messages = state.get("messages", [])
    last_user_msg = None
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_user_msg = msg.get("content")
            break

    if not last_user_msg:
        return {"retrieved_contexts": []}

    configurable = config.get("configurable", {})
    current_user = configurable.get("current_user")

    try:
        import asyncio
        from src.models.search_schemas import SearchQuery
        from src.services.search.hybrid_search_service import hybrid_search_service

        search_request = SearchQuery(query=last_user_msg, limit=5, search_type="hybrid")
        org_id = str(current_user.organization_id) if current_user and current_user.organization_id else None
        uid = str(current_user.id) if current_user else None

        loop = asyncio.get_running_loop()
        search_response = await loop.run_in_executor(
            None,
            lambda: hybrid_search_service.search(
                search_request=search_request,
                user_id=uid,
                organization_id=org_id,
            ),
        )

        contexts = []
        for i, result in enumerate(search_response.results[:5]):
            metadata = getattr(result, "metadata", {}) or {}
            content = metadata.get("full_text") or metadata.get("text", "")
            if not content:
                content = getattr(result, "content_preview", None) or getattr(result, "content", "") or ""

            contexts.append({
                "document_id": str(getattr(result, "document_id", "")) or None,
                "title": getattr(result, "title", "Untitled") or f"Document {i+1}",
                "content": content[:3000],
                "score": float(getattr(result, "relevance_score", 0.0)),
            })

        return {"retrieved_contexts": contexts}

    except Exception as e:
        logger.warning("RAG retrieval failed in graph", exc_info=e)
        return {"retrieved_contexts": []}


async def llm_node(state: AgentState, config) -> dict:
    """Call the LLM with tools bound."""
    llm = _build_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    system_prompt = _build_system_prompt(state)
    messages = [SystemMessage(content=system_prompt)] + state["messages"]

    response = await llm_with_tools.ainvoke(messages, config=config)

    return {
        "messages": [response],
        "tool_loop_count": state.get("tool_loop_count", 0) + 1,
    }


async def tool_node(state: AgentState, config) -> dict:
    """Execute tool calls from the last AI message."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []
    tool_executions = list(state.get("tool_executions", []))
    tools_by_name = {t.name: t for t in ALL_TOOLS}

    for tc in last_message.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_call_id = tc["id"]

        t0 = time.monotonic()
        try:
            tool_fn = tools_by_name.get(tool_name)
            if tool_fn:
                result = await tool_fn.ainvoke(tool_args, config=config)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            result = {"error": str(e)}
        duration_ms = int((time.monotonic() - t0) * 1000)

        # Record for frontend display
        tool_executions.append({
            "id": tool_call_id,
            "tool_name": tool_name,
            "tool_display_name": tool_name.replace("_", " ").title(),
            "args": tool_args,
            "status": "completed" if "error" not in result else "failed",
            "result": result,
            "duration_ms": duration_ms,
        })

        content = json.dumps(result) if isinstance(result, dict) else str(result)
        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))

    return {"messages": tool_messages, "tool_executions": tool_executions}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def should_continue(state: AgentState) -> Literal["tool_node", "__end__"]:
    """Route: if last message has tool calls AND under loop limit, go to tools."""
    last_message = state["messages"][-1]
    if (
        isinstance(last_message, AIMessage)
        and last_message.tool_calls
        and state.get("tool_loop_count", 0) < MAX_TOOL_LOOPS
    ):
        return "tool_node"
    return "__end__"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_agent_graph() -> StateGraph:
    """Build and return the compiled agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("rag_node", rag_node)
    builder.add_node("llm_node", llm_node)
    builder.add_node("tool_node", tool_node)

    builder.add_edge(START, "rag_node")
    builder.add_edge("rag_node", "llm_node")
    builder.add_conditional_edges("llm_node", should_continue, ["tool_node", END])
    builder.add_edge("tool_node", "llm_node")

    return builder


def compile_agent_graph(checkpointer=None):
    """Compile the graph with optional checkpointer."""
    builder = build_agent_graph()
    return builder.compile(checkpointer=checkpointer)
```

**Step 2: Commit**

```bash
git add backend/src/services/agent/graph.py
git commit -m "feat(langgraph): build StateGraph with rag_node, llm_node, tool_node, conditional routing"
```

---

## Task 5: Create PostgreSQL Checkpointer

**Files:**

- Create: `backend/src/services/agent/checkpointer.py`

**Step 1: Create checkpointer setup**

```python
# backend/src/services/agent/checkpointer.py
"""PostgreSQL checkpointer for LangGraph agent."""

import logging
from typing import Optional

from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_checkpointer = None


def get_db_uri() -> str:
    """Build PostgreSQL URI from settings."""
    return (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )


async def get_checkpointer():
    """Get or create the async PostgreSQL checkpointer singleton."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        db_uri = get_db_uri()
        _checkpointer = AsyncPostgresSaver.from_conn_string(db_uri)
        await _checkpointer.setup()
        logger.info("LangGraph PostgreSQL checkpointer initialized")
        return _checkpointer
    except Exception as e:
        logger.warning("Failed to init PostgreSQL checkpointer, using memory", exc_info=e)
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
        return _checkpointer
```

**Step 2: Commit**

```bash
git add backend/src/services/agent/checkpointer.py
git commit -m "feat(langgraph): add PostgreSQL checkpointer with memory fallback"
```

---

## Task 6: Add Async Job System to Endpoint

**Files:**

- Modify: `backend/src/api/agent/execute.py`

**Step 1: Add job storage and poll endpoint**

Add near the top of `execute.py` (after imports):

```python
import uuid as _uuid
from collections import OrderedDict
from threading import Lock

# In-memory job storage with TTL cleanup
_jobs: OrderedDict[str, dict] = OrderedDict()
_jobs_lock = Lock()
MAX_JOBS = 500

def _cleanup_jobs():
    """Remove oldest jobs when over limit."""
    with _jobs_lock:
        while len(_jobs) > MAX_JOBS:
            _jobs.popitem(last=False)

def _set_job(job_id: str, data: dict):
    with _jobs_lock:
        _jobs[job_id] = data
    _cleanup_jobs()

def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)
```

**Step 2: Add job response schemas**

```python
class JobStartResponse(BaseModel):
    job_id: str

class JobStatusResponse(BaseModel):
    status: str  # "running", "completed", "failed"
    result: Optional[AgentExecuteResponse] = None
    tool_executions: Optional[List[ToolExecutionResponse]] = None
    error: Optional[str] = None
```

**Step 3: Add poll endpoint**

```python
@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll for agent job status."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)
```

**Step 4: Rewrite `execute_agent` to use LangGraph + async job**

Replace the entire `execute_agent` function body with:

```python
@router.post("/execute", response_model=JobStartResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start an agent execution job. Returns job_id for polling."""
    job_id = str(_uuid.uuid4())

    _set_job(job_id, {"status": "running", "tool_executions": []})

    background_tasks.add_task(
        _run_agent_graph,
        job_id=job_id,
        request=request,
        current_user=current_user,
        db=db,
    )

    return JobStartResponse(job_id=job_id)
```

**Step 5: Add background graph runner**

```python
async def _run_agent_graph(
    job_id: str,
    request: AgentExecuteRequest,
    current_user: User,
    db: AsyncSession,
):
    """Run the LangGraph agent in the background."""
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.checkpointer import get_checkpointer
    from langchain_core.messages import HumanMessage

    try:
        checkpointer = await get_checkpointer()
        graph = compile_agent_graph(checkpointer=checkpointer)

        # Build initial state
        messages = []
        for msg in request.messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))

        initial_state = {
            "messages": messages,
            "page_context": {
                "type": request.page_context.type,
                "project_id": request.page_context.project_id,
            },
            "retrieved_contexts": [],
            "tool_executions": [],
            "thread_id": request.thread_id or "",
            "tool_loop_count": 0,
        }

        config = {
            "configurable": {
                "thread_id": request.thread_id or job_id,
                "db": db,
                "current_user": current_user,
                "page_context": {
                    "type": request.page_context.type,
                    "project_id": request.page_context.project_id,
                },
            }
        }

        # Run the graph
        final_state = await graph.ainvoke(initial_state, config=config)

        # Extract assistant response
        assistant_content = ""
        for msg in reversed(final_state["messages"]):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                assistant_content = msg.content
                break

        # Persist thread & messages (reuse existing logic)
        thread_id = request.thread_id or ""
        conversation_id = ""
        try:
            thread_id, conversation_id = await _persist_thread_messages(
                db, current_user, request, assistant_content
            )
        except Exception as e:
            logger.warning("Failed to persist thread", exc_info=e)

        # Build response
        tool_execs = [
            ToolExecutionResponse(**te) for te in final_state.get("tool_executions", [])
        ]
        retrieved = [
            RetrievedContextResponse(**rc) for rc in final_state.get("retrieved_contexts", [])
        ]

        result = AgentExecuteResponse(
            message=AgentMessage(role="assistant", content=assistant_content),
            model="gpt-4o",
            usage={},
            finish_reason="stop",
            timestamp=datetime.now(timezone.utc).isoformat(),
            rag_enabled=request.use_rag,
            retrieved_contexts=retrieved if retrieved else None,
            tool_executions=tool_execs if tool_execs else None,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )

        _set_job(job_id, {
            "status": "completed",
            "result": result.model_dump(),
            "tool_executions": [te.model_dump() for te in tool_execs],
        })

    except Exception as e:
        logger.error("Agent graph execution failed", exc_info=e)
        _set_job(job_id, {"status": "failed", "error": str(e)})
```

**Step 6: Extract thread persistence into helper**

Extract the existing thread creation/message persistence block into:

```python
async def _persist_thread_messages(
    db: AsyncSession,
    current_user: User,
    request: AgentExecuteRequest,
    assistant_content: str,
) -> tuple[str, str]:
    """Persist thread and messages. Returns (thread_id, conversation_id)."""
    # ... (move existing persistence logic here)
```

**Step 7: Add BackgroundTasks import**

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
```

**Step 8: Restart and verify**

Run: `docker compose -f docker-compose.development.yml restart backend`
Test: `curl -s http://localhost:8000/api/v1/agent/health`

**Step 9: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "feat(langgraph): replace manual tool loop with LangGraph graph + async job system"
```

---

## Task 7: Update Frontend for Async Polling

**Files:**

- Modify: `frontend/src/services/agentChatService.ts`
- Modify: `frontend/src/store/agentChatStore.ts`

**Step 1: Add polling to agentChatService**

```typescript
// Add to agentChatService class:

async startJob(request: AgentExecuteRequest): Promise<{ job_id: string }> {
  return apiClient.post<{ job_id: string }>('/agent/execute', request);
}

async pollJob(jobId: string): Promise<{
  status: 'running' | 'completed' | 'failed';
  result?: AgentExecuteResponse;
  tool_executions?: Array<{
    id: string;
    tool_name: string;
    tool_display_name: string;
    args: Record<string, unknown>;
    status: string;
    result?: unknown;
    error?: string;
    duration_ms?: number;
  }>;
  error?: string;
}> {
  return apiClient.get(`/agent/jobs/${encodeURIComponent(jobId)}`);
}
```

**Step 2: Update sendMessage in agentChatStore to use polling**

Replace the `sendMessage` implementation:

```typescript
sendMessage: async () => {
  const { inputValue, isStreaming, pageContext, activeThreadId, uiMode } = get();
  const trimmed = inputValue.trim();
  if (!trimmed || isStreaming) return;

  const userMessage: AgentMessage = {
    id: `msg-${Date.now()}`,
    role: 'user',
    content: trimmed,
    timestamp: new Date(),
  };

  set((state) => {
    state.messages.push(userMessage);
    state.inputValue = '';
    state.isStreaming = true;
  });

  try {
    const { agentChatService } = await import('@/services/agentChatService');

    const apiMessages = get()
      .messages.filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }));

    // Start the job
    const { job_id } = await agentChatService.startJob({
      messages: apiMessages,
      page_context: {
        type: pageContext.type,
        project_id: pageContext.projectId,
      },
      thread_id: activeThreadId ?? undefined,
    });

    // Poll until complete
    const POLL_INTERVAL = 1500;
    const MAX_POLLS = 120; // 3 minutes max
    let polls = 0;

    while (polls < MAX_POLLS) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL));
      polls++;

      const job = await agentChatService.pollJob(job_id);

      // Update tool executions progressively
      if (job.tool_executions && job.tool_executions.length > 0) {
        set((state) => {
          // Update the last assistant message or create a placeholder
          const lastMsg = state.messages[state.messages.length - 1];
          if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id.includes('streaming')) {
            lastMsg.toolExecutions = job.tool_executions!.map((te) => ({
              id: te.id,
              toolName: te.tool_name,
              toolDisplayName: te.tool_display_name,
              args: te.args,
              status: te.status as 'running' | 'completed' | 'failed',
              result: te.result,
              error: te.error,
              durationMs: te.duration_ms,
            }));
          }
        });
      }

      if (job.status === 'completed' && job.result) {
        const response = job.result;
        const assistantMessage: AgentMessage = {
          id: `msg-${Date.now()}-assistant`,
          role: 'assistant',
          content: response.message.content,
          timestamp: new Date(response.timestamp),
          citations: response.retrieved_contexts?.map((ctx) => ({
            documentId: ctx.document_id ?? '',
            documentTitle: ctx.title,
            snippet: ctx.content,
            score: ctx.score,
          })),
          toolExecutions: response.tool_executions?.map((te) => ({
            id: te.id,
            toolName: te.tool_name,
            toolDisplayName: te.tool_display_name,
            args: te.args,
            status: te.status as 'running' | 'completed' | 'failed',
            result: te.result,
            error: te.error,
            durationMs: te.duration_ms,
          })),
        };

        set((state) => {
          // Remove streaming placeholder if present
          state.messages = state.messages.filter((m) => !m.id.includes('streaming'));
          state.messages.push(assistantMessage);
          state.isStreaming = false;
          state.activeThreadId = response.thread_id || state.activeThreadId;
        });

        if (uiMode === 'closed') {
          set((state) => { state.hasUnread = true; });
        }
        return; // Done
      }

      if (job.status === 'failed') {
        throw new Error(job.error || 'Agent execution failed');
      }
    }

    // Timeout
    throw new Error('Agent request timed out');

  } catch (error) {
    console.error('Agent chat error:', error);
    set((state) => {
      state.messages = state.messages.filter((m) => !m.id.includes('streaming'));
      state.messages.push({
        id: `msg-${Date.now()}-error`,
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date(),
      });
      state.isStreaming = false;
    });
  }
},
```

**Step 3: Verify type-check**

Run: `cd frontend && npm run type-check`

**Step 4: Commit**

```bash
git add frontend/src/services/agentChatService.ts frontend/src/store/agentChatStore.ts
git commit -m "feat(langgraph): update frontend to poll async agent jobs"
```

---

## Task 8: Integration Test & Validation

**Step 1: Rebuild and restart**

```bash
docker compose -f docker-compose.development.yml build backend
docker compose -f docker-compose.development.yml up -d backend
```

**Step 2: Verify health**

```bash
curl -s http://localhost:8000/api/v1/agent/health
```

**Step 3: Test single-step (Q&A)**

Open agent panel, ask "What is deep learning?" — should get a RAG-powered response.

**Step 4: Test multi-step (search + action)**

On a project page, ask "Search arXiv for papers on RAG evaluation and list documents in my project" — should see multiple tool execution cards.

**Step 5: Test tool chaining**

Ask "Find papers on transformers, add the top one to my project, and create a summary note" — should chain search → ingest → add → note.

**Step 6: Run frontend tests**

```bash
cd frontend && npx jest --no-coverage --testPathIgnorePatterns='/node_modules/'
```

**Step 7: Commit any fixes**

```bash
git add -A
git commit -m "test(langgraph): integration test fixes"
```

---

## Summary

| Task | What                                | Files                                      |
| ---- | ----------------------------------- | ------------------------------------------ |
| 1    | Install dependencies                | `requirements.txt`                         |
| 2    | Agent state schema                  | `services/agent/state.py`                  |
| 3    | Repackage tools                     | `services/agent/tools.py`                  |
| 4    | LangGraph graph                     | `services/agent/graph.py`                  |
| 5    | PostgreSQL checkpointer             | `services/agent/checkpointer.py`           |
| 6    | Async job system + endpoint rewrite | `api/agent/execute.py`                     |
| 7    | Frontend polling                    | `agentChatService.ts`, `agentChatStore.ts` |
| 8    | Integration test                    | All                                        |
