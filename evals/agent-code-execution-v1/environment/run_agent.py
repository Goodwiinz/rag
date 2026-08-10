#!/usr/bin/env python3
"""Run the code-execution benchmark against the production LangGraph graph.

The task sends a real user turn through production classification. The
explicit "Use Python" request deterministically selects the research route,
where ``execute_code`` is bound; "find" preserves the same keyword fallback.
The observed intent is read back from the checkpoint; the adapter never seeds
or asserts routing state.

``execute_code`` is DESTRUCTIVE, so the root-graph ``interrupt_node`` pauses
once before any sandbox is created. The E2B SDK's sandbox-lifecycle calls
(create/kill) are redirected to the mock double via ``E2B_API_URL``/
``E2B_SANDBOX_URL``; the code-interpreter's streamed ``/execute`` route does
NOT honor ``E2B_SANDBOX_URL`` (an SDK gap found in the Task 2 spike — see
harness.md Fidelity limits), so ``e2b_code_interpreter...AsyncSandbox.
_jupyter_url`` is patched directly, mirroring the class-attribute patch
pattern already used for the arXiv client in Task 1.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from langgraph.types import Command

from evals.harbor_common.db import bootstrap_schema, initial_agent_state, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe, utc_now
from evals.harbor_common.trajectory import (
    build_atif_trajectory,
    collect_model_usage,
    final_assistant_message,
)

BENCHMARK_ID = "agent-code-execution-v1"
SOURCE_REVISION = "27018e69c0c9e0339aab5db5f76d34e1715a316c"
AGENT_REVISION = SOURCE_REVISION
APPROVAL_TEXT = "Yes, run it."

TARGET_STRING = "nous-benchmark-1101"
EXPECTED_DIGEST = hashlib.sha256(TARGET_STRING.encode()).hexdigest()
INSTRUCTION_TEXT = (
    f"Use Python to find the SHA-256 hex digest of the exact string "
    f'"{TARGET_STRING}" and report the digest.'
)
EXPECTED_INSTRUCTION = INSTRUCTION_TEXT

ORG_ID = UUID("00000000-0000-4000-8000-000000001101")
USER_ID = UUID("00000000-0000-4000-8000-000000001102")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000001103")
THREAD_ID = "00000000-0000-4000-8000-000000001104"

DESTRUCTIVE_TOOL = "execute_code"
MAX_RESUMES = 2

MOCK_HOST = "http://mock-services:8080"

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"


async def seed_database() -> None:
    await seed_tenant(
        org_id=ORG_ID,
        user_id=USER_ID,
        workspace_id=WORKSPACE_ID,
        name_prefix="Benchmark",
        email="benchmark-code-exec@example.invalid",
    )


def mock_events() -> list[dict[str, Any]]:
    response = httpx.get(f"{MOCK_HOST}/events", timeout=10)
    response.raise_for_status()
    return response.json().get("events", [])


async def probe_mock_internal() -> bool:
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{MOCK_HOST}/health")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def patch_e2b_client() -> dict[str, Any]:
    """Redirect the E2B SDK's sandbox-lifecycle + jupyter-execute routes.

    ``E2B_API_URL``/``E2B_SANDBOX_URL`` (read by ``e2b.connection_config.
    ConnectionConfig``) cover sandbox create/kill and the envd health probe.
    They do NOT cover the code-interpreter's ``/execute`` route: its
    ``_jupyter_url`` property calls ``SandboxBase.get_host``, which builds
    ``https://{port}-{sandbox_id}.{sandbox_domain}`` from ``ConnectionConfig.
    get_host`` and never consults ``_sandbox_url`` (verified against the
    installed SDK during the Task 2 spike — see harness.md Fidelity limits).
    The adapter patches the property directly, the same seam category as
    Task 1's ``ArXivIngestionService.ARXIV_API_BASE`` class-attribute patch.
    """
    import e2b_code_interpreter.code_interpreter_async as e2b_ci

    e2b_ci.AsyncSandbox._jupyter_url = property(lambda self: MOCK_HOST)
    return {
        "E2B_API_URL": os.environ.get("E2B_API_URL", ""),
        "E2B_SANDBOX_URL": os.environ.get("E2B_SANDBOX_URL", ""),
        "jupyter_url_patched_to": MOCK_HOST,
    }


def extract_interrupt(snapshot: Any) -> dict[str, Any] | None:
    for task in getattr(snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            payload = getattr(item, "value", None)
            if isinstance(payload, dict):
                return json_safe(payload)
    return None


def interrupt_tools(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    tools = payload.get("tools")
    return (
        [tool for tool in tools if isinstance(tool, dict)]
        if isinstance(tools, list)
        else []
    )


async def collect_updates(
    graph: Any,
    graph_input: Any,
    config: dict[str, Any],
    phase: str,
    events: list[dict[str, Any]],
    sequence: list[int],
) -> None:
    async for event in graph.astream(graph_input, config=config, stream_mode="updates"):
        sequence[0] += 1
        events.append(
            {
                "sequence": sequence[0],
                "phase": phase,
                "observed_at": utc_now(),
                "update": json_safe(event),
            }
        )


def record_milestone(
    milestones: list[dict[str, Any]], sequence: list[int], name: str
) -> None:
    sequence[0] += 1
    milestones.append(
        {"milestone": name, "sequence": sequence[0], "observed_at": utc_now()}
    )


async def drive_turn(
    graph: Any,
    config: dict[str, Any],
    instruction: str,
    events: list[dict[str, Any]],
    sequence: list[int],
    milestones: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Send the real user turn, approving any interrupt it raises.

    Returns ``(interrupts, mock_events_before_first_approval)`` — the latter
    is the HITL pre-approval snapshot: it must be empty, proving no sandbox
    request reached the double before approval (Landmine 2/3).
    """
    interrupts: list[dict[str, Any]] = []
    pre_approval_events: list[dict[str, Any]] = []
    graph_input: Any = initial_agent_state(instruction, THREAD_ID, user_id=str(USER_ID))
    phase = "turn:initial"
    for resume_index in range(MAX_RESUMES + 1):
        await collect_updates(graph, graph_input, config, phase, events, sequence)
        snapshot = await graph.aget_state(config)
        payload = extract_interrupt(snapshot)
        if payload is None:
            record_milestone(milestones, sequence, "turn:completed")
            return interrupts, pre_approval_events

        if resume_index >= MAX_RESUMES:
            raise InfrastructureFailure(
                f"graph still interrupting after {MAX_RESUMES} approvals"
            )

        tools = interrupt_tools(payload)
        for tool in tools:
            record_milestone(
                milestones, sequence, f"interrupt:{tool.get('name') or 'unknown'}"
            )
        if resume_index == 0:
            pre_approval_events = mock_events()
        record_milestone(milestones, sequence, "preapproval_mock_events_read")
        approved_at = utc_now()
        for tool in tools:
            name = tool.get("name") or "unknown"
            interrupts.append(
                {
                    "tool": name,
                    "args": json_safe(tool.get("args") or {}),
                    "approved_at": approved_at,
                }
            )
            record_milestone(milestones, sequence, f"approval:{name}")
        graph_input = Command(resume={"confirmed": True})
        phase = f"turn:resume:{resume_index + 1}"

    return interrupts, pre_approval_events


