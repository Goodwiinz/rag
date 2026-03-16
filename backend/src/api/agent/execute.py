"""
Agent execution endpoint.
Wraps chat completions with tool-calling capabilities and page context injection.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core.dependencies import get_current_user
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AgentMessage(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, system, tool")
    content: str = Field(..., description="Message content")


class PageContextRequest(BaseModel):
    type: str = Field(default="unknown", description="Page context type")
    project_id: Optional[str] = Field(default=None, description="Project ID if on project page")
    metadata: Optional[Dict[str, Any]] = None


class AgentExecuteRequest(BaseModel):
    messages: List[AgentMessage] = Field(..., description="Conversation messages")
    page_context: PageContextRequest = Field(default_factory=PageContextRequest)
    model: str = Field(default="gpt-4o")
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

{context_line}

When answering questions, use retrieved document context when available.
Cite sources using [Doc N] format inline.
Be concise and action-oriented."""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    current_user: User = Depends(get_current_user),
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
                loop = asyncio.get_event_loop()
                search_response = await loop.run_in_executor(
                    None,
                    lambda: hybrid_search_service.search(
                        search_request=search_request,
                        user_id=None,
                        organization_id=None,
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
        llm_messages.append({"role": msg.role, "content": msg.content})

    # ------------------------------------------------------------------
    # Call LLM via Azure OpenAI service
    # ------------------------------------------------------------------
    try:
        from src.services.infrastructure.azure_openai_service import azure_openai_service

        response = await azure_openai_service.chat_completion(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=2048,
        )

        return AgentExecuteResponse(
            message=AgentMessage(
                role="assistant",
                content=response["content"],
            ),
            model=response.get("model", request.model),
            usage=response.get("usage", {}),
            finish_reason=response.get("finish_reason", "stop"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            rag_enabled=request.use_rag,
            retrieved_contexts=retrieved_contexts if retrieved_contexts else None,
            thread_id=request.thread_id or "",
            conversation_id="",
        )

    except Exception as e:
        logger.error("Agent LLM call failed", exc_info=e)
        raise HTTPException(status_code=500, detail="Agent execution failed")


@router.get("/health")
async def agent_health():
    """Health check for agent service."""
    return {"status": "ok", "service": "agent"}
