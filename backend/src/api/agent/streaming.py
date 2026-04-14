"""SSE streaming logic for agent execution.

Contains the event_generator functions used by the /stream and
/stream/confirm endpoints, plus SSE formatting helpers.
"""

import asyncio
import json as _json
import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional

from langgraph.errors import GraphInterrupt
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User

from .jobs import (
    _get_latest_user_content,
    _page_context_to_dict,
    _persist_thread_messages,
)
from .trace_context import build_trace_payload

logger = logging.getLogger(__name__)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


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


def _format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format a single SSE event frame."""
    return f"event: {event_type}\ndata: {_json.dumps(data)}\n\n"


async def stream_event_generator(
    request_body: Any,  # AgentExecuteRequest
    request: Any,  # FastAPI Request
    current_user: User,
    db: AsyncSession,
):
    """SSE event generator for the /stream endpoint.

    Yields SSE-formatted events: token, tool_start, tool_end,
    rag_context, plan, reflection, confirmation, done, error.
    """
    from langchain_core.messages import HumanMessage

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph

    # Lazy import schemas to avoid circular imports
    from .execute import (
        AgentExecuteRequest,
        AgentMessage,
        PageContextRequest,
        ToolExecutionResponse,
    )

    stream_thread_id = request_body.thread_id or "unknown"
    config: Dict[str, Any] = {}  # Initialize before try block for safe access in except handlers
    try:
        _bootstrap_langsmith()
        checkpointer = await get_checkpointer()
        graph = compile_agent_graph(checkpointer=checkpointer)

        messages = [
            HumanMessage(content=m.content)
            for m in request_body.messages
            if m.role == "user"
        ]

        initial_state = {
            "messages": messages,
            "page_context": _page_context_to_dict(request_body.page_context),
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
            "plan": [],
            "reflection_count": 0,
            "compaction_count": 0,
            "intent_confidence": 0.0,
            "last_error_info": {},
            "user_id": str(current_user.id),
        }

        stream_thread_id = request_body.thread_id or str(_uuid.uuid4())
        config = {
            "configurable": {
                "thread_id": stream_thread_id,
                "db": db,
                "current_user": current_user,
                "page_context": _page_context_to_dict(request_body.page_context),
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

        async with asyncio.timeout(300):  # 5 minutes
            async for event in graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                if await request.is_disconnected():
                    break

                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield f"event: token\ndata: {_json.dumps({'content': chunk.content})}\n\n"

                elif kind == "on_tool_start":
                    yield f"event: tool_start\ndata: {_json.dumps({'tool': name})}\n\n"

                elif kind == "on_tool_end":
                    output = event.get("data", {}).get("output", "")
                    yield f"event: tool_end\ndata: {_json.dumps({'tool': name, 'result': str(output)[:500]})}\n\n"

                elif kind == "on_chain_end" and name == "rag_node":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        contexts = output.get("retrieved_contexts", [])
                        if contexts:
                            yield f"event: rag_context\ndata: {_json.dumps({'contexts': contexts[:3]})}\n\n"

                elif kind == "on_chain_end" and name == "planner_node":
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

            await _persist_thread_messages(
                db, current_user, request_body, assistant_content, tool_executions_out,
            )
        except Exception as e:
            logger.warning("Failed to persist SSE thread messages", exc_info=e)

        yield f"event: done\ndata: {_json.dumps({'status': 'complete'})}\n\n"

    except GraphInterrupt as exc:
        # Graph hit an interrupt mid-stream (HITL confirmation needed)
        interrupts = getattr(exc, "interrupts", [])
        confirmation_details = {}
        if interrupts:
            confirmation_details = getattr(interrupts[0], "value", {})
        thread_id = config["configurable"]["thread_id"] if config else stream_thread_id
        yield f"event: confirmation\ndata: {_json.dumps({'thread_id': thread_id, 'confirmation': confirmation_details})}\n\n"

    except Exception as e:
        logger.error("SSE stream error", exc_info=e)
        yield f"event: error\ndata: {_json.dumps({'error': str(e)})}\n\n"

    finally:
        logger.info("SSE stream ended for thread %s", stream_thread_id)


async def stream_confirm_event_generator(
    request_body: Any,  # StreamConfirmRequest
    request: Any,  # FastAPI Request
    current_user: User,
    db: AsyncSession,
):
    """SSE event generator for the /stream/confirm endpoint.

    Resumes a graph interrupted by HITL and streams the remaining events.
    """
    from langgraph.types import Command

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph

    # Lazy import schemas
    from .execute import (
        AgentExecuteRequest,
        AgentMessage,
        PageContextRequest,
        ToolExecutionResponse,
    )

    try:
        _bootstrap_langsmith()
        checkpointer = await get_checkpointer()
        graph = compile_agent_graph(checkpointer=checkpointer)

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

        # Verify thread ownership — prevent users from resuming others' graphs
        snapshot_user_id = current_snapshot.values.get("user_id", "")
        if snapshot_user_id and snapshot_user_id != str(current_user.id):
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

        async with asyncio.timeout(300):
            async for event in graph.astream_events(
                resume_input, config=config, version="v2"
            ):
                if await request.is_disconnected():
                    break

                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield f"event: token\ndata: {_json.dumps({'content': chunk.content})}\n\n"

                elif kind == "on_tool_start":
                    yield f"event: tool_start\ndata: {_json.dumps({'tool': name})}\n\n"

                elif kind == "on_tool_end":
                    output = event.get("data", {}).get("output", "")
                    yield f"event: tool_end\ndata: {_json.dumps({'tool': name, 'result': str(output)[:500]})}\n\n"

                elif kind == "on_chain_end" and name == "planner_node":
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
                thread_id=request_body.thread_id,
            )
            await _persist_thread_messages(
                db,
                current_user,
                resumed_request,
                assistant_content,
                tool_executions_out,
            )
        except Exception as e:
            logger.warning(
                "Failed to persist SSE confirmation thread messages",
                exc_info=e,
            )

        yield f"event: done\ndata: {_json.dumps({'status': 'complete', 'tool_executions': [te.model_dump() for te in tool_executions_out] if tool_executions_out else []})}\n\n"

    except Exception as e:
        logger.error("SSE stream confirm error", exc_info=e)
        yield f"event: error\ndata: {_json.dumps({'error': str(e)})}\n\n"

    finally:
        logger.info("SSE confirm stream ended for thread %s", request_body.thread_id)
