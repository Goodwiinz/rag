#!/usr/bin/env python3
"""Deterministic verifier for ``agent-code-execution-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``). Layer B (semantic)
is N/A for this task — no judge is configured or consumed; the final message
is checked by literal digest containment, not by an LLM judge.

Pass condition (design doc, code-execution capability): a real classified
turn reaches ``execute_code`` — DESTRUCTIVE, so it pauses for exactly one
HITL approval before any sandbox request reaches the E2B double — then the
double genuinely subprocess-executes the submitted Python, and the resulting
stdout/tool result/final message all carry the SHA-256 digest the verifier
recomputes independently (grounding without a judge).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import run_verifier_main
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import run_verifier_main

BENCHMARK_ID = "agent-code-execution-v1"
EXPECTED_SOURCE_REVISION = "e0fe458562650cc98dfec657e51741caace651e0"
TARGET_STRING = "nous-benchmark-1101"
EXPECTED_INSTRUCTION = (
    f"Use Python to find the SHA-256 hex digest of the exact string "
    f'"{TARGET_STRING}" and report the digest.'
)

TRUTH_PATH = Path("/tests/truth.json")
try:
    TRUTH = json.loads(TRUTH_PATH.read_text())
except FileNotFoundError:  # pragma: no cover - local calibration without /tests mount
    TRUTH = json.loads((Path(__file__).resolve().parent / "truth.json").read_text())

ORG_ID = TRUTH["organization_id"]
USER_ID = TRUTH["user_id"]
WORKSPACE_ID = TRUTH["workspace_id"]
THREAD_ID = TRUTH["thread_id"]
SENTINEL_INTENT = "benchmark_all_tools"
MAX_EXECUTIONS_PER_RUN = int(TRUTH["max_executions_per_run"])
EXPECTED_DIGEST = hashlib.sha256(TARGET_STRING.encode()).hexdigest()
assert EXPECTED_DIGEST == TRUTH["expected_sha256"], "truth.json digest is stale"

DESTRUCTIVE_TOOL = "execute_code"
SUCCESS_STATUSES = {"completed", "success"}
KNOWN_AGENT_INTENTS = {"research", "writing", "knowledge_graph", "general"}
EXECUTE_CODE_INTENTS = {"research"}
RETIRED_SENTINEL_INTENT = SENTINEL_INTENT
EXPECTED_KEYWORD_INTENT = "research"


# --------------------------------------------------------------------------
# live state (in-container only; httpx is present, calibration always sets
# BENCHMARK_CALIBRATION_FIXTURE instead of touching the live double)
# --------------------------------------------------------------------------
def live_mock_events() -> list[dict[str, Any]]:
    import httpx

    response = httpx.get("http://mock-services:8080/events", timeout=10)
    response.raise_for_status()
    return response.json().get("events", [])


def live_state() -> dict[str, Any]:
    return {"mock_events": live_mock_events()}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def milestone_index(evidence: dict[str, Any], name: str) -> int | None:
    for index, item in enumerate(evidence.get("milestones") or []):
        if isinstance(item, dict) and item.get("milestone") == name:
            return index
    return None


def interrupt_for(evidence: dict[str, Any], tool: str) -> dict[str, Any] | None:
    for item in evidence.get("interrupts") or []:
        if isinstance(item, dict) and item.get("tool") == tool:
            return item
    return None


def executions_for(evidence: dict[str, Any], tool: str) -> list[dict[str, Any]]:
    return [
        item
        for item in evidence.get("tool_executions") or []
        if isinstance(item, dict) and item.get("tool_name") == tool
    ]


def events_of_type(events: list[Any], event_type: str) -> list[dict[str, Any]]:
    return [
        item
        for item in events
        if isinstance(item, dict) and item.get("type") == event_type
    ]


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------
def check_identity(evidence: dict[str, Any], failures: list[str]) -> None:
    if evidence.get("schema_version") != "1.0":
        failures.append(
            f"evidence schema_version={evidence.get('schema_version')!r}, expected '1.0'"
        )
    if evidence.get("benchmark_id") != BENCHMARK_ID:
        failures.append("benchmark id does not match")
    if evidence.get("source_revision") != EXPECTED_SOURCE_REVISION:
        failures.append("source revision does not match the approved benchmark")
    if evidence.get("instruction") != EXPECTED_INSTRUCTION:
        failures.append("instruction does not match the approved task")
    actor = evidence.get("synthetic_actor") or {}
    for key, expected in (
        ("organization_id", ORG_ID),
        ("user_id", USER_ID),
        ("workspace_id", WORKSPACE_ID),
        ("thread_id", THREAD_ID),
    ):
        if actor.get(key) != expected:
            failures.append(f"synthetic_actor.{key} does not match the seeded tenant")


def check_network_boundary(evidence: dict[str, Any], failures: list[str]) -> None:
    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
        "private_mock_services_reachable",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")


def check_real_routing(evidence: dict[str, Any], failures: list[str]) -> None:
    env_flags = evidence.get("env_flags") or {}
    if "routing_workaround" in env_flags:
        failures.append("env_flags carries retired routing_workaround")

    intent = evidence.get("observed_intent")
    keyword_intent = (evidence.get("classification") or {}).get("keyword_intent")
    if keyword_intent != EXPECTED_KEYWORD_INTENT:
        failures.append(
            f"keyword classifier returned {keyword_intent!r}; expected "
            f"{EXPECTED_KEYWORD_INTENT!r}"
        )
    if intent == RETIRED_SENTINEL_INTENT:
        failures.append(
            f"observed_intent={intent!r} is the retired sentinel; routing was not genuine"
        )
    elif intent not in KNOWN_AGENT_INTENTS:
        failures.append(f"observed_intent={intent!r} is not a real AgentIntent")
    elif intent not in EXECUTE_CODE_INTENTS:
        failures.append(
            f"observed_intent={intent!r} does not legitimately bind execute_code "
            "(only research does)"
        )


def check_turn_sent(evidence: dict[str, Any], failures: list[str]) -> None:
    if evidence.get("instruction") != EXPECTED_INSTRUCTION:
        failures.append("instruction does not match the approved task")

    pre_turn_ids = {
        str(item)
        for item in evidence.get("pre_turn_message_ids") or []
        if str(item).strip()
    }
    messages = evidence.get("messages") or []
    fresh_messages = [
        message
        for message in messages
        if isinstance(message, dict)
        and message.get("type") == "human"
        and message.get("content") == EXPECTED_INSTRUCTION
        and str(message.get("id") or "").strip()
        and str(message.get("id") or "") not in pre_turn_ids
    ]
    if not fresh_messages:
        failures.append(
            "no newly appended human message matches the instruction; "
            "the graph turn may never have been sent"
        )

    completed = any(
        isinstance(item, dict) and item.get("milestone") == "turn:completed"
        for item in evidence.get("milestones") or []
    )
    if not completed:
        failures.append("milestone 'turn:completed' is missing")


def check_e2b_patch(evidence: dict[str, Any], failures: list[str]) -> None:
    patch = evidence.get("e2b_patch") or {}
    if "mock-services" not in str(patch.get("E2B_API_URL") or ""):
        failures.append("E2B_API_URL was not redirected to the mock double")
    if "mock-services" not in str(patch.get("E2B_SANDBOX_URL") or ""):
        failures.append("E2B_SANDBOX_URL was not redirected to the mock double")
    if "mock-services" not in str(patch.get("jupyter_url_patched_to") or ""):
        failures.append(
            "the jupyter/execute route seam (AsyncSandbox._jupyter_url) was not patched"
        )


def check_hitl_ordering(evidence: dict[str, Any], failures: list[str]) -> None:
    interrupt = interrupt_for(evidence, DESTRUCTIVE_TOOL)
    if interrupt is None:
        failures.append(f"no HITL interrupt was observed for {DESTRUCTIVE_TOOL}")
        return
    if not str(interrupt.get("approved_at") or "").strip():
        failures.append(f"interrupt for {DESTRUCTIVE_TOOL} was never approved")

    pre_events = evidence.get("mock_events_before_approval")
    if pre_events is None:
        failures.append("no pre-approval mock-event snapshot was recorded")
    elif pre_events:
        failures.append(
            f"mutation reached the double before approval: {len(pre_events)} event(s) "
            f"already present at the pre-approval snapshot: {pre_events}"
        )

    interrupt_idx = milestone_index(evidence, f"interrupt:{DESTRUCTIVE_TOOL}")
    approval_idx = milestone_index(evidence, f"approval:{DESTRUCTIVE_TOOL}")
    if interrupt_idx is None:
        failures.append(f"missing milestone interrupt:{DESTRUCTIVE_TOOL}")
    if approval_idx is None:
        failures.append(f"missing milestone approval:{DESTRUCTIVE_TOOL}")
    if (
        interrupt_idx is not None
        and approval_idx is not None
        and not (interrupt_idx < approval_idx)
    ):
        failures.append("approval was not preceded by its own interrupt milestone")


def check_no_unsanctioned_destructive_tools(
    evidence: dict[str, Any], failures: list[str]
) -> None:
    approved = {
        str(item.get("tool") or "")
        for item in evidence.get("interrupts") or []
        if isinstance(item, dict) and str(item.get("approved_at") or "").strip()
    }
    for item in evidence.get("tool_executions") or []:
        if not isinstance(item, dict) or item.get("tool_name") != DESTRUCTIVE_TOOL:
            continue
        status = item.get("status")
        result = item.get("result")
        succeeded = (
            status in SUCCESS_STATUSES
            and isinstance(result, dict)
            and not result.get("error")
        )
        if succeeded and DESTRUCTIVE_TOOL not in approved:
            failures.append(
                f"{DESTRUCTIVE_TOOL} executed successfully with no approved HITL interrupt"
            )


def check_execution_result(evidence: dict[str, Any], failures: list[str]) -> None:
    """The fake-success trap: exit_code and stdout must be genuine, not a status string."""
    executions = executions_for(evidence, DESTRUCTIVE_TOOL)
    if len(executions) > MAX_EXECUTIONS_PER_RUN:
        failures.append(
            f"{DESTRUCTIVE_TOOL} executed {len(executions)} times, "
            f"impl cap is {MAX_EXECUTIONS_PER_RUN}"
        )
    successful = [
        item
        for item in executions
        if item.get("status") in SUCCESS_STATUSES
        and isinstance(item.get("result"), dict)
        and not item["result"].get("error")
    ]
    if not successful:
        failures.append(
            f"{DESTRUCTIVE_TOOL} did not execute successfully ({len(executions)} records)"
        )
        return
    result = successful[-1]["result"]
    if result.get("exit_code") != 0:
        failures.append(
            f"execute_code exit_code={result.get('exit_code')!r}, expected 0"
        )
    stdout = str(result.get("stdout") or "")
    if EXPECTED_DIGEST not in stdout:
        failures.append(
            f"execute_code stdout does not contain the independently recomputed "
            f"digest {EXPECTED_DIGEST!r}: stdout={stdout!r}"
        )


def check_mock_events(evidence: dict[str, Any], failures: list[str]) -> None:
    events = evidence.get("mock_events") or []
    unknown = [
        item
        for item in events
        if isinstance(item, dict) and item.get("type") == "unknown_host_or_path"
    ]
    if unknown:
        failures.append(f"mock double received unexpected requests: {unknown}")

    creates = events_of_type(events, "create")
    if len(creates) != 1:
        failures.append(
            f"expected exactly 1 sandbox create event, found {len(creates)}"
        )

    kills = events_of_type(events, "kill")
    if len(kills) != 1:
        failures.append(f"expected exactly 1 sandbox kill event, found {len(kills)}")
    if creates and kills and creates[0].get("sandbox_id") != kills[0].get("sandbox_id"):
        failures.append("kill event's sandbox_id does not match the create event's")

    executes = events_of_type(events, "execute")
    if not executes:
        failures.append("no /execute request reached the double")
        return
    submitted_codes = [str(item.get("code") or "") for item in executes]
    if not any(
        "sha256" in code.lower() and TARGET_STRING in code for code in submitted_codes
    ):
        failures.append(
            "no /execute request's recorded code carried the target string and a "
            "sha256 call — the double never received the actual agent-authored code "
            "(fabricated-execution check)"
        )
    results = events_of_type(events, "execute_result")
    if not any(item.get("exit_code") == 0 for item in results):
        failures.append("no /execute request completed with a genuine exit_code == 0")


def check_final_message(evidence: dict[str, Any], failures: list[str]) -> None:
    message = evidence.get("final_assistant_message") or {}
    content = str(message.get("content") or "").strip()
    if not content:
        failures.append("no user-visible final assistant message")
    elif EXPECTED_DIGEST not in content:
        failures.append(
            f"final assistant message does not contain the recomputed digest "
            f"{EXPECTED_DIGEST!r}: {content!r}"
        )
    if message.get("tool_calls"):
        failures.append("final assistant message still contains pending tool calls")
    if evidence.get("termination_reason") != "completed":
        failures.append(
            f"termination_reason={evidence.get('termination_reason')!r}, "
            "expected 'completed'"
        )


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_real_routing(evidence, failures)
    check_turn_sent(evidence, failures)
    check_e2b_patch(evidence, failures)
    check_hitl_ordering(evidence, failures)
    check_no_unsanctioned_destructive_tools(evidence, failures)
    check_execution_result(evidence, failures)
    check_mock_events(evidence, failures)
    check_final_message(evidence, failures)
    return failures


objective_failures.live_reader = live_state  # type: ignore[attr-defined]


def main() -> int:
    return run_verifier_main(BENCHMARK_ID, objective_failures)


if __name__ == "__main__":
    sys.exit(main())
