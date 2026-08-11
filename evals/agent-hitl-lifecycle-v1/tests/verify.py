#!/usr/bin/env python3
"""Deterministic verifier for ``agent-hitl-lifecycle-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``).

This capability gates the HITL interrupt *lifecycle* itself — not the
ordering invariant (interrupt before mutation) every other HITL-bearing task
already asserts. Four independent phases share one seeded org/user/workspace,
each driving the production ``create_project`` tool through the real
``/execute`` -> ``/jobs/{job_id}`` -> ``/confirm/{job_id}`` HTTP surface:

  * ``approve_once``       - gate 1 (exact interrupt payload) + gate 3 (the
                              single approval fires exactly once).
  * ``reject``              - gate 2 (zero mutation, coherent final message).
  * ``reconfirm_resolved``  - gate 4 (confirm on an already-resolved
                              interrupt is a stable, mutation-free no-op).
  * ``cancel_while_parked`` - gate 5 (the parked interrupt is re-delivered
                              unchanged across repeated polls).

Gate 6 (checkpointer connection string must be ``postgresql://``, never
``+asyncpg``) is evaluated as an infrastructure precondition: a violation
raises ``InfrastructureFailure`` (exit 2), never a gate failure (exit 10),
because it indicates the environment wired the wrong driver, not that the
agent behaved incorrectly.

Anti-fabrication: the load-bearing proofs for gates 2, 3, and 4 are the
adapter's own sequential row-count snapshots (its own DB connection, read at
each step of the lifecycle — the same trust level as
``agent-project-management-v1``'s ``before_approvals`` snapshots) *plus* one
independent read of the ``projects`` table taken by the verifier's own
connection (``state["projects"]``), which the reject gate treats as
authoritative (a leaked row is a failure even if the adapter's own snapshot
claims otherwise) and which every phase's final count must agree with.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import InfrastructureFailure, run_verifier_main
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import InfrastructureFailure, run_verifier_main

BENCHMARK_ID = "agent-hitl-lifecycle-v1"
EXPECTED_SOURCE_REVISION = "cf3d04631cfd4ffb3d3e3f04be34333d5a091c3f"

WORKSPACE_ID = "00000000-0000-4000-8000-000000000803"
DESTRUCTIVE_TOOL = "create_project"

REQUIRED_PHASE_KEYS: dict[str, tuple[str, ...]] = {
    "approve_once": (
        "tool",
        "args",
        "interrupt",
        "rows_before_approval",
        "rows_after_approval",
        "tool_execution_count_after_approval",
        "final_assistant_message",
    ),
    "reject": (
        "tool",
        "args",
        "interrupt",
        "rows_before_reject",
        "rows_after_reject",
        "final_assistant_message",
    ),
    "reconfirm_resolved": ("job_id", "attempts"),
    "cancel_while_parked": (
        "tool",
        "args",
        "interrupt_first",
        "polls",
        "resumed_after_cancel",
    ),
}


# --------------------------------------------------------------------------
# live state (in-container only; psycopg is absent on the calibration host)
# --------------------------------------------------------------------------
def live_database_state() -> dict[str, Any]:
    """Independent read of every ``projects`` row in the seeded workspace."""
    import psycopg
    from psycopg.rows import dict_row

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        rows = connection.execute(
            """
            SELECT name, workspace_id::text, is_deleted
            FROM collections
            WHERE workspace_id = %s::uuid
            ORDER BY created_at, id
            """,
            (WORKSPACE_ID,),
        ).fetchall()
    return {"projects": [dict(row) for row in rows]}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def require_keys(evidence: dict[str, Any]) -> None:
    """Raise ``InfrastructureFailure`` for any missing/empty required key.

    A capability that cannot tell "the phase never ran" from "the phase ran
    and passed" is worthless — this is checked before any gate logic runs.
    """
    phases = evidence.get("phases")
    if not isinstance(phases, dict):
        raise InfrastructureFailure("evidence missing 'phases'")
    for phase_name, keys in REQUIRED_PHASE_KEYS.items():
        phase = phases.get(phase_name)
        if not isinstance(phase, dict):
            raise InfrastructureFailure(f"evidence missing phases.{phase_name}")
        for key in keys:
            if key not in phase or phase[key] in (None, "", [], {}):
                raise InfrastructureFailure(
                    f"evidence missing or empty phases.{phase_name}.{key}"
                )
    attempts = phases["reconfirm_resolved"].get("attempts")
    if not isinstance(attempts, list) or len(attempts) < 2:
        raise InfrastructureFailure(
            "evidence requires at least two reconfirm_resolved.attempts"
        )
    polls = phases["cancel_while_parked"].get("polls")
    if not isinstance(polls, list) or not polls:
        raise InfrastructureFailure(
            "evidence requires at least one cancel_while_parked.polls entry"
        )


def check_checkpointer_scheme(evidence: dict[str, Any]) -> None:
    """Gate 6 — a wrong driver scheme is an infrastructure failure, not a gate."""
    scheme = str(
        (evidence.get("checkpointer") or {}).get("db_uri_scheme") or ""
    ).strip()
    if not scheme:
        raise InfrastructureFailure("evidence missing checkpointer.db_uri_scheme")
    if scheme != "postgresql":
        raise InfrastructureFailure(
            f"checkpointer uses scheme {scheme!r}; expected the psycopg v3 "
            "'postgresql' scheme (a '+asyncpg' URL is an environment defect)"
        )


def rows_named(state: dict[str, Any], name: str | None) -> list[dict[str, Any]]:
    if not name:
        return []
    return [
        row
        for row in state.get("projects") or []
        if isinstance(row, dict)
        and row.get("name") == name
        and row.get("is_deleted") is False
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


def check_network_boundary(evidence: dict[str, Any], failures: list[str]) -> None:
    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")


def check_gate1_interrupt_exact(evidence: dict[str, Any], failures: list[str]) -> None:
    """Gate 1 — the interrupt names the tool and its args exactly."""
    phases = evidence["phases"]
    for phase_name, interrupt_key in (
        ("approve_once", "interrupt"),
        ("reject", "interrupt"),
        ("cancel_while_parked", "interrupt_first"),
    ):
        phase = phases[phase_name]
        tool = phase.get("tool")
        args = phase.get("args")
        interrupt = phase.get(interrupt_key) or {}
        tools = interrupt.get("tools") if isinstance(interrupt, dict) else None
        matched = isinstance(tools, list) and any(
            isinstance(item, dict)
            and item.get("name") == tool
            and item.get("args") == args
            for item in tools
        )
        if not matched:
            failures.append(
                f"{phase_name}: interrupt payload does not name {tool!r} with "
                f"the exact recorded args {args!r} (compared by value, not substring)"
            )


def check_gate2_reject_zero_mutation(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    """Gate 2 — reject resumes with zero mutations and a coherent message."""
    reject = evidence["phases"]["reject"]
    before = reject.get("rows_before_reject")
    after = reject.get("rows_after_reject")
    if before != after:
        failures.append(
            f"reject: adapter's own row snapshot shows a mutation across the "
            f"reject resume ({before} -> {after})"
        )
    name = (reject.get("args") or {}).get("name")
    leaked = rows_named(state, name)
    if leaked:
        failures.append(
            f"reject: independent DB read found {len(leaked)} row(s) named "
            f"{name!r} after reject (expected zero — authoritative over the "
            "adapter's own snapshot)"
        )
    message = str(
        (reject.get("final_assistant_message") or {}).get("content") or ""
    ).strip()
    if not message:
        failures.append("reject: no coherent non-empty final assistant message")


def check_gate3_approval_exactly_once(
    evidence: dict[str, Any], failures: list[str]
) -> None:
    """Gate 3 — the single approval executes exactly once."""
    approve = evidence["phases"]["approve_once"]
    before = approve.get("rows_before_approval")
    after = approve.get("rows_after_approval")
    if not isinstance(before, int) or not isinstance(after, int):
        failures.append("approve_once: row counts are not recorded as integers")
    elif after - before != 1:
        failures.append(
            f"approve_once: expected exactly one mutation row from the single "
            f"approval, observed {before} -> {after}"
        )
    if approve.get("tool_execution_count_after_approval") != 1:
        failures.append(
            "approve_once: expected exactly one tool-execution record after "
            f"approval, got {approve.get('tool_execution_count_after_approval')!r}"
        )


def check_gate4_confirm_replay_stable(
    evidence: dict[str, Any], failures: list[str]
) -> None:
    """Gate 4 — confirm on an already-resolved interrupt is a stable no-op."""
    approve = evidence["phases"]["approve_once"]
    attempts = evidence["phases"]["reconfirm_resolved"].get("attempts") or []
    statuses = {
        attempt.get("http_status") for attempt in attempts if isinstance(attempt, dict)
    }
    if len(statuses) != 1:
        failures.append(
            "reconfirm_resolved: confirm-on-resolved did not return a stable "
            f"HTTP status across repeats: {sorted(str(s) for s in statuses)}"
        )
    baseline = approve.get("rows_after_approval")
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict):
            continue
        if attempt.get("rows_after") != baseline:
            failures.append(
                f"reconfirm_resolved: attempt {index} changed the row count "
                f"from {baseline} to {attempt.get('rows_after')} — confirm on "
                "an already-resolved interrupt must not mutate state further"
            )


def check_gate5_cancel_redeliverable(
    evidence: dict[str, Any], failures: list[str]
) -> None:
    """Gate 5 — cancel while parked leaves the interrupt re-deliverable."""
    cancel = evidence["phases"]["cancel_while_parked"]
    first = cancel.get("interrupt_first")
    polls = cancel.get("polls") or []
    if not isinstance(first, dict) or not first.get("tools"):
        failures.append(
            "cancel_while_parked: no interrupt payload recorded for the parked job"
        )
        return
    for index, poll in enumerate(polls, start=1):
        if poll != first:
            failures.append(
                f"cancel_while_parked: poll {index} confirmation payload "
                "differs from the original interrupt — interrupt was not "
                "re-delivered unchanged"
            )


def check_final_state_agreement(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    """Cross-check every phase's own final row count against the live read."""
    phases = evidence["phases"]
    approve = phases["approve_once"]
    reject = phases["reject"]
    cancel = phases["cancel_while_parked"]
    reconfirm_attempts = phases["reconfirm_resolved"].get("attempts") or []

    approve_final = (
        reconfirm_attempts[-1].get("rows_after")
        if reconfirm_attempts and isinstance(reconfirm_attempts[-1], dict)
        else approve.get("rows_after_approval")
    )
    checks = (
        ((approve.get("args") or {}).get("name"), approve_final, "approve_once"),
        (
            (reject.get("args") or {}).get("name"),
            reject.get("rows_after_reject"),
            "reject",
        ),
        (
            (cancel.get("args") or {}).get("name"),
            (cancel.get("resumed_after_cancel") or {}).get("rows_after"),
            "cancel_while_parked",
        ),
    )
    for name, expected, phase_name in checks:
        if not name or expected is None:
            continue
        actual = len(rows_named(state, name))
        if actual != expected:
            failures.append(
                f"{phase_name}: adapter's final row count for {name!r} "
                f"({expected}) disagrees with the independent DB read ({actual})"
            )


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    require_keys(evidence)
    check_checkpointer_scheme(
        evidence
    )  # gate 6: raises InfrastructureFailure, never a gate failure

    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_gate1_interrupt_exact(evidence, failures)
    check_gate2_reject_zero_mutation(evidence, state, failures)
    check_gate3_approval_exactly_once(evidence, failures)
    check_gate4_confirm_replay_stable(evidence, failures)
    check_gate5_cancel_redeliverable(evidence, failures)
    check_final_state_agreement(evidence, state, failures)
    return failures


# Consumed by ``load_inputs`` for live (non-calibration) runs only.
objective_failures.live_reader = live_database_state  # type: ignore[attr-defined]


def db_snapshot(evidence: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"database_state": state}


def main() -> int:
    return run_verifier_main(
        BENCHMARK_ID, objective_failures, report_extra_fn=db_snapshot
    )


if __name__ == "__main__":
    sys.exit(main())
