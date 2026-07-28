"""SSE streaming logic for agent execution.

Contains the event_generator functions used by the /stream and
/stream/confirm endpoints, plus SSE formatting helpers.
"""

import asyncio
import contextlib
import json as _json
import logging
import time
import uuid as _uuid
from typing import Any, Dict, List, Optional

from langgraph.errors import GraphInterrupt

from src.core.database import AsyncSessionLocal
from src.models.user import User

# The job runner lives in the service layer (audit B5); `_jobs_mod` keeps its
# historical alias so the late-bound call sites (and the tests that patch
# them) read unchanged.
from src.services.agent import agent_execution_service as _jobs_mod
from src.services.agent import stream_buffer as _stream_buffer
from src.services.agent._builders import RECURSION_LIMIT
from src.services.agent._errors import client_safe_error, extract_interrupt_confirmation
from src.services.agent._pii_redact import redact_pii, redact_tool_args
from src.services.agent.agent_execution_service import (
    _clear_stale_pending_confirmation,
    _latest_user_client_message_id,
    _page_context_to_dict,
    _persist_assistant_message,
    _persist_user_message_guarded,
    _resolve_and_bind_project,
    _resolve_thread,
)
from src.services.agent.observability import record_token_usage
from src.shared.enums import AgentStreamEvent

from .trace_context import build_trace_payload

logger = logging.getLogger(__name__)


def _canonical_persistence_enabled() -> bool:
    """Server-canonical persistence rollout flag (PR 1 of the
    dual-persistence consolidation). When on, the assistant row is
    persisted synchronously before `done` and the done payload carries
    the persisted ids so the client can reconcile instead of writing its
    own copy. Read per-call (not at import) so tests and the dev cluster
    can flip it without a process restart."""
    import os

    return os.getenv("AGENT_CANONICAL_PERSISTENCE", "").lower() in (
        "1",
        "true",
        "yes",
    )


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

# Only chat-model streams originating from these LangGraph nodes are
# forwarded as user-visible `token` SSE events. Internal LLM calls
# (intent classifier inside rag_node, planner's structured-output
# complexity check, reflection critique, summarisers inside subgraph
# tool nodes) ALSO trigger on_chat_model_stream — emitting their tokens
# leaks raw JSON ({"intent":…}, {"step_count":1}) and interleaves
# parallel summarisations into the response stream. The four allow-listed
# nodes are the only ones whose chat output the user is meant to see.
_USER_FACING_LLM_NODES = frozenset(
    {
        "llm_node",
        "research_llm_node",
        "writing_llm_node",
        "data_llm_node",
    }
)


def _is_user_facing_token_event(event: Dict[str, Any]) -> bool:
    """Return True when this on_chat_model_stream event came from a node
    whose tokens we want to forward to the client.

    astream_events v2 records the originating LangGraph node on
    ``event['metadata']['langgraph_node']``. Nested subgraph nodes set
    this to the subgraph's own node name (e.g. ``research_llm_node``),
    not the parent's ``research_subgraph`` wrapper — so a flat allow-list
    on the inner node names is enough.
    """
    metadata = event.get("metadata") or {}
    node = metadata.get("langgraph_node")
    return node in _USER_FACING_LLM_NODES


def _bootstrap_langsmith() -> None:
    """Enable LangSmith tracing when the API key is configured."""
    try:
        from src.services.agent.observability import configure_langsmith

        configure_langsmith()
    except Exception:
        logger.warning(
            "Failed to configure LangSmith tracing; continuing without tracing",
            exc_info=True,
        )


def _extract_usage_tokens(event: Dict[str, Any]) -> tuple[int, int]:
    """Pull (input_tokens, output_tokens) out of an `on_chat_model_end` event.

    LangChain attaches usage metadata to the AIMessage in ``data.output`` —
    either as ``usage_metadata`` (preferred, normalized across providers) or
    on ``response_metadata.token_usage`` (raw provider payload). We try both,
    defaulting to (0, 0) when the model didn't report usage.
    """
    output = event.get("data", {}).get("output")
    if output is None:
        return 0, 0

    usage = getattr(output, "usage_metadata", None)
    if isinstance(usage, dict):
        return (
            int(usage.get("input_tokens", 0) or 0),
            int(usage.get("output_tokens", 0) or 0),
        )

    response_meta = getattr(output, "response_metadata", None)
    if isinstance(response_meta, dict):
        token_usage = response_meta.get("token_usage") or {}
        if isinstance(token_usage, dict):
            return (
                int(
                    token_usage.get("prompt_tokens")
                    or token_usage.get("input_tokens")
                    or 0
                ),
                int(
                    token_usage.get("completion_tokens")
                    or token_usage.get("output_tokens")
                    or 0
                ),
            )

    return 0, 0


def _encode_tool_result(output: Any) -> str:
    """Render a tool's return value for the SSE ``tool_end.result`` field.

    For dict/list outputs, emit JSON so the CLI can parse and summarize.
    For everything else (strings, primitives, exotic objects), fall back
    to ``str()`` — same as before. Catches serialization failures so an
    unexpectedly non-JSON-able value (e.g. a tool that returns a
    ``datetime``) never breaks the stream.
    """
    if isinstance(output, (dict, list)):
        try:
            return _json.dumps(output, default=str)[:500]
        except (TypeError, ValueError):
            pass
    return str(output)[:500]


def _tool_args_preview(tool_input: Any) -> Any:
    """Render a tool's input args for the SSE ``tool_start.args`` field.

    Returns a JSON-safe **object** when the tool input is a dict, so the
    frontend's args summarizer (which ignores non-object args) renders the
    live preview. Previously this emitted a Python-repr string
    (``str({'query': 'x'})``) which rendered nothing live while the persisted
    object rendered on reload — the designed live preview never worked. PII is
    redacted per value before the payload leaves the server (browser-visible
    SSE). Non-dict inputs fall back to a redacted, capped string.

    Shared by the main and confirm/resume streams so they can never drift
    (the confirm path previously skipped redaction entirely).
    """
    if isinstance(tool_input, dict):
        return redact_tool_args(tool_input)
    return redact_pii(str(tool_input))[:500] if tool_input else ""


def _format_sse_event(
    event_type: str, data: Dict[str, Any], seq: Optional[int] = None
) -> str:
    """Format a single SSE event frame.

    When ``seq`` is given, prepend an ``id:`` line so EventSource clients
    (and the resume endpoint) can address individual frames.
    """
    prefix = f"id: {seq}\n" if seq is not None else ""
    return f"{prefix}event: {event_type}\ndata: {_json.dumps(data)}\n\n"


