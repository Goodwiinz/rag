"""
Agent execution endpoint.
Wraps chat completions with tool-calling capabilities and page context injection.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.chat_message import ChatMessage, MessageRole
from src.models.citation import Citation
from src.models.conversation import Conversation
from src.models.thread import Thread, ThreadStatus
from src.models.user import User
from src.models.workspace import Workspace

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


# ---------------------------------------------------------------------------
# Agent Tools
# ---------------------------------------------------------------------------

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_arxiv",
            "description": "Search arXiv for academic papers. Use when the user asks to find, search, or look up research papers, academic publications, or scientific articles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for arXiv papers (e.g., 'transformer attention mechanisms')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (1-20)",
                        "default": 5,
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "ArXiv categories to filter (e.g., ['cs.AI', 'cs.LG']). Optional.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ingest_arxiv_papers",
            "description": "Ingest arXiv papers into the RAG system for indexing and search. Use when the user wants to add, import, download, or ingest specific arXiv papers. Requires paper IDs (e.g., '2401.12345').",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of arXiv paper IDs to ingest (e.g., ['2401.12345', '2312.67890'])",
                    },
                },
                "required": ["paper_ids"],
            },
        },
    },
]


async def execute_tool(tool_name: str, args: Dict[str, Any], user_id: str = "") -> Dict[str, Any]:
    """Execute an agent tool and return the result."""
    if tool_name == "search_arxiv":
        return await _tool_search_arxiv(args)
    if tool_name == "ingest_arxiv_papers":
        return await _tool_ingest_arxiv(args, user_id)
    return {"error": f"Unknown tool: {tool_name}"}


async def _tool_search_arxiv(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search arXiv for papers."""
    from src.services.arxiv.arxiv_service import ArXivIngestionService

    query = args.get("query", "")
    max_results = min(args.get("max_results", 5), 20)
    categories = args.get("categories")

    try:
        async with ArXivIngestionService() as service:
            papers = await service.search_papers(
                query=query,
                max_results=max_results,
                categories=categories,
                sort_by="relevance",
                sort_order="descending",
            )
            results = []
            for p in papers[:max_results]:
                results.append({
                    "id": p.get("id", ""),
                    "title": p.get("title", ""),
                    "authors": p.get("authors", [])[:5],
                    "abstract": (p.get("abstract", "") or "")[:500],
                    "published": str(p.get("published", "")),
                    "categories": p.get("categories", []),
                    "pdf_url": p.get("pdf_url", ""),
                })
            return {"papers": results, "total": len(results), "query": query}
    except Exception as e:
        logger.error("ArXiv search tool failed", exc_info=e)
        return {"error": f"ArXiv search failed: {str(e)}", "query": query}


