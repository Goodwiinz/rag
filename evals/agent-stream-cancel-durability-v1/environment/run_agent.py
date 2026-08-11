#!/usr/bin/env python3
"""Exercise production SSE cancellation through the real FastAPI boundary."""

from __future__ import annotations

import asyncio
import json
import math
import os
import socket
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from sqlalchemy import func, select, text

BENCHMARK_ID = "agent-stream-cancel-durability-v1"
SOURCE_REVISION = "92678fc4692c8d5cb7025b7ad446209b0fa63590"
AGENT_REVISION = "92678fc4692c8d5cb7025b7ad446209b0fa63590"
EXPECTED_INSTRUCTION = (
    "Research three approaches to evaluating a production RAG system. Compare "
    "retrieval quality, answer faithfulness, latency, and cost, then recommend "
    "an approach."
)

ORG_ID = UUID("00000000-0000-4000-8000-000000000401")
USER_ID = UUID("00000000-0000-4000-8000-000000000402")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000403")
CONVERSATION_ID = UUID("00000000-0000-4000-8000-000000000404")
THREAD_ID = UUID("00000000-0000-4000-8000-000000000405")
CLIENT_MESSAGE_ID = UUID("00000000-0000-4000-8000-000000000406")
ASSISTANT_CLIENT_MESSAGE_ID = uuid5(
    NAMESPACE_URL, f"nous-assistant:{CLIENT_MESSAGE_ID}"
)
REQUEST_ID = "harbor-stream-stop-000000000407"

APP_URL = "http://127.0.0.1:8081"
TOKEN_TIMEOUT_SECONDS = 45.0
TERMINAL_TIMEOUT_SECONDS = 10.0
RESUME_WINDOW_SECONDS = 3.0

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"
APP_LOG_PATH = AGENT_LOG_DIR / "app.log"


