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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from anyio import CancelScope
from langgraph.errors import GraphInterrupt

from src.core.database import AsyncSessionLocal
from src.middleware.disconnect_signal import AGENT_DISCONNECT_EVENT
from src.models.user import User

# The job runner lives in the service layer (audit B5); `_jobs_mod` keeps its
# historical alias so the late-bound call sites (and the tests that patch
# them) read unchanged.
from src.services.agent import agent_execution_service as _jobs_mod
from src.services.agent import stream_buffer as _stream_buffer
from src.services.agent._builders import RECURSION_LIMIT
from src.services.agent._errors import (
    classify_agent_error,
    client_safe_error,
    error_frame_payload,
    extract_interrupt_confirmation,
)
from src.services.agent._pii_redact import redact_pii, redact_tool_args
from src.services.agent.agent_execution_service import (
    TombstoneReport,
    _clear_stale_pending_confirmation,
    _latest_user_client_message_id,
    _page_context_to_dict,
    _persist_assistant_message,
    _persist_user_message_guarded,
    _resolve_and_bind_project,
    _resolve_thread,
    resync_thread_checkpoint,
)
from src.services.agent.agent_run_service import get_active_run_for_thread
from src.services.agent.agent_submission_service import (
    AcceptedSubmission,
    accept_submission,
    finalize_submission,
    mark_submission_dispatched,
)
from src.services.agent.observability import AgentStreamSLOTracker, record_token_usage
from src.services.agent.run_event_types import RunEventType
from src.services.agent.trace_metadata import TraceSource, build_trace_metadata
from src.shared.enums import AgentErrorCategory, AgentStreamEvent, JobStatus

from .trace_context import build_trace_payload

logger = logging.getLogger(__name__)

AGENT_STREAM_SCHEMA_VERSION = "1.0"
_STREAM_ROUTES = frozenset({"pending", "luna", "graph", "unknown"})


def _accept_eligible(thread_obj: Any) -> bool:
    """True when this submission has a thread the accept transaction can use.

    ``agent_runs.thread_id`` and ``chat_messages.thread_id`` are real GUID
    foreign keys, so an ownership-verified ``Thread`` with a parseable id is
    the precondition for making acceptance durable. When it is absent
    (``_resolve_thread`` found no workspace) there is no turn to persist at
    all, and the stream degrades to its pre-P0-C behaviour rather than
    failing a chat that can still answer.
    """
    if thread_obj is None:
        return False
    try:
        _uuid.UUID(str(getattr(thread_obj, "id", None)))
    except (ValueError, TypeError, AttributeError):
        return False
    return True


async def _finalize_run(
    db: Any,
    acceptance: Optional[AcceptedSubmission],
    current_user: Any,
    *,
    status: JobStatus,
    event_type: Optional[RunEventType] = None,
    payload: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Close the accepted run out at a stream exit. No-op without an accept.

    A run left non-terminal keeps holding ``uq_agent_runs_active_thread`` and
    is eventually reaped as "stale running" — i.e. a successful turn would be
    projected as a failure. Purely bookkeeping: it runs after the client's
    frames, and ``finalize_submission`` never raises.
    """
    if acceptance is None:
        return
    await _finalize_run_id(
        db,
        acceptance.run_id,
        current_user,
        status=status,
        event_type=event_type,
        payload=payload,
        error_code=error_code,
        error=error,
    )


async def _finalize_run_id(
    db: Any,
    run_id: Optional[str],
    current_user: Any,
    *,
    status: JobStatus,
    event_type: Optional[RunEventType] = None,
    payload: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Close a caller-owned durable run when only its id is available."""
    if not run_id:
        return
    await finalize_submission(
        db,
        run_id=run_id,
        status=status,
        organization_id=getattr(current_user, "organization_id", None),
        event_type=event_type,
        payload=payload,
        error_code=error_code,
        error=error,
    )


# `accept_submission` raises a bare ValueError when the submitted messages
# contain no user turn — a malformed *request*, not a server fault. It carries
# no dedicated type, so the branch is keyed on the exact sentinel text raised in
# `agent_submission_service.accept_submission`; anything else falls through to
# the generic classifier rather than being optimistically blamed on the client.
_NO_USER_MESSAGE_SENTINEL = "accept_submission requires a user message"


# Anti-enumeration: /stream/confirm's "no such checkpoint" and "not your
# checkpoint" branches MUST be indistinguishable to the caller — same message,
# same category, byte-identical payload. Both branches build their frame from
# these two constants precisely so neither the string nor the category can
# drift into an oracle for whether a guessed thread id exists.
_CONFIRM_NOT_FOUND_MESSAGE = "Thread not found"
_CONFIRM_NOT_FOUND_CATEGORY = AgentErrorCategory.INVALID_REQUEST


def _stream_failure_category(exc: BaseException) -> AgentErrorCategory:
    """Category for the /stream catch-all: `invalid_request` for the
    missing-user-message rejection, otherwise the generic classification."""
    if isinstance(exc, ValueError) and _NO_USER_MESSAGE_SENTINEL in str(exc):
        return AgentErrorCategory.INVALID_REQUEST
    return classify_agent_error(exc)


def _request_trace_id(request: Any) -> str:
    """Return a safe per-turn correlation id.

    Reuse the request id installed by middleware when available so HTTP logs,
    SSE frames, LangSmith metadata, and Prometheus exemplars can be correlated.
    Unit generators and middleware-free callers get a UUID fallback.
    """
    state = getattr(request, "state", None)
    request_id = getattr(state, "request_id", None)
    if not request_id:
        headers = getattr(request, "headers", {})
        request_id = headers.get("x-request-id") if headers else None
    value = str(request_id or _uuid.uuid4())
    return value[:128]


def _assistant_client_message_id(request_body: Any) -> Optional[str]:
    last_user = next(
        (
            message
            for message in reversed(request_body.messages)
            if message.role == "user"
        ),
        None,
    )
    user_cmid = getattr(last_user, "client_message_id", None)
    if user_cmid is None:
        return None
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"nous-assistant:{user_cmid}"))


def _chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


