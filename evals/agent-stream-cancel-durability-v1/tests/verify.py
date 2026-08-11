#!/usr/bin/env python3
"""Independent verifier for the production stream cancellation benchmark.

Exit 0 means capability pass, 10 means a valid scoreable capability failure,
and any other non-zero code means verifier/infrastructure failure. The shell
wrapper deliberately emits no reward for infrastructure failures.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import psycopg
import redis
from psycopg.rows import dict_row

BENCHMARK_ID = "agent-stream-cancel-durability-v1"
SOURCE_REVISION = "fa3858d79baeb9dba79f0a44a077856418933898"
EXPECTED_INSTRUCTION = (
    "Research three approaches to evaluating a production RAG system. Compare "
    "retrieval quality, answer faithfulness, latency, and cost, then recommend "
    "an approach."
)
ORG_ID = "00000000-0000-4000-8000-000000000401"
USER_ID = "00000000-0000-4000-8000-000000000402"
THREAD_ID = "00000000-0000-4000-8000-000000000405"
CLIENT_MESSAGE_ID = "00000000-0000-4000-8000-000000000406"
ASSISTANT_CLIENT_MESSAGE_ID = str(
    uuid5(NAMESPACE_URL, f"nous-assistant:{CLIENT_MESSAGE_ID}")
)
REQUEST_ID = "harbor-stream-stop-000000000407"

DEFAULT_EVIDENCE = Path("/logs/agent/evidence.json")
REPORT_PATH = Path(os.environ.get("VERIFIER_REPORT_PATH", "/logs/verifier/audit.json"))


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
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


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


def live_database_state(run_id: str | None) -> dict[str, Any]:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        # This count is also the dependency/schema probe when the accepted
        # frame did not carry a run id.
        run_count_for_thread = connection.execute(
            "SELECT count(*) AS count FROM agent_runs WHERE thread_id = %s::uuid",
            (THREAD_ID,),
        ).fetchone()["count"]
        run = None
        events: list[dict[str, Any]] = []
        if run_id:
            run = connection.execute(
                """
                SELECT job_id, status, organization_id, user_id,
                       thread_id, conversation_id, user_message_id,
                       assistant_message_id, client_message_id,
                       idempotency_key, last_event_seq, started_at,
                       completed_at, cancel_requested_at, error_code,
                       error, usage, run_metadata, created_at, updated_at
                FROM agent_runs
                WHERE job_id = %s
                """,
                (run_id,),
            ).fetchone()
            events = list(
                connection.execute(
                    """
                    SELECT id, run_id, organization_id, seq, event_type,
                           payload, created_at, updated_at
                    FROM agent_run_events
                    WHERE run_id = %s
                    ORDER BY seq
                    """,
                    (run_id,),
                ).fetchall()
            )
        messages = list(
            connection.execute(
                """
                SELECT id, thread_id, user_id, role::text AS role, content,
                       token_count, latency_ms, stopped, model_name,
                       client_message_id, tool_executions, plan, token_usage,
                       superseded_by_message_id, created_at, updated_at
                FROM chat_messages
                WHERE thread_id = %s::uuid
                ORDER BY created_at, id
                """,
                (THREAD_ID,),
            ).fetchall()
        )
    return {
        "run_count_for_thread": int(run_count_for_thread),
        "run": json_safe(dict(run)) if run is not None else None,
        "events": [json_safe(dict(row)) for row in events],
        "messages": [json_safe(dict(row)) for row in messages],
    }


def live_redis_state() -> dict[str, Any]:
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        raise RuntimeError("REDIS_URL is missing")
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        if not client.ping():
            raise RuntimeError("Redis ping returned false")
        active_key = f"agent:stream:active:{THREAD_ID}"
        keys = sorted(client.keys("agent:stream:*"))
        buffers: list[dict[str, Any]] = []
        for key in keys:
            if key.startswith("agent:stream:active:"):
                continue
            entries: list[dict[str, Any]] = []
            for raw in client.lrange(key, 0, -1):
                parsed = json.loads(raw)
                parsed["parsed_frame"] = parse_sse_text(str(parsed.get("frame") or ""))
                entries.append(json_safe(parsed))
            buffers.append(
                {
                    "key": key,
                    "stream_id": key.removeprefix("agent:stream:"),
                    "ttl_seconds": client.ttl(key),
                    "entries": entries,
                }
            )
        return {
            "active_key": active_key,
            "active_stream_id": client.get(active_key),
            "matching_keys": keys,
            "buffers": buffers,
        }
    finally:
        client.close()


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    calibration = os.environ.get("BENCHMARK_CALIBRATION_FIXTURE")
    if calibration:
        fixture = json.loads(Path(calibration).read_text())
        return (
            fixture["evidence"],
            fixture["database_state"],
            fixture["redis_state"],
            calibration,
        )
    if not DEFAULT_EVIDENCE.exists():
        raise FileNotFoundError(f"agent evidence missing: {DEFAULT_EVIDENCE}")
    evidence = json.loads(DEFAULT_EVIDENCE.read_text())
    run_id = (evidence.get("accepted") or {}).get("run_id")
    return evidence, live_database_state(run_id), live_redis_state(), "live"


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def all_buffer_frames(redis_state: dict[str, Any]) -> list[dict[str, Any]]:
    frames: list[tuple[int, dict[str, Any]]] = []
    for buffer in redis_state.get("buffers") or []:
        for entry in buffer.get("entries") or []:
            try:
                sequence = int(entry.get("seq"))
            except (TypeError, ValueError):
                sequence = -1
            parsed = entry.get("parsed_frame")
            if not isinstance(parsed, dict):
                parsed = parse_sse_text(str(entry.get("frame") or ""))
            frames.append((sequence, parsed))
    return [frame for _sequence, frame in sorted(frames, key=lambda item: item[0])]


def token_log_from_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"content": str(data.get("content") or "")}
        for frame in frames
        if frame.get("event") == "token"
        and isinstance(data := frame.get("data"), dict)
        and data.get("content")
    ]


def objective_failures(
    evidence: dict[str, Any],
    database: dict[str, Any],
    redis_state: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if evidence.get("schema_version") != "1.0":
        failures.append("unsupported or missing evidence schema_version")
    if evidence.get("benchmark_id") != BENCHMARK_ID:
        failures.append("benchmark id does not match")
    if evidence.get("source_revision") != SOURCE_REVISION:
        failures.append("source revision does not match the approved benchmark")
    if evidence.get("instruction") != EXPECTED_INSTRUCTION:
        failures.append("instruction does not match the approved task")

    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
        "private_postgres_reachable",
        "private_redis_reachable",
        "private_fastapi_reachable",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network/dependency boundary not proven: {key}")

    initial_db = (evidence.get("database") or {}).get("initial") or {}
    expected_initial = {
        "thread_exists": True,
        "thread_message_count": 0,
        "agent_runs": 0,
        "run_events": 0,
        "chat_messages": 0,
    }
    if initial_db != expected_initial:
        failures.append(f"database was not empty before the trial: {initial_db}")
    initial_redis = (evidence.get("redis") or {}).get("initial") or {}
    if initial_redis.get("active_stream_id") is not None or initial_redis.get(
        "buffers"
    ):
        failures.append("Redis stream namespace was not empty before the trial")

    response = (evidence.get("sse") or {}).get("response") or {}
    if response.get("status_code") != 200:
        failures.append(f"stream HTTP status was {response.get('status_code')!r}")
    content_type = str((response.get("headers") or {}).get("content-type") or "")
    if "text/event-stream" not in content_type:
        failures.append(f"stream content type was {content_type!r}")

    frames = list((evidence.get("sse") or {}).get("frames") or [])
    if not frames:
        failures.append("no live SSE frames were recorded")
    sequences: list[int] = []
    trace_ids: list[str] = []
    for frame in frames:
        data = frame.get("data")
        if not isinstance(data, dict):
            failures.append(f"SSE frame {frame.get('event')!r} lacked an envelope")
            continue
        try:
            sequence_value = data.get("sequence")
            if sequence_value is None:
                raise TypeError("missing sequence")
            sequence = int(sequence_value)
            sequences.append(sequence)
            if str(frame.get("id")) != str(sequence):
                failures.append(f"SSE id/sequence mismatch at {sequence}")
        except (TypeError, ValueError):
            failures.append("SSE envelope sequence was missing or invalid")
        if data.get("trace_id"):
            trace_ids.append(str(data["trace_id"]))
        if data.get("schema_version") != "1.0":
            failures.append("SSE frame used an unexpected schema version")
    if sequences and (
        sequences != sorted(sequences)
        or len(sequences) != len(set(sequences))
        or sequences[0] != 1
    ):
        failures.append(f"live SSE sequence is not strictly monotonic: {sequences}")
    if trace_ids and len(set(trace_ids)) != 1:
        failures.append(f"live SSE trace ids drifted: {sorted(set(trace_ids))}")

    accepted = evidence.get("accepted") or {}
    run_id = accepted.get("run_id")
    accepted_frames = [
        frame
        for frame in frames
        if frame.get("event") == "status"
        and isinstance(frame.get("data"), dict)
        and frame["data"].get("phase") == "accepted"
    ]
    if len(accepted_frames) != 1:
        failures.append(f"accepted frames observed={len(accepted_frames)}, expected 1")
    elif accepted_frames[0]["data"].get("run_id") != run_id:
        failures.append("accepted frame run id does not match recorded run id")
    if not run_id:
        failures.append("accepted frame did not carry a durable run id")
    if accepted.get("thread_id") != THREAD_ID:
        failures.append("accepted thread id does not match the seeded thread")
    if accepted.get("client_message_id") != CLIENT_MESSAGE_ID:
        failures.append("accepted client message id does not match the request")

    first_token = (evidence.get("sse") or {}).get("first_token") or {}
    first_token_log = token_log_from_frames([first_token])
    first_content = first_token_log[0]["content"] if first_token_log else ""
    if not first_content:
        failures.append("no non-empty first assistant token was recorded")
    first_data = first_token.get("data") or {}
    if isinstance(first_data, dict) and first_data.get("route") != "graph":
        failures.append(
            f"first token route was {first_data.get('route')!r}, expected graph"
        )
    if any(frame.get("event") == "done" for frame in frames):
        failures.append("live stream completed before the scripted Stop")

    disconnect = evidence.get("disconnect") or {}
    disconnect_at = parse_time(disconnect.get("initiated_at"))
    if disconnect_at is None:
        failures.append("disconnect timestamp is missing or invalid")
    elapsed = disconnect.get("terminalization_elapsed_ms")
    if disconnect.get("terminal_observed_within_bound") is not True:
        failures.append("accepted run did not reach a terminal state within 10 seconds")
    if not isinstance(elapsed, int) or not 0 <= elapsed <= 10_000:
        failures.append(f"terminalization elapsed time is invalid: {elapsed!r}")

    run = database.get("run") or {}
    if int(database.get("run_count_for_thread", 0)) != 1:
        failures.append(
            f"independent DB has {database.get('run_count_for_thread')} runs for the thread"
        )
    if run.get("job_id") != run_id:
        failures.append("independent AgentRun id does not match accepted run")
    if run.get("status") != "cancelled":
        failures.append(
            f"AgentRun status was {run.get('status')!r}, expected cancelled"
        )
    if run.get("thread_id") != THREAD_ID:
        failures.append("AgentRun thread linkage is wrong")
    if run.get("user_id") != USER_ID or run.get("organization_id") != ORG_ID:
        failures.append("AgentRun tenant linkage is wrong")
    if run.get("client_message_id") != CLIENT_MESSAGE_ID:
        failures.append("AgentRun client_message_id does not match the submitted turn")
    completed_at = parse_time(run.get("completed_at"))
    if completed_at is None:
        failures.append("cancelled AgentRun has no terminal timestamp")
    elif disconnect_at is not None:
        if completed_at < disconnect_at:
            failures.append(
                "AgentRun terminal timestamp predates the client disconnect"
            )
        if completed_at > disconnect_at + timedelta(seconds=10):
            failures.append("AgentRun terminal timestamp exceeded the 10-second bound")
    if run.get("error_code") or run.get("error"):
        failures.append("cancelled AgentRun was projected as an error")

    events = list(database.get("events") or [])
    event_sequences = [event.get("seq") for event in events]
    if event_sequences != sorted(event_sequences) or len(event_sequences) != len(
        set(event_sequences)
    ):
        failures.append(f"durable run-event sequence is invalid: {event_sequences}")
    if events and int(run.get("last_event_seq") or -1) != int(
        events[-1].get("seq") or -2
    ):
        failures.append(
            "AgentRun last_event_seq does not match the durable event ledger"
        )
    terminal_events = [
        event
        for event in events
        if event.get("event_type") in {"run.completed", "run.failed", "run.cancelled"}
    ]
    cancelled_events = [
        event for event in events if event.get("event_type") == "run.cancelled"
    ]
    if len(cancelled_events) != 1 or len(terminal_events) != 1:
        failures.append(
            f"terminal ledger has cancelled={len(cancelled_events)}, total={len(terminal_events)}"
        )
    if any(event.get("event_type") == "run.completed" for event in events):
        failures.append("durable ledger contains run.completed after Stop")
    if cancelled_events:
        payload = cancelled_events[0].get("payload") or {}
        if payload.get("reason") != "client_disconnected":
            failures.append("run.cancelled reason is not client_disconnected")
        if payload.get("request_id") != REQUEST_ID:
            failures.append(
                "run.cancelled request_id does not match the streamed trace"
            )

    messages = list(database.get("messages") or [])
    user_messages = [item for item in messages if item.get("role") == "user"]
    assistant_messages = [item for item in messages if item.get("role") == "assistant"]
    if len(user_messages) != 1:
        failures.append(f"durable user rows={len(user_messages)}, expected 1")
    elif (
        user_messages[0].get("id") != run.get("user_message_id")
        or user_messages[0].get("client_message_id") != CLIENT_MESSAGE_ID
        or user_messages[0].get("content") != EXPECTED_INSTRUCTION
    ):
        failures.append("durable user row does not match the accepted submission")
    if len(assistant_messages) != 1:
        failures.append(f"durable assistant rows={len(assistant_messages)}, expected 1")
    else:
        assistant = assistant_messages[0]
        if assistant.get("stopped") is not True:
            failures.append("partial assistant row is not marked stopped=true")
        if assistant.get("client_message_id") != ASSISTANT_CLIENT_MESSAGE_ID:
            failures.append("partial assistant idempotency key is wrong")
        if not str(assistant.get("content") or ""):
            failures.append("partial assistant row has empty content")
        if first_content and not str(assistant.get("content") or "").startswith(
            first_content
        ):
            failures.append(
                "persisted partial content does not include the observed first token"
            )
        if run.get("assistant_message_id") != assistant.get("id"):
            failures.append(
                "cancelled AgentRun is not linked to its persisted partial assistant row"
            )

    if accepted.get("user_message_id") != run.get("user_message_id"):
        failures.append("recorded user_message_id does not match independent AgentRun")

    if redis_state.get("active_stream_id") is not None:
        failures.append(
            f"Redis active stream pointer was not cleared: {redis_state.get('active_stream_id')}"
        )
    buffers = list(redis_state.get("buffers") or [])
    if len(buffers) != 1:
        failures.append(f"Redis replay buffers={len(buffers)}, expected 1")
    for buffer in buffers:
        if not isinstance(buffer.get("ttl_seconds"), int) or buffer["ttl_seconds"] <= 0:
            failures.append("Redis replay buffer has no positive TTL")
        seqs = [entry.get("seq") for entry in buffer.get("entries") or []]
        if seqs != sorted(seqs) or len(seqs) != len(set(seqs)):
            failures.append(f"Redis buffered sequence is invalid: {seqs}")
    buffered_frames = all_buffer_frames(redis_state)
    server_token_log = token_log_from_frames(buffered_frames)
    if not server_token_log:
        failures.append(
            "Redis replay buffer does not contain the observed partial token"
        )
    if any(frame.get("event") == "done" for frame in buffered_frames):
        failures.append("Redis replay buffer contains a later done completion")
    if assistant_messages:
        server_text = "".join(entry["content"] for entry in server_token_log)
        persisted = str(assistant_messages[0].get("content") or "")
        if not server_text.startswith(persisted):
            failures.append(
                "persisted partial is not a prefix of the server replay token history"
            )

    activity = evidence.get("post_disconnect_activity") or {}
    if activity.get("observable_model_or_tool_starts"):
        failures.append("a new observable model/tool call started after disconnect")
    if activity.get("completion_events"):
        failures.append("a successful completion was observed after disconnect")
    late_durable_tool_start = False
    for event in events:
        event_time = parse_time(event.get("created_at"))
        if (
            event.get("event_type") == "tool.started"
            and event_time is not None
            and disconnect_at is not None
            and event_time > disconnect_at
        ):
            late_durable_tool_start = True
            break
    if late_durable_tool_start:
        failures.append("durable tool.started was appended after disconnect")

    resume = evidence.get("resume") or {}
    if resume.get("status_code") not in {200, 204}:
        failures.append(
            f"resume HTTP status was {resume.get('status_code')!r}, expected 200 or 204"
        )
    if resume.get("timed_out") is True:
        failures.append("resume request remained attached to an active stream")
    if any(frame.get("event") == "done" for frame in resume.get("frames") or []):
        failures.append("resume replayed a later done completion")

    correlation = evidence.get("correlation") or {}
    expected_correlation = {
        "request_id": REQUEST_ID,
        "agent_run_id": run_id,
        "thread_id": THREAD_ID,
        "user_message_id": run.get("user_message_id"),
        "client_message_id": CLIENT_MESSAGE_ID,
        "deployment_sha": SOURCE_REVISION,
        "image_tag": "harbor-agent-stream-cancel-durability-v1",
    }
    for key, expected in expected_correlation.items():
        if correlation.get(key) != expected:
            failures.append(
                f"correlation {key}={correlation.get(key)!r}, expected {expected!r}"
            )
    if correlation.get("trace_ids") != [REQUEST_ID]:
        failures.append(f"trace ids are not stable: {correlation.get('trace_ids')}")

    if evidence.get("termination_reason") != "cancelled":
        failures.append(
            f"termination_reason={evidence.get('termination_reason')!r}, expected cancelled"
        )
    return failures


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        evidence, database, redis_state, source = load_inputs()
        failures = objective_failures(evidence, database, redis_state)
        report = {
            "benchmark_id": BENCHMARK_ID,
            "input_source": source,
            "passed": not failures,
            "failures": failures,
            "observed": {
                "run_id": (evidence.get("accepted") or {}).get("run_id"),
                "run_status": (database.get("run") or {}).get("status"),
                "terminal_events": [
                    event.get("event_type")
                    for event in database.get("events") or []
                    if event.get("event_type")
                    in {"run.completed", "run.failed", "run.cancelled"}
                ],
                "assistant_message_id": (database.get("run") or {}).get(
                    "assistant_message_id"
                ),
                "assistant_rows": len(
                    [
                        item
                        for item in database.get("messages") or []
                        if item.get("role") == "assistant"
                    ]
                ),
                "redis_active_stream_id": redis_state.get("active_stream_id"),
                "resume_status": (evidence.get("resume") or {}).get("status_code"),
            },
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(json.dumps(report, sort_keys=True))
        return 0 if not failures else 10
    except Exception as exc:
        report = {
            "benchmark_id": BENCHMARK_ID,
            "verifier_error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