class InfrastructureFailure(RuntimeError):
    """A setup/dependency failure that must not receive an agent score."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "value"):
        try:
            return json_safe(value.value)
        except Exception:
            pass
    return str(value)


async def bootstrap_schema() -> None:
    """Create the disposable schema from the same ORM metadata used by tests.

    The pinned revision's historical Alembic chain cannot initialize an empty
    database: its first revision is a no-op and its successor references tables
    that do not exist. This fidelity limit is recorded in evidence so this task
    measures cancellation, not the independently-known migration defect.
    """
    try:
        from src.core.database import async_engine
        from src.models import Base

        async with async_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except Exception as exc:
        raise InfrastructureFailure(
            f"SQLAlchemy metadata bootstrap failed: {type(exc).__name__}"
        ) from exc


async def reset_redis() -> None:
    import redis.asyncio as aioredis

    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        if not await client.ping():
            raise InfrastructureFailure("Redis ping returned false")
        await client.flushdb()
    except InfrastructureFailure:
        raise
    except Exception as exc:
        raise InfrastructureFailure(
            f"isolated Redis reset failed: {type(exc).__name__}"
        ) from exc
    finally:
        await client.aclose()


async def seed_database() -> None:
    from src.core.database import AsyncSessionLocal
    from src.core.encryption import (
        EncryptionKeyType,
        get_key_manager,
        initialize_encryption,
    )
    from src.models.conversation import Conversation
    from src.models.organization import Organization, StorageTier
    from src.models.thread import Thread, ThreadStatus
    from src.models.user import User, UserRole
    from src.models.workspace import Workspace

    initialize_encryption()
    key_manager = get_key_manager()
    if key_manager.get_active_key(EncryptionKeyType.DATA) is None:
        key_manager.generate_key(EncryptionKeyType.DATA)

    async with AsyncSessionLocal() as session:
        session.add(
            Organization(
                id=ORG_ID,
                name="Cancellation Benchmark Organization",
                storage_tier=StorageTier.FREE,
                storage_used_bytes=0,
                storage_limit_bytes=10 * 1024**3,
                is_active=True,
            )
        )
        session.add(
            User(
                id=USER_ID,
                email="stream-cancel-benchmark@example.invalid",
                password_hash="benchmark-password-not-used",
                first_name="Stream",
                last_name="Benchmark",
                role=UserRole.USER,
                is_active=True,
                organization_id=ORG_ID,
            )
        )
        session.add(
            Workspace(
                id=WORKSPACE_ID,
                name="Cancellation Benchmark Workspace",
                description="Synthetic state for the Harbor cancellation task.",
                owner_id=USER_ID,
                organization_id=ORG_ID,
                is_archived=False,
                is_public=False,
            )
        )
        session.add(
            Conversation(
                id=CONVERSATION_ID,
                workspace_id=WORKSPACE_ID,
                title="Cancellation durability",
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
                title="Stop after first token",
                status=ThreadStatus.ACTIVE,
                created_by_id=USER_ID,
                rag_document_scope={"source": "agent"},
                message_count=0,
                token_count=0,
            )
        )
        await session.commit()


async def initial_database_state() -> dict[str, Any]:
    from src.core.database import AsyncSessionLocal
    from src.models.agent_run import AgentRun
    from src.models.agent_run_event import AgentRunEvent
    from src.models.chat_message import ChatMessage
    from src.models.thread import Thread

    async with AsyncSessionLocal() as session:
        thread = await session.get(Thread, THREAD_ID)
        return {
            "thread_exists": thread is not None,
            "thread_message_count": int(getattr(thread, "message_count", -1)),
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


async def redis_snapshot() -> dict[str, Any]:
    import redis.asyncio as aioredis

    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        if not await client.ping():
            raise InfrastructureFailure("Redis ping returned false")
        active_key = f"agent:stream:active:{THREAD_ID}"
        active = await client.get(active_key)
        keys = sorted(await client.keys("agent:stream:*"))
        buffers: list[dict[str, Any]] = []
        for key in keys:
            if key.startswith("agent:stream:active:"):
                continue
            raw_entries = await client.lrange(key, 0, -1)
            entries: list[dict[str, Any]] = []
            for raw in raw_entries:
                try:
                    item = json.loads(raw)
                    item["parsed_frame"] = parse_sse_text(str(item.get("frame") or ""))
                    entries.append(json_safe(item))
                except (TypeError, ValueError, json.JSONDecodeError):
                    entries.append({"malformed": True, "raw": str(raw)[:1000]})
            buffers.append(
                {
                    "key": key,
                    "stream_id": key.removeprefix("agent:stream:"),
                    "ttl_seconds": await client.ttl(key),
                    "entries": entries,
                }
            )
        return {
            "active_key": active_key,
            "active_stream_id": active,
            "matching_keys": keys,
            "buffers": buffers,
        }
    except InfrastructureFailure:
        raise
    except Exception as exc:
        raise InfrastructureFailure(
            f"isolated Redis evidence read failed: {type(exc).__name__}"
        ) from exc
    finally:
        await client.aclose()


def token_log_from_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize server replay token frames for diagnostic evidence."""
    return [
        {"content": str(data.get("content") or "")}
        for frame in frames
        if frame.get("event") == "token"
        and isinstance(data := frame.get("data"), dict)
        and data.get("content")
    ]


def validate_network_boundary() -> dict[str, Any]:
    direct_blocked = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect(("1.1.1.1", 443))
    except OSError:
        direct_blocked = True
    finally:
        sock.close()

    endpoint = os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "").strip()
    host = urlparse(endpoint).hostname if endpoint else None
    if not host:
        raise InfrastructureFailure("AZURE_OPENAI_CHAT_ENDPOINT is missing or invalid")

    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            allowed = client.get(endpoint.rstrip("/") + "/")
            approved_reachable = 100 <= allowed.status_code <= 599
    except httpx.HTTPError as exc:
        raise InfrastructureFailure(
            f"approved model-host proxy preflight failed: {type(exc).__name__}"
        ) from exc

    blocked_status: int | None = None
    unrelated_blocked = False
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            blocked = client.get("https://example.com/")
            blocked_status = blocked.status_code
            unrelated_blocked = blocked_status == 403
    except httpx.ProxyError as exc:
        unrelated_blocked = "403" in str(exc)
        blocked_status = 403 if unrelated_blocked else None
    except httpx.HTTPError as exc:
        raise InfrastructureFailure(
            f"blocked-host proxy preflight failed ambiguously: {type(exc).__name__}"
        ) from exc

    result = {
        "direct_public_socket_blocked": direct_blocked,
        "approved_model_host_reachable_via_proxy": approved_reachable,
        "approved_model_host": host,
        "approved_model_probe_status": allowed.status_code,
        "unrelated_https_blocked_by_proxy": unrelated_blocked,
        "unrelated_probe_status": blocked_status,
        "private_postgres_reachable": True,
        "private_redis_reachable": True,
    }
    if not all((direct_blocked, approved_reachable, unrelated_blocked)):
        raise InfrastructureFailure(f"network boundary check failed: {result}")
    return result


