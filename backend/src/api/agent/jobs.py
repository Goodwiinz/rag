"""In-memory job storage and background graph execution.

Manages the async job lifecycle for agent execution:
- Job creation/retrieval/cleanup
- Background graph invocation via _run_agent_graph
- Graph resume after human-in-the-loop confirmation via _resume_agent_graph
"""

import asyncio
import logging
import time
import uuid as _uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job storage — in-memory L1 + Redis L2
# ---------------------------------------------------------------------------
#
# The in-memory ``OrderedDict`` lives in ``job_store._l1`` (the single
# source of truth for L1).  ``_jobs`` is an alias so the confirm endpoint's
# ``with _jobs_lock: _jobs.get(job_id)`` pattern keeps working without
# changes.  ``_jobs_lock`` is a compatibility alias for the same lock.
# All writes go through ``job_store.set_job()`` (async) or the
# ``_set_job`` sync wrapper which sprays to both L1 and Redis.

from src.services.agent.job_store import _l1 as _jobs
from src.services.agent.job_store import _l1_lock as _jobs_lock
from src.services.agent.job_store import set_job as _set_job_async
from src.services.agent.job_store import get_job as _get_job_async
from src.services.agent.job_store import delete_job as _delete_job_async
from src.services.agent.job_store import _write_to_redis_only

MAX_JOBS = 500


def _cleanup_jobs():
    """No-op — Redis TTL handles expiry; L1 cleanup is in job_store."""
    pass


def _maybe_cleanup_jobs():
    """No-op — L1 cleanup is in job_store."""
    pass


def _set_job(job_id: str, data: dict):
    """Persist a job — writes L1 immediately, then Redis via fire-and-forget.

    The fire-and-forget task uses ``_write_to_redis_only`` so it never
    touches the L1 cache — the L1 write was already done synchronously
    above.  This avoids a race where the background task overwrites a
    later L1 update from the main async flow (e.g. idempotency guard
    changing status from "running" to "error").
    """
    import asyncio as _asyncio

    data["created_at"] = time.time()
    with _jobs_lock:
        _jobs[job_id] = data

    try:
        loop = _asyncio.get_running_loop()
        loop.create_task(_write_to_redis_only(job_id, data))
    except RuntimeError:
        pass


def _get_job(job_id: str) -> dict | None:
    """Retrieve a job from the shared L1 cache.

    The confirm endpoint's synchronous ``with _jobs_lock`` pattern only
    needs the L1 cache.  Async pollers should prefer ``_get_job_async``
    which falls back to Redis L2.
    """
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


async def _clear_stale_pending_confirmation(graph: Any, config: Dict[str, Any]) -> bool:
    """Wipe a stale HITL interrupt from the checkpoint before a fresh turn.

    A pending confirmation can only be answered with ``Command(resume=...)``.
    If the next request is a fresh ``HumanMessage`` instead, the user has
    abandoned the interrupt — re-firing it would block the new turn forever.

    Also resets the per-turn ephemeral counters (``tool_loop_count``,
    ``error_count``, ``reflection_count``). ``preprocessing_node`` already
    resets these on a normal turn entry, but clearing them here makes the
    invariant local to this function so future graph refactors that bypass
    ``preprocessing_node`` cannot silently inherit a stale counter from the
    abandoned turn.

    Returns True when state was cleared so callers can log/observe.
    """
    try:
        snapshot = await graph.aget_state(config)
    except Exception:
        return False
    if not snapshot or not snapshot.values:
        return False
    if not snapshot.values.get("pending_confirmation"):
        return False
    try:
        await graph.aupdate_state(
            config,
            {
                "pending_confirmation": {},
                "user_confirmed": False,
                "tool_loop_count": 0,
                "error_count": 0,
                "reflection_count": 0,
            },
        )
    except Exception:
        logger.exception("Failed to clear stale pending_confirmation")
        return False
    logger.info(
        "Cleared stale pending_confirmation for thread %s",
        config.get("configurable", {}).get("thread_id"),
    )
    return True


