"""In-memory job storage and background graph execution.

Manages the async job lifecycle for agent execution:
- Job creation/retrieval/cleanup
- Background graph invocation via _run_agent_graph
- Graph resume after human-in-the-loop confirmation via _resume_agent_graph
"""

import logging
import uuid as _uuid
from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory job storage
# ---------------------------------------------------------------------------

_jobs: OrderedDict[str, dict] = OrderedDict()
_jobs_lock = Lock()
MAX_JOBS = 500


def _cleanup_jobs():
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


# ---------------------------------------------------------------------------
# Schemas used by job runner (imported from execute for consistency)
# ---------------------------------------------------------------------------

# Forward imports — these are defined in execute.py and we import them lazily
# to avoid circular imports during module initialization.


def _get_schemas():
    """Lazily import schema classes to avoid circular imports."""
    from .execute import (
        AgentExecuteRequest,
        AgentExecuteResponse,
        AgentMessage,
        PageContextRequest,
        RetrievedContextResponse,
        ToolExecutionResponse,
    )
    return {
        "AgentExecuteRequest": AgentExecuteRequest,
        "AgentExecuteResponse": AgentExecuteResponse,
        "AgentMessage": AgentMessage,
        "PageContextRequest": PageContextRequest,
        "RetrievedContextResponse": RetrievedContextResponse,
        "ToolExecutionResponse": ToolExecutionResponse,
    }


# ---------------------------------------------------------------------------
# Helpers shared with endpoints
# ---------------------------------------------------------------------------


def _page_context_to_dict(
    page_context: Any,
) -> Dict[str, Any]:
    """Normalize page context so every execution path forwards the same shape."""
    if hasattr(page_context, "model_dump"):
        raw = page_context.model_dump()
    else:
        raw = page_context or {}

    return {
        "type": raw.get("type", "unknown"),
        "project_id": raw.get("project_id"),
        "project_name": raw.get("project_name"),
        "label": raw.get("label"),
        "metadata": raw.get("metadata"),
    }


def _get_latest_user_content(messages: List[Any]) -> Optional[str]:
    """Return the latest user or human message content from graph state."""
    for message in reversed(messages):
        msg_type = getattr(message, "type", None)
        if msg_type in {"human", "user"} and getattr(message, "content", None):
            return message.content
    return None


# ---------------------------------------------------------------------------
# Thread persistence helper
# ---------------------------------------------------------------------------


async def _persist_thread_messages(
    db: AsyncSession,
    current_user: User,
    request: Any,  # AgentExecuteRequest
    assistant_content: str,
    tool_executions_out: Optional[list] = None,
) -> tuple[str, str]:
    """Persist thread & messages to the database.

    Returns ``(thread_id, conversation_id)`` as strings.
    """
    from uuid import UUID

    from sqlalchemy import select

    from src.models.chat_message import ChatMessage, MessageRole
    from src.models.conversation import Conversation
    from src.models.thread import Thread, ThreadStatus
    from src.models.workspace import Workspace

    AGENT_THREAD_MARKER = {"source": "agent"}

    thread_id = request.thread_id or ""
    conversation_id = ""

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

        # Save assistant message with tool executions
        tool_exec_data = None
        if tool_executions_out:
            tool_exec_data = [
                {
                    "id": te.id,
                    "tool_name": te.tool_name,
                    "tool_display_name": te.tool_display_name,
                    "args": te.args,
                    "status": te.status,
                    "result": te.result,
                    "error": te.error,
                    "duration_ms": te.duration_ms,
                }
                for te in tool_executions_out
            ]
        asst_msg = ChatMessage(
            thread_id=thread.id,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            model_name=request.model,
            tool_executions=tool_exec_data,
        )
        db.add(asst_msg)

        # Update thread stats
        thread.message_count = (thread.message_count or 0) + 2
        thread.last_message_at = datetime.now(timezone.utc)

        await db.commit()

    return thread_id, conversation_id


# ---------------------------------------------------------------------------
# Background graph runner
# ---------------------------------------------------------------------------


