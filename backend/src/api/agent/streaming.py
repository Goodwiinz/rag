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

from . import jobs as _jobs_mod
from .jobs import (
    _clear_stale_pending_confirmation,
    _get_latest_user_content,
    _page_context_to_dict,
    _persist_assistant_message,
    _persist_thread_messages,
    _persist_user_message,
    _resolve_and_bind_project,
    _resolve_thread,
)
from .trace_context import build_trace_payload

logger = logging.getLogger(__name__)

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


def _format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format a single SSE event frame."""
    return f"event: {event_type}\ndata: {_json.dumps(data)}\n\n"


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


async def _graph_events_with_keepalive(event_stream_iter, request: Any):
    """Yield LangGraph events, interleaving keepalive markers during long gaps.

    On client disconnect, emits a ``{"type": "disconnect"}`` sentinel and stops.
    The caller closes the underlying graph iterator so the agent run is actually
    cancelled rather than left generating into a dead connection.
    """
    pending: asyncio.Task | None = None
    try:
        while True:
            if await request.is_disconnected():
                yield {"type": "disconnect"}
                return
            if pending is None:
                pending = asyncio.create_task(event_stream_iter.__anext__())
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
    from langchain_core.messages import HumanMessage

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
    config: Dict[str, Any] = {}  # Initialize before try block for safe access in except handlers
    db = AsyncSessionLocal()
    graph = None  # type: ignore[assignment]
    resolved_thread_id: Optional[str] = None
    stream_started_at = time.monotonic()
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
                await _persist_user_message(db, current_user, request_body)
        except Exception:
            logger.warning(
                "Failed to persist user turn before LLM call",
                exc_info=True,
            )

        _bootstrap_langsmith()
        checkpointer = await get_checkpointer()
        store = await get_memory_store()
        graph = compile_agent_graph(checkpointer=checkpointer, store=store)

        messages = [
            HumanMessage(content=m.content)
            for m in request_body.messages
            if m.role == "user"
        ]

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

                project_memories = await load_project_memories(
                    db, str(_pm_project_id)
                )
            except Exception:
                logger.warning("project memory load failed", exc_info=True)

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
        }

        stream_thread_id = request_body.thread_id or str(_uuid.uuid4())
        config = {
            "configurable": {
                "thread_id": stream_thread_id,
                "db": db,
                "current_user": current_user,
                "page_context": page_context,
            }
        }

        yield _format_sse_event(
            "trace",
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
        client_disconnected = False
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
                            elapsed_ms = int((time.monotonic() - stream_started_at) * 1000)
                            yield (
                                "event: heartbeat\n"
                                f"data: {_json.dumps({'elapsed_ms': elapsed_ms})}\n\n"
                            )
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
                                yield f"event: token\ndata: {_json.dumps({'content': chunk.content})}\n\n"

                        elif kind == "on_chat_model_end":
                            inp, out = _extract_usage_tokens(event)
                            turn_input_tokens += inp
                            turn_output_tokens += out

                        elif kind == "on_tool_start":
                            tool_input = event.get("data", {}).get("input", {})
                            args_preview = str(tool_input)[:500] if tool_input else ""
                            yield f"event: tool_start\ndata: {_json.dumps({'tool': name, 'args': args_preview})}\n\n"

                        elif kind == "on_tool_end":
                            output = event.get("data", {}).get("output", "")
                            is_error = (
                                isinstance(output, dict) and bool(output.get("isError"))
                            ) or (
                                getattr(output, "status", None) == "error"
                            )
                            yield f"event: tool_end\ndata: {_json.dumps({'tool': name, 'result': _encode_tool_result(output), 'is_error': is_error})}\n\n"

                        elif kind == "on_chain_end" and name == "rag_node":
                            output = event.get("data", {}).get("output", {})
                            if isinstance(output, dict):
                                contexts = output.get("retrieved_contexts", [])
                                if contexts:
                                    yield f"event: rag_context\ndata: {_json.dumps({'contexts': contexts[:3]})}\n\n"

                        elif kind == "on_chain_end" and name in _PLANNER_CHAIN_NODES:
                            output = event.get("data", {}).get("output", {})
                            if isinstance(output, dict):
                                plan_steps = output.get("plan", [])
                                if plan_steps:
                                    yield f"event: plan\ndata: {_json.dumps({'steps': plan_steps, 'reasoning': ''})}\n\n"

                        elif kind == "on_chain_end" and name == "reflection_gate":
                            output = event.get("data", {}).get("output", {})
                            if isinstance(output, dict):
                                reflection_result = output.get("_reflection_result")
                                if reflection_result is not None:
                                    passed = getattr(reflection_result, "passed", True)
                                    issues = getattr(reflection_result, "issues", [])
                                    round_num = output.get("reflection_count", 0)
                                    yield f"event: reflection\ndata: {_json.dumps({'passed': passed, 'issues': issues, 'round': round_num})}\n\n"
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
                    graph = compile_agent_graph(
                        checkpointer=checkpointer, store=store
                    )
                    await _clear_stale_pending_confirmation(graph, config)
                    event_stream_iter = await _open_event_stream()
                    continue

        # Client hung up mid-stream (hit Stop / closed the tab). Cancel the
        # agent run by closing the graph iterator instead of letting it finish
        # generating into a dead socket, and skip the persist + `done` path —
        # the client preserves and saves its own partial answer.
        if client_disconnected:
            with contextlib.suppress(Exception):
                await event_stream_iter.aclose()
            logger.info(
                "SSE client disconnected; cancelled agent run for thread %s",
                stream_thread_id,
            )
            return

        # Check graph state after streaming completes
        try:
            final_snapshot = await graph.aget_state(config)
            final_values = final_snapshot.values if final_snapshot else {}

            # Check for pending interrupts (HITL confirmation needed)
            pending_tasks = final_snapshot.tasks if final_snapshot else ()
            has_interrupt = any(
                getattr(t, "interrupts", None) for t in pending_tasks
            )

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
                yield f"event: confirmation\ndata: {_json.dumps({'thread_id': thread_id, 'confirmation': confirmation_details})}\n\n"
                return

            assistant_content = ""
            for msg in reversed(final_values.get("messages", [])):
                if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                    assistant_content = msg.content
                    break

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
                )
                if background_tasks is not None:
                    background_tasks.add_task(
                        _jobs_mod._persist_assistant_message_safe,
                        **persist_kwargs,
                    )
                else:
                    # No BackgroundTasks plumbing available (e.g. unit
                    # tests that directly invoke the generator without
                    # passing one). Run inline through the safe wrapper
                    # so the failure-metric path is still exercised.
                    await _jobs_mod._persist_assistant_message_safe(
                        **persist_kwargs
                    )
        except Exception as e:
            logger.warning("Failed to persist SSE thread messages", exc_info=e)

        if turn_input_tokens > 0 or turn_output_tokens > 0:
            yield (
                "event: usage\n"
                f"data: {_json.dumps({'input_tokens': turn_input_tokens, 'output_tokens': turn_output_tokens})}\n\n"
            )

        yield f"event: done\ndata: {_json.dumps({'status': 'complete'})}\n\n"

    except asyncio.CancelledError:
        raise

    except GraphInterrupt as exc:
        # Graph hit an interrupt mid-stream (HITL confirmation needed).
        # Verify the checkpoint was persisted before telling the CLI to confirm.
        interrupts = getattr(exc, "interrupts", [])
        confirmation_details = {}
        if interrupts:
            confirmation_details = getattr(interrupts[0], "value", {})
        thread_id = (config.get("configurable") or {}).get("thread_id") or stream_thread_id

        checkpoint_ok = False
        try:
            if graph is not None:
                verify_snapshot = await graph.aget_state(config)
                checkpoint_ok = bool(
                    verify_snapshot and verify_snapshot.values
                    and any(getattr(t, "interrupts", None) for t in (verify_snapshot.tasks or ()))
                )
        except Exception:
            logger.warning("Failed to verify checkpoint after GraphInterrupt for thread %s", thread_id)

        if not checkpoint_ok:
            logger.error(
                "GraphInterrupt raised but checkpoint not persisted for thread %s — "
                "cannot send confirmation event (client would get 'Thread not found' on resume)",
                thread_id,
            )
            yield f"event: error\ndata: {_json.dumps({'error': 'Interrupt state could not be saved. Please retry.'})}\n\n"
        else:
            yield f"event: confirmation\ndata: {_json.dumps({'thread_id': thread_id, 'confirmation': confirmation_details})}\n\n"

    except Exception as e:
        logger.error("SSE stream error", exc_info=e)
        yield f"event: error\ndata: {_json.dumps({'error': str(e)})}\n\n"

    finally:
        await db.close()
        logger.info("SSE stream ended for thread %s", stream_thread_id)


async def stream_confirm_event_generator(
    request_body: Any,  # StreamConfirmRequest
    request: Any,  # FastAPI Request
    current_user: User,
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
    try:
        _bootstrap_langsmith()
        checkpointer = await get_checkpointer()
        store = await get_memory_store()
        graph = compile_agent_graph(checkpointer=checkpointer, store=store)

        snapshot_config = {
            "configurable": {
                "thread_id": request_body.thread_id,
                "db": db,
                "current_user": current_user,
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
                    "db": db,
                    "current_user": current_user,
                }
            }
            current_snapshot = await graph.aget_state(snapshot_config)

        # Verify thread exists
        if not current_snapshot or not current_snapshot.values:
            yield f"event: error\ndata: {_json.dumps({'error': 'Thread not found'})}\n\n"
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
            yield f"event: error\ndata: {_json.dumps({'error': 'Thread not found'})}\n\n"
            return

        page_context = _page_context_to_dict(
            current_snapshot.values.get("page_context", {})
        )

        config = {
            "configurable": {
                "thread_id": request_body.thread_id,
                "db": db,
                "current_user": current_user,
                "page_context": page_context,
            }
        }

        resume_input = Command(resume={"confirmed": request_body.confirmed})

        yield _format_sse_event(
            "trace",
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

        async with asyncio.timeout(300):
            async for event in graph.astream_events(
                resume_input, config=config, version="v2"
            ):
                if await request.is_disconnected():
                    break

                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chat_model_stream":
                    if not _is_user_facing_token_event(event):
                        continue
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield f"event: token\ndata: {_json.dumps({'content': chunk.content})}\n\n"
                        tokens_emitted = True

                elif kind == "on_chat_model_end":
                    inp, out = _extract_usage_tokens(event)
                    turn_input_tokens += inp
                    turn_output_tokens += out

                elif kind == "on_tool_start":
                    tool_input = event.get("data", {}).get("input", {})
                    args_preview = str(tool_input)[:500] if tool_input else ""
                    yield f"event: tool_start\ndata: {_json.dumps({'tool': name, 'args': args_preview})}\n\n"

                elif kind == "on_tool_end":
                    output = event.get("data", {}).get("output", "")
                    is_error = (
                        isinstance(output, dict) and bool(output.get("isError"))
                    ) or (
                        getattr(output, "status", None) == "error"
                    )
                    yield f"event: tool_end\ndata: {_json.dumps({'tool': name, 'result': _encode_tool_result(output), 'is_error': is_error})}\n\n"

                elif kind == "on_chain_end" and name in _PLANNER_CHAIN_NODES:
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        plan_steps = output.get("plan", [])
                        if plan_steps:
                            yield f"event: plan\ndata: {_json.dumps({'steps': plan_steps, 'reasoning': ''})}\n\n"

                elif kind == "on_chain_end" and name == "reflection_gate":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        reflection_result = output.get("_reflection_result")
                        if reflection_result is not None:
                            passed = getattr(reflection_result, "passed", True)
                            issues = getattr(reflection_result, "issues", [])
                            round_num = output.get("reflection_count", 0)
                            yield f"event: reflection\ndata: {_json.dumps({'passed': passed, 'issues': issues, 'round': round_num})}\n\n"

        # Check for nested interrupts (e.g. ingest confirmed -> add needs confirm)
        final_snapshot = await graph.aget_state(config)
        pending_tasks = final_snapshot.tasks if final_snapshot else ()
        has_interrupt = any(
            getattr(t, "interrupts", None) for t in pending_tasks
        )

        if has_interrupt:
            confirmation_details = {}
            for task in pending_tasks:
                for intr in getattr(task, "interrupts", []):
                    confirmation_details = getattr(intr, "value", {})
                    break
                if confirmation_details:
                    break
            yield f"event: confirmation\ndata: {_json.dumps({'thread_id': request_body.thread_id, 'confirmation': confirmation_details})}\n\n"
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

        try:
            latest_user_content = _get_latest_user_content(
                final_values.get("messages", [])
            )
            resumed_request = AgentExecuteRequest(
                messages=[
                    AgentMessage(role="user", content=latest_user_content)
                ] if latest_user_content else [],
                page_context=PageContextRequest(
                    **_page_context_to_dict(
                        final_values.get("page_context", page_context)
                    )
                ),
                model=getattr(request_body, "model", "") or "",
                thread_id=request_body.thread_id,
            )
            await _persist_thread_messages(
                db,
                current_user,
                resumed_request,
                assistant_content,
                tool_executions_out,
                retrieved_contexts=final_values.get("retrieved_contexts"),
                create_if_missing=False,
            )
        except Exception as e:
            logger.warning(
                "Failed to persist SSE confirmation thread messages",
                exc_info=e,
            )

        if turn_input_tokens > 0 or turn_output_tokens > 0:
            yield (
                "event: usage\n"
                f"data: {_json.dumps({'input_tokens': turn_input_tokens, 'output_tokens': turn_output_tokens})}\n\n"
            )

        if not tokens_emitted and tool_executions_out:
            names = ", ".join(
                getattr(te, "tool_name", str(te)) for te in tool_executions_out
            )
            yield f"event: token\ndata: {_json.dumps({'content': f'Done — completed: {names}.'})}\n\n"

        yield f"event: done\ndata: {_json.dumps({'status': 'complete', 'tool_executions': [te.model_dump() for te in tool_executions_out] if tool_executions_out else []})}\n\n"

    except Exception as e:
        logger.error("SSE stream confirm error", exc_info=e)
        yield f"event: error\ndata: {_json.dumps({'error': str(e)})}\n\n"

    finally:
        await db.close()
        logger.info("SSE confirm stream ended for thread %s", request_body.thread_id)
