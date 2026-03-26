"""Agent execution endpoint.

FastAPI route definitions for the agent API. Tool implementations,
job management, streaming, and helpers live in sibling modules:

- tools_impl.py   — _tool_* functions, execute_tool, AGENT_TOOLS
- tool_helpers.py  — _resolve_document_id, _verify_project_ownership, etc.
- jobs.py          — _jobs, _set_job, _get_job, _run_agent_graph, _resume_agent_graph
- streaming.py     — SSE event generators for /stream and /stream/confirm
"""

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.errors import GraphInterrupt  # noqa: F401  re-export for backward compat
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.chat_message import ChatMessage, MessageRole
from src.models.conversation import Conversation
from src.models.document import Document
from src.models.thread import Thread, ThreadStatus
from src.models.user import User
from src.models.workspace import Workspace

# Re-export from new modules so existing imports keep working.
# Every `from src.api.agent.execute import <name>` must resolve.
from .tools_impl import (  # noqa: F401
    AGENT_TOOLS,
    execute_tool,
    _tool_search_arxiv,
    _tool_ingest_arxiv,
    _tool_search_documents,
    _tool_add_document_to_project,
    _tool_create_project_note,
    _tool_list_project_documents,
    _tool_summarize_document,
    _tool_compare_documents,
    _tool_extract_entities,
    _tool_search_knowledge_graph,
    _tool_create_draft,
    _tool_export_bibliography,
    _tool_execute_code,
)

from .tool_helpers import (  # noqa: F401
    _sanitize_metadata,
    _resolve_document_id,
    _resolve_project_id,
    _verify_project_ownership,
)

from .jobs import (  # noqa: F401
    _jobs,
    _cleanup_jobs,
    _set_job,
    _get_job,
    _page_context_to_dict,
    _get_latest_user_content,
    _persist_thread_messages,
    _run_agent_graph,
    _resume_agent_graph,
    MAX_JOBS,
)

from .streaming import (  # noqa: F401
    _SSE_HEADERS,
    stream_event_generator,
    stream_confirm_event_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AgentMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="Message role: user or assistant")
    content: str = Field(..., max_length=32000, description="Message content")


class PageContextRequest(BaseModel):
    type: str = Field(default="unknown", description="Page context type")
    project_id: Optional[str] = Field(default=None, description="Project ID if on project page")
    project_name: Optional[str] = Field(default=None, description="Project name for display")
    label: Optional[str] = Field(default=None, description="Current page label (e.g., 'Documents', 'Notes')")
    metadata: Optional[Dict[str, Any]] = None


class AgentExecuteRequest(BaseModel):
    messages: List[AgentMessage] = Field(..., max_length=50, description="Conversation messages")
    page_context: PageContextRequest = Field(default_factory=PageContextRequest)
    model: Literal["gpt-4o", "gpt-4o-mini"] = Field(default="gpt-4o")
    use_rag: bool = Field(default=True)
    max_context_docs: int = Field(default=5, ge=1, le=10)
    thread_id: Optional[str] = None


class RetrievedContextResponse(BaseModel):
    document_id: Optional[str] = None
    title: str
    content: str
    score: float


class ToolExecutionResponse(BaseModel):
    id: str
    tool_name: str
    tool_display_name: str
    args: Dict[str, Any]
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentExecuteResponse(BaseModel):
    message: AgentMessage
    model: str
    usage: Dict[str, int]
    finish_reason: str
    timestamp: str
    rag_enabled: bool = False
    retrieved_contexts: Optional[List[RetrievedContextResponse]] = None
    tool_executions: Optional[List[ToolExecutionResponse]] = None
    thread_id: str = ""
    conversation_id: str = ""


class JobStartResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    status: str
    result: Optional[dict] = None
    tool_executions: Optional[List[dict]] = None
    error: Optional[str] = None
    confirmation: Optional[dict] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PAGE_TYPES = {"project", "documents", "dashboard", "chat", "unknown"}