async def _run_agent_graph(
    job_id: str,
    request: Any,  # AgentExecuteRequest
    current_user: User,
    db: AsyncSession,
):
    """Run the LangGraph agent graph in the background and update job status."""
    from langgraph.errors import GraphInterrupt
    from langchain_core.messages import HumanMessage

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph

    schemas = _get_schemas()
    ToolExecutionResponse = schemas["ToolExecutionResponse"]
    AgentExecuteResponse = schemas["AgentExecuteResponse"]
    AgentMessage = schemas["AgentMessage"]
    RetrievedContextResponse = schemas["RetrievedContextResponse"]

    try:
        # Configure LangSmith tracing if available
        try:
            from src.services.agent.observability import configure_langsmith

            configure_langsmith()
        except Exception:
            pass

        checkpointer = await get_checkpointer()
        graph = compile_agent_graph(checkpointer=checkpointer)

        messages = [
            HumanMessage(content=m.content)
            for m in request.messages
            if m.role == "user"
        ]

        initial_state = {
            "messages": messages,
            "page_context": _page_context_to_dict(request.page_context),
            "retrieved_contexts": [],
            "tool_executions": [],
            "thread_id": request.thread_id or "",
            "tool_loop_count": 0,
            "error_count": 0,
            "last_error": "",
            "pending_confirmation": {},
            "user_confirmed": False,
            "intent": "",
            "user_memories": [],
            "plan": [],
            "reflection_count": 0,
            "compaction_count": 0,
            "intent_confidence": 0.0,
            "last_error_info": {},
        }

        config = {
            "configurable": {
                "thread_id": request.thread_id or job_id,
                "db": db,
                "current_user": current_user,
                "page_context": _page_context_to_dict(request.page_context),
            }
        }

        try:
            final_state = await graph.ainvoke(initial_state, config=config)
        except GraphInterrupt as exc:
            interrupts = getattr(exc, "interrupts", [])
            confirmation_details = {}
            if interrupts:
                confirmation_details = getattr(interrupts[0], "value", {})
            _set_job(job_id, {
                "status": "awaiting_confirmation",
                "confirmation": confirmation_details,
                "tool_executions": [],
                "user_id": str(current_user.id),
                "request": request.model_dump(),
            })
            return

        # Extract assistant content from the last AI message
        assistant_content = ""
        for msg in reversed(final_state["messages"]):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                assistant_content = msg.content
                break

        # Persist thread & messages
        thread_id, conversation_id = "", ""
        try:
            tool_executions_out = [
                ToolExecutionResponse(**te)
                for te in final_state.get("tool_executions", [])
            ] or None
            thread_id, conversation_id = await _persist_thread_messages(
                db, current_user, request, assistant_content, tool_executions_out,
            )
        except Exception as e:
            logger.warning("Failed to persist thread", exc_info=e)
            # Only rollback the thread persistence, not tool side-effects
            try:
                await db.rollback()
            except Exception:
                pass
            try:
                await db.begin()
            except Exception:
                pass

        # Build response
        result = AgentExecuteResponse(
            message=AgentMessage(role="assistant", content=assistant_content),
            model="gpt-4o",
            usage={},
            finish_reason="stop",
            timestamp=datetime.now(timezone.utc).isoformat(),
            rag_enabled=request.use_rag,
            retrieved_contexts=[
                RetrievedContextResponse(**rc)
                for rc in final_state.get("retrieved_contexts", [])
            ] or None,
            tool_executions=[
                ToolExecutionResponse(**te)
                for te in final_state.get("tool_executions", [])
            ] or None,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )

        _set_job(job_id, {
            "status": "completed",
            "result": result.model_dump(),
            "tool_executions": [
                te for te in final_state.get("tool_executions", [])
            ],
        })
    except Exception as e:
        logger.error("Agent graph execution failed", exc_info=e)
        _set_job(job_id, {"status": "failed", "error": str(e)})


async def _resume_agent_graph(
    job_id: str,
    confirmed: bool,
    current_user: User,
    db: AsyncSession,
):
    """Resume the agent graph after human confirmation."""
    from langgraph.types import Command

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph

    schemas = _get_schemas()
    AgentExecuteRequest = schemas["AgentExecuteRequest"]
    ToolExecutionResponse = schemas["ToolExecutionResponse"]
    AgentExecuteResponse = schemas["AgentExecuteResponse"]
    AgentMessage = schemas["AgentMessage"]

    try:
        checkpointer = await get_checkpointer()
        graph = compile_agent_graph(checkpointer=checkpointer)
        job = _get_job(job_id)
        original_request = None
        if job and job.get("request"):
            original_request = AgentExecuteRequest(**job["request"])

        config = {
            "configurable": {
                "thread_id": (
                    original_request.thread_id
                    if original_request and original_request.thread_id
                    else job_id
                ),
                "db": db,
                "current_user": current_user,
                "page_context": (
                    _page_context_to_dict(original_request.page_context)
                    if original_request
                    else {}
                ),
            }
        }

        final_state = await graph.ainvoke(
            Command(resume={"confirmed": confirmed}),
            config=config,
        )

        # Extract assistant content
        assistant_content = ""
        for msg in reversed(final_state["messages"]):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                assistant_content = msg.content
                break

        # Persist thread messages
        thread_id, conversation_id = "", ""
        try:
            if original_request:
                tool_executions_out = [
                    ToolExecutionResponse(**te)
                    for te in final_state.get("tool_executions", [])
                ] or None
                thread_id, conversation_id = await _persist_thread_messages(
                    db, current_user, original_request, assistant_content, tool_executions_out,
                )
        except Exception as e:
            logger.warning("Failed to persist confirmation thread messages", exc_info=e)

        result = AgentExecuteResponse(
            message=AgentMessage(role="assistant", content=assistant_content),
            model="gpt-4o",
            usage={},
            finish_reason="stop",
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_executions=[
                ToolExecutionResponse(**te)
                for te in final_state.get("tool_executions", [])
            ] or None,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )

        _set_job(job_id, {
            "status": "completed",
            "result": result.model_dump(),
            "tool_executions": final_state.get("tool_executions", []),
        })
    except Exception as e:
        logger.error("Agent graph resume failed", exc_info=e)
        _set_job(job_id, {"status": "failed", "error": str(e)})