# ---------------------------------------------------------------------------
# Thread persistence helper
# ---------------------------------------------------------------------------


async def _resolve_thread(
    db: AsyncSession,
    current_user: User,
    request: Any,  # AgentExecuteRequest
) -> tuple[Optional[Any], str]:
    """Resolve or create the Thread + Conversation for this request.

    Returns ``(thread, conversation_id)``. ``thread`` is ``None`` when no
    workspace exists for the user (caller should treat this as "skip
    persistence"). When a fresh thread/conversation is created it is
    committed so the row has an ``id`` callers can reference.
    """
    from uuid import UUID

    from sqlalchemy import select

    from src.models.conversation import Conversation
    from src.models.thread import Thread, ThreadStatus
    from src.models.workspace import Workspace

    AGENT_THREAD_MARKER = {"source": "agent"}

    thread: Optional[Thread] = None
    if request.thread_id:
        stmt = (
            select(Thread)
            .join(Conversation, Thread.conversation_id == Conversation.id)
            .join(Workspace, Conversation.workspace_id == Workspace.id)
            .where(Thread.id == UUID(request.thread_id))
            .where(Workspace.owner_id == current_user.id)
        )
        result = await db.execute(stmt)
        thread = result.scalar_one_or_none()

    if thread is None:
        ws_stmt = (
            select(Workspace).where(Workspace.owner_id == current_user.id).limit(1)
        )
        ws_result = await db.execute(ws_stmt)
        workspace = ws_result.scalar_one_or_none()

        if workspace:
            conv = Conversation(
                workspace_id=workspace.id,
                title="Agent Chat",
                created_by_id=current_user.id,
            )
            db.add(conv)
            await db.flush()

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
            await db.commit()
            # Refresh so caller sees a usable id / conversation_id without
            # an additional roundtrip in the same transaction.
            await db.refresh(thread)

    conversation_id = str(thread.conversation_id) if thread is not None else ""
    return thread, conversation_id


async def _persist_user_message(
    db: AsyncSession,
    current_user: User,
    request: Any,  # AgentExecuteRequest
) -> bool:
    """Insert the latest user message idempotently.

    Uses ``INSERT ... ON CONFLICT DO NOTHING`` against the partial unique
    index on ``chat_messages (thread_id, client_message_id) WHERE
    client_message_id IS NOT NULL AND role = 'user'`` (Alembic revision
    v0a1b2c3d4e5). The ``index_where`` clause passed here mirrors the
    index predicate exactly so Postgres can infer the index.

    Returns ``True`` if a new row was inserted, ``False`` if a duplicate
    was silently dropped or there is nothing to insert (no user message
    in the request or no ``request.thread_id``).

    Commits independently of ``_persist_assistant_message``; callers that
    rely on a single all-or-nothing commit must adapt — a partial commit
    (user row durable, assistant row missing) is possible if the
    assistant write later fails.
    """
    from uuid import UUID

    from sqlalchemy.dialects.postgresql import insert

    from src.models.chat_message import ChatMessage, MessageRole
    from src.models.thread import Thread

    if request.thread_id is None:
        return False

    last = next(
        (m for m in reversed(request.messages) if m.role == "user"), None
    )
    if last is None:
        return False

    cmid = getattr(last, "client_message_id", None)
    cmid_value = str(cmid) if cmid is not None else None

    stmt = (
        insert(ChatMessage)
        .values(
            thread_id=UUID(request.thread_id),
            user_id=current_user.id,
            role=MessageRole.USER,
            content=last.content,
            client_message_id=cmid_value,
        )
        .on_conflict_do_nothing(
            index_elements=["thread_id", "client_message_id"],
            index_where=(
                ChatMessage.client_message_id.isnot(None)
                & (ChatMessage.role == MessageRole.USER)
            ),
        )
    )
    result = await db.execute(stmt)
    inserted = result.rowcount == 1
    if inserted:
        thread = await db.get(Thread, UUID(request.thread_id))
        if thread is not None:
            thread.message_count = (thread.message_count or 0) + 1
            thread.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    return inserted