async def _tool_ingest_arxiv(args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Ingest arXiv papers into the RAG system by searching for them first, then ingesting."""
    from src.services.arxiv.arxiv_service import ArXivIngestionService

    paper_ids = args.get("paper_ids", [])
    if not paper_ids:
        return {"error": "No paper IDs provided"}
    if len(paper_ids) > 10:
        return {"error": "Maximum 10 papers per ingest request"}

    try:
        async with ArXivIngestionService() as service:
            # Fetch paper metadata for each ID, then ingest
            papers_to_ingest = []
            for pid in paper_ids:
                # Search by ID to get full paper dict
                results = await service.search_papers(
                    query=f"id:{pid}",
                    max_results=1,
                )
                if results:
                    papers_to_ingest.append(results[0])
                else:
                    # Build minimal paper dict from ID
                    papers_to_ingest.append({
                        "id": pid,
                        "title": f"arXiv:{pid}",
                        "authors": [],
                        "abstract": "",
                        "published": "",
                        "updated": "",
                        "categories": [],
                        "links": {"pdf": f"https://arxiv.org/pdf/{pid}"},
                    })

            ingested = await service.ingest_papers(
                papers=papers_to_ingest,
                download_pdfs=True,
                extract_content=True,
            )

            return {
                "status": "ingestion_complete",
                "paper_ids": paper_ids,
                "ingested_count": len(ingested) if ingested else len(papers_to_ingest),
                "message": f"Ingested {len(paper_ids)} paper(s) into the RAG system.",
            }
    except Exception as e:
        logger.error("ArXiv ingest tool failed", exc_info=e)
        return {"error": f"Ingestion failed: {str(e)}", "paper_ids": paper_ids}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_agent_system_prompt(page_context: PageContextRequest) -> str:
    context_line = ""
    if page_context.type == "project" and page_context.project_id:
        context_line = f"The user is viewing a project (ID: {page_context.project_id})."
    elif page_context.type != "unknown":
        context_line = f"The user is on the {page_context.type} page."

    return f"""You are an AI research agent for a RAG-powered academic research system.
You help users search documents, manage research projects, find ArXiv papers, create notes, and analyze research.

You have access to tools. When the user asks to find or search for papers, use the search_arxiv tool.

{context_line}

When answering questions, use retrieved document context when available.
Cite sources using [Doc N] format inline.
Be concise and action-oriented."""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

AGENT_THREAD_MARKER = {"source": "agent"}


@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute an agent chat completion with optional RAG and tool calling."""
    logger.info(
        "Agent execute request",
        extra={
            "user_id": str(current_user.id),
            "page_context": request.page_context.type,
            "message_count": len(request.messages),
            "use_rag": request.use_rag,
        },
    )

    system_prompt = build_agent_system_prompt(request.page_context)
    retrieved_contexts: List[RetrievedContextResponse] = []

    # ------------------------------------------------------------------
    # RAG retrieval
    # ------------------------------------------------------------------
    if request.use_rag and request.messages:
        last_user_msg = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            None,
        )
        if last_user_msg:
            try:
                from src.models.search_schemas import SearchQuery
                from src.services.search.hybrid_search_service import hybrid_search_service

                search_request = SearchQuery(
                    query=last_user_msg,
                    limit=request.max_context_docs,
                    search_type="hybrid",
                )

                # hybrid_search_service.search is synchronous; run in thread pool
                loop = asyncio.get_running_loop()
                org_id = str(current_user.organization_id) if current_user.organization_id else None
                uid = str(current_user.id)
                search_response = await loop.run_in_executor(
                    None,
                    lambda: hybrid_search_service.search(
                        search_request=search_request,
                        user_id=uid,
                        organization_id=org_id,
                    ),
                )

                for i, result in enumerate(search_response.results[: request.max_context_docs]):
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

                    doc_content = content[:3000]
                    score = getattr(result, "relevance_score", 0.0)

                    retrieved_contexts.append(
                        RetrievedContextResponse(
                            document_id=str(doc_id) if doc_id else None,
                            title=title,
                            content=doc_content,
                            score=float(score),
                        )
                    )

                if retrieved_contexts:
                    context_text = "\n\n".join(
                        f"[Doc {i + 1}] {ctx.title}:\n{ctx.content}"
                        for i, ctx in enumerate(retrieved_contexts)
                    )
                    system_prompt += f"\n\nRetrieved context:\n{context_text}"

            except Exception as e:
                logger.warning("RAG retrieval failed, proceeding without context", exc_info=e)

    # ------------------------------------------------------------------
    # Build messages for LLM
    # ------------------------------------------------------------------
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in request.messages:
        if msg.role in ("user", "assistant"):
            llm_messages.append({"role": msg.role, "content": msg.content})

    # ------------------------------------------------------------------
    # Call LLM via Azure OpenAI service (with tool calling)
    # ------------------------------------------------------------------
    try:
        from src.services.infrastructure.azure_openai_service import azure_openai_service
        import json as _json

        response = await azure_openai_service.chat_completion(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=2048,
            tools=AGENT_TOOLS,
        )

        # Handle tool calls if the LLM requested them
        tool_executions_out: List[ToolExecutionResponse] = []

        tool_calls = response.get("tool_calls")
        if tool_calls:
            # Execute each tool call
            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                tool_args = _json.loads(fn.get("arguments", "{}"))
                tool_call_id = tc.get("id", "")

                import time
                t0 = time.monotonic()
                tool_result = await execute_tool(tool_name, tool_args, user_id=str(current_user.id))
                duration_ms = int((time.monotonic() - t0) * 1000)

                tool_executions_out.append(ToolExecutionResponse(
                    id=tool_call_id,
                    tool_name=tool_name,
                    tool_display_name=tool_name.replace("_", " ").title(),
                    args=tool_args,
                    status="completed" if "error" not in tool_result else "failed",
                    result=tool_result,
                    duration_ms=duration_ms,
                ))

                # Feed tool result back to LLM for synthesis
                llm_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc],
                })
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": _json.dumps(tool_result),
                })

            # Second LLM call to synthesize tool results
            response = await azure_openai_service.chat_completion(
                messages=llm_messages,
                temperature=0.7,
                max_tokens=2048,
            )

        assistant_content = response["content"]

        # --------------------------------------------------------------
        # Persist thread & messages
        # --------------------------------------------------------------
        thread_id = request.thread_id or ""
        conversation_id = ""

        try:
            # Resolve or create thread
            thread: Optional[Thread] = None
            if request.thread_id:
                thread = await db.get(Thread, UUID(request.thread_id))

            if thread is None:
                # Need a workspace + conversation for the thread
                ws_stmt = select(Workspace).where(
                    Workspace.owner_id == current_user.id
                ).limit(1)
                ws_result = await db.execute(ws_stmt)
                workspace = ws_result.scalar_one_or_none()

                if workspace:
                    # Create conversation
                    conv = Conversation(
                        workspace_id=workspace.id,
                        title="Agent Chat",
                        created_by_id=current_user.id,
                    )
                    db.add(conv)
                    await db.flush()

                    # Derive title from first user message
                    first_msg = next(
                        (m.content for m in request.messages if m.role == "user"), ""
                    )
                    title = first_msg[:80] if first_msg else "Agent Chat"

                    thread = Thread(
                        conversation_id=conv.id,
                        title=title,
                        status=ThreadStatus.ACTIVE,
                        created_by_id=current_user.id,
                        rag_document_scope=AGENT_THREAD_MARKER,
                        message_count=0,
                    )
                    db.add(thread)
                    await db.flush()

            if thread:
                thread_id = str(thread.id)
                conversation_id = str(thread.conversation_id)

                # Save user message (only the latest one)
                last_user_content = next(
                    (m.content for m in reversed(request.messages) if m.role == "user"),
                    None,
                )
                if last_user_content:
                    user_msg = ChatMessage(
                        thread_id=thread.id,
                        user_id=current_user.id,
                        role=MessageRole.USER,
                        content=last_user_content,
                    )
                    db.add(user_msg)

                # Save assistant message
                asst_msg = ChatMessage(
                    thread_id=thread.id,
                    role=MessageRole.ASSISTANT,
                    content=assistant_content,
                    model_name=request.model,
                )
                db.add(asst_msg)

                # Update thread stats
                thread.message_count = (thread.message_count or 0) + 2
                thread.last_message_at = datetime.now(timezone.utc)

                await db.commit()

        except Exception as e:
            logger.warning("Failed to persist agent thread/messages", exc_info=e)
            await db.rollback()

        return AgentExecuteResponse(
            message=AgentMessage(
                role="assistant",
                content=assistant_content,
            ),
            model=response.get("model", request.model),
            usage=response.get("usage", {}),
            finish_reason=response.get("finish_reason", "stop"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            rag_enabled=request.use_rag,
            retrieved_contexts=retrieved_contexts if retrieved_contexts else None,
            tool_executions=tool_executions_out if tool_executions_out else None,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )

    except Exception as e:
        logger.error("Agent LLM call failed", exc_info=e)
        raise HTTPException(status_code=500, detail="Agent execution failed")


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
            )
        )

    return ThreadMessagesResponse(messages=message_responses, total=len(message_responses))