class _SeqEmitter:
    """Sequence-numbered SSE frames, teed into the resumable-stream Redis
    buffer (``src.services.agent.stream_buffer``). Buffering is best-effort:
    Redis down degrades to plain live streaming, never a failed turn.
    """

    def __init__(self) -> None:
        self.seq = 0
        self.sid: Optional[str] = None
        self.thread_id: Optional[str] = None

    async def start(self, thread_id: str) -> None:
        self.thread_id = thread_id
        try:
            self.sid = await _stream_buffer.start_stream(thread_id)
        except Exception:
            logger.debug("stream_buffer.start_stream failed", exc_info=True)

    async def emit(
        self, event_type: str, data: Dict[str, Any], *, buffer: bool = True
    ) -> str:
        self.seq += 1
        frame = _format_sse_event(event_type, data, seq=self.seq)
        if buffer and self.sid is not None:
            try:
                await _stream_buffer.append(self.sid, self.seq, frame)
            except Exception:
                pass  # buffering is best-effort
        return frame

    async def finish(self) -> None:
        """Clear the thread's active-stream pointer after a terminal frame."""
        if self.sid is None or self.thread_id is None:
            return
        try:
            await _stream_buffer.finish_stream(self.thread_id, self.sid)
        except Exception:
            logger.debug("stream_buffer.finish_stream failed", exc_info=True)
        self.sid = None


# Trace 019e6a0e: ~20s planner + internal LLM phases emit no SSE frames;
# idle connections get cut at ~30s. Comment keepalives reset proxy timers.
_SSE_KEEPALIVE_SECONDS = 10
_PLANNER_CHAIN_NODES = frozenset(
    {
        "planner_node",
        "research_planner_node",
        "writing_planner_node",
        "data_planner_node",
    }
)