async def _persist_assistant_message(
    db: AsyncSession,
    *,
    thread_id: str,
    content: str,
    model_name: Optional[str],
    tool_executions_out: Optional[list],
    retrieved_contexts: Optional[list] = None,
) -> None:
    """Insert the assistant turn and bump ``thread.message_count`` by 1.

    Commits independently of ``_persist_user_message``. A failure here
    after a successful user-row commit leaves the user message durable
    without its assistant counterpart — callers that depend on the old
    single-commit behavior must handle this.
    """
    from uuid import UUID

    from src.models.chat_message import ChatMessage, MessageRole
    from src.models.citation import Citation as CitationModel
    from src.models.thread import Thread

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

    msg = ChatMessage(
        thread_id=UUID(thread_id),
        role=MessageRole.ASSISTANT,
        content=content,
        model_name=model_name,
        tool_executions=tool_exec_data,
    )
    db.add(msg)
    await db.flush()

    if retrieved_contexts:
        for ctx in retrieved_contexts:
            doc_id = ctx.get("document_id")
            db.add(
                CitationModel(
                    message_id=msg.id,
                    document_id=UUID(doc_id) if doc_id else None,
                    external_reference_id=ctx.get("external_reference_id"),
                    document_title=ctx.get("title"),
                    snippet=ctx.get("content", "")[:2000],
                    score=ctx.get("score"),
                    rerank_score=ctx.get("rerank_score"),
                )
            )

    thread = await db.get(Thread, UUID(thread_id))
    if thread is not None:
        thread.message_count = (thread.message_count or 0) + 1
        thread.last_message_at = datetime.now(timezone.utc)
    await db.commit()


async def _persist_assistant_message_safe(
    *,
    thread_id: str,
    content: str,
    model_name: Optional[str],
    tool_executions_out: Optional[list],
    retrieved_contexts: Optional[list] = None,
) -> None:
    """Background-task-safe wrapper around ``_persist_assistant_message``.

    Opens its own ``AsyncSessionLocal()`` so it doesn't depend on the
    request session being alive — by the time FastAPI runs background
    tasks the original streaming session has already been closed.
    Swallows + logs any exception so a background-task failure can't
    crash the worker, and bumps
    ``agent_assistant_persist_failures_total`` on failure so dashboards
    surface silently-lost assistant rows.
    """
    try:
        async with AsyncSessionLocal() as db:
            await _persist_assistant_message(
                db,
                thread_id=thread_id,
                content=content,
                model_name=model_name,
                tool_executions_out=tool_executions_out,
                retrieved_contexts=retrieved_contexts,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Background assistant persist failed for thread %s: %s",
            thread_id,
            exc,
            exc_info=exc,
        )
        try:
            from src.services.agent.observability import (
                agent_assistant_persist_failures_total,
            )

            agent_assistant_persist_failures_total.inc()
        except Exception:
            # Metrics path is best-effort: never let a bookkeeping
            # failure mask the real error (already logged above).
            pass


# DEPRECATED — remove after streaming path migration to background tasks (Task 5).
# Compatibility shim preserving the old ``(thread_id, conversation_id)`` contract
# used by callers in ``execute.py`` and the confirm path at ``jobs.py:629``.
# Internally delegates to the three split helpers above, which each commit
# independently (see their docstrings for the partial-commit warning).
async def _persist_thread_messages(
    db: AsyncSession,
    current_user: User,
    request: Any,  # AgentExecuteRequest
    assistant_content: str,
    tool_executions_out: Optional[list] = None,
    retrieved_contexts: Optional[list] = None,
) -> tuple[str, str]:
    """Persist thread & messages to the database (deprecated shim).

    Returns ``(thread_id, conversation_id)`` as strings. See the module-level
    notice above: this function is preserved for compatibility while Task 5
    migrates the streaming path to background tasks; new code should call
    ``_persist_user_message`` / ``_persist_assistant_message`` directly.
    """
    thread, conversation_id = await _resolve_thread(db, current_user, request)
    if thread is None:
        return request.thread_id or "", ""

    thread_id = str(thread.id)

    if request.thread_id != thread_id:
        request.thread_id = thread_id

    await _persist_user_message(db, current_user, request)
    await _persist_assistant_message(
        db,
        thread_id=thread_id,
        content=assistant_content,
        model_name=request.model,
        tool_executions_out=tool_executions_out,
        retrieved_contexts=retrieved_contexts,
    )

    return thread_id, conversation_id