async def start_application() -> tuple[asyncio.subprocess.Process, Any]:
    APP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
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
                    return {
                        "ready": True,
                        "status_code": response.status_code,
                        "body": response.json(),
                    }
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


def parse_sse_text(raw: str) -> dict[str, Any]:
    event_id: str | None = None
    event_type = "message"
    data_lines: list[str] = []
    comments: list[str] = []
    for line in raw.splitlines():
        if line.startswith("id:"):
            event_id = line.removeprefix("id:").strip()
        elif line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").lstrip())
        elif line.startswith(":"):
            comments.append(line[1:].strip())
    data_text = "\n".join(data_lines)
    try:
        data: Any = json.loads(data_text) if data_text else None
    except json.JSONDecodeError:
        data = data_text
    return {
        "id": event_id,
        "event": event_type,
        "data": data,
        "comments": comments,
    }


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
        "max_context_docs": 5,
        "thread_id": str(THREAD_ID),
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "X-Request-ID": REQUEST_ID,
    }
    frames: list[dict[str, Any]] = []
    response_meta: dict[str, Any] = {}
    first_token: dict[str, Any] | None = None
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
                    for key in (
                        "content-type",
                        "cache-control",
                        "x-accel-buffering",
                        "x-request-id",
                        "x-process-time",
                    )
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
                        observed = {
                            **parsed,
                            "received_at": utc_now(),
                            "received_monotonic": time.monotonic(),
                        }
                        frames.append(observed)
                        payload = parsed.get("data")
                        content = (
                            str(payload.get("content") or "")
                            if isinstance(payload, dict)
                            else ""
                        )
                        if parsed.get("event") == "token" and content:
                            first_token = observed
                            disconnect_initiated_at = utc_now()
                            disconnect_monotonic = time.monotonic()
                            await response.aclose()
                            disconnect_completed_at = utc_now()
                            break
            except TimeoutError as exc:
                raise InfrastructureFailure(
                    f"no non-empty assistant token within {TOKEN_TIMEOUT_SECONDS:.0f}s"
                ) from exc

    if first_token is None or disconnect_monotonic is None:
        terminal_events = [frame.get("event") for frame in frames]
        raise InfrastructureFailure(
            f"stream ended without a non-empty assistant token; events={terminal_events}"
        )

    return {
        "request": request_body,
        "response": response_meta,
        "frames": frames,
        "first_token": first_token,
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


async def database_state(run_id: str | None) -> dict[str, Any]:
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
                               thread_id, conversation_id, user_message_id,
                               assistant_message_id, client_message_id,
                               idempotency_key, last_event_seq, started_at,
                               completed_at, cancel_requested_at, error_code,
                               error, usage, run_metadata, created_at, updated_at
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
                        SELECT id, run_id, organization_id, seq, event_type,
                               payload, created_at, updated_at
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
                    SELECT id, thread_id, user_id, role::text AS role, content,
                           token_count, latency_ms, stopped, model_name,
                           client_message_id, tool_executions, plan, token_usage,
                           superseded_by_message_id, created_at, updated_at
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


async def wait_for_terminal(
    run_id: str | None,
    disconnect_monotonic: float,
    disconnect_at: str,
) -> tuple[dict[str, Any], int | None, bool]:
    if not run_id:
        return await database_state(None), None, False

    def durable_elapsed_ms(database: dict[str, Any]) -> int | None:
        completed_at = (database.get("run") or {}).get("completed_at")
        if not completed_at:
            return None
        try:
            completed = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
            disconnected = datetime.fromisoformat(disconnect_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        delta_ms = (completed - disconnected).total_seconds() * 1000
        if delta_ms < 0:
            return None
        # Round upward so a terminal write even a fraction beyond the bound
        # cannot be presented as an in-bound cancellation.
        return math.ceil(delta_ms)

    deadline = disconnect_monotonic + TERMINAL_TIMEOUT_SECONDS
    while True:
        latest = await database_state(run_id)
        status = (latest.get("run") or {}).get("status")
        if status in {"completed", "failed", "cancelled"}:
            elapsed_ms = durable_elapsed_ms(latest)
            if elapsed_ms is None:
                elapsed_ms = math.ceil((time.monotonic() - disconnect_monotonic) * 1000)
            return (
                latest,
                elapsed_ms,
                elapsed_ms <= int(TERMINAL_TIMEOUT_SECONDS * 1000),
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        await asyncio.sleep(min(0.1, remaining))

    # One final independent read closes the race where the terminal commit
    # lands during the last database query. Its durable timestamp, rather than
    # the poll response time, decides whether the write met the bound.
    latest = await database_state(run_id)
    status = (latest.get("run") or {}).get("status")
    if status in {"completed", "failed", "cancelled"}:
        elapsed_ms = durable_elapsed_ms(latest)
        if elapsed_ms is not None:
            return (
                latest,
                elapsed_ms,
                elapsed_ms <= int(TERMINAL_TIMEOUT_SECONDS * 1000),
            )
    return latest, None, False


async def resume_stream(token: str) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    timed_out = False
    response_meta: dict[str, Any] = {}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "X-Request-ID": f"{REQUEST_ID}-resume",
    }
    async with httpx.AsyncClient(trust_env=False, timeout=None) as client:
        async with client.stream(
            "GET",
            f"{APP_URL}/api/v1/agent/stream/resume/{THREAD_ID}",
            headers=headers,
            params={"after": 0},
        ) as response:
            response_meta = {
                "status_code": response.status_code,
                "headers": {
                    key: response.headers.get(key)
                    for key in ("content-type", "cache-control", "x-request-id")
                    if response.headers.get(key) is not None
                },
            }
            if response.status_code == 204:
                return {**response_meta, "frames": [], "timed_out": False}

            raw_lines: list[str] = []
            try:
                async with asyncio.timeout(RESUME_WINDOW_SECONDS):
                    async for line in response.aiter_lines():
                        if line != "":
                            raw_lines.append(line)
                            continue
                        if not raw_lines:
                            continue
                        raw = "\n".join(raw_lines) + "\n\n"
                        raw_lines.clear()
                        frames.append(
                            {
                                **parse_sse_text(raw),
                                "received_at": utc_now(),
                            }
                        )
            except TimeoutError:
                timed_out = True
                await response.aclose()
    return {**response_meta, "frames": frames, "timed_out": timed_out}


def frame_occurred_at(frame: dict[str, Any]) -> str | None:
    data = frame.get("data")
    if isinstance(data, dict):
        value = data.get("occurred_at")
        return str(value) if value else None
    return None


def after_timestamp(value: str | None, boundary: str | None) -> bool:
    if not value or not boundary:
        return False
    try:
        lhs = datetime.fromisoformat(value.replace("Z", "+00:00"))
        rhs = datetime.fromisoformat(boundary.replace("Z", "+00:00"))
        return lhs > rhs
    except ValueError:
        return False


def post_disconnect_activity(
    disconnect_at: str | None,
    database: dict[str, Any],
    redis_state: dict[str, Any],
) -> dict[str, Any]:
    durable = [
        event
        for event in database.get("events") or []
        if after_timestamp(str(event.get("created_at") or ""), disconnect_at)
    ]
    buffered: list[dict[str, Any]] = []
    for buffer in redis_state.get("buffers") or []:
        for entry in buffer.get("entries") or []:
            parsed = entry.get("parsed_frame") or {}
            if after_timestamp(frame_occurred_at(parsed), disconnect_at):
                buffered.append(parsed)
    starts = [
        item
        for item in durable
        if item.get("event_type") in {"tool.started", "model.started"}
    ] + [
        item for item in buffered if item.get("event") in {"tool_start", "model_start"}
    ]
    completions = [
        item for item in durable if item.get("event_type") == "run.completed"
    ] + [item for item in buffered if item.get("event") == "done"]
    return {
        "window_seconds": TERMINAL_TIMEOUT_SECONDS,
        "durable_events_after_disconnect": durable,
        "buffered_frames_after_disconnect": buffered,
        "observable_model_or_tool_starts": starts,
        "completion_events": completions,
        "model_start_observability": (
            "The public SSE and durable ledger expose tool starts but not raw "
            "chat-model starts; graph cancellation plus absence of later tool "
            "starts or successful completion is the observable boundary."
        ),
    }


def model_usage(database: dict[str, Any]) -> dict[str, int]:
    totals = {"input_tokens": 0, "output_tokens": 0, "cache_tokens": 0}
    for message in database.get("messages") or []:
        if message.get("role") != "assistant":
            continue
        usage = message.get("token_usage") or {}
        totals["input_tokens"] += int(usage.get("input_tokens") or 0)
        totals["output_tokens"] += int(usage.get("output_tokens") or 0)
    return totals


def build_trajectory(evidence: dict[str, Any]) -> dict[str, Any]:
    token_frame = (evidence.get("sse") or {}).get("first_token") or {}
    token_data = token_frame.get("data") or {}
    partial = (
        str(token_data.get("content") or "") if isinstance(token_data, dict) else ""
    )
    observed_database = (evidence.get("database") or {}).get("observed") or {}
    observed_run = observed_database.get("run") or {}
    steps = [
        {
            "step_id": 1,
            "source": "user",
            "message": EXPECTED_INSTRUCTION,
        },
        {
            "step_id": 2,
            "source": "agent",
            "message": partial or "[no assistant token]",
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
            "extra": {"model_call_count": "not observable at the public SSE boundary"},
        },
        {
            "step_id": 3,
            "source": "system",
            "message": "The client closed the SSE response after the first non-empty assistant token.",
            "extra": {
                "accepted_run_id": ((evidence.get("accepted") or {}).get("run_id")),
                "durable_status": observed_run.get("status"),
            },
        },
    ]
    usage = evidence.get("model_usage") or {}
    run_id = str((evidence.get("accepted") or {}).get("run_id") or THREAD_ID)
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": str(THREAD_ID),
        "trajectory_id": f"{BENCHMARK_ID}:{run_id}",
        "agent": {
            "name": "nous-production-agent",
            "version": AGENT_REVISION[:12],
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        },
        "steps": steps,
        "notes": "Production FastAPI SSE stream stopped after its first visible token.",
        "final_metrics": {
            "total_prompt_tokens": usage.get("input_tokens", 0),
            "total_completion_tokens": usage.get("output_tokens", 0),
            "total_cached_tokens": usage.get("cache_tokens", 0),
            "total_steps": len(steps),
        },
        "extra": {
            "benchmark_id": BENCHMARK_ID,
            "source_revision": SOURCE_REVISION,
            "termination_reason": evidence.get("termination_reason"),
        },
    }


async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started_monotonic = time.monotonic()
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure("instruction contract drift")

    await bootstrap_schema()
    await reset_redis()
    await seed_database()
    initial_db = await initial_database_state()
    initial_redis = await redis_snapshot()
    if initial_db != {
        "thread_exists": True,
        "thread_message_count": 0,
        "agent_runs": 0,
        "run_events": 0,
        "chat_messages": 0,
    }:
        raise InfrastructureFailure(
            f"database reset/seed invariant failed: {initial_db}"
        )
    if initial_redis.get("active_stream_id") is not None or initial_redis.get(
        "buffers"
    ):
        raise InfrastructureFailure("Redis reset left agent stream state behind")

    network = validate_network_boundary()
    process: asyncio.subprocess.Process | None = None
    log_handle: Any | None = None
    evidence: dict[str, Any] | None = None
    app_exit_code: int | None = None
    try:
        process, log_handle = await start_application()
        health = await wait_for_application(process)
        network["private_fastapi_reachable"] = True

        from src.core.security import create_cli_token

        token, _expires_at = create_cli_token(
            str(USER_ID),
            "stream-cancel-benchmark@example.invalid",
            str(ORG_ID),
            role="USER",
        )
        streamed = await stream_until_first_token(token)
        frames = streamed["frames"]
        run_id = accepted_run_id(frames)
        disconnect = streamed["disconnect"]
        observed_db, terminal_elapsed_ms, terminal_observed = await wait_for_terminal(
            run_id,
            float(disconnect["monotonic"]),
            str(disconnect["initiated_at"]),
        )
        # Emitter.finish precedes run finalization, but give Redis one scheduler
        # turn before independently reading the final replay state.
        await asyncio.sleep(0.2)
        observed_redis = await redis_snapshot()
        redis_frames = [
            entry["parsed_frame"]
            for buffer in observed_redis["buffers"]
            for entry in buffer["entries"]
            if isinstance(entry.get("parsed_frame"), dict)
        ]
        resumed = await resume_stream(token)

        trace_ids = sorted(
            {
                str((frame.get("data") or {}).get("trace_id"))
                for frame in frames
                if isinstance(frame.get("data"), dict)
                and (frame.get("data") or {}).get("trace_id")
            }
        )
        observed_run = observed_db.get("run") or {}
        accepted = {
            "run_id": run_id,
            "thread_id": str(THREAD_ID),
            "user_message_id": observed_run.get("user_message_id"),
            "client_message_id": str(CLIENT_MESSAGE_ID),
            "assistant_client_message_id": str(ASSISTANT_CLIENT_MESSAGE_ID),
        }
        activity = post_disconnect_activity(
            disconnect.get("initiated_at"), observed_db, observed_redis
        )
        termination_reason = (
            str(observed_run.get("status"))
            if terminal_observed and observed_run.get("status")
            else "terminalization_timeout"
        )
        evidence = {
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
            "network_boundary": network,
            "application": health,
            "request": {
                "client_message_id": str(CLIENT_MESSAGE_ID),
                "request_id": REQUEST_ID,
                "thread_id": str(THREAD_ID),
                "model": streamed["request"]["model"],
                "use_rag": streamed["request"]["use_rag"],
                "page_context": streamed["request"]["page_context"],
            },
            "sse": {
                "response": streamed["response"],
                "frames": frames,
                "first_token": streamed["first_token"],
            },
            "server_token_log": token_log_from_frames(redis_frames),
            "accepted": accepted,
            "disconnect": {
                "initiated_at": disconnect.get("initiated_at"),
                "completed_at": disconnect.get("completed_at"),
                "terminal_observed_within_bound": terminal_observed,
                "terminalization_elapsed_ms": terminal_elapsed_ms,
                "bound_ms": int(TERMINAL_TIMEOUT_SECONDS * 1000),
            },
            "database": {
                "bootstrap": "src.models.Base.metadata.create_all",
                "initial": initial_db,
                "observed": observed_db,
            },
            "redis": {
                "initial": initial_redis,
                "observed": observed_redis,
            },
            "post_disconnect_activity": activity,
            "resume": resumed,
            "correlation": {
                "trace_ids": trace_ids,
                "request_id": trace_ids[0] if len(trace_ids) == 1 else None,
                "agent_run_id": run_id,
                "thread_id": str(THREAD_ID),
                "user_message_id": observed_run.get("user_message_id"),
                "client_message_id": str(CLIENT_MESSAGE_ID),
                "deployment_sha": os.environ.get("GIT_SHA"),
                "image_tag": os.environ.get("IMAGE_TAG"),
            },
            "resolved_config": {
                "environment": os.environ.get("ENVIRONMENT"),
                "agent_fast_path_enabled": os.environ.get("AGENT_FAST_PATH_ENABLED"),
                "agent_canonical_persistence": os.environ.get(
                    "AGENT_CANONICAL_PERSISTENCE"
                ),
                "agent_server_side_history": os.environ.get(
                    "AGENT_SERVER_SIDE_HISTORY"
                ),
                "allow_memory_fallback": os.environ.get("ALLOW_MEMORY_FALLBACK"),
                "model_deployment": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
                "lightweight_deployment": os.environ.get(
                    "AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT"
                ),
            },
            "fidelity_limits": [
                "single local FastAPI process; no ingress, browser Fetch, HPA, or multi-pod race",
                "fresh ORM metadata schema because the pinned historical Alembic bootstrap is independently broken",
                "raw model-start callbacks are not public SSE or durable-ledger events",
            ],
            "termination_reason": termination_reason,
            "model_usage": model_usage(observed_db),
            "elapsed_ms": int((time.monotonic() - started_monotonic) * 1000),
        }
    finally:
        app_exit_code = await stop_application(process, log_handle)

    if evidence is None:
        raise InfrastructureFailure("benchmark ended without evidence")
    evidence["application"]["shutdown_exit_code"] = app_exit_code
    return evidence


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