def tool_executions_for(
    tool_executions: list[Any], tool_name: str
) -> list[dict[str, Any]]:
    return [
        item
        for item in tool_executions
        if isinstance(item, dict) and item.get("tool_name") == tool_name
    ]


def hitl_steps(steps: list[dict[str, Any]], evidence: dict[str, Any]) -> list[Any]:
    """Splice the harness-supplied execute_code approval into the trajectory."""
    if steps and steps[-1].get("source") == "agent":
        approved = [
            call.get("function_name")
            for call in steps[-1].get("tool_calls") or []
            if call.get("function_name") == DESTRUCTIVE_TOOL
        ]
        if approved and not any(
            step.get("extra", {}).get("hitl_resume") for step in steps
        ):
            return steps + [
                {
                    "source": "user",
                    "message": APPROVAL_TEXT,
                    "extra": {
                        "hitl_resume": {"confirmed": True},
                        "approved_tools": approved,
                    },
                }
            ]
    return steps


async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure(
            f"instruction contract drift: expected {EXPECTED_INSTRUCTION!r}"
        )

    async def _mock_reachable() -> bool:
        return await probe_mock_internal()

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", ""),
        extra_probes={"private_mock_services_reachable": _mock_reachable},
    )

    e2b_patch = patch_e2b_client()
    await bootstrap_schema()
    await seed_database()

    from src.services.agent._builders import RECURSION_LIMIT
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store
    from src.services.sandbox.e2b_sandbox_manager import get_sandbox_manager

    checkpointer = await get_checkpointer()
    store = await get_memory_store()
    graph = compile_agent_graph(checkpointer=checkpointer, store=store)

    config = {
        "recursion_limit": RECURSION_LIMIT,
        "configurable": {
            "thread_id": THREAD_ID,
            "user_id": str(USER_ID),
            "organization_id": str(ORG_ID),
            "page_context": {},
            "runtime_snapshot_id": "",
            "current_project_id": "",
        },
        "metadata": {
            "benchmark_id": BENCHMARK_ID,
            "source_revision": SOURCE_REVISION,
            "thread_id": THREAD_ID,
            "user_id": str(USER_ID),
            "organization_id": str(ORG_ID),
        },
    }

    events: list[dict[str, Any]] = []
    sequence = [0]
    milestones: list[dict[str, Any]] = []
    record_milestone(milestones, sequence, "instruction")

    from src.services.agent.classifier import (
        classify_intent_keywords,
        classify_intent_with_fallback,
    )

    keyword_probe = classify_intent_keywords(instruction)
    classification_probe = await classify_intent_with_fallback(instruction, {})
    pre_turn_snapshot = await graph.aget_state(config)
    pre_turn_values = dict(getattr(pre_turn_snapshot, "values", {}) or {})
    pre_turn_messages = list(pre_turn_values.get("messages") or [])
    pre_turn_message_ids = sorted(
        str(getattr(message, "id", "") or "")
        for message in pre_turn_messages
        if str(getattr(message, "id", "") or "")
    )
    record_milestone(milestones, sequence, "pre_turn_snapshot")

    interrupts, mock_events_before_approval = await drive_turn(
        graph, config, instruction, events, sequence, milestones
    )

    final_snapshot = await graph.aget_state(config)
    final_values = dict(getattr(final_snapshot, "values", {}) or {})
    pending_interrupt = extract_interrupt(final_snapshot)

    messages = list(final_values.get("messages") or [])
    current_turn_human_message_ids = sorted(
        str(getattr(message, "id", "") or "")
        for message in messages
        if (
            str(getattr(message, "id", "") or "").strip()
            and str(getattr(message, "id", "") or "") not in pre_turn_message_ids
            and getattr(message, "type", "") == "human"
            and getattr(message, "content", "") == instruction
        )
    )
    tool_executions = list(final_values.get("tool_executions") or [])
    execute_code_executions = tool_executions_for(tool_executions, DESTRUCTIVE_TOOL)

    # Explicit sandbox teardown — `_tool_execute_code` keeps sandboxes alive
    # for conversation statefulness (15-minute idle cleanup), so nothing in
    # the graph run itself calls `kill`. The adapter closes the session the
    # same way a real client eventually would, giving the double a genuine
    # `kill` wire event to record rather than leaving the double's contract
    # partially unexercised.
    manager = get_sandbox_manager()
    await manager.cleanup(THREAD_ID)
    record_milestone(milestones, sequence, "sandbox_cleanup")

    final_message = final_assistant_message(messages)
    if final_message:
        record_milestone(milestones, sequence, "final_assistant_message")

    termination_reason = (
        "awaiting_confirmation"
        if pending_interrupt is not None
        else "completed" if not getattr(final_snapshot, "next", ()) else "incomplete"
    )

    return {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": AGENT_REVISION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "instruction": instruction,
        "target_string": TARGET_STRING,
        "expected_digest": EXPECTED_DIGEST,
        "synthetic_actor": {
            "organization_id": str(ORG_ID),
            "user_id": str(USER_ID),
            "workspace_id": str(WORKSPACE_ID),
            "thread_id": THREAD_ID,
        },
        "observed_intent": final_values.get("intent"),
        "classification": {
            "keyword_intent": keyword_probe.intent,
            "keyword_confidence": keyword_probe.confidence,
            "keyword_source": keyword_probe.source,
            "probe_intent": getattr(classification_probe, "intent", None),
            "probe_source": getattr(classification_probe, "source", None),
            "observed_intent": final_values.get("intent"),
        },
        "pre_turn_message_count": len(pre_turn_messages),
        "pre_turn_message_ids": pre_turn_message_ids,
        "current_turn_human_message_ids": current_turn_human_message_ids,
        "e2b_patch": e2b_patch,
        "network_boundary": network_boundary,
        "interrupts": interrupts,
        "interrupt": (
            {
                "count": len(interrupts),
                "tools": [item.get("tool") for item in interrupts],
            }
            if interrupts
            else None
        ),
        "approval": {
            "count": len(interrupts),
            "text": APPROVAL_TEXT if interrupts else None,
            "resume": {"confirmed": True} if interrupts else None,
        },
        "pending_interrupt_after_resume": pending_interrupt,
        "mock_events_before_approval": mock_events_before_approval,
        "mock_events": mock_events(),
        "execute_code_executions": json_safe(execute_code_executions),
        "tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "events": events,
        "milestones": milestones,
        "suppress_observation_for": [],
        "notes": (
            "Production graph with an isolated database, an E2B "
            "sandbox-lifecycle + jupyter-execute protocol double, the "
            "real production intent classification, a research-subgraph "
            "execute_code route, and one post-interrupt approval."
        ),
        "final_assistant_message": final_message,
        "termination_reason": termination_reason,
        "model_usage": collect_model_usage(messages),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


async def async_main() -> int:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        evidence = await run_benchmark()
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        TRAJECTORY_PATH.write_text(
            json.dumps(
                build_atif_trajectory(
                    evidence, BENCHMARK_ID, THREAD_ID, extra_steps_hook=hitl_steps
                ),
                indent=2,
                sort_keys=True,
            )
        )
        print(
            json.dumps(
                {
                    "benchmark_id": BENCHMARK_ID,
                    "termination_reason": evidence["termination_reason"],
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

            await close_shared_langgraph_pool()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