def build_agent_system_prompt(page_context: PageContextRequest) -> str:
    ctx_type = page_context.type if page_context.type in VALID_PAGE_TYPES else "unknown"
    context_line = ""
    if ctx_type == "project" and page_context.project_id:
        context_line = f"The user is viewing a project (ID: {page_context.project_id})."
    elif ctx_type != "unknown":
        context_line = f"The user is on the {ctx_type} page."

    return f"""You are an AI research agent for a RAG-powered academic research system.
You help users search documents, manage research projects, find ArXiv papers, create notes, and analyze research.

You have access to the following tools:
- **search_arxiv**: Search arXiv for academic papers. Use when the user asks to find research papers or scientific articles.
- **ingest_arxiv_papers**: Ingest arXiv papers into the RAG system. Use when the user wants to add/import specific arXiv papers by ID.
- **search_documents**: Search the user's indexed documents by title or content. Use when the user wants to find documents they have already uploaded.
- **add_document_to_project**: Add an existing document to a research project. Use when the user wants to organize a document into a project.
- **create_project_note**: Create a markdown note in a research project. Use when the user wants to write or save notes, observations, or summaries.
- **list_project_documents**: List all documents in a research project. Use when the user wants to see what documents are in a project.
- **summarize_document**: Summarize a document's content. Use for overviews or summaries of specific documents.
- **compare_documents**: Compare 2-5 documents for similarities, differences, and themes.
- **extract_entities**: Extract named entities (people, organizations, concepts) from a document.
- **search_knowledge_graph**: Search the knowledge graph for entities and their relationships.
- **create_draft**: Generate a literature review draft from project documents around specific themes.
- **export_bibliography**: Export bibliography for documents in bibtex, apa, ieee, or mla format.

{context_line}
When the user is on a project page, the project_id is available from the page context and does not need to be asked for.

When answering questions, use retrieved document context when available.
Cite sources using [Doc N] format inline.
Be concise and action-oriented."""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

AGENT_THREAD_MARKER = {"source": "agent"}


class ConfirmationRequest(BaseModel):
    confirmed: bool = Field(..., description="Whether the user confirms the action")


class StreamConfirmRequest(BaseModel):
    thread_id: str
    confirmed: bool