# ---------------------------------------------------------------------------
# Background graph runner
# ---------------------------------------------------------------------------


async def _run_agent_graph(
    job_id: str,
    request: Any,  # AgentExecuteRequest
    current_user: User,
):
    """Run the LangGraph agent graph in the background and update job status."""
    from langgraph.errors import GraphInterrupt
    from langchain_core.messages import HumanMessage

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store

    schemas = _get_schemas()
    ToolExecutionResponse = schemas["ToolExecutionResponse"]
    AgentExecuteResponse = schemas["AgentExecuteResponse"]
    AgentMessage = schemas["AgentMessage"]
    RetrievedContextResponse = schemas["RetrievedContextResponse"]

    async with AsyncSessionLocal() as db:
        try:
            # Persist the user turn BEFORE the LLM call so a graph failure or
            # client cancellation still leaves the user row durable. The
            # assistant row continues to be written after the graph
            # finishes — Task 4 of docs/plans/2026-05-13-agent-persist-perf.md.
            resolved_thread_id: Optional[str] = None
            thread_obj = None
            try:
                thread_obj, _conversation_id = await _resolve_thread(
                    db, current_user, request
                )
                if thread_obj is not None:
                    resolved_thread_id = str(thread_obj.id)
                    if request.thread_id != resolved_thread_id:
                        request.thread_id = resolved_thread_id
                    await _persist_user_message(db, current_user, request)
            except Exception:
                logger.warning(
                    "Failed to persist user turn before agent graph run",
                    exc_info=True,
                )

            # Configure LangSmith tracing if available
            try:
                from src.services.agent.observability import configure_langsmith

                configure_langsmith()
            except Exception:
                pass

            checkpointer = await get_checkpointer()
            store = await get_memory_store()
            graph = compile_agent_graph(checkpointer=checkpointer, store=store)

            messages = [
                HumanMessage(content=m.content)
                for m in request.messages
                if m.role == "user"
            ]

            page_context = _page_context_to_dict(request.page_context)
            if (
                thread_obj is not None
                and getattr(thread_obj, "source_project_id", None)
                and not page_context.get("project_id")
            ):
                page_context["project_id"] = str(thread_obj.source_project_id)
                if hasattr(thread_obj, "source_project") and thread_obj.source_project:
                    page_context["project_name"] = thread_obj.source_project.name
                if not page_context.get("type") or page_context["type"] == "chat":
                    page_context["type"] = "project"

            initial_state = {
                "messages": messages,
                "page_context": page_context,
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
                "user_id": str(current_user.id),
                "model": request.model,
            }

            config = {
                "configurable": {
                    "thread_id": request.thread_id or job_id,
                    "db": db,
                    "current_user": current_user,
                    "page_context": page_context,
                }
            }

            try:
                # Drop any stale HITL interrupt left over from a previous turn
                # the user abandoned (e.g. /new in the CLI). A fresh
                # HumanMessage cannot resume an interrupt, so re-firing the
                # old one would block this turn forever.
                await _clear_stale_pending_confirmation(graph, config)

                async with asyncio.timeout(360):
                    final_state = await graph.ainvoke(initial_state, config=config)
            except GraphInterrupt as exc:
                interrupts = getattr(exc, "interrupts", [])
                confirmation_details = {}
                if interrupts:
                    confirmation_details = getattr(interrupts[0], "value", {})
                await _set_job_async(
                    job_id,
                    {
                        "status": "awaiting_confirmation",
                        "confirmation": confirmation_details,
                        "tool_executions": [],
                        "user_id": str(current_user.id),
                        "request": request.model_dump(),
                    },
                )
                return

            # Extract assistant content from the last AI message
            assistant_content = ""
            for msg in reversed(final_state["messages"]):
                if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                    assistant_content = msg.content
                    break

            # User row was already persisted up-front (before the graph ran).
            # Only write the assistant row here — Task 4 of
            # docs/plans/2026-05-13-agent-persist-perf.md.
            thread_id, conversation_id = "", ""
            try:
                tool_executions_out = [
                    ToolExecutionResponse(**te)
                    for te in final_state.get("tool_executions", [])
                ] or None
                if resolved_thread_id is not None:
                    thread_id = resolved_thread_id
                    # Re-fetch conversation_id for the response payload. The
                    # _resolve_thread call already returned it but the local
                    # variable was scoped to the up-front block; fetch from
                    # the thread row to avoid threading an extra variable.
                    from uuid import UUID as _UUID

                    from src.models.thread import Thread as _Thread

                    thread_row = await db.get(_Thread, _UUID(thread_id))
                    if thread_row is not None:
                        conversation_id = str(thread_row.conversation_id)
                    # Run inline (no HTTP response to release here) but
                    # route through the safe wrapper so background and
                    # worker paths share the failure-metric bump on a
                    # bad commit — Task 5 of
                    # docs/plans/2026-05-13-agent-persist-perf.md.
                    await _persist_assistant_message_safe(
                        thread_id=thread_id,
                        content=assistant_content,
                        model_name=request.model,
                        tool_executions_out=tool_executions_out,
                        retrieved_contexts=final_state.get("retrieved_contexts"),
                    )
            except Exception as e:
                logger.warning("Failed to persist thread", exc_info=e)

            response_model_name: str = getattr(request, "model", "") or ""
            result = AgentExecuteResponse(
                message=AgentMessage(role="assistant", content=assistant_content),
                model=response_model_name,
                usage={},
                finish_reason="stop",
                timestamp=datetime.now(timezone.utc).isoformat(),
                rag_enabled=request.use_rag,
                retrieved_contexts=[
                    RetrievedContextResponse(**rc)
                    for rc in final_state.get("retrieved_contexts", [])
                ]
                or None,
                tool_executions=[
                    ToolExecutionResponse(**te)
                    for te in final_state.get("tool_executions", [])
                ]
                or None,
                thread_id=thread_id,
                conversation_id=conversation_id,
            )

            await _set_job_async(
                job_id,
                {
                    "status": "completed",
                    "result": result.model_dump(),
                    "tool_executions": list(final_state.get("tool_executions", [])),
                },
            )
        except asyncio.CancelledError:
            # CancelledError inherits from BaseException (since Python 3.8),
            # so the broader ``except Exception`` below would NOT catch it
            # and the job would stay stuck in ``"running"`` forever. Mark it
            # cancelled first, then re-raise so the task tears down cleanly.
            logger.warning("Agent graph execution cancelled", extra={"job_id": job_id})
            try:
                await _set_job_async(
                    job_id, {"status": "cancelled", "error": "execution cancelled"}
                )
            except Exception:
                logger.exception("Failed to mark cancelled job %s", job_id)
            raise
        except asyncio.TimeoutError:
            logger.error("Agent graph execution timed out", extra={"job_id": job_id})
            await _set_job_async(
                job_id,
                {"status": "failed", "error": "Agent execution timed out after 360s"},
            )
        except Exception as e:
            logger.error("Agent graph execution failed", exc_info=e)
            await _set_job_async(job_id, {"status": "failed", "error": str(e)})