async def _graph_events_with_keepalive(
    event_stream_iter, request: Any, *, drain_on_disconnect: bool = False
):
    """Yield LangGraph events, interleaving keepalive markers during long gaps.

    On client disconnect, emits a ``{"type": "disconnect"}`` sentinel. With
    ``drain_on_disconnect=False`` (legacy) it then stops and the caller closes
    the graph iterator, cancelling the run. With ``drain_on_disconnect=True``
    (resumable-stream buffering active) it keeps yielding the remaining graph
    events — no keepalives, no further disconnect checks — so the caller can
    buffer the full turn for a later resume.
    """
    pending: asyncio.Task | None = None
    disconnected = False
    try:
        while True:
            if not disconnected and await request.is_disconnected():
                yield {"type": "disconnect"}
                if not drain_on_disconnect:
                    return
                disconnected = True
            if pending is None:
                pending = asyncio.create_task(event_stream_iter.__anext__())
            if disconnected:
                # Client gone; nobody needs keepalives — just await events.
                try:
                    event = await pending
                except StopAsyncIteration:
                    pending = None
                    break
                except Exception:
                    pending = None
                    raise
                pending = None
                yield {"type": "event", "event": event}
                continue
            sleep_task = asyncio.create_task(asyncio.sleep(_SSE_KEEPALIVE_SECONDS))
            done, _ = await asyncio.wait(
                {pending, sleep_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if sleep_task in done and pending not in done:
                yield {"type": "keepalive", "elapsed_ms": int(time.time() * 1000)}
                continue
            sleep_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sleep_task
            try:
                event = pending.result()
            except StopAsyncIteration:
                pending = None
                break
            except Exception:
                pending = None
                raise
            pending = None
            yield {"type": "event", "event": event}
    finally:
        # Never leak the in-flight __anext__ task — on disconnect or error it
        # would otherwise drive one more graph step after we stop reading.
        if pending is not None and not pending.done():
            pending.cancel()
            with contextlib.suppress(BaseException):
                await pending


async def stream_event_generator(
    request_body: Any,  # AgentExecuteRequest
    request: Any,  # FastAPI Request
    current_user: User,
    *,
    background_tasks: Any = None,  # fastapi.BackgroundTasks (optional for tests)
):
    """SSE event generator for the /stream endpoint.

    Yields SSE-formatted events: token, tool_start, tool_end,
    rag_context, plan, reflection, confirmation, done, error.
    """
    from src.services.agent.checkpointer import get_checkpointer, reset_checkpointer
    from src.services.agent._builders import compile_agent_graph
    from src.services.agent.memory import get_memory_store

    # Lazy import schemas to avoid circular imports
    from .execute import (
        AgentExecuteRequest,
        AgentMessage,
        PageContextRequest,
        ToolExecutionResponse,
    )

    stream_thread_id = request_body.thread_id or "unknown"
    config: Dict[str, Any] = (
        {}
    )  # Initialize before try block for safe access in except handlers
    db = AsyncSessionLocal()
    graph = None  # type: ignore[assignment]
    resolved_thread_id: Optional[str] = None
    stream_started_at = time.monotonic()
    emitter = _SeqEmitter()
    client_disconnected = False
    # Set once an assistant row for this turn has been persisted/scheduled —
    # the error-path partial persist must never double-write the turn.
    assistant_persisted = False
    persist_partial_stop = None  # bound inside try once its inputs exist
    try:
        # Persist the user turn BEFORE the LLM call so a mid-stream client
        # disconnect (or any failure inside ``astream_events``) still leaves
        # the user row durable. The assistant row is written after the
        # stream completes — Task 4 of docs/plans/2026-05-13-agent-persist-perf.md.
        thread_obj = None
        try:
            thread_obj, _conversation_id = await _resolve_thread(
                db, current_user, request_body
            )
            if thread_obj is not None:
                resolved_thread_id = str(thread_obj.id)
                if request_body.thread_id != resolved_thread_id:
                    request_body.thread_id = resolved_thread_id
                # Retry-once + observable-on-failure so a swallowed persist
                # can't silently diverge the two stores (audit D3 / P2.6).
                await _persist_user_message_guarded(db, current_user, request_body)
        except Exception:
            logger.warning(
                "Failed to persist user turn before LLM call",
                exc_info=True,
            )

        _bootstrap_langsmith()
        checkpointer = await get_checkpointer()
        store = await get_memory_store()
        graph = compile_agent_graph(checkpointer=checkpointer, store=store)

        from src.core.config import get_settings

        messages = None
        if get_settings().AGENT_SERVER_SIDE_HISTORY:
            # Option B: rebuild context from the checkpoint (seeding from the DB
            # when empty); ignore all but the newest turn in the request array.
            # Best-effort: a DB/checkpoint failure (or a newest turn lacking a
            # client_message_id -> None) falls back to the legacy path below so a
            # turn that works today is never aborted by the opt-in path.
            try:
                # Seed only from the ownership-verified thread id (set by
                # _resolve_thread); never the raw client-supplied thread_id.
                messages = await _jobs_mod.build_graph_input_messages(
                    db, graph, resolved_thread_id or "", request_body.messages
                )
            except Exception:
                logger.warning(
                    "Option B message assembly failed; using legacy history",
                    exc_info=True,
                )
                messages = None
        if messages is None:
            # Legacy path (flag off, or Option B declined/failed): B1's
            # deterministic-id rebuild of the resent history.
            messages = _jobs_mod.build_user_history_messages(
                request_body.messages, request_body.thread_id or ""
            )

        page_context = _page_context_to_dict(request_body.page_context)
        await _resolve_and_bind_project(db, current_user, thread_obj, page_context)

        # Project-scoped memory recall (best-effort; never blocks a turn).
        project_memories: list = []
        _pm_project_id = page_context.get("project_id")
        if _pm_project_id:
            try:
                from src.services.research.project_memory_service import (
                    load_project_memories,
                )

                project_memories = await load_project_memories(db, str(_pm_project_id))
            except Exception:
                logger.warning("project memory load failed", exc_info=True)

        from src.services.agent.runtime_snapshot import (
            create_runtime_snapshot,
            runtime_config_fields,
            runtime_state_fields,
        )

        runtime_snapshot = await create_runtime_snapshot(
            db,
            user_id=current_user.id,
            project_id=page_context.get("project_id"),
            thread_id=getattr(thread_obj, "id", None),
        )

        initial_state = {
            "messages": messages,
            "page_context": page_context,
            "retrieved_contexts": [],
            "tool_executions": [],
            "thread_id": request_body.thread_id or "",
            "tool_loop_count": 0,
            "error_count": 0,
            "last_error": "",
            "pending_confirmation": {},
            "user_confirmed": False,
            "intent": "",
            "user_memories": [],
            "project_memories": project_memories,
            "plan": [],
            "reflection_count": 0,
            "compaction_count": 0,
            "intent_confidence": 0.0,
            "last_error_info": {},
            "user_id": str(current_user.id),
            "model": request_body.model,
            **runtime_state_fields(runtime_snapshot, page_context.get("project_id")),
        }

        stream_thread_id = request_body.thread_id or str(_uuid.uuid4())
        config = {
            "recursion_limit": RECURSION_LIMIT,
            # Ids only (audit B8): graph nodes/tools open their own
            # tool_session() and re-load the user org-scoped — never smuggle
            # the live AsyncSession / ORM User through LangGraph config.
            "configurable": {
                "thread_id": stream_thread_id,
                "user_id": str(current_user.id),
                "organization_id": str(
                    getattr(current_user, "organization_id", "") or ""
                ),
                "page_context": page_context,
                **runtime_config_fields(
                    runtime_snapshot.id, page_context.get("project_id")
                ),
            },
            # LangSmith run metadata — per-tenant/turn filterable traces.
            # Inherited by child runs; never carries secrets.
            "metadata": {
                "user_id": str(current_user.id),
                "org_id": str(getattr(current_user, "organization_id", "") or ""),
                "thread_id": stream_thread_id,
            },
        }

        await emitter.start(stream_thread_id)

        yield await emitter.emit(
            AgentStreamEvent.TRACE,
            build_trace_payload(
                thread_id=config["configurable"]["thread_id"],
                cli_session_id="",
                langsmith_run_id="",
            ),
        )

        # Per-turn token accounting. Aggregated across every chat model call
        # in the graph (planner, intent classifier, llm_node, reflection…)
        # and emitted as a single `usage` SSE event right before `done`.
        turn_input_tokens = 0
        turn_output_tokens = 0

        # Drop any stale HITL interrupt left over from a previous turn the
        # user abandoned (e.g. /new in the CLI). A fresh HumanMessage cannot
        # resume an interrupt, so re-firing it would block this turn.
        await _clear_stale_pending_confirmation(graph, config)

        # If the checkpointer's pgbouncer/Supabase connection was
        # idle-killed since the singleton was built, the first aget_tuple
        # inside astream_events raises psycopg.OperationalError("the
        # connection is closed"). Reset + rebuild + retry once before
        # failing the whole stream.
        from psycopg import OperationalError as _PgOpError

        async def _open_event_stream():
            return graph.astream_events(
                initial_state, config=config, version="v2"
            ).__aiter__()

        event_stream_iter = await _open_event_stream()
        first_event_yielded = False
        streamed_token = False
        persisted_assistant_id: Optional[str] = None
        # Accumulated user-facing tokens, so a client abort can persist the
        # partial answer server-side (stopped=True) instead of losing it.
        streamed_parts: List[str] = []
        # Deterministic assistant-side idempotency key derived from the user
        # turn's client_message_id: an SSE retry of the same turn maps to the
        # same key, so the assistant-role partial unique index dedupes it.
        assistant_cmid: Optional[str] = None
        _last_user_msg = next(
            (m for m in reversed(request_body.messages) if m.role == "user"), None
        )
        _user_cmid = getattr(_last_user_msg, "client_message_id", None)
        if _user_cmid is not None:
            assistant_cmid = str(
                _uuid.uuid5(_uuid.NAMESPACE_URL, f"nous-assistant:{_user_cmid}")
            )

        async def persist_partial_stop() -> None:
            """Persist the accumulated partial answer with stopped=True.

            Shared by the legacy (no stream buffer) disconnect branch and the
            error path when a disconnected drain dies mid-run (e.g. the 300s
            timeout) — without it that partial would be silently lost.
            """
            nonlocal assistant_persisted
            partial = "".join(streamed_parts)
            if assistant_persisted or resolved_thread_id is None or not partial:
                return
            assistant_persisted = True
            stop_kwargs = dict(
                thread_id=resolved_thread_id,
                content=partial,
                model_name=request_body.model,
                tool_executions_out=None,
                retrieved_contexts=None,
                latency_ms=int((time.monotonic() - stream_started_at) * 1000),
                stopped=True,
                client_message_id=assistant_cmid,
                # Tokens accumulated up to the abort; no plan here — it
                # would need a checkpoint read on a path that must stay
                # cheap (client already hung up).
                token_usage=(
                    {
                        "input_tokens": turn_input_tokens,
                        "output_tokens": turn_output_tokens,
                    }
                    if (turn_input_tokens or turn_output_tokens)
                    else None
                ),
            )
            if background_tasks is not None:
                background_tasks.add_task(
                    _jobs_mod._persist_assistant_message_safe, **stop_kwargs
                )
            else:
                await _jobs_mod._persist_assistant_message_safe(**stop_kwargs)

        async with asyncio.timeout(300):  # 5 minutes
            while True:
                try:
                    async for item in _graph_events_with_keepalive(
                        event_stream_iter,
                        request,
                        drain_on_disconnect=emitter.sid is not None,
                    ):
                        if item["type"] == "disconnect":
                            client_disconnected = True
                            if emitter.sid is None:
                                # No buffer available — legacy behavior:
                                # cancel the run and persist the partial.
                                break
                            # Buffering active: keep draining graph events
                            # into the buffer so a resume gets the full turn.
                            continue
                        if item["type"] == "keepalive":
                            elapsed_ms = int(
                                (time.monotonic() - stream_started_at) * 1000
                            )
                            frame = await emitter.emit(
                                AgentStreamEvent.HEARTBEAT,
                                {"elapsed_ms": elapsed_ms},
                                buffer=False,
                            )
                            if not client_disconnected:
                                yield frame
                            continue

                        event = item["event"]
                        first_event_yielded = True
                        kind = event.get("event", "")
                        name = event.get("name", "")

                        if kind == "on_chat_model_stream":
                            if not _is_user_facing_token_event(event):
                                continue
                            chunk = event.get("data", {}).get("chunk")
                            if chunk and hasattr(chunk, "content") and chunk.content:
                                streamed_token = True
                                streamed_parts.append(chunk.content)
                                frame = await emitter.emit(
                                    AgentStreamEvent.TOKEN, {"content": chunk.content}
                                )
                                if not client_disconnected:
                                    yield frame

                        elif kind == "on_chat_model_end":
                            inp, out = _extract_usage_tokens(event)
                            turn_input_tokens += inp
                            turn_output_tokens += out

                        elif kind == "on_tool_start":
                            tool_input = event.get("data", {}).get("input", {})
                            args_preview = _tool_args_preview(tool_input)
                            frame = await emitter.emit(
                                AgentStreamEvent.TOOL_START,
                                {"tool": name, "args": args_preview},
                            )
                            if not client_disconnected:
                                yield frame

                        elif kind == "on_tool_end":
                            output = event.get("data", {}).get("output", "")
                            is_error = (
                                isinstance(output, dict) and bool(output.get("isError"))
                            ) or (getattr(output, "status", None) == "error")
                            frame = await emitter.emit(
                                AgentStreamEvent.TOOL_END,
                                {
                                    "tool": name,
                                    "result": _encode_tool_result(output),
                                    "is_error": is_error,
                                },
                            )
                            if not client_disconnected:
                                yield frame

                        elif kind == "on_chain_end" and name == "rag_node":
                            output = event.get("data", {}).get("output", {})
                            if isinstance(output, dict):
                                contexts = output.get("retrieved_contexts", [])
                                if contexts:
                                    frame = await emitter.emit(
                                        AgentStreamEvent.RAG_CONTEXT,
                                        {"contexts": contexts[:3]},
                                    )
                                    if not client_disconnected:
                                        yield frame

                        elif kind == "on_chain_end" and name in _PLANNER_CHAIN_NODES:
                            output = event.get("data", {}).get("output", {})
                            if isinstance(output, dict):
                                plan_steps = output.get("plan", [])
                                if plan_steps:
                                    frame = await emitter.emit(
                                        AgentStreamEvent.PLAN,
                                        {"steps": plan_steps, "reasoning": ""},
                                    )
                                    if not client_disconnected:
                                        yield frame

                        elif kind == "on_chain_end" and name == "reflection_gate":
                            output = event.get("data", {}).get("output", {})
                            if isinstance(output, dict):
                                reflection_result = output.get("_reflection_result")
                                if reflection_result is not None:
                                    passed = getattr(reflection_result, "passed", True)
                                    issues = getattr(reflection_result, "issues", [])
                                    round_num = output.get("reflection_count", 0)
                                    severity = getattr(
                                        reflection_result, "severity", "none"
                                    )
                                    revising = (
                                        (not passed)
                                        and severity == "major"
                                        and round_num < 2
                                    )
                                    frame = await emitter.emit(
                                        AgentStreamEvent.REFLECTION,
                                        {
                                            "passed": passed,
                                            "issues": issues,
                                            "round": round_num,
                                            "revising": revising,
                                        },
                                    )
                                    if not client_disconnected:
                                        yield frame
                    break
                except _PgOpError as op_err:
                    if first_event_yielded:
                        raise
                    logger.warning(
                        "stream: checkpointer connection dead (%s); "
                        "resetting and retrying",
                        op_err,
                    )
                    await reset_checkpointer()
                    checkpointer = await get_checkpointer()
                    graph = compile_agent_graph(checkpointer=checkpointer, store=store)
                    await _clear_stale_pending_confirmation(graph, config)
                    event_stream_iter = await _open_event_stream()
                    continue

        # Client hung up mid-stream (hit Stop / closed the tab). Cancel the
        # agent run by closing the graph iterator instead of letting it finish
        # generating into a dead socket. Persist the partial answer
        # server-side with stopped=True — server-canonical clients no longer
        # save their own copy, so without this an aborted turn would leave
        # the thread with a user message and no assistant row at all.
        # When resumable-stream buffering is active (emitter.sid set) a
        # disconnect does NOT take this branch: the loop above drained the
        # full run into the Redis buffer and we fall through to the normal
        # end-of-stream logic (persistence, usage, done) with yields
        # suppressed — a resume then replays the complete turn.
        if client_disconnected and emitter.sid is None:
            with contextlib.suppress(Exception):
                await event_stream_iter.aclose()
            logger.info(
                "SSE client disconnected; cancelled agent run for thread %s",
                stream_thread_id,
            )
            await persist_partial_stop()
            return

        # Check graph state after streaming completes
        tool_executions_out: Optional[list] = None
        try:
            final_snapshot = await graph.aget_state(config)
            final_values = final_snapshot.values if final_snapshot else {}

            # Check for pending interrupts (HITL confirmation needed)
            pending_tasks = final_snapshot.tasks if final_snapshot else ()
            has_interrupt = any(getattr(t, "interrupts", None) for t in pending_tasks)

            if has_interrupt:
                # Extract confirmation details from the interrupt
                confirmation_details = {}
                for task in pending_tasks:
                    for intr in getattr(task, "interrupts", []):
                        confirmation_details = getattr(intr, "value", {})
                        break
                    if confirmation_details:
                        break

                thread_id = config["configurable"]["thread_id"]
                frame = await emitter.emit(
                    AgentStreamEvent.CONFIRMATION,
                    {"thread_id": thread_id, "confirmation": confirmation_details},
                )
                if not client_disconnected:
                    yield frame
                await emitter.finish()
                return

            assistant_content = ""
            for msg in reversed(final_values.get("messages", [])):
                if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                    assistant_content = msg.content
                    break

            # Surface a final answer that was produced WITHOUT streaming — the
            # greeting fast-path, a templated/degraded reply, or force_synthesis
            # set the AIMessage directly and emit no on_chat_model_stream chunks.
            # Without this the client receives zero `token` events and renders an
            # empty response ("stream completed without any tokens").
            if not streamed_token and assistant_content:
                frame = await emitter.emit(
                    AgentStreamEvent.TOKEN, {"content": assistant_content}
                )
                if not client_disconnected:
                    yield frame

            tool_executions_out = [
                ToolExecutionResponse(**te)
                for te in final_values.get("tool_executions", [])
            ] or None

            # User row was already persisted up-front (before the LLM call).
            # Defer the assistant-row commit to a FastAPI BackgroundTask so
            # the SSE `done` event releases the response without waiting on
            # one more DB roundtrip — Task 5 of
            # docs/plans/2026-05-13-agent-persist-perf.md. Resolved late
            # via the jobs module so tests can monkeypatch the safe
            # wrapper at runtime.
            if resolved_thread_id is not None:
                persist_kwargs = dict(
                    thread_id=resolved_thread_id,
                    content=assistant_content,
                    model_name=request_body.model,
                    tool_executions_out=tool_executions_out,
                    retrieved_contexts=final_values.get("retrieved_contexts"),
                    latency_ms=int((time.monotonic() - stream_started_at) * 1000),
                    stopped=False,
                    client_message_id=assistant_cmid,
                    plan=final_values.get("plan") or None,
                    token_usage=(
                        {
                            "input_tokens": turn_input_tokens,
                            "output_tokens": turn_output_tokens,
                        }
                        if (turn_input_tokens or turn_output_tokens)
                        else None
                    ),
                )
                if _canonical_persistence_enabled():
                    # Server-canonical mode: persist BEFORE `done` so the
                    # event can carry the persisted ids and the client can
                    # reconcile its optimistic message without a re-fetch.
                    persisted_assistant_id = (
                        await _jobs_mod._persist_assistant_message_safe(
                            **persist_kwargs
                        )
                    )
                elif background_tasks is not None:
                    background_tasks.add_task(
                        _jobs_mod._persist_assistant_message_safe,
                        **persist_kwargs,
                    )
                else:
                    # No BackgroundTasks plumbing available (e.g. unit
                    # tests that directly invoke the generator without
                    # passing one). Run inline through the safe wrapper
                    # so the failure-metric path is still exercised.
                    await _jobs_mod._persist_assistant_message_safe(**persist_kwargs)
                assistant_persisted = True
        except Exception as e:
            logger.warning("Failed to persist SSE thread messages", exc_info=e)

        if turn_input_tokens > 0 or turn_output_tokens > 0:
            # Server-side token cost metric (was previously SSE-only, so cost
            # never reached Prometheus). Model label drives per-model spend.
            try:
                record_token_usage(
                    getattr(request_body, "model", None) or "unknown",
                    turn_input_tokens,
                    turn_output_tokens,
                )
            except Exception:  # never let metrics break the stream
                logger.debug("record_token_usage failed", exc_info=True)
            frame = await emitter.emit(
                AgentStreamEvent.USAGE,
                {
                    "input_tokens": turn_input_tokens,
                    "output_tokens": turn_output_tokens,
                },
            )
            if not client_disconnected:
                yield frame

        # Carry the graph-final tool executions so the client's committed turn
        # renders them without a reload. Without this the in-memory turn's
        # tool strip depended entirely on every live tool_start/tool_end frame
        # surviving the wire — a dropped frame left the committed bubble
        # tool-less until a refresh re-read the persisted row. Args redacted
        # like every browser-visible copy. Mirrors the /stream/confirm payload.
        done_payload: Dict[str, Any] = {
            "status": "complete",
            "tool_executions": (
                [
                    {**te.model_dump(), "args": redact_tool_args(te.args)}
                    for te in tool_executions_out
                ]
                if tool_executions_out
                else []
            ),
        }
        if _canonical_persistence_enabled():
            # Ids let the client reconcile its optimistic bubbles with the
            # server-persisted rows instead of double-saving (server-canonical
            # mode: the frontend no longer writes messages itself).
            done_payload.update(
                {
                    "thread_id": resolved_thread_id,
                    "assistant_message_id": persisted_assistant_id,
                    "client_message_id": assistant_cmid,
                }
            )
        frame = await emitter.emit(AgentStreamEvent.DONE, done_payload)
        if not client_disconnected:
            yield frame
        await emitter.finish()

    except asyncio.CancelledError:
        raise

    except GraphInterrupt as exc:
        # Graph hit an interrupt mid-stream (HITL confirmation needed).
        # Verify the checkpoint was persisted before telling the CLI to confirm.
        confirmation_details = extract_interrupt_confirmation(exc)
        thread_id = (config.get("configurable") or {}).get(
            "thread_id"
        ) or stream_thread_id

        checkpoint_ok = False
        try:
            if graph is not None:
                verify_snapshot = await graph.aget_state(config)
                checkpoint_ok = bool(
                    verify_snapshot
                    and verify_snapshot.values
                    and any(
                        getattr(t, "interrupts", None)
                        for t in (verify_snapshot.tasks or ())
                    )
                )
        except Exception:
            logger.warning(
                "Failed to verify checkpoint after GraphInterrupt for thread %s",
                thread_id,
            )

        if not checkpoint_ok:
            logger.error(
                "GraphInterrupt raised but checkpoint not persisted for thread %s — "
                "cannot send confirmation event (client would get 'Thread not found' on resume)",
                thread_id,
            )
            frame = await emitter.emit(
                AgentStreamEvent.ERROR,
                {"error": "Interrupt state could not be saved. Please retry."},
            )
            if not client_disconnected:
                yield frame
        else:
            frame = await emitter.emit(
                AgentStreamEvent.CONFIRMATION,
                {"thread_id": thread_id, "confirmation": confirmation_details},
            )
            if not client_disconnected:
                yield frame
        await emitter.finish()

    except Exception as e:
        logger.error("SSE stream error", exc_info=e)
        # Persist whatever was streamed before the failure (stopped=True) so the
        # partial answer survives a reload. Covers both the disconnected drain
        # dying (e.g. the 300s timeout) and an error while the client is still
        # connected — in server-canonical mode the frontend saves nothing, so
        # without this an errored turn leaves a user row and no assistant row.
        # Idempotent: no-ops if nothing streamed or the row was already saved.
        if persist_partial_stop is not None:
            with contextlib.suppress(Exception):
                await persist_partial_stop()
        frame = await emitter.emit(
            AgentStreamEvent.ERROR, {"error": client_safe_error(e)}
        )
        if not client_disconnected:
            yield frame
        await emitter.finish()

    finally:
        await db.close()
        logger.info("SSE stream ended for thread %s", stream_thread_id)


async def stream_confirm_event_generator(
    request_body: Any,  # StreamConfirmRequest
    request: Any,  # FastAPI Request
    current_user: User,
    *,
    background_tasks: Any = None,  # fastapi.BackgroundTasks (optional for tests)
):
    """SSE event generator for the /stream/confirm endpoint.

    Resumes a graph interrupted by HITL and streams the remaining events.
    """
    from langgraph.types import Command

    from src.services.agent.checkpointer import get_checkpointer, reset_checkpointer
    from src.services.agent._builders import compile_agent_graph
    from src.services.agent.memory import get_memory_store

    # Lazy import schemas
    from .execute import (
        AgentExecuteRequest,
        AgentMessage,
        PageContextRequest,
        ToolExecutionResponse,
    )

    db = AsyncSessionLocal()
    emitter = _SeqEmitter()
    client_disconnected = False
    # Set once an assistant row for this turn has been persisted/scheduled —
    # the error-path partial persist must never double-write the turn.
    assistant_persisted = False
    persist_partial_stop = None  # bound inside try once its inputs exist
    # CX1 claim state — pre-declared so the except handler can reference
    # them even when an exception fires before the claim block runs.
    confirm_claim_key: Optional[str] = None
    redis_client = None
    events_started = False
    try:
        _bootstrap_langsmith()
        checkpointer = await get_checkpointer()
        store = await get_memory_store()
        graph = compile_agent_graph(checkpointer=checkpointer, store=store)

        # Ids only in configurable (audit B8) — checkpoint lookup needs the
        # thread_id; the ids keep parity with the run config shape.
        snapshot_config = {
            "configurable": {
                "thread_id": request_body.thread_id,
                "user_id": str(current_user.id),
                "organization_id": str(
                    getattr(current_user, "organization_id", "") or ""
                ),
            }
        }
        current_snapshot = await graph.aget_state(snapshot_config)

        # Retry once with a fresh connection if checkpoint not found — the
        # pooler may have dropped the idle connection during HITL wait time.
        if not current_snapshot or not current_snapshot.values:
            logger.warning(
                "Checkpoint not found for thread %s on first attempt, retrying with fresh connection",
                request_body.thread_id,
            )
            await reset_checkpointer()
            checkpointer = await get_checkpointer()
            store = await get_memory_store()
            graph = compile_agent_graph(checkpointer=checkpointer, store=store)
            snapshot_config = {
                "configurable": {
                    "thread_id": request_body.thread_id,
                    "user_id": str(current_user.id),
                    "organization_id": str(
                        getattr(current_user, "organization_id", "") or ""
                    ),
                }
            }
            current_snapshot = await graph.aget_state(snapshot_config)

        # Verify thread exists
        if not current_snapshot or not current_snapshot.values:
            yield await emitter.emit(
                AgentStreamEvent.ERROR, {"error": "Thread not found"}
            )
            return

        # Verify thread ownership — checkpoints without an owner predate the
        # ownership field and cannot be safely resumed from a public thread id.
        snapshot_user_id = current_snapshot.values.get("user_id")
        if not snapshot_user_id or snapshot_user_id != str(current_user.id):
            logger.warning(
                "HITL ownership mismatch: thread %s owned by %s, requested by %s",
                request_body.thread_id,
                snapshot_user_id,
                current_user.id,
            )
            yield await emitter.emit(
                AgentStreamEvent.ERROR, {"error": "Thread not found"}
            )
            return

        page_context = _page_context_to_dict(
            current_snapshot.values.get("page_context", {})
        )
        from src.services.agent.runtime_snapshot import resume_runtime_config_fields

        runtime_context = resume_runtime_config_fields(current_snapshot.values)

        # Resume idempotency key anchored to the interrupt CHECKPOINT — not
        # the thread's latest user client_message_id. A user can send a new
        # turn in the same thread while the resume streams; the latest-cmid
        # derivation then re-pointed the key at the NEW turn and the dedup
        # index silently dropped that turn's real answer (round-3 M6).
        # Concurrent double-confirms read the same pre-resume snapshot →
        # same key → still dedupe.
        try:
            resume_ckpt_id = (current_snapshot.config or {})["configurable"][
                "checkpoint_id"
            ]
        except Exception:
            resume_ckpt_id = None

        # CX1: atomically claim this interrupt before resuming. The job
        # confirm endpoint has a CAS (execute.py compare_and_set_status);
        # this SSE path had none — two concurrent confirms both issued
        # Command(resume=...) and a destructive tool could run twice.
        # Claim key is anchored to the interrupt checkpoint (same anchor as
        # the #1065 resume-dedup cmid): a nested confirm re-parks on a NEW
        # checkpoint, so its key rotates and the next confirm still works.
        if resume_ckpt_id:
            from src.core.caching import _acquire_lock
            from src.services.agent.job_store import get_redis

            redis_client = await get_redis()
            if redis_client is not None:
                confirm_claim_key = (
                    f"hitl-confirm-claim:{request_body.thread_id}:{resume_ckpt_id}"
                )
                # TTL > the 300s stream timeout so a live winner can't lose
                # its claim mid-run; a crashed winner unblocks after TTL.
                if not await _acquire_lock(redis_client, confirm_claim_key, ttl=330):
                    yield await emitter.emit(
                        AgentStreamEvent.ERROR,
                        {"error": "Confirmation already in progress"},
                    )
                    return
            # ponytail: Redis down → no claim (single-worker in-memory CAS
            # like job_store._cas_in_memory is the upgrade if this bites).
        else:
            logger.warning(
                "No checkpoint id for resumed thread %s; confirm proceeds "
                "unclaimed (matches the cmid fallback philosophy)",
                request_body.thread_id,
            )

        async def _resume_assistant_cmid() -> Optional[str]:
            if resume_ckpt_id:
                return str(
                    _uuid.uuid5(
                        _uuid.NAMESPACE_URL,
                        f"nous-assistant-resume:{request_body.thread_id}:{resume_ckpt_id}",
                    )
                )
            # Fallback (checkpoint id missing): the original latest-user-cmid
            # derivation — imperfect but better than a non-idempotent row.
            try:
                user_cmid = await _latest_user_client_message_id(
                    db, request_body.thread_id
                )
                if user_cmid is not None:
                    return str(
                        _uuid.uuid5(_uuid.NAMESPACE_URL, f"nous-assistant:{user_cmid}")
                    )
            except Exception:
                logger.warning(
                    "Failed to derive assistant client_message_id for resumed "
                    "thread %s; assistant row will not be idempotent",
                    request_body.thread_id,
                    exc_info=True,
                )
            return None

        config = {
            "recursion_limit": RECURSION_LIMIT,
            # Ids only (audit B8) — see stream_event_generator's run config.
            "configurable": {
                "thread_id": request_body.thread_id,
                "user_id": str(current_user.id),
                "organization_id": str(
                    getattr(current_user, "organization_id", "") or ""
                ),
                "page_context": page_context,
                **runtime_context,
            },
        }

        resume_input = Command(resume={"confirmed": request_body.confirmed})

        await emitter.start(request_body.thread_id)

        yield await emitter.emit(
            AgentStreamEvent.TRACE,
            build_trace_payload(
                thread_id=request_body.thread_id,
                cli_session_id="",
                langsmith_run_id="",
            ),
        )

        # Per-turn token accounting for the confirm/resume stream.
        turn_input_tokens = 0
        turn_output_tokens = 0
        tokens_emitted = False

        # Accumulate user-facing tokens so a mid-resume disconnect can persist
        # the partial answer server-side (a resumed turn may have already
        # committed a destructive tool — losing the assistant row entirely
        # leaves the thread with a confirm action and no record of the result).
        streamed_parts: list[str] = []

        async def persist_partial_stop() -> None:
            """Persist the accumulated partial answer with stopped=True.

            Shared by the legacy (no stream buffer) disconnect branch and the
            error path when a disconnected drain dies mid-run (e.g. the 300s
            timeout) — without it that partial would be silently lost.
            """
            nonlocal assistant_persisted
            partial = "".join(streamed_parts)
            if assistant_persisted or not partial:
                return
            assistant_persisted = True
            # Checkpoint-anchored idempotency key (see _resume_assistant_cmid),
            # which itself falls back to the latest-user-cmid derivation when
            # the checkpoint id is missing — so a retried/duplicated confirm
            # dedupes on the assistant partial unique index instead of leaving
            # a duplicate row.
            disconnect_cmid: Optional[str] = await _resume_assistant_cmid()
            stop_kwargs = dict(
                thread_id=request_body.thread_id,
                content=partial,
                model_name=getattr(request_body, "model", "") or None,
                # ponytail: tool_executions/plan omitted — reading them needs
                # a checkpoint fetch on a path that must stay cheap (client
                # already hung up), same tradeoff as the main stream.
                tool_executions_out=None,
                retrieved_contexts=None,
                latency_ms=None,
                stopped=True,
                client_message_id=disconnect_cmid,
                token_usage=(
                    {
                        "input_tokens": turn_input_tokens,
                        "output_tokens": turn_output_tokens,
                    }
                    if (turn_input_tokens or turn_output_tokens)
                    else None
                ),
            )
            if background_tasks is not None:
                background_tasks.add_task(
                    _jobs_mod._persist_assistant_message_safe, **stop_kwargs
                )
            else:
                await _jobs_mod._persist_assistant_message_safe(**stop_kwargs)

        # Named iterator so a mid-stream client disconnect can aclose() it and
        # cancel the resumed graph run, instead of leaving it executing into a
        # dead socket (a resumed turn may run destructive tools).
        confirm_event_iter = graph.astream_events(
            resume_input, config=config, version="v2"
        ).__aiter__()
        # Route through the keepalive helper (mirrors the main /stream loop) so
        # a long silent resume phase emits `heartbeat` frames instead of going
        # quiet until a proxy idle-timeout cuts the connection with no
        # done/error. The helper also owns the disconnect check + sentinel.
        stream_started_at = time.monotonic()
        async with asyncio.timeout(300):
            async for item in _graph_events_with_keepalive(
                confirm_event_iter,
                request,
                drain_on_disconnect=emitter.sid is not None,
            ):
                # CX1: the resumed graph is now making real progress — a
                # failure from here on must NOT release the claim (the
                # winner may already have run a destructive tool; TTL
                # handles cleanup instead of letting a racing retry in).
                events_started = True
                if item["type"] == "disconnect":
                    client_disconnected = True
                    if emitter.sid is None:
                        # No buffer available — legacy behavior below.
                        break
                    # Buffering active: keep draining the resumed run into
                    # the buffer so a reconnect gets the full turn.
                    continue
                if item["type"] == "keepalive":
                    elapsed_ms = int((time.monotonic() - stream_started_at) * 1000)
                    frame = await emitter.emit(
                        AgentStreamEvent.HEARTBEAT,
                        {"elapsed_ms": elapsed_ms},
                        buffer=False,
                    )
                    if not client_disconnected:
                        yield frame
                    continue
                event = item["event"]

                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chat_model_stream":
                    if not _is_user_facing_token_event(event):
                        continue
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        streamed_parts.append(chunk.content)
                        frame = await emitter.emit(
                            AgentStreamEvent.TOKEN, {"content": chunk.content}
                        )
                        if not client_disconnected:
                            yield frame
                        tokens_emitted = True

                elif kind == "on_chat_model_end":
                    inp, out = _extract_usage_tokens(event)
                    turn_input_tokens += inp
                    turn_output_tokens += out

                elif kind == "on_tool_start":
                    tool_input = event.get("data", {}).get("input", {})
                    args_preview = _tool_args_preview(tool_input)
                    frame = await emitter.emit(
                        AgentStreamEvent.TOOL_START,
                        {"tool": name, "args": args_preview},
                    )
                    if not client_disconnected:
                        yield frame

                elif kind == "on_tool_end":
                    output = event.get("data", {}).get("output", "")
                    is_error = (
                        isinstance(output, dict) and bool(output.get("isError"))
                    ) or (getattr(output, "status", None) == "error")
                    frame = await emitter.emit(
                        AgentStreamEvent.TOOL_END,
                        {
                            "tool": name,
                            "result": _encode_tool_result(output),
                            "is_error": is_error,
                        },
                    )
                    if not client_disconnected:
                        yield frame

                elif kind == "on_chain_end" and name in _PLANNER_CHAIN_NODES:
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        plan_steps = output.get("plan", [])
                        if plan_steps:
                            frame = await emitter.emit(
                                AgentStreamEvent.PLAN,
                                {"steps": plan_steps, "reasoning": ""},
                            )
                            if not client_disconnected:
                                yield frame

                elif kind == "on_chain_end" and name == "reflection_gate":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        reflection_result = output.get("_reflection_result")
                        if reflection_result is not None:
                            passed = getattr(reflection_result, "passed", True)
                            issues = getattr(reflection_result, "issues", [])
                            round_num = output.get("reflection_count", 0)
                            severity = getattr(reflection_result, "severity", "none")
                            revising = (
                                (not passed) and severity == "major" and round_num < 2
                            )
                            frame = await emitter.emit(
                                AgentStreamEvent.REFLECTION,
                                {
                                    "passed": passed,
                                    "issues": issues,
                                    "round": round_num,
                                    "revising": revising,
                                },
                            )
                            if not client_disconnected:
                                yield frame

        # Client hung up mid-resume — cancel the run by closing the graph
        # iterator instead of letting it finish into a dead socket, then persist
        # the partial answer server-side with stopped=True (mirrors
        # stream_event_generator's disconnect branch). A resumed turn may have
        # already committed a destructive tool; without this the thread is left
        # with the confirm action and no assistant row recording the result.
        # With buffering active a disconnect drained the resumed run into the
        # buffer instead — fall through to the normal end-of-stream logic with
        # yields suppressed (mirrors stream_event_generator).
        if client_disconnected and emitter.sid is None:
            with contextlib.suppress(Exception):
                await confirm_event_iter.aclose()
            logger.info(
                "SSE confirm client disconnected; cancelled resumed run for thread %s",
                request_body.thread_id,
            )
            await persist_partial_stop()
            return

        # Check for nested interrupts (e.g. ingest confirmed -> add needs confirm)
        final_snapshot = await graph.aget_state(config)
        pending_tasks = final_snapshot.tasks if final_snapshot else ()
        has_interrupt = any(getattr(t, "interrupts", None) for t in pending_tasks)

        if has_interrupt:
            confirmation_details = {}
            for task in pending_tasks:
                for intr in getattr(task, "interrupts", []):
                    confirmation_details = getattr(intr, "value", {})
                    break
                if confirmation_details:
                    break
            frame = await emitter.emit(
                AgentStreamEvent.CONFIRMATION,
                {
                    "thread_id": request_body.thread_id,
                    "confirmation": confirmation_details,
                },
            )
            if not client_disconnected:
                yield frame
            # The run is parked awaiting confirmation — no longer producing,
            # so clear the active pointer; the buffered frames stay until TTL.
            await emitter.finish()
            return

        final_values = final_snapshot.values if final_snapshot else {}
        tool_executions_out = [
            ToolExecutionResponse(**te)
            for te in final_values.get("tool_executions", [])
        ] or None

        assistant_content = ""
        for msg in reversed(final_values.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                assistant_content = msg.content
                break

        # Persist ONLY the assistant row for the resumed turn. The user row
        # that started this turn was already written up-front by the original
        # /stream request (stream_event_generator → _persist_user_message),
        # so re-persisting it here would insert a SECOND bare
        # user row every confirm (no client_message_id → no dedup), inflated
        # thread.message_count, and confused context assembly.
        #
        # The resumed turn carries no fresh idempotency key (the frontend only
        # sends {thread_id, confirmed}) — use the checkpoint-anchored key so a
        # double-confirm dedupes without colliding with a concurrent new turn
        # (see _resume_assistant_cmid).
        assistant_cmid = await _resume_assistant_cmid()

        token_usage_payload = (
            {
                "input_tokens": turn_input_tokens,
                "output_tokens": turn_output_tokens,
            }
            if (turn_input_tokens or turn_output_tokens)
            else None
        )
        persisted_assistant_id: Optional[str] = None
        try:
            persist_kwargs = dict(
                thread_id=request_body.thread_id,
                content=assistant_content,
                model_name=getattr(request_body, "model", "") or None,
                tool_executions_out=tool_executions_out,
                retrieved_contexts=final_values.get("retrieved_contexts"),
                plan=final_values.get("plan") or None,
                token_usage=token_usage_payload,
                client_message_id=assistant_cmid,
                latency_ms=int((time.monotonic() - stream_started_at) * 1000),
            )
            # _persist_assistant_message_safe opens its own session so this
            # request session can be closed immediately after `done`. Run it
            # inline (not as a background task) in canonical mode so the id
            # is available for the done payload; otherwise fall back to a
            # background task to release the SSE without waiting on the write.
            if _canonical_persistence_enabled():
                persisted_assistant_id = (
                    await _jobs_mod._persist_assistant_message_safe(**persist_kwargs)
                )
            elif background_tasks is not None:
                background_tasks.add_task(
                    _jobs_mod._persist_assistant_message_safe,
                    **persist_kwargs,
                )
            else:
                await _jobs_mod._persist_assistant_message_safe(**persist_kwargs)
            assistant_persisted = True
        except Exception as e:
            logger.warning(
                "Failed to persist SSE confirmation thread messages",
                exc_info=e,
            )

        if turn_input_tokens > 0 or turn_output_tokens > 0:
            # Server-side token cost metric (was previously SSE-only, so cost
            # never reached Prometheus). Model label drives per-model spend.
            try:
                record_token_usage(
                    getattr(request_body, "model", None) or "unknown",
                    turn_input_tokens,
                    turn_output_tokens,
                )
            except Exception:  # never let metrics break the stream
                logger.debug("record_token_usage failed", exc_info=True)
            frame = await emitter.emit(
                AgentStreamEvent.USAGE,
                {
                    "input_tokens": turn_input_tokens,
                    "output_tokens": turn_output_tokens,
                },
            )
            if not client_disconnected:
                yield frame

        if not tokens_emitted and assistant_content:
            # Resume produced a final answer without streaming (templated /
            # degraded / non-streamed node) — surface it so the client isn't
            # left with an empty response.
            tokens_emitted = True
            frame = await emitter.emit(
                AgentStreamEvent.TOKEN, {"content": assistant_content}
            )
            if not client_disconnected:
                yield frame

        if not tokens_emitted and tool_executions_out:
            names = ", ".join(
                getattr(te, "tool_name", str(te)) for te in tool_executions_out
            )
            frame = await emitter.emit(
                AgentStreamEvent.TOKEN, {"content": f"Done — completed: {names}."}
            )
            if not client_disconnected:
                yield frame

        # Canonical mode carries the persisted ids so the client can reconcile
        # its optimistic bubble with the server row (mirrors the main /stream
        # done payload). tool_executions stays for legacy CLI clients — args
        # redacted like every other browser-visible copy (the live tool_start
        # preview was redacted in #1046 but this payload kept raw args).
        done_payload: Dict[str, Any] = {
            "status": "complete",
            "tool_executions": (
                [
                    {**te.model_dump(), "args": redact_tool_args(te.args)}
                    for te in tool_executions_out
                ]
                if tool_executions_out
                else []
            ),
        }
        if _canonical_persistence_enabled():
            done_payload.update(
                {
                    "thread_id": request_body.thread_id,
                    "assistant_message_id": persisted_assistant_id,
                    "client_message_id": assistant_cmid,
                }
            )
        frame = await emitter.emit(AgentStreamEvent.DONE, done_payload)
        if not client_disconnected:
            yield frame
        await emitter.finish()

    except Exception as e:
        logger.error("SSE stream confirm error", exc_info=e)
        # CX1: the winner failed before the resumed graph produced any
        # event — release the claim so a legit retry is not locked out for
        # the full TTL. Once events_started is True the resume may have run
        # a destructive tool already, so the claim is left for TTL cleanup.
        if confirm_claim_key and not events_started:
            with contextlib.suppress(Exception):
                from src.core.caching import _release_lock

                await _release_lock(redis_client, confirm_claim_key)
        # Persist whatever was streamed before the failure (stopped=True) so the
        # partial answer survives a reload. Covers both the disconnected drain
        # dying (e.g. the 300s timeout) and an error while the client is still
        # connected — in server-canonical mode the frontend saves nothing, so
        # without this an errored turn leaves a user row and no assistant row.
        # Idempotent: no-ops if nothing streamed or the row was already saved.
        if persist_partial_stop is not None:
            with contextlib.suppress(Exception):
                await persist_partial_stop()
        frame = await emitter.emit(
            AgentStreamEvent.ERROR, {"error": client_safe_error(e)}
        )
        if not client_disconnected:
            yield frame
        await emitter.finish()

    finally:
        await db.close()
        logger.info("SSE confirm stream ended for thread %s", request_body.thread_id)