async def _stream_luna_fast_path(
    *,
    request_body: Any,
    request: Any,
    current_user: User,
    db: Any,
    resolved_thread_id: str,
    emitter: Any,
    stream_started_at: float,
    trace_metadata: Dict[str, str],
    acceptance: Optional[AcceptedSubmission] = None,
):
    """Run one evidence-independent turn without entering LangGraph execution.

    ``acceptance`` is the committed P0-C accept record (``None`` on the
    degraded no-durable-thread path). When present the user row is already
    durable, and this path owns closing the run out.
    """
    from langchain_core.messages import AIMessage, HumanMessage

    from src.core.config import get_settings
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.fast_path import (
        build_fast_path_messages,
        stream_fast_path_chunks,
    )
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.llm_factory import (
        _resolve_fast_path_deployment,
        build_fast_path_llm,
    )
    from src.services.agent.memory import get_memory_store

    settings = get_settings()
    deployment = _resolve_fast_path_deployment()
    stream_thread_id = resolved_thread_id
    assistant_cmid = _assistant_client_message_id(request_body)
    last_user = next(
        (
            message
            for message in reversed(request_body.messages)
            if message.role == "user"
        ),
        None,
    )
    if last_user is None:
        raise ValueError("Fast path requires a user message")
    user_message_id = str(
        getattr(last_user, "client_message_id", None)
        or _uuid.uuid5(
            _uuid.NAMESPACE_URL,
            f"{stream_thread_id}:fast-user:{last_user.content}",
        )
    )
    assistant_message_id = assistant_cmid or str(
        _uuid.uuid5(_uuid.NAMESPACE_URL, f"{user_message_id}:fast-assistant")
    )

    prompt = build_fast_path_messages(
        request_body.messages,
        max_input_chars=settings.AGENT_FAST_PATH_MAX_INPUT_CHARS,
    )
    llm = build_fast_path_llm()
    parts: list[str] = []
    input_tokens = 0
    output_tokens = 0
    client_disconnected = False
    assistant_saved = False

    # Edit-and-resend on the fast path. Under an accept (P0-C) the tombstones
    # are already committed — they rode the accept transaction alongside the
    # user row — so the report is seeded from it. On the degraded path the
    # persist still owns them, and it runs CONCURRENTLY with the model stream
    # (that is the whole point of this route), so nothing can be converged
    # before the answer is streamed either way. Convergence happens at the
    # post-answer checkpoint write below, the first point where this route
    # holds a compiled graph.
    tombstones = TombstoneReport()
    if acceptance is not None and acceptance.tombstoned:
        tombstones.mark()

    async def persist_user() -> bool:
        # Already committed by the accept transaction (P0-C). Re-running the
        # insert would add a SECOND user row for a legacy client that sends no
        # client_message_id — there is nothing for ON CONFLICT to infer.
        if acceptance is not None:
            return False
        return await _persist_user_message_guarded(
            db, current_user, request_body, tombstoned_out=tombstones
        )

    # Declared here so cancel_fast_path can link the cancelled run to the
    # stopped partial row it persists — same contract as the graph path.
    persisted_partial_id: Optional[str] = None
    persisted_assistant_id: Optional[str] = None

    async def persist_partial() -> None:
        nonlocal persisted_partial_id
        if assistant_saved:
            return
        partial = "".join(parts)
        if not partial:
            return
        persisted_partial_id = await _jobs_mod._persist_assistant_message_safe(
            thread_id=resolved_thread_id,
            content=partial,
            model_name=deployment,
            tool_executions_out=None,
            retrieved_contexts=None,
            latency_ms=int((time.monotonic() - stream_started_at) * 1000),
            stopped=True,
            client_message_id=assistant_cmid,
        )

    async def cancel_fast_path() -> None:
        with contextlib.suppress(BaseException):
            await persist_partial()
        with contextlib.suppress(BaseException):
            await emitter.finish()
        with contextlib.suppress(BaseException):
            cancelled_payload: Dict[str, Any] = {
                "reason": "client_disconnected",
                "request_id": emitter.trace_id,
            }
            # Link the run to the stopped partial row persisted just above,
            # so a cancelled run can still name the message holding its
            # output. Omitted when nothing streamed before the abort.
            linked_assistant_id = persisted_partial_id or persisted_assistant_id
            if linked_assistant_id:
                cancelled_payload["assistant_message_id"] = linked_assistant_id
            await _finalize_run(
                db,
                acceptance,
                current_user,
                status=JobStatus.CANCELLED,
                event_type=RunEventType.RUN_CANCELLED,
                payload=cancelled_payload,
            )

    try:
        await emitter.start(stream_thread_id)
        yield await emitter.emit(
            AgentStreamEvent.STATUS,
            {"phase": "routing", "detail": "Using the direct Luna path"},
        )
        yield await emitter.emit(
            AgentStreamEvent.TRACE,
            build_trace_payload(
                thread_id=stream_thread_id,
                cli_session_id="",
                langsmith_run_id="",
            ),
        )

        if acceptance is not None:
            # The dispatch this outbox row recorded is about to happen
            # in-process. Stamping it keeps a future relay from re-dispatching
            # a run that already ran (best-effort; never raises).
            await mark_submission_dispatched(
                db,
                run_id=acceptance.run_id,
                outbox_id=acceptance.outbox_id,
                organization_id=getattr(current_user, "organization_id", None),
            )
        async with asyncio.timeout(settings.AGENT_FAST_PATH_REQUEST_TIMEOUT):
            writing_emitted = False
            fast_path_chunks = stream_fast_path_chunks(
                llm=llm,
                messages=prompt,
                persist_user=persist_user,
                trace_metadata=trace_metadata,
            ).__aiter__()
            fast_path_events = _graph_events_with_keepalive(fast_path_chunks, request)
            try:
                async for item in fast_path_events:
                    if item["type"] == "disconnect":
                        client_disconnected = True
                        await cancel_fast_path()
                        return
                    if item["type"] == "keepalive":
                        frame = await emitter.emit(
                            AgentStreamEvent.HEARTBEAT,
                            {
                                "elapsed_ms": int(
                                    (time.monotonic() - stream_started_at) * 1000
                                )
                            },
                            buffer=False,
                        )
                        if not client_disconnected:
                            yield frame
                        continue

                    chunk = item["event"]
                    text = _chunk_text(chunk)
                    usage = getattr(chunk, "usage_metadata", None)
                    if isinstance(usage, dict):
                        input_tokens = max(
                            input_tokens, int(usage.get("input_tokens", 0) or 0)
                        )
                        output_tokens = max(
                            output_tokens, int(usage.get("output_tokens", 0) or 0)
                        )
                    if not text:
                        continue
                    if not writing_emitted:
                        yield await emitter.emit(
                            AgentStreamEvent.STATUS,
                            {"phase": "writing", "detail": "Luna is responding"},
                        )
                        writing_emitted = True
                    # Buffer BEFORE recording for persistence — same ordering
                    # invariant as the graph path: the stopped partial must stay
                    # a prefix of the buffered stream, so a cancellation inside
                    # this await can only lose the last chunk, never invent one.
                    frame = await emitter.emit(
                        AgentStreamEvent.TOKEN,
                        {"content": text},
                    )
                    parts.append(text)
                    if not client_disconnected:
                        yield frame
            finally:
                await _close_async_iterator(fast_path_events)

        assistant_content = "".join(parts)
        if not assistant_content:
            raise RuntimeError("Luna completed without response content")

        yield await emitter.emit(
            AgentStreamEvent.STATUS,
            {"phase": "finalizing", "detail": "Saving the response"},
        )

        persisted_assistant_id = await _jobs_mod._persist_assistant_message_safe(
            thread_id=resolved_thread_id,
            content=assistant_content,
            model_name=deployment,
            tool_executions_out=None,
            retrieved_contexts=None,
            latency_ms=int((time.monotonic() - stream_started_at) * 1000),
            stopped=False,
            client_message_id=assistant_cmid,
            token_usage=(
                {"input_tokens": input_tokens, "output_tokens": output_tokens}
                if input_tokens or output_tokens
                else None
            ),
        )
        assistant_saved = True

        # Keep the graph checkpoint authoritative for a later grounded/tool turn.
        checkpointer, store = await asyncio.gather(
            get_checkpointer(),
            get_memory_store(),
        )
        graph = compile_agent_graph(checkpointer=checkpointer, store=store)
        checkpoint_config = {
            "configurable": {
                "thread_id": stream_thread_id,
                "user_id": str(current_user.id),
                "organization_id": str(
                    getattr(current_user, "organization_id", "") or ""
                ),
            }
        }
        # Edit-and-resend: rebuild HEAD from the post-edit DB first, so the
        # replaced turn stops feeding the model.
        if tombstones.any:
            await resync_thread_checkpoint(
                graph,
                thread_id=stream_thread_id,
                user=current_user,
            )
        # The append ALWAYS runs, including right after a resync. It is
        # idempotent by id: ``add_messages`` (the reducer behind
        # ``aupdate_state``) replaces a same-id message in place rather than
        # appending a duplicate (pinned by
        # test_agent_edit_resend_checkpoint.py::
        # test_langgraph_replaces_a_same_id_message_in_place), so the write is
        # at worst a no-op. It is also the REPAIR for a partial-row dedup: a
        # cancelled attempt can persist a stopped partial answer under this
        # same deterministic assistant cmid, the retry's insert dedups onto that
        # row WITHOUT updating its content, and the resync then seeds the
        # PARTIAL text. Skipping the append there would leave the model's
        # context holding a truncated answer the client never saw.
        await graph.aupdate_state(
            checkpoint_config,
            {
                "messages": [
                    HumanMessage(content=last_user.content, id=user_message_id),
                    AIMessage(content=assistant_content, id=assistant_message_id),
                ]
            },
            as_node="memory_save_node",
        )

        if input_tokens or output_tokens:
            record_token_usage(deployment, input_tokens, output_tokens)
            yield await emitter.emit(
                AgentStreamEvent.USAGE,
                {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )

        done_payload: Dict[str, Any] = {
            "status": "complete",
            "tool_executions": [],
        }
        if _canonical_persistence_enabled():
            done_payload.update(
                {
                    "thread_id": resolved_thread_id,
                    "assistant_message_id": persisted_assistant_id,
                    "client_message_id": assistant_cmid,
                }
            )
        # Commit completion before exposing the terminal frame. A disconnect
        # immediately after ``done`` must not race into run.cancelled.
        await _finalize_run(
            db,
            acceptance,
            current_user,
            status=JobStatus.COMPLETED,
            event_type=RunEventType.RUN_COMPLETED,
            payload=(
                {"assistant_message_id": persisted_assistant_id}
                if persisted_assistant_id
                else {}
            ),
        )
        yield await emitter.emit(AgentStreamEvent.DONE, done_payload)
        await emitter.finish()
    except (asyncio.CancelledError, GeneratorExit) as exit_exc:
        await _run_interrupted_cleanup(cancel_fast_path)
        raise exit_exc
    except Exception as exc:
        logger.error("Luna fast-path stream failed", exc_info=exc)
        await persist_partial()
        yield await emitter.emit(
            AgentStreamEvent.ERROR,
            error_frame_payload(exc),
        )
        await emitter.finish()
        await _finalize_run(
            db,
            acceptance,
            current_user,
            status=JobStatus.FAILED,
            event_type=RunEventType.RUN_FAILED,
            payload={
                "code": "luna_stream_failed",
                "message": client_safe_error(exc),
            },
        )


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
            encoded = _json.dumps(output, default=str)
            if len(encoded) <= 500:
                return encoded
            if isinstance(output, dict):
                # Over the cap: shorten long string values instead of slicing
                # the serialized JSON mid-token — identity fields the frontend
                # parses (note_id, project_id, …) must survive as valid JSON.
                compact = {
                    key: (
                        value[:120] + "…"
                        if isinstance(value, str) and len(value) > 120
                        else value
                    )
                    for key, value in output.items()
                }
                encoded = _json.dumps(compact, default=str)
                if len(encoded) <= 500:
                    return encoded
            return encoded[:500]
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


def build_stream_envelope(
    data: Dict[str, Any],
    *,
    seq: int,
    trace_id: str,
    thread_id: Optional[str] = None,
    route: str = "pending",
    stream_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Wrap an SSE payload in the agent stream envelope.

    Single source of the envelope shape (schema_version, sequence, event_id,
    occurred_at, trace_id, thread_id, route). ``_SeqEmitter.emit`` is the main
    caller; anything else that has to put a frame on the wire outside a live
    stream (see ``_pending_confirmation_frame`` on the resume path) goes
    through here rather than hand-rolling a payload that drifts.
    """
    envelope = {
        **data,
        "schema_version": AGENT_STREAM_SCHEMA_VERSION,
        "sequence": seq,
        "event_id": f"{trace_id}:{seq}",
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trace_id": trace_id,
        "thread_id": thread_id,
        "route": route,
    }
    # Additive run-correlation field (codex audit CX1): clients echo it on
    # /stream/resume so a replayed resume can't attach to a NEWER stream on
    # the same thread. Omitted (not null) when the emitter has no buffer id,
    # so non-buffered frames keep their exact pre-change shape.
    if stream_id is not None:
        envelope["stream_id"] = stream_id
    return envelope


def format_stream_envelope_frame(
    event_type: Any,
    data: Dict[str, Any],
    *,
    seq: int,
    trace_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    route: str = "pending",
    stream_id: Optional[str] = None,
) -> str:
    """Serialize one enveloped SSE frame, ``id:`` line included.

    The ``id:`` line is what EventSource turns into Last-Event-ID, so a frame
    emitted without it silently freezes the client's resume cursor.
    """
    return _format_sse_event(
        event_type,
        build_stream_envelope(
            data,
            seq=seq,
            trace_id=trace_id or str(_uuid.uuid4()),
            thread_id=thread_id,
            route=route,
            stream_id=stream_id,
        ),
        seq=seq,
    )


class _SeqEmitter:
    """Sequence-numbered SSE frames, teed into the resumable-stream Redis
    buffer (``src.services.agent.stream_buffer``). Buffering is best-effort:
    Redis down degrades to plain live streaming, never a failed turn.
    """

    def __init__(
        self,
        *,
        trace_id: Optional[str] = None,
        slo_tracker: Optional[AgentStreamSLOTracker] = None,
        started_at: Optional[float] = None,
    ) -> None:
        """``started_at`` is a ``time.monotonic()`` reading from the route
        handler's first line. The emitter is built only after auth, rate
        limiting, and body parsing have run, so stamping the SLI clock here
        would exclude the very overhead the accepted-latency SLI exists to
        measure. Falls back to "now" when a caller has no reading."""
        self.seq = 0
        self.sid: Optional[str] = None
        self.thread_id: Optional[str] = None
        self.trace_id = trace_id or str(_uuid.uuid4())
        self.route = "pending"
        self.slo_tracker = slo_tracker or AgentStreamSLOTracker(started_at=started_at)

    def set_context(
        self, *, thread_id: Optional[str] = None, route: Optional[str] = None
    ) -> None:
        if thread_id is not None:
            self.thread_id = thread_id
        if route is not None:
            self.route = route if route in _STREAM_ROUTES else "unknown"
            self.slo_tracker.set_route(self.route)

    async def start(self, thread_id: str) -> None:
        self.set_context(thread_id=thread_id)
        try:
            self.sid = await _stream_buffer.start_stream(thread_id)
        except Exception:
            logger.debug("stream_buffer.start_stream failed", exc_info=True)

    async def emit(
        self, event_type: str, data: Dict[str, Any], *, buffer: bool = True
    ) -> str:
        self.seq += 1
        self.slo_tracker.record(event_type, data)
        frame = format_stream_envelope_frame(
            event_type,
            data,
            seq=self.seq,
            trace_id=self.trace_id,
            thread_id=self.thread_id,
            route=self.route,
            stream_id=self.sid,
        )
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
_SSE_DISCONNECT_POLL_SECONDS = 0.5


def _get_disconnect_signal(request: Any) -> Optional[asyncio.Event]:
    signal = getattr(getattr(request, "state", None), AGENT_DISCONNECT_EVENT, None)
    return signal if isinstance(signal, asyncio.Event) else None


async def _request_disconnected(request: Any) -> bool:
    signal = _get_disconnect_signal(request)
    return bool(signal and signal.is_set()) or await request.is_disconnected()


async def _run_interrupted_cleanup(cleanup: Any) -> None:
    """Finish durable cleanup outside the request's cancelled AnyIO scope."""

    async def shielded_cleanup() -> None:
        with CancelScope(shield=True):
            await cleanup()

    cleanup_task = asyncio.create_task(shielded_cleanup())
    while not cleanup_task.done():
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            continue


def _cancel_current_task_on_disconnect(request: Any) -> Optional[asyncio.Task]:
    signal = _get_disconnect_signal(request)
    stream_task = asyncio.current_task()
    if signal is None or stream_task is None:
        return None

    async def cancel_stream() -> None:
        await signal.wait()
        stream_task.cancel()

    return asyncio.create_task(cancel_stream())


_PLANNER_CHAIN_NODES = frozenset(
    {
        "planner_node",
        "research_planner_node",
        "writing_planner_node",
        "data_planner_node",
    }
)


def _consume_pending_pull_result(pending: asyncio.Task) -> None:
    """Consume a detached pull result so asyncio never reports it as unhandled."""
    try:
        pending.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.debug("Detached agent stream pull failed", exc_info=True)


async def _close_async_iterator(iterator: Any) -> None:
    """Bound iterator shutdown so durable cancellation cannot wait on an LLM."""
    close_task = asyncio.create_task(iterator.aclose())
    try:
        done, _ = await asyncio.wait({close_task}, timeout=_SSE_DISCONNECT_POLL_SECONDS)
    except BaseException:
        close_task.cancel()
        if close_task.done():
            _consume_pending_pull_result(close_task)
        else:
            close_task.add_done_callback(_consume_pending_pull_result)
        raise
    if close_task in done:
        _consume_pending_pull_result(close_task)
        return
    close_task.cancel()
    await _cancel_pending_graph_pull(close_task, request_cancel=False)
    logger.warning(
        "Timed out closing agent stream iterator",
        extra={
            "event": "agent_stream_iterator_close_timeout",
            "cleanup_timeout_seconds": _SSE_DISCONNECT_POLL_SECONDS,
        },
    )


async def _cancel_pending_graph_pull(
    pending: asyncio.Task, *, request_cancel: bool = True
) -> None:
    """Cancel and briefly settle one pull without swallowing caller cancellation."""
    current_task = asyncio.current_task()
    cancellation_count = current_task.cancelling() if current_task else 0
    cancellation_active = cancellation_count > 0
    cancellation_exc: asyncio.CancelledError | None = None
    cleanup_deadline = time.monotonic() + _SSE_DISCONNECT_POLL_SECONDS

    if request_cancel and not pending.done():
        pending.cancel()
    while not pending.done():
        remaining = cleanup_deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            await asyncio.wait_for(asyncio.shield(pending), timeout=remaining)
        except asyncio.TimeoutError:
            break
        except asyncio.CancelledError as exc:
            if (
                cancellation_exc is None
                and not cancellation_active
                and current_task is not None
                and current_task.cancelling() > cancellation_count
            ):
                cancellation_exc = exc
            continue
        except BaseException:
            break
    if pending.done():
        _consume_pending_pull_result(pending)
    else:
        logger.warning(
            "Timed out settling cancelled agent stream pull",
            extra={
                "event": "agent_stream_pull_cleanup_timeout",
                "cleanup_timeout_seconds": _SSE_DISCONNECT_POLL_SECONDS,
            },
        )
        pending.add_done_callback(_consume_pending_pull_result)
    if cancellation_exc is not None:
        raise cancellation_exc


async def _graph_events_with_keepalive(event_stream_iter, request: Any):
    """Yield LangGraph events, interleaving keepalive markers during long gaps.

    On client disconnect, emit a ``{"type": "disconnect"}`` sentinel and stop.
    A browser Stop is an explicit cancellation boundary even when resumable
    buffering is available; the caller closes the graph and records the
    terminal cancelled event instead of producing a later completion.
    """
    pending: asyncio.Task | None = None
    pending_cancel_requested = False
    next_keepalive_at = time.monotonic() + _SSE_KEEPALIVE_SECONDS
    try:
        while True:
            if await _request_disconnected(request):
                if pending is not None:
                    pending.cancel()
                    pending_cancel_requested = True
                yield {"type": "disconnect"}
                return
            if pending is None:
                pending = asyncio.create_task(event_stream_iter.__anext__())
            done, _ = await asyncio.wait(
                {pending},
                timeout=min(
                    _SSE_DISCONNECT_POLL_SECONDS,
                    max(0, next_keepalive_at - time.monotonic()),
                ),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if pending in done:
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
                continue

            if await _request_disconnected(request):
                pending.cancel()
                pending_cancel_requested = True
                yield {"type": "disconnect"}
                return
            now = time.monotonic()
            if now >= next_keepalive_at:
                yield {"type": "keepalive", "elapsed_ms": int(time.time() * 1000)}
                next_keepalive_at = now + _SSE_KEEPALIVE_SECONDS
    finally:
        # Never leak the in-flight __anext__ task — on disconnect or error it
        # would otherwise drive one more graph step after we stop reading.
        if pending is not None:
            pending_pull = pending
            pending = None
            await _cancel_pending_graph_pull(
                pending_pull,
                request_cancel=not pending_cancel_requested,
            )


async def stream_event_generator(
    request_body: Any,  # AgentExecuteRequest
    request: Any,  # FastAPI Request
    current_user: User,
    *,
    background_tasks: Any = None,  # fastapi.BackgroundTasks (optional for tests)
    request_started_at: Optional[float] = None,
):
    """SSE event generator for the /stream endpoint.

    Yields SSE-formatted events: token, tool_start, tool_end,
    rag_context, plan, reflection, confirmation, done, error.

    ``request_started_at`` is the route handler's entry ``time.monotonic()``
    reading; it anchors the accepted-latency SLI to request arrival rather
    than to generator start (which happens after auth and rate limiting).

    Since P0-C the ``accepted`` frame follows the accept transaction rather
    than preceding it, so that SLI now covers thread resolution and the commit
    as well. That is intended: the number the SLI exists to report is how long
    until the client has a *trustworthy* acknowledgment, and an acknowledgment
    emitted before the write it describes was never worth measuring.
    """
    from src.services.agent.checkpointer import get_checkpointer, reset_checkpointer
    from src.services.agent.graph import compile_agent_graph
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
    emitter = _SeqEmitter(
        trace_id=_request_trace_id(request),
        started_at=request_started_at,
    )
    client_disconnected = False
    # Set once an assistant row for this turn has been persisted/scheduled —
    # the error-path partial persist must never double-write the turn.
    assistant_persisted = False
    persist_partial_stop = None  # bound inside try once its inputs exist
    # Declared out here, not in the try: the CancelledError cleanup below reads
    # it to link the cancelled run to its stopped partial row, and that handler
    # can fire before the try body has run.
    persisted_assistant_id: Optional[str] = None
    event_stream_iter = None
    # Set once the accept transaction has COMMITTED (P0-C). Everything after
    # the accepted frame keys off this: the run's ledger, the outbox stamp and
    # the terminal status all address `acceptance.run_id`.
    acceptance: Optional[AcceptedSubmission] = None
    org_id = getattr(current_user, "organization_id", None)
    latest_user_message = next(
        (
            message
            for message in reversed(request_body.messages)
            if message.role == "user"
        ),
        None,
    )
    client_message_id = getattr(latest_user_message, "client_message_id", None)
    disconnect_canceller = _cancel_current_task_on_disconnect(request)
    try:
        # Resolve the thread and verify ownership BEFORE acknowledging anything
        # — the acknowledgment is now a claim about durable state, so it cannot
        # precede the write it describes.
        thread_obj = None
        try:
            thread_obj, _conversation_id = await _resolve_thread(
                db, current_user, request_body
            )
            if thread_obj is not None:
                resolved_thread_id = str(thread_obj.id)
                if request_body.thread_id != resolved_thread_id:
                    request_body.thread_id = resolved_thread_id
        except Exception:
            logger.warning(
                "Failed to resolve agent thread before routing",
                exc_info=True,
            )

        # ------------------------------------------------------------------
        # Atomic accept (P0-C). One transaction commits the user message, the
        # run row, its `run.created` event and the outbox dispatch record; the
        # accepted frame below is emitted only afterwards and carries the real
        # run id. A failure here raises into the error handler: no `accepted`,
        # an `error` frame, and the rollback guarantees nothing half-written.
        #
        # Degraded path: a user with no workspace has no durable thread
        # (`_resolve_thread` returns None), so there is nothing to make atomic.
        # That turn still streams an answer exactly as before, with a null run
        # id on the accepted frame — unchanged behaviour, not a new hole.
        # ------------------------------------------------------------------
        if _accept_eligible(thread_obj):
            acceptance = await accept_submission(
                db,
                current_user=current_user,
                request=request_body,
                thread=thread_obj,
            )
        else:
            logger.info(
                "Agent stream accepted without a durable run: no ownership-"
                "verified thread for this submission",
                extra={"thread_id": request_body.thread_id},
            )

        # First server-sourced progress signal — now a post-commit fact. It
        # stays unbuffered: the resumable Redis pointer is opened by the route
        # branches below, which own the thread-scoped stream id.
        yield await emitter.emit(
            AgentStreamEvent.STATUS,
            {
                "phase": "accepted",
                "detail": "Request accepted",
                "run_id": acceptance.run_id if acceptance is not None else None,
            },
            buffer=False,
        )

        from src.core.config import get_settings
        from src.services.agent.fast_path import classify_fast_path_turn

        settings = get_settings()
        page_context = _page_context_to_dict(request_body.page_context)
        fast_decision = classify_fast_path_turn(
            messages=request_body.messages,
            page_context=page_context,
            use_rag=request_body.use_rag,
            max_input_chars=settings.AGENT_FAST_PATH_MAX_INPUT_CHARS,
        )
        if (
            settings.AGENT_FAST_PATH_ENABLED
            and fast_decision.eligible
            and resolved_thread_id is not None
        ):
            emitter.set_context(route="luna")
            fast_path_iter = _stream_luna_fast_path(
                request_body=request_body,
                request=request,
                current_user=current_user,
                db=db,
                resolved_thread_id=resolved_thread_id,
                emitter=emitter,
                stream_started_at=stream_started_at,
                trace_metadata=build_trace_metadata(
                    trace_source=TraceSource.NON_GRAPH,
                    user_id=current_user.id,
                    org_id=org_id,
                    thread_id=(
                        acceptance.thread_id if acceptance is not None else None
                    ),
                    request_id=emitter.trace_id,
                    agent_run_id=(
                        acceptance.run_id if acceptance is not None else None
                    ),
                    user_message_id=(
                        acceptance.user_message_id if acceptance is not None else None
                    ),
                    client_message_id=client_message_id,
                ),
                acceptance=acceptance,
            )
            try:
                async for frame in fast_path_iter:
                    yield frame
            finally:
                await _close_async_iterator(fast_path_iter)
            return

        # Edit-and-resend: whichever writer owned this turn's user row also
        # owned its tombstones, so the report is sourced from that writer —
        # the accept transaction (P0-C) when it ran, the guarded persist on the
        # degraded no-durable-run path.
        tombstones = TombstoneReport()
        if acceptance is not None:
            if acceptance.tombstoned:
                tombstones.mark()
        elif thread_obj is not None:
            # Degraded accept (no durable run): keep the pre-P0-C
            # durable-before-LLM guarantee for the user row. When the accept
            # committed, that row is already in it — writing it again here
            # would insert a SECOND row for a legacy client that sends no
            # client_message_id (nothing for ON CONFLICT to infer).
            await _persist_user_message_guarded(
                db,
                current_user,
                request_body,
                tombstoned_out=tombstones,
            )

        _bootstrap_langsmith()
        checkpointer = await get_checkpointer()
        store = await get_memory_store()
        graph = compile_agent_graph(checkpointer=checkpointer, store=store)

        # Edit-and-resend: rebuild the HEAD checkpoint from the post-edit DB
        # BEFORE assembling model input, so the model never sees the superseded
        # prompt or its answer. Never rewinds to an earlier checkpoint_id —
        # that forks the thread while every other writer targets head.
        if tombstones.any:
            await resync_thread_checkpoint(
                graph,
                thread_id=resolved_thread_id or stream_thread_id,
                user=current_user,
            )

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
            "use_rag": request_body.use_rag,
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
            "metadata": build_trace_metadata(
                trace_source=TraceSource.GRAPH,
                user_id=current_user.id,
                org_id=org_id,
                thread_id=(acceptance.thread_id if acceptance is not None else None),
                request_id=emitter.trace_id,
                agent_run_id=(acceptance.run_id if acceptance is not None else None),
                user_message_id=(
                    acceptance.user_message_id if acceptance is not None else None
                ),
                client_message_id=client_message_id,
            ),
        }

        emitter.set_context(route="graph")
        await emitter.start(stream_thread_id)

        yield await emitter.emit(
            AgentStreamEvent.STATUS,
            {"phase": "routing", "detail": "Choosing the safest response path"},
        )

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
        if acceptance is not None:
            # The dispatch the outbox row recorded has now happened (in-process,
            # exactly as before P0-C). Stamping it closes the record so a future
            # relay cannot re-dispatch a run that already ran, and moves the run
            # queued → running. Best-effort; never raises.
            await mark_submission_dispatched(
                db,
                run_id=acceptance.run_id,
                outbox_id=acceptance.outbox_id,
                organization_id=org_id,
            )
        first_event_yielded = False
        streamed_token = False
        # persisted_assistant_id is hoisted to the function top (see there).
        completed_root_values: Optional[Dict[str, Any]] = None
        # Accumulated user-facing tokens, so a client abort can persist the
        # partial answer server-side (stopped=True) instead of losing it.
        streamed_parts: List[str] = []
        # Deterministic assistant-side idempotency key derived from the user
        # turn's client_message_id: an SSE retry of the same turn maps to the
        # same key, so the assistant-role partial unique index dedupes it.
        assistant_cmid: Optional[str] = None
        if client_message_id is not None:
            assistant_cmid = str(
                _uuid.uuid5(
                    _uuid.NAMESPACE_URL,
                    f"nous-assistant:{client_message_id}",
                )
            )

        async def persist_partial_stop(*, force_inline: bool = False) -> None:
            """Persist the accumulated partial answer with stopped=True.

            Shared by the legacy (no stream buffer) disconnect branch and the
            error path when a disconnected drain dies mid-run (e.g. the 300s
            timeout) — without it that partial would be silently lost.
            """
            nonlocal assistant_persisted, persisted_assistant_id
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
            if background_tasks is not None and not force_inline:
                # Deferred to a background task: no id to capture here. Callers
                # that need the run linked to its partial row (cancellation)
                # pass force_inline=True and take the awaited branch below.
                background_tasks.add_task(
                    _jobs_mod._persist_assistant_message_safe, **stop_kwargs
                )
            else:
                persisted_assistant_id = (
                    await _jobs_mod._persist_assistant_message_safe(**stop_kwargs)
                )

        async def cancel_current_stream() -> None:
            """Best-effort durable cleanup for polling and ASGI cancellation."""
            if event_stream_iter is not None:
                with contextlib.suppress(BaseException):
                    await _close_async_iterator(event_stream_iter)
            with contextlib.suppress(BaseException):
                await persist_partial_stop(force_inline=True)
            with contextlib.suppress(BaseException):
                await emitter.finish()
            with contextlib.suppress(BaseException):
                cancelled_payload: Dict[str, Any] = {
                    "reason": "client_disconnected",
                    "request_id": emitter.trace_id,
                }
                # Link the run to the stopped partial row persisted just above,
                # so a cancelled run can still name the message holding its
                # output. Omitted when nothing streamed before the abort.
                if persisted_assistant_id:
                    cancelled_payload["assistant_message_id"] = persisted_assistant_id
                await _finalize_run(
                    db,
                    acceptance,
                    current_user,
                    status=JobStatus.CANCELLED,
                    event_type=RunEventType.RUN_CANCELLED,
                    payload=cancelled_payload,
                )

        async with asyncio.timeout(300):  # 5 minutes
            while True:
                try:
                    async for item in _graph_events_with_keepalive(
                        event_stream_iter, request
                    ):
                        if item["type"] == "disconnect":
                            client_disconnected = True
                            break
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

                        if kind == "on_chain_end" and not event.get("parent_ids"):
                            output = event.get("data", {}).get("output")
                            if isinstance(output, dict):
                                messages_out = output.get("messages") or []
                                last_message = (
                                    messages_out[-1] if messages_out else None
                                )
                                if last_message is not None and not getattr(
                                    last_message, "tool_calls", None
                                ):
                                    completed_root_values = output

                        if kind == "on_chat_model_stream":
                            if not _is_user_facing_token_event(event):
                                continue
                            chunk = event.get("data", {}).get("chunk")
                            # _chunk_text, not chunk.content: on the Responses
                            # API content is a list of typed blocks, and the
                            # reasoning ones must not reach the wire.
                            chunk_text = _chunk_text(chunk) if chunk else ""
                            if chunk_text:
                                streamed_token = True
                                # Buffer BEFORE recording for persistence.
                                # streamed_parts feeds the stopped partial row;
                                # emit() feeds the resumable buffer. Appending
                                # first meant a cancellation inside this await
                                # persisted a chunk no replay ever saw. This
                                # order can only lose the last chunk instead,
                                # keeping the persisted partial a prefix of the
                                # buffered stream.
                                frame = await emitter.emit(
                                    AgentStreamEvent.TOKEN, {"content": chunk_text}
                                )
                                streamed_parts.append(chunk_text)
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
        # A browser Stop is terminal even when Redis buffering is active: close
        # the graph, keep the partial answer, clear the buffer pointer, and
        # persist run.cancelled before returning.
        if client_disconnected:
            logger.info(
                "SSE client disconnected; cancelled agent run for thread %s",
                stream_thread_id,
            )
            await cancel_current_stream()
            return

        # Check graph state after streaming completes
        tool_executions_out: Optional[list] = None
        try:
            final_snapshot = None
            if completed_root_values is not None:
                final_values = completed_root_values
            else:
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
                # Parked, not finished: the run resumes on /stream/confirm, so
                # its ledger stays OPEN (no terminal event) and only the status
                # moves. It keeps holding the thread's active-run slot until it
                # resumes or the next submission supersedes it.
                await _finalize_run(
                    db,
                    acceptance,
                    current_user,
                    status=JobStatus.AWAITING_CONFIRMATION,
                )
                return

            assistant_content = ""
            for msg in reversed(final_values.get("messages", [])):
                if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                    assistant_content = _chunk_text(msg)
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
        # Commit completion before exposing the terminal frame. A disconnect
        # immediately after ``done`` must not race into run.cancelled.
        await _finalize_run(
            db,
            acceptance,
            current_user,
            status=JobStatus.COMPLETED,
            event_type=RunEventType.RUN_COMPLETED,
            payload=(
                {"assistant_message_id": persisted_assistant_id}
                if persisted_assistant_id
                else {}
            ),
        )
        frame = await emitter.emit(AgentStreamEvent.DONE, done_payload)
        if not client_disconnected:
            yield frame
        await emitter.finish()

    except (asyncio.CancelledError, GeneratorExit) as cancellation_exc:
        # Starlette cancels StreamingResponse's body iterator directly when
        # the client aborts the fetch. Shield the cleanup so that cancellation
        # cannot leave the graph running or the durable run non-terminal.
        async def cleanup_cancelled_response() -> None:
            if event_stream_iter is not None:
                with contextlib.suppress(BaseException):
                    await _close_async_iterator(event_stream_iter)
            if persist_partial_stop is not None:
                with contextlib.suppress(BaseException):
                    await persist_partial_stop(force_inline=True)
            with contextlib.suppress(BaseException):
                await emitter.finish()
            with contextlib.suppress(BaseException):
                cancelled_payload: Dict[str, Any] = {
                    "reason": "client_disconnected",
                    "request_id": emitter.trace_id,
                }
                # Link the run to the stopped partial row persisted just above,
                # so a cancelled run can still name the message holding its
                # output. Omitted when nothing streamed before the abort.
                if persisted_assistant_id:
                    cancelled_payload["assistant_message_id"] = persisted_assistant_id
                await _finalize_run(
                    db,
                    acceptance,
                    current_user,
                    status=JobStatus.CANCELLED,
                    event_type=RunEventType.RUN_CANCELLED,
                    payload=cancelled_payload,
                )

        await _run_interrupted_cleanup(cleanup_cancelled_response)
        raise cancellation_exc

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
                error_frame_payload(
                    "Interrupt state could not be saved. Please retry.",
                    AgentErrorCategory.CHECKPOINT_UNAVAILABLE,
                ),
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
        if checkpoint_ok:
            # Parked on a confirmation — ledger stays open (see above).
            await _finalize_run(
                db,
                acceptance,
                current_user,
                status=JobStatus.AWAITING_CONFIRMATION,
            )
        else:
            await _finalize_run(
                db,
                acceptance,
                current_user,
                status=JobStatus.FAILED,
                event_type=RunEventType.RUN_FAILED,
                payload={
                    "code": "interrupt_not_checkpointed",
                    "message": "Interrupt state could not be saved.",
                    # Same enum as the wire `category` key — the ledger's
                    # `code`/`error_code` stay the historical SITE codes (they
                    # are already persisted and identify where it broke, not
                    # why), so this adds the category without renaming them.
                    "category": AgentErrorCategory.CHECKPOINT_UNAVAILABLE.value,
                },
                error_code="interrupt_not_checkpointed",
                error="Interrupt state could not be saved. Please retry.",
            )

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
        category = _stream_failure_category(e)
        frame = await emitter.emit(
            AgentStreamEvent.ERROR, error_frame_payload(e, category)
        )
        if not client_disconnected:
            yield frame
        await emitter.finish()
        # `acceptance is None` here covers the case that matters most: the
        # accept transaction itself failed, so there is nothing to finalize —
        # and, by construction, no `accepted` frame was ever emitted.
        await _finalize_run(
            db,
            acceptance,
            current_user,
            status=JobStatus.FAILED,
            event_type=RunEventType.RUN_FAILED,
            payload={
                "code": "stream_failed",
                "message": client_safe_error(e),
                # See the interrupt branch above: `code`/`error_code` keep
                # their historical site values; the category rides alongside.
                "category": category.value,
            },
            error_code="stream_failed",
            error=client_safe_error(e),
        )

    finally:
        if disconnect_canceller is not None:
            disconnect_canceller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await disconnect_canceller
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
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store

    # Lazy import schemas
    from .execute import (
        AgentExecuteRequest,
        AgentMessage,
        PageContextRequest,
        ToolExecutionResponse,
    )

    db = AsyncSessionLocal()
    emitter = _SeqEmitter(trace_id=_request_trace_id(request))
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
    confirm_event_iter = None
    active_run = None
    persist_partial_stop = None
    # Declared out here, not in the try: the CancelledError cleanup below reads
    # it to link the cancelled run to its stopped partial row, and that handler
    # can fire before the try body has run.
    persisted_assistant_id: Optional[str] = None
    disconnect_canceller = _cancel_current_task_on_disconnect(request)
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
                AgentStreamEvent.ERROR,
                error_frame_payload(
                    _CONFIRM_NOT_FOUND_MESSAGE, _CONFIRM_NOT_FOUND_CATEGORY
                ),
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
                AgentStreamEvent.ERROR,
                error_frame_payload(
                    _CONFIRM_NOT_FOUND_MESSAGE, _CONFIRM_NOT_FOUND_CATEGORY
                ),
            )
            return

        # The checkpoint proves thread ownership; the tenant-scoped durable
        # run lookup supplies only identifiers that can be joined to the run
        # ledger. A legacy checkpoint with no active run still gets release,
        # actor, thread, and request correlation without inventing run ids.
        active_run = await get_active_run_for_thread(
            db,
            request_body.thread_id,
            organization_id=getattr(current_user, "organization_id", None),
            user_id=current_user.id,
        )
        if asyncio.iscoroutine(active_run):  # fail closed on a malformed DB adapter
            active_run.close()
            active_run = None

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
                        error_frame_payload(
                            "Confirmation already in progress",
                            AgentErrorCategory.CONFLICT,
                        ),
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
            "metadata": build_trace_metadata(
                trace_source=TraceSource.GRAPH,
                user_id=current_user.id,
                org_id=getattr(current_user, "organization_id", None),
                thread_id=request_body.thread_id,
                request_id=emitter.trace_id,
                agent_run_id=(active_run.job_id if active_run is not None else None),
                user_message_id=(
                    active_run.user_message_id if active_run is not None else None
                ),
                client_message_id=(
                    active_run.client_message_id if active_run is not None else None
                ),
            ),
        }

        resume_input = Command(resume={"confirmed": request_body.confirmed})

        emitter.set_context(route="graph")
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

        async def persist_partial_stop(*, force_inline: bool = False) -> None:
            """Persist the accumulated partial answer with stopped=True.

            Shared by the legacy (no stream buffer) disconnect branch and the
            error path when a disconnected drain dies mid-run (e.g. the 300s
            timeout) — without it that partial would be silently lost.
            """
            nonlocal assistant_persisted, persisted_assistant_id
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
            if background_tasks is not None and not force_inline:
                # Deferred to a background task: no id to capture here. Callers
                # that need the run linked to its partial row (cancellation)
                # pass force_inline=True and take the awaited branch below.
                background_tasks.add_task(
                    _jobs_mod._persist_assistant_message_safe, **stop_kwargs
                )
            else:
                persisted_assistant_id = (
                    await _jobs_mod._persist_assistant_message_safe(**stop_kwargs)
                )

        async def cancel_confirm_stream() -> None:
            if confirm_event_iter is not None:
                with contextlib.suppress(BaseException):
                    await _close_async_iterator(confirm_event_iter)
            with contextlib.suppress(BaseException):
                await persist_partial_stop(force_inline=True)
            with contextlib.suppress(BaseException):
                await emitter.finish()
            with contextlib.suppress(BaseException):
                cancelled_payload: Dict[str, Any] = {
                    "reason": "client_disconnected",
                    "request_id": emitter.trace_id,
                }
                # Link the run to the stopped partial row persisted just above,
                # so a cancelled run can still name the message holding its
                # output. Omitted when nothing streamed before the abort.
                if persisted_assistant_id:
                    cancelled_payload["assistant_message_id"] = persisted_assistant_id
                await _finalize_run_id(
                    db,
                    str(active_run.job_id) if active_run is not None else None,
                    current_user,
                    status=JobStatus.CANCELLED,
                    event_type=RunEventType.RUN_CANCELLED,
                    payload=cancelled_payload,
                )

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
            async for item in _graph_events_with_keepalive(confirm_event_iter, request):
                # CX1: the resumed graph is now making real progress — a
                # failure from here on must NOT release the claim (the
                # winner may already have run a destructive tool; TTL
                # handles cleanup instead of letting a racing retry in).
                events_started = True
                if item["type"] == "disconnect":
                    client_disconnected = True
                    break
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
                    # See the note on the main stream: Responses-API chunks
                    # carry typed blocks, not a bare string.
                    chunk_text = _chunk_text(chunk) if chunk else ""
                    if chunk_text:
                        # Buffer BEFORE recording for persistence — same
                        # ordering invariant as the main stream: the stopped
                        # partial must stay a prefix of the buffered stream, so
                        # a cancellation inside this await can only lose the
                        # last chunk, never invent one.
                        frame = await emitter.emit(
                            AgentStreamEvent.TOKEN, {"content": chunk_text}
                        )
                        streamed_parts.append(chunk_text)
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
        if client_disconnected:
            logger.info(
                "SSE confirm client disconnected; cancelled resumed run for thread %s",
                request_body.thread_id,
            )
            await cancel_confirm_stream()
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
            await _finalize_run_id(
                db,
                str(active_run.job_id) if active_run is not None else None,
                current_user,
                status=JobStatus.AWAITING_CONFIRMATION,
            )
            return

        final_values = final_snapshot.values if final_snapshot else {}
        tool_executions_out = [
            ToolExecutionResponse(**te)
            for te in final_values.get("tool_executions", [])
        ] or None

        assistant_content = ""
        for msg in reversed(final_values.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                assistant_content = _chunk_text(msg)
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
        # persisted_assistant_id is hoisted to the function top (see there).
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
        # Commit completion before exposing the terminal frame. A disconnect
        # immediately after ``done`` must not race into run.cancelled.
        await _finalize_run_id(
            db,
            str(active_run.job_id) if active_run is not None else None,
            current_user,
            status=JobStatus.COMPLETED,
            event_type=RunEventType.RUN_COMPLETED,
            payload=(
                {"assistant_message_id": persisted_assistant_id}
                if persisted_assistant_id
                else {}
            ),
        )
        frame = await emitter.emit(AgentStreamEvent.DONE, done_payload)
        if not client_disconnected:
            yield frame
        await emitter.finish()

    except (asyncio.CancelledError, GeneratorExit) as cancellation_exc:

        async def cleanup_cancelled_confirm_response() -> None:
            if confirm_event_iter is not None:
                with contextlib.suppress(BaseException):
                    await _close_async_iterator(confirm_event_iter)
            if persist_partial_stop is not None:
                with contextlib.suppress(BaseException):
                    await persist_partial_stop(force_inline=True)
            with contextlib.suppress(BaseException):
                await emitter.finish()
            with contextlib.suppress(BaseException):
                cancelled_payload: Dict[str, Any] = {
                    "reason": "client_disconnected",
                    "request_id": emitter.trace_id,
                }
                # Link the run to the stopped partial row persisted just above,
                # so a cancelled run can still name the message holding its
                # output. Omitted when nothing streamed before the abort.
                if persisted_assistant_id:
                    cancelled_payload["assistant_message_id"] = persisted_assistant_id
                await _finalize_run_id(
                    db,
                    str(active_run.job_id) if active_run is not None else None,
                    current_user,
                    status=JobStatus.CANCELLED,
                    event_type=RunEventType.RUN_CANCELLED,
                    payload=cancelled_payload,
                )

        await _run_interrupted_cleanup(cleanup_cancelled_confirm_response)
        raise cancellation_exc

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
        # R2-H1: an error at confirm time previously left the durable run
        # AWAITING_CONFIRMATION forever — the thread read as blocked and the
        # run never terminated. Finalize as FAILED (best-effort; the user
        # still gets the ERROR frame either way).
        with contextlib.suppress(Exception):
            await _finalize_run_id(
                db,
                str(active_run.job_id) if active_run is not None else None,
                current_user,
                status=JobStatus.FAILED,
                event_type=RunEventType.RUN_FAILED,
                payload={
                    "reason": "confirm_error",
                    "error": str(e)[:500],
                    "request_id": emitter.trace_id,
                },
            )
        frame = await emitter.emit(AgentStreamEvent.ERROR, error_frame_payload(e))
        if not client_disconnected:
            yield frame
        await emitter.finish()

    finally:
        if disconnect_canceller is not None:
            disconnect_canceller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await disconnect_canceller
        await db.close()
        logger.info("SSE confirm stream ended for thread %s", request_body.thread_id)