async def _resume_agent_graph(
    job_id: str,
    confirmed: bool,
    current_user: User,
):
    """Resume the agent graph after human confirmation."""
    from langgraph.types import Command

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store

    schemas = _get_schemas()
    AgentExecuteRequest = schemas["AgentExecuteRequest"]
    ToolExecutionResponse = schemas["ToolExecutionResponse"]
    AgentExecuteResponse = schemas["AgentExecuteResponse"]
    AgentMessage = schemas["AgentMessage"]

    async with AsyncSessionLocal() as db:
        try:
            checkpointer = await get_checkpointer()
            store = await get_memory_store()
            graph = compile_agent_graph(checkpointer=checkpointer, store=store)
            job = _get_job(job_id)
            original_request = None
            if job and job.get("request"):
                original_request = AgentExecuteRequest(**job["request"])

            resume_thread_id = (
                original_request.thread_id
                if original_request and original_request.thread_id
                else job_id
            )

            config = {
                "configurable": {
                    "thread_id": resume_thread_id,
                    "db": db,
                    "current_user": current_user,
                    "page_context": (
                        _page_context_to_dict(original_request.page_context)
                        if original_request
                        else {}
                    ),
                }
            }

            # Verify thread ownership before resuming
            snapshot = await graph.aget_state(config)
            if snapshot and snapshot.values:
                snapshot_user_id = snapshot.values.get("user_id", "")
                if snapshot_user_id and snapshot_user_id != str(current_user.id):
                    logger.warning(
                        "HITL ownership mismatch: job %s thread owned by %s, requested by %s",
                        job_id,
                        snapshot_user_id,
                        current_user.id,
                    )
                    await _set_job_async(
                        job_id,
                        {
                            "status": "error",
                            "error": "Thread not found",
                        },
                    )
                    return

                # Idempotency guard: if the interrupt has already been
                # consumed (e.g. by a prior resume that completed without
                # updating the in-memory job, or by a stale background
                # task firing late), short-circuit instead of issuing a
                # second Command(resume=...) that would have nothing to
                # resume against.
                if not snapshot.values.get("pending_confirmation"):
                    logger.warning(
                        "Resume requested for job %s but no pending_confirmation in "
                        "checkpoint; interrupt already consumed",
                        job_id,
                    )
                    await _set_job_async(
                        job_id,
                        {
                            "status": "error",
                            "error": "Interrupt already consumed",
                            "user_id": str(current_user.id),
                        },
                    )
                    return

            async with asyncio.timeout(360):
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

            # Persist thread messages — session managed by AsyncSessionLocal context
            thread_id, conversation_id = "", ""
            try:
                if original_request:
                    tool_executions_out = [
                        ToolExecutionResponse(**te)
                        for te in final_state.get("tool_executions", [])
                    ] or None
                    thread_id, conversation_id = await _persist_thread_messages(
                        db,
                        current_user,
                        original_request,
                        assistant_content,
                        tool_executions_out,
                    )
            except Exception as e:
                logger.warning(
                    "Failed to persist confirmation thread messages", exc_info=e
                )

            response_model_name: str = (
                getattr(original_request, "model", "") if original_request else ""
            )
            result = AgentExecuteResponse(
                message=AgentMessage(role="assistant", content=assistant_content),
                model=response_model_name,
                usage={},
                finish_reason="stop",
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool_executions=[
                    ToolExecutionResponse(**te)
                    for te in final_state.get("tool_executions", [])
                ]
                or None,
                thread_id=thread_id,
                conversation_id=conversation_id,
            )

            await _set_job_async(
                job_id,
                {
                    "status": "completed",
                    "result": result.model_dump(),
                    "tool_executions": list(final_state.get("tool_executions", [])),
                },
            )
        except asyncio.CancelledError:
            # See parallel handler in _run_agent_graph above — CancelledError
            # is a BaseException, so the ``except Exception`` below misses it.
            logger.warning("Agent graph resume cancelled", extra={"job_id": job_id})
            try:
                await _set_job_async(
                    job_id, {"status": "cancelled", "error": "resume cancelled"}
                )
            except Exception:
                logger.exception("Failed to mark cancelled resume job %s", job_id)
            raise
        except asyncio.TimeoutError:
            logger.error("Agent graph resume timed out", extra={"job_id": job_id})
            await _set_job_async(
                job_id,
                {"status": "failed", "error": "Agent execution timed out after 360s"},
            )
        except Exception as e:
            logger.error("Agent graph resume failed", exc_info=e)
            await _set_job_async(job_id, {"status": "failed", "error": str(e)})