@router.post("/execute", response_model=JobStartResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute an agent chat completion via LangGraph.

    Returns a job ID immediately.  Poll ``GET /jobs/{job_id}`` for the result.
    """
    logger.info(
        "Agent execute request",
        extra={
            "user_id": str(current_user.id),
            "page_context": request.page_context.type,
            "message_count": len(request.messages),
            "use_rag": request.use_rag,
        },
    )

    job_id = str(_uuid.uuid4())
    _set_job(job_id, {"status": "running", "tool_executions": [], "user_id": str(current_user.id), "request": request.model_dump()})

    background_tasks.add_task(
        _run_agent_graph, job_id, request, current_user, db,
    )
    return JobStartResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, current_user: User = Depends(get_current_user)):
    """Poll for agent job status."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") and job["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


@router.post("/confirm/{job_id}")
async def confirm_agent_action(
    job_id: str,
    request: ConfirmationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm or deny a pending agent action (human-in-the-loop)."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") and job["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "awaiting_confirmation":
        raise HTTPException(status_code=400, detail="Job is not awaiting confirmation")

    # Resume the graph with the user's decision
    background_tasks.add_task(
        _resume_agent_graph, job_id, request.confirmed, current_user, db,
    )
    _set_job(job_id, {**job, "status": "running"})
    return {"status": "running", "job_id": job_id}


@router.post("/stream")
async def stream_agent(
    request_body: AgentExecuteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream agent responses via Server-Sent Events.

    SSE event types: token, tool_start, tool_end, rag_context, done, error
    """
    return StreamingResponse(
        stream_event_generator(request_body, request, current_user, db),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/stream/confirm")
async def stream_confirm_agent(
    request_body: StreamConfirmRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a graph interrupted by HITL via SSE streaming."""
    return StreamingResponse(
        stream_confirm_event_generator(request_body, request, current_user, db),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/graph/mermaid")
async def get_graph_mermaid(
    current_user: User = Depends(get_current_user),
):
    """Get the agent graph structure as a Mermaid diagram. Admin-only."""
    from src.services.agent.visualization import get_graph_mermaid

    diagram = get_graph_mermaid()
    return {"mermaid": diagram}


@router.get("/graph/trace/{thread_id}")
async def get_graph_trace(
    thread_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get an execution trace for a thread as a Mermaid sequence diagram."""
    from src.services.agent.visualization import get_execution_trace_mermaid

    diagram = await get_execution_trace_mermaid(thread_id)
    if diagram is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"mermaid": diagram, "thread_id": thread_id}


@router.get("/health")
async def agent_health():
    """Health check for agent service."""
    return {"status": "ok", "service": "agent"}


# ---------------------------------------------------------------------------
# Thread listing & message retrieval schemas
# ---------------------------------------------------------------------------

class ThreadSummary(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int
    last_message_at: Optional[str] = None
    source_project_id: Optional[str] = None
    status: str = "active"
    conversation_id: str = ""


class ThreadListResponse(BaseModel):
    threads: List[ThreadSummary]
    total: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    tool_executions: Optional[List[Dict[str, Any]]] = None


class ThreadMessagesResponse(BaseModel):
    messages: List[MessageResponse]
    total: int


# ---------------------------------------------------------------------------
# Thread listing & message retrieval endpoints
# ---------------------------------------------------------------------------

@router.get("/threads", response_model=ThreadListResponse)
async def list_agent_threads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List threads for the current user, ordered by most recently updated."""
    # Build query: Thread -> Conversation -> Workspace, filter by owner
    stmt = (
        select(Thread)
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            Workspace.owner_id == current_user.id,
            Thread.is_deleted == False,
            Thread.rag_document_scope == AGENT_THREAD_MARKER,
        )
        .order_by(desc(Thread.updated_at))
        .limit(50)
    )
    result = await db.execute(stmt)
    threads = result.scalars().all()

    # Count total (without limit)
    count_stmt = (
        select(func.count(Thread.id))
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            Workspace.owner_id == current_user.id,
            Thread.is_deleted == False,
            Thread.rag_document_scope == AGENT_THREAD_MARKER,
        )
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    thread_summaries = []
    for t in threads:
        thread_summaries.append(
            ThreadSummary(
                id=str(t.id),
                title=t.title,
                created_at=t.created_at.isoformat() if t.created_at else "",
                updated_at=t.updated_at.isoformat() if t.updated_at else "",
                message_count=t.message_count or 0,
                last_message_at=t.last_message_at.isoformat() if t.last_message_at else None,
                source_project_id=str(t.source_project_id) if t.source_project_id else None,
                status=t.status.value if t.status else "active",
                conversation_id=str(t.conversation_id) if t.conversation_id else "",
            )
        )

    return ThreadListResponse(threads=thread_summaries, total=total)


@router.get("/threads/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def get_thread_messages(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a specific agent thread, verifying user ownership."""
    # Verify thread exists and belongs to the current user via ownership chain
    ownership_stmt = (
        select(Thread)
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            Thread.id == thread_id,
            Workspace.owner_id == current_user.id,
            Thread.is_deleted == False,
        )
    )
    ownership_result = await db.execute(ownership_stmt)
    thread = ownership_result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Fetch messages with citations eagerly loaded
    messages_stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .options(selectinload(ChatMessage.citations))
        .order_by(ChatMessage.created_at.asc())
    )
    messages_result = await db.execute(messages_stmt)
    messages = messages_result.scalars().all()

    message_responses = []
    for msg in messages:
        # Build citations list from the relationship
        citations_data = None
        if msg.citations:
            citations_data = [c.to_frontend_format() for c in msg.citations]

        message_responses.append(
            MessageResponse(
                id=str(msg.id),
                role=msg.role.value if msg.role else "user",
                content=msg.content or "",
                created_at=msg.created_at.isoformat() if msg.created_at else "",
                tool_name=msg.tool_name,
                tool_call_id=msg.tool_call_id,
                citations=citations_data,
                tool_executions=msg.tool_executions,
            )
        )

    return ThreadMessagesResponse(messages=message_responses, total=len(message_responses))
