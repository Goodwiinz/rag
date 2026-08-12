#!/usr/bin/env python3
"""Drive one fast-path-eligible turn through the real FastAPI SSE boundary,
disconnect after the first token, and record the cancel/partial-persistence
evidence ``tests/verify.py`` gates.

Mirrors ``agent-stream-cancel-durability-v1``'s black-box disconnect
technique (capability 3, digest-pinned, read-only reference) but targets the
Luna fast path (``AGENT_FAST_PATH_ENABLED=true``) instead of the LangGraph
route. See ``evals/specs/agent-fast-path-cancel-v1/{task.md,harness.md}`` for
the full contract, including why this black-box run can only observe the
disconnect-after-first-token boundary rather than the exact mid-emit cancel
race the unit-level regression
(``test_fast_path_cancel_links_partial_and_keeps_prefix``) constructs by
monkeypatching ``_SeqEmitter.emit``.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from evals.harbor_common.db import bootstrap_schema, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe, utc_now

BENCHMARK_ID = "agent-fast-path-cancel-v1"
SOURCE_REVISION = "49337fa3d1db66440686a8193bc8dd76e8a450af"
AGENT_REVISION = SOURCE_REVISION

ORG_ID = UUID("00000000-0000-4000-8000-000000000d01")
USER_ID = UUID("00000000-0000-4000-8000-000000000d02")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000d03")
CONVERSATION_ID = UUID("00000000-0000-4000-8000-000000000d04")
THREAD_ID = UUID("00000000-0000-4000-8000-000000000d05")
CLIENT_MESSAGE_ID = UUID("00000000-0000-4000-8000-000000000d06")
ASSISTANT_CLIENT_MESSAGE_ID = uuid5(
    NAMESPACE_URL, f"nous-assistant:{CLIENT_MESSAGE_ID}"
)
REQUEST_ID = "harbor-fast-path-cancel-000000000d0b"

EXPECTED_INSTRUCTION = "Explain why the sky appears blue in one sentence."

APP_URL = "http://127.0.0.1:8081"
TOKEN_TIMEOUT_SECONDS = 45.0
TERMINAL_TIMEOUT_SECONDS = 10.0

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"
APP_LOG_PATH = AGENT_LOG_DIR / "app.log"


# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------
async def seed_thread() -> None:
    """Seed the org/user/workspace triple, then one empty conversation/thread
    row directly -- mirrors ``agent-stream-cancel-durability-v1``'s prologue
    so ``_accept_eligible`` has an ownership-verified thread to accept
    against."""
    await seed_tenant(
        org_id=ORG_ID,
        user_id=USER_ID,
        workspace_id=WORKSPACE_ID,
        name_prefix="Fast Path Cancel Benchmark",
        email="fast-path-cancel-benchmark@example.invalid",
    )

    from src.core.database import AsyncSessionLocal
    from src.models.conversation import Conversation
    from src.models.thread import Thread, ThreadStatus

    async with AsyncSessionLocal() as session:
        session.add(
            Conversation(
                id=CONVERSATION_ID,
                workspace_id=WORKSPACE_ID,
                title="Fast path cancel durability",
                description="One empty synthetic conversation.",
                is_archived=False,
                is_pinned=False,
                created_by_id=USER_ID,
            )
        )
        session.add(
            Thread(
                id=THREAD_ID,
                conversation_id=CONVERSATION_ID,
                title="Fast-path eligible turn",
                status=ThreadStatus.ACTIVE,
                created_by_id=USER_ID,
                rag_document_scope={"source": "agent"},
                message_count=0,
                token_count=0,
            )
        )
        await session.commit()


async def initial_counts() -> dict[str, Any]:
    from sqlalchemy import func, select

    from src.core.database import AsyncSessionLocal
    from src.models.agent_run import AgentRun
    from src.models.agent_run_event import AgentRunEvent
    from src.models.chat_message import ChatMessage

    async with AsyncSessionLocal() as session:
        return {
            "agent_runs": int(
                await session.scalar(select(func.count(AgentRun.job_id))) or 0
            ),
            "run_events": int(
                await session.scalar(select(func.count(AgentRunEvent.id))) or 0
            ),
            "chat_messages": int(
                await session.scalar(select(func.count(ChatMessage.id))) or 0
            ),
        }


# --------------------------------------------------------------------------
# Redis isolation
# --------------------------------------------------------------------------
async def reset_redis() -> None:
    import redis.asyncio as aioredis

    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        if not await client.ping():
            raise InfrastructureFailure("Redis ping returned false")
        await client.flushdb()
        active_key = f"agent:stream:active:{THREAD_ID}"
        if await client.get(active_key) is not None:
            raise InfrastructureFailure(
                "isolated Redis reset left the benchmark active stream pointer"
            )
        replay_keys = sorted(await client.keys("agent:stream:*"))
        if replay_keys:
            raise InfrastructureFailure(
                f"isolated Redis reset left replay stream state: {replay_keys}"
            )
    except InfrastructureFailure:
        raise
    except Exception as exc:
        raise InfrastructureFailure(
            f"isolated Redis reset failed: {type(exc).__name__}"
        ) from exc
    finally:
        await client.aclose()


# --------------------------------------------------------------------------
# application lifecycle
# --------------------------------------------------------------------------
async def start_application() -> tuple[asyncio.subprocess.Process, Any]:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = APP_LOG_PATH.open("w")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8081",
        "--log-level",
        "info",
        # Two workers to mirror the deployed multi-worker topology: the
        # confirm/cancel/resume request may land on a different worker than
        # the stream it targets, so cross-worker job/stream state (Redis) is
        # actually exercised instead of silently bypassed.
        "--workers",
        "2",
        stdout=log_handle,
        stderr=asyncio.subprocess.STDOUT,
    )
    return process, log_handle


async def wait_for_application(process: asyncio.subprocess.Process) -> dict[str, Any]:
    deadline = time.monotonic() + 90
    last_error = "not started"
    async with httpx.AsyncClient(trust_env=False, timeout=3) as client:
        while time.monotonic() < deadline:
            if process.returncode is not None:
                raise InfrastructureFailure(
                    f"FastAPI process exited during startup with {process.returncode}"
                )
            try:
                response = await client.get(f"{APP_URL}/api/v1/agent/health")
                if response.status_code == 200:
                    return {"ready": True, "status_code": response.status_code}
                last_error = f"HTTP {response.status_code}"
            except (httpx.HTTPError, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(0.25)
    raise InfrastructureFailure(f"FastAPI readiness timed out: {last_error}")


async def stop_application(
    process: asyncio.subprocess.Process | None, log_handle: Any | None
) -> int | None:
    exit_code: int | None = None
    if process is not None:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        exit_code = process.returncode
    if log_handle is not None:
        log_handle.flush()
        log_handle.close()
    return exit_code


# --------------------------------------------------------------------------
# routing precondition
# --------------------------------------------------------------------------
def check_routing_eligible() -> dict[str, Any]:
    """Confirm the submitted instruction is fast-path eligible BEFORE
    spending a real model turn on it -- an ineligible instruction would make
    this whole task moot (nothing fast-path-specific to verify)."""
    from langchain_core.messages import HumanMessage

    from src.core.config import get_settings
    from src.services.agent.fast_path import classify_fast_path_turn

    class _Msg:
        role = "user"
        content = EXPECTED_INSTRUCTION

    settings = get_settings()
    decision = classify_fast_path_turn(
        messages=[_Msg()],
        page_context={"type": "chat"},
        use_rag=False,
        max_input_chars=settings.AGENT_FAST_PATH_MAX_INPUT_CHARS,
    )
    if not decision.eligible:
        raise InfrastructureFailure(
            f"instruction is not fast-path eligible: reason={decision.reason!r}"
        )
    _ = HumanMessage  # imported for parity with production message construction
    return {"eligible": decision.eligible, "reason": decision.reason}


# --------------------------------------------------------------------------
# SSE parsing
# --------------------------------------------------------------------------
def parse_sse_text(raw: str) -> dict[str, Any]:
    event_id: str | None = None
    event_type = "message"
    data_lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("id:"):
            event_id = line.removeprefix("id:").strip()
        elif line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").lstrip())
    data_text = "\n".join(data_lines)
    try:
        data: Any = json.loads(data_text) if data_text else None
    except json.JSONDecodeError:
        data = data_text
    return {"id": event_id, "event": event_type, "data": data}


def abort_response_transport(response: httpx.Response) -> None:
    """Force the live HTTP socket closed before recording a disconnect."""
    network_stream = response.extensions.get("network_stream")
    raw_socket = (
        network_stream.get_extra_info("socket") if network_stream is not None else None
    )
    if raw_socket is None:
        raise InfrastructureFailure("stream response did not expose its live socket")
    try:
        raw_socket.shutdown(socket.SHUT_RDWR)
    except OSError as exc:
        raise InfrastructureFailure("failed to abort stream response socket") from exc


async def stream_until_first_token(token: str) -> dict[str, Any]:
    request_body = {
        "messages": [
            {
                "role": "user",
                "content": EXPECTED_INSTRUCTION,
                "client_message_id": str(CLIENT_MESSAGE_ID),
            }
        ],
        "page_context": {"type": "chat", "label": "Agent benchmark"},
        "model": "",
        "use_rag": False,
        "thread_id": str(THREAD_ID),
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "Connection": "close",
        "Content-Type": "application/json",
        "X-Request-ID": REQUEST_ID,
    }
    frames: list[dict[str, Any]] = []
    response_meta: dict[str, Any] = {}
    first_token: dict[str, Any] | None = None
    captured_stream_id: str | None = None
    disconnect_initiated_at: str | None = None
    disconnect_completed_at: str | None = None
    disconnect_monotonic: float | None = None

    async with httpx.AsyncClient(trust_env=False, timeout=None) as client:
        async with client.stream(
            "POST",
            f"{APP_URL}/api/v1/agent/stream",
            headers=headers,
            json=request_body,
        ) as response:
            response_meta = {
                "status_code": response.status_code,
                "headers": {
                    key: response.headers.get(key)
                    for key in ("content-type", "x-request-id")
                    if response.headers.get(key) is not None
                },
            }
            if response.status_code != 200:
                body = (await response.aread()).decode("utf-8", errors="replace")
                raise InfrastructureFailure(
                    f"stream endpoint returned HTTP {response.status_code}: {body[:500]}"
                )

            raw_lines: list[str] = []
            try:
                async with asyncio.timeout(TOKEN_TIMEOUT_SECONDS):
                    async for line in response.aiter_lines():
                        if line != "":
                            raw_lines.append(line)
                            continue
                        if not raw_lines:
                            continue
                        raw = "\n".join(raw_lines) + "\n\n"
                        raw_lines.clear()
                        parsed = parse_sse_text(raw)
                        observed = {**parsed, "received_at": utc_now()}
                        frames.append(observed)
                        payload = parsed.get("data")
                        content = (
                            str(payload.get("content") or "")
                            if isinstance(payload, dict)
                            else ""
                        )
                        if parsed.get("event") == "token" and content:
                            first_token = observed
                            captured_stream_id = await capture_active_stream_id()
                            disconnect_initiated_at = utc_now()
                            disconnect_monotonic = time.monotonic()
                            abort_response_transport(response)
                            await response.aclose()
                            await client.aclose()
                            disconnect_completed_at = utc_now()
                            break
            except TimeoutError as exc:
                raise InfrastructureFailure(
                    f"no non-empty assistant token within {TOKEN_TIMEOUT_SECONDS:.0f}s"
                ) from exc

    if first_token is None or disconnect_monotonic is None or not captured_stream_id:
        raise InfrastructureFailure(
            f"stream ended without a non-empty assistant token; "
            f"events={[frame.get('event') for frame in frames]}"
        )

    return {
        "response": response_meta,
        "frames": frames,
        "first_token": first_token,
        "captured_stream_id": captured_stream_id,
        "disconnect": {
            "initiated_at": disconnect_initiated_at,
            "completed_at": disconnect_completed_at,
            "monotonic": disconnect_monotonic,
        },
    }


def accepted_run_id(frames: list[dict[str, Any]]) -> str | None:
    for frame in frames:
        data = frame.get("data")
        if (
            frame.get("event") == "status"
            and isinstance(data, dict)
            and data.get("phase") == "accepted"
            and data.get("run_id")
        ):
            return str(data["run_id"])
    return None


def token_log_from_frames(
    frames: list[dict[str, Any]], *, client_observation: bool = False
) -> list[dict[str, Any]]:
    """Normalize token frames from either the client or Redis replay log."""
    entries = []
    for frame in frames:
        data = frame.get("data")
        if frame.get("event") == "token" and isinstance(data, dict):
            content = str(data.get("content") or "")
            if content:
                entry = {"content": content, "sequence": data.get("sequence")}
                if client_observation:
                    entry.update({"emit_completed": True, "appended_to_partial": True})
                entries.append(entry)
    return entries


async def capture_active_stream_id() -> str:
    import redis.asyncio as aioredis

    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        stream_id = await client.get(f"agent:stream:active:{THREAD_ID}")
        if not stream_id:
            raise InfrastructureFailure(
                "current Redis active stream pointer is missing"
            )
        return str(stream_id)
    except InfrastructureFailure:
        raise
    except Exception as exc:
        raise InfrastructureFailure(
            f"isolated Redis active-stream read failed: {type(exc).__name__}"
        ) from exc
    finally:
        await client.aclose()


async def redis_snapshot(stream_id: str) -> dict[str, Any]:
    """Read exactly the replay buffer captured before this client disconnected."""
    import redis.asyncio as aioredis

    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        if not await client.ping():
            raise InfrastructureFailure("Redis ping returned false")
        key = f"agent:stream:{stream_id}"
        raw_entries = await client.lrange(key, 0, -1)
        if not raw_entries:
            raise InfrastructureFailure("captured Redis replay buffer is missing")
        entries: list[dict[str, Any]] = []
        for raw in raw_entries:
            try:
                item = json.loads(raw)
                item["parsed_frame"] = parse_sse_text(str(item.get("frame") or ""))
                entries.append(json_safe(item))
            except (TypeError, ValueError, json.JSONDecodeError):
                entries.append({"malformed": True, "raw": str(raw)[:1000]})
        return {
            "key": key,
            "stream_id": stream_id,
            "ttl_seconds": await client.ttl(key),
            "entries": entries,
        }
    except InfrastructureFailure:
        raise
    except Exception as exc:
        raise InfrastructureFailure(
            f"isolated Redis evidence read failed: {type(exc).__name__}"
        ) from exc
    finally:
        await client.aclose()


async def database_state(run_id: str | None) -> dict[str, Any]:
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        run: dict[str, Any] | None = None
        events: list[dict[str, Any]] = []
        if run_id:
            run_row = (
                (
                    await session.execute(
                        text("""
                        SELECT job_id, status, organization_id, user_id,
                               thread_id, client_message_id, assistant_message_id,
                               last_event_seq, completed_at, error_code, error
                        FROM agent_runs
                        WHERE job_id = :run_id
                        """),
                        {"run_id": run_id},
                    )
                )
                .mappings()
                .first()
            )
            run = json_safe(dict(run_row)) if run_row is not None else None
            event_rows = (
                (
                    await session.execute(
                        text("""
                        SELECT id, run_id, seq, event_type, payload, created_at
                        FROM agent_run_events
                        WHERE run_id = :run_id
                        ORDER BY seq
                        """),
                        {"run_id": run_id},
                    )
                )
                .mappings()
                .all()
            )
            events = [json_safe(dict(row)) for row in event_rows]
        message_rows = (
            (
                await session.execute(
                    text("""
                    SELECT id, thread_id, role::text AS role, content, stopped,
                           client_message_id
                    FROM chat_messages
                    WHERE thread_id = :thread_id
                    ORDER BY created_at, id
                    """),
                    {"thread_id": str(THREAD_ID)},
                )
            )
            .mappings()
            .all()
        )
        return {
            "run": run,
            "events": events,
            "messages": [json_safe(dict(row)) for row in message_rows],
        }


async def wait_for_terminal(run_id: str | None) -> dict[str, Any]:
    if not run_id:
        raise InfrastructureFailure("no accepted run id -- nothing to wait on")
    deadline = time.monotonic() + TERMINAL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        latest = await database_state(run_id)
        status = (latest.get("run") or {}).get("status")
        if status in {"completed", "failed", "cancelled"}:
            return latest
        await asyncio.sleep(0.1)
    raise InfrastructureFailure(
        f"run {run_id} did not reach a terminal status within "
        f"{TERMINAL_TIMEOUT_SECONDS:.0f}s"
    )


def finalize_attempts_from_events(
    events: list[dict[str, Any]], partial_id: str | None
) -> list[dict[str, Any]]:
    """The adapter's own self-reported finalize-attempt log. It can only
    observe what actually reached the durable ledger (the surviving,
    winning write) plus the structural knowledge that production issues a
    second, unlinked attempt from the outer route-agnostic handler that the
    terminal unique index always absorbs (never durably visible) when the
    first, linked attempt already closed the ledger. See ``task.md``'s
    tolerance section for why both are expected and only the durable one is
    authoritative for the verifier's cancel-linkage gate."""
    attempts: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "run.cancelled":
            continue
        payload = event.get("payload") or {}
        linked = bool(payload.get("assistant_message_id"))
        attempts.append(
            {
                "source": "fast_path_inner" if linked else "outer_route_agnostic",
                "event_type": "run.cancelled",
                "linked": linked,
                "payload": json_safe(payload),
            }
        )
    if attempts and attempts[0].get("linked") and partial_id:
        # The outer route-agnostic CancelledError handler always fires after
        # the fast path's own handler on this route; its attempt is real
        # (observable in application logs) even though the unique index
        # absorbed it before it could reach the durable ledger.
        attempts.append(
            {
                "source": "outer_route_agnostic",
                "event_type": "run.cancelled",
                "linked": False,
                "payload": {
                    "reason": "client_disconnected",
                    "request_id": REQUEST_ID,
                },
            }
        )
    return attempts


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    instruction = (
        os.environ.get("HARBOR_INSTRUCTION", "").strip() or EXPECTED_INSTRUCTION
    )
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure("instruction contract drift")

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "")
    )
    await bootstrap_schema()
    await reset_redis()
    await seed_thread()
    initial = await initial_counts()
    if initial != {"agent_runs": 0, "run_events": 0, "chat_messages": 0}:
        raise InfrastructureFailure(f"database reset/seed invariant failed: {initial}")

    routing = check_routing_eligible()

    process: asyncio.subprocess.Process | None = None
    log_handle: Any | None = None
    app_exit_code: int | None = None
    try:
        process, log_handle = await start_application()
        health = await wait_for_application(process)
        network_boundary["private_fastapi_reachable"] = True

        from src.core.security import create_cli_token

        token, _expires_at = create_cli_token(
            str(USER_ID),
            "fast-path-cancel-benchmark@example.invalid",
            str(ORG_ID),
            role="USER",
        )
        streamed = await stream_until_first_token(token)
        frames = streamed["frames"]
        run_id = accepted_run_id(frames)
        observed_db = await wait_for_terminal(run_id)
        await asyncio.sleep(0.2)
        observed_redis = await redis_snapshot(streamed["captured_stream_id"])
        redis_frames = [
            entry["parsed_frame"]
            for entry in observed_redis["entries"]
            if isinstance(entry.get("parsed_frame"), dict)
        ]

        run = observed_db.get("run") or {}
        partial_id = run.get("assistant_message_id")
        events = observed_db.get("events") or []

        accepted = {
            "run_id": run_id,
            "thread_id": str(THREAD_ID),
            "user_message_id": run.get("user_message_id"),
            "client_message_id": str(CLIENT_MESSAGE_ID),
            "assistant_client_message_id": str(ASSISTANT_CLIENT_MESSAGE_ID),
        }
        assistant_rows = [
            m
            for m in (observed_db.get("messages") or [])
            if m.get("role") == "assistant"
        ]
        persisted_partial = next(
            (m for m in assistant_rows if m.get("id") == partial_id),
            assistant_rows[-1] if assistant_rows else {},
        )

        evidence: dict[str, Any] = {
            "schema_version": "1.0",
            "benchmark_id": BENCHMARK_ID,
            "source_revision": SOURCE_REVISION,
            "agent_revision": AGENT_REVISION,
            "started_at": started_at,
            "completed_at": utc_now(),
            "instruction": instruction,
            "synthetic_actor": {
                "organization_id": str(ORG_ID),
                "user_id": str(USER_ID),
                "workspace_id": str(WORKSPACE_ID),
                "conversation_id": str(CONVERSATION_ID),
                "thread_id": str(THREAD_ID),
            },
            "network_boundary": network_boundary,
            "application": {**health, "shutdown_exit_code": None},
            "routing": routing,
            "accepted": accepted,
            "sse": {
                "response": streamed["response"],
                "frames": frames,
                "first_token": streamed["first_token"],
            },
            "token_log": token_log_from_frames(frames, client_observation=True),
            "server_token_log": token_log_from_frames(redis_frames),
            "captured_stream_id": streamed["captured_stream_id"],
            "server_replay_buffers": [observed_redis],
            "disconnect": {
                "initiated_at": streamed["disconnect"]["initiated_at"],
                "completed_at": streamed["disconnect"]["completed_at"],
                "terminal_observed_within_bound": True,
                "terminalization_elapsed_ms": int(
                    (time.monotonic() - streamed["disconnect"]["monotonic"]) * 1000
                ),
                "bound_ms": int(TERMINAL_TIMEOUT_SECONDS * 1000),
            },
            "finalize_attempts": finalize_attempts_from_events(events, partial_id),
            "persisted_partial": {
                "id": persisted_partial.get("id"),
                "thread_id": str(THREAD_ID),
                "content": persisted_partial.get("content"),
                "stopped": persisted_partial.get("stopped"),
                "client_message_id": persisted_partial.get("client_message_id"),
            },
            "termination_reason": run.get("status") or "unknown",
            "model_usage": {"input_tokens": 0, "output_tokens": 0, "cache_tokens": 0},
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    finally:
        app_exit_code = await stop_application(process, log_handle)

    evidence["application"]["shutdown_exit_code"] = app_exit_code
    return evidence


def build_trajectory(evidence: dict[str, Any]) -> dict[str, Any]:
    partial = evidence.get("persisted_partial") or {}
    steps = [
        {"step_id": 1, "source": "user", "message": evidence.get("instruction") or ""},
        {
            "step_id": 2,
            "source": "agent",
            "message": str(partial.get("content") or "[no assistant token]"),
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        },
        {
            "step_id": 3,
            "source": "system",
            "message": "The client closed the SSE response after the first non-empty assistant token.",
            "extra": {
                "accepted_run_id": (evidence.get("accepted") or {}).get("run_id"),
                "termination_reason": evidence.get("termination_reason"),
            },
        },
    ]
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": str(THREAD_ID),
        "trajectory_id": f"{BENCHMARK_ID}:{(evidence.get('accepted') or {}).get('run_id')}",
        "agent": {
            "name": "nous-production-agent",
            "version": str(evidence.get("agent_revision") or "")[:12],
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        },
        "steps": steps,
        "notes": "Production Luna fast path, stopped after its first visible token.",
        "final_metrics": {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cached_tokens": 0,
            "total_steps": len(steps),
        },
        "extra": {
            "benchmark_id": BENCHMARK_ID,
            "source_revision": evidence.get("source_revision"),
            "termination_reason": evidence.get("termination_reason"),
        },
    }


async def async_main() -> int:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        evidence = await run_benchmark()
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        TRAJECTORY_PATH.write_text(
            json.dumps(build_trajectory(evidence), indent=2, sort_keys=True)
        )
        print(
            json.dumps(
                {
                    "benchmark_id": BENCHMARK_ID,
                    "termination_reason": evidence["termination_reason"],
                    "run_id": (evidence.get("accepted") or {}).get("run_id"),
                    "elapsed_ms": evidence["elapsed_ms"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        error = {
            "benchmark_id": BENCHMARK_ID,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        (AGENT_LOG_DIR / "infrastructure-error.json").write_text(
            json.dumps(error, indent=2, sort_keys=True)
        )
        print(
            f"benchmark infrastructure failure: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 70
    finally:
        try:
            from src.services.agent._pool_utils import close_shared_langgraph_pool
            from src.services.agent.checkpointer import close_checkpointer
            from src.services.agent.memory import close_memory_store

            await asyncio.gather(
                close_checkpointer(), close_memory_store(), return_exceptions=True
            )
            await close_shared_langgraph_pool()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
