#!/usr/bin/env python3
"""Deterministic verifier for ``agent-fast-path-cancel-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``).

This capability gates capability 3's ("Stream cancellation durability")
cancel/partial-persistence invariants applied to the Luna fast-path route
(``backend/src/services/agent/fast_path.py`` +
``backend/src/api/agent/streaming.py:_stream_luna_fast_path``):

  * gate 1 - emit-before-append ordering (``check_emit_before_append``)
  * gate 2 - cancel linkage (``check_cancel_linkage``)
  * gate 3 - partial persisted and linked to the run (``check_partial_persisted``)
  * gate 4 - prefix retained (``check_prefix_retained``)

THE CRITICAL DESIGN POINT (see ``evals/specs/agent-fast-path-cancel-v1/task.md``
for the full rationale): the fast path's own ``CancelledError`` handler
(``cancel_fast_path``) issues the FIRST, linked ``run.cancelled`` finalize.
That ``CancelledError`` then also trips ``stream_event_generator``'s outer,
route-agnostic ``CancelledError`` handler, which issues a SECOND, unlinked
``run.cancelled`` finalize. In production this second call is a no-op:
``finalize_submission``'s terminal-status guard and ``append_event``'s
``RunAlreadyTerminalError`` (backed by the ``uq_agent_run_events_one_terminal``
partial unique index) absorb it, so the durable ledger holds exactly one
terminal event, ever. THE VERIFIER MUST PASS when it sees one linked finalize
plus at most one absorbed unlinked duplicate, and MUST FAIL when the LINKED
event is missing (even if the unlinked one is present) — a verifier that
treats the duplicate itself as a failure would fail every honest run.

Anti-fabrication: the load-bearing proof for gate 2 is the independent DB
read (``state["events"]``/``state["run"]``), never the adapter's own
self-reported ``evidence["finalize_attempts"]`` log — an adapter could claim
a linked finalize happened while the durable ledger disagrees, and the
durable ledger wins.
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

BENCHMARK_ID = "agent-fast-path-cancel-v1"
EXPECTED_SOURCE_REVISION = "27018e69c0c9e0339aab5db5f76d34e1715a316c"

REQUIRED_EVIDENCE_KEYS = (
    "routing",
    "accepted",
    "token_log",
    "finalize_attempts",
    "persisted_partial",
    "termination_reason",
)

REQUIRED_TOKEN_LOG_KEYS = ("content", "emit_completed", "appended_to_partial")
REQUIRED_FINALIZE_KEYS = ("source", "event_type", "linked", "payload")
REQUIRED_PARTIAL_KEYS = ("id", "content", "stopped")


# --------------------------------------------------------------------------
# live state (in-container only; psycopg is absent on the calibration host)
# --------------------------------------------------------------------------
def live_database_state() -> dict[str, Any]:
    """Independent read of the run/event/message rows for this trial."""
    import psycopg
    from psycopg.rows import dict_row

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")
    thread_id = "00000000-0000-4000-8000-000000000d05"
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        runs = list(
            connection.execute(
                """
                SELECT job_id::text, status, organization_id::text, user_id::text,
                       thread_id::text, client_message_id::text,
                       assistant_message_id::text, last_event_seq,
                       completed_at::text, error_code, error
                FROM agent_runs
                WHERE thread_id = %s::uuid
                ORDER BY created_at, job_id
                """,
                (thread_id,),
            ).fetchall()
        )
        run = runs[-1] if runs else None
        events: list[dict[str, Any]] = []
        if run is not None:
            events = list(
                connection.execute(
                    """
                    SELECT id::text, run_id::text, seq, event_type, payload,
                           created_at::text
                    FROM agent_run_events
                    WHERE run_id = %s
                    ORDER BY seq
                    """,
                    (run["job_id"],),
                ).fetchall()
            )
        messages: list[dict[str, Any]] = []
        if thread_id:
            messages = list(
                connection.execute(
                    """
                    SELECT id::text, thread_id::text, role::text AS role, content,
                           stopped, client_message_id::text
                    FROM chat_messages
                    WHERE thread_id = %s::uuid
                    ORDER BY created_at, id
                    """,
                    (thread_id,),
                ).fetchall()
            )
    return {
        "run": dict(run) if run is not None else None,
        "events": [dict(row) for row in events],
        "messages": [dict(row) for row in messages],
        "run_count_for_thread": len(runs),
    }


# --------------------------------------------------------------------------
# structural preconditions
# --------------------------------------------------------------------------
def require_keys(evidence: dict[str, Any], state: dict[str, Any]) -> None:
    """Raise ``InfrastructureFailure`` for anything that means "the trial
    never ran / never recorded", never for a durability failure that ran
    cleanly."""
    for key in REQUIRED_EVIDENCE_KEYS:
        if key not in evidence or evidence[key] in (None, "", [], {}):
            raise InfrastructureFailure(f"evidence missing or empty {key!r}")

    routing = evidence["routing"]
    if not isinstance(routing, dict) or routing.get("eligible") is not True:
        raise InfrastructureFailure(
            f"turn never entered the fast path (routing={routing!r}) -- "
            "nothing fast-path-specific to verify"
        )

    token_log = evidence["token_log"]
    if not isinstance(token_log, list) or not token_log:
        raise InfrastructureFailure("evidence.token_log must be a non-empty list")
    for index, entry in enumerate(token_log):
        if not isinstance(entry, dict):
            raise InfrastructureFailure(f"evidence.token_log[{index}] is not an object")
        for key in REQUIRED_TOKEN_LOG_KEYS:
            if key not in entry:
                raise InfrastructureFailure(
                    f"evidence.token_log[{index}] missing {key!r}"
                )

    finalize_attempts = evidence["finalize_attempts"]
    if not isinstance(finalize_attempts, list) or not finalize_attempts:
        raise InfrastructureFailure(
            "evidence.finalize_attempts must be a non-empty list"
        )
    for index, attempt in enumerate(finalize_attempts):
        if not isinstance(attempt, dict):
            raise InfrastructureFailure(
                f"evidence.finalize_attempts[{index}] is not an object"
            )
        for key in REQUIRED_FINALIZE_KEYS:
            if key not in attempt:
                raise InfrastructureFailure(
                    f"evidence.finalize_attempts[{index}] missing {key!r}"
                )

    partial = evidence["persisted_partial"]
    if not isinstance(partial, dict):
        raise InfrastructureFailure("evidence.persisted_partial is not an object")
    for key in REQUIRED_PARTIAL_KEYS:
        if key not in partial:
            raise InfrastructureFailure(f"evidence.persisted_partial missing {key!r}")

    if not isinstance(state, dict) or not state.get("run") or not state.get("events"):
        raise InfrastructureFailure(
            "independent state missing 'run'/'events' -- cannot distinguish "
            "'the trial never ran' from 'the trial ran and passed'"
        )


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


def check_emit_before_append(evidence: dict[str, Any], failures: list[str]) -> None:
    """Gate 1 - a chunk may be appended to the partial only after its emit
    completed. Encodes the "buffer BEFORE recording for persistence"
    invariant verbatim from the fast-path streaming loop."""
    token_log = evidence["token_log"]
    seen_gap = False
    for index, entry in enumerate(token_log):
        emit_completed = bool(entry.get("emit_completed"))
        appended = bool(entry.get("appended_to_partial"))
        if appended and not emit_completed:
            failures.append(
                f"token_log[{index}]: chunk {entry.get('content')!r} was "
                "appended to the persisted partial before its emit completed "
                "(emit-before-append ordering violated)"
            )
        if not appended:
            seen_gap = True
        elif seen_gap:
            failures.append(
                f"token_log[{index}]: chunk {entry.get('content')!r} was "
                "appended after an earlier chunk was not -- appended chunks "
                "must form a contiguous prefix"
            )


def check_prefix_retained(evidence: dict[str, Any], failures: list[str]) -> None:
    """Gate 4 - persisted content equals exactly the concatenation of every
    appended chunk, in order -- never truncated, never extended."""
    token_log = evidence["token_log"]
    expected = "".join(
        str(entry.get("content") or "")
        for entry in token_log
        if entry.get("appended_to_partial")
    )
    partial = evidence["persisted_partial"]
    actual = str(partial.get("content") or "")
    if not actual:
        failures.append("persisted_partial.content is empty")
    if actual != expected:
        failures.append(
            f"persisted_partial.content {actual!r} does not equal the "
            f"concatenation of appended chunks {expected!r} -- the prefix "
            "was not retained exactly"
        )
    if partial.get("stopped") is not True:
        failures.append("persisted_partial.stopped is not true")


def check_partial_persisted(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    """Gate 3 - the stopped partial row is durably persisted and the
    AgentRun row's own status/linkage columns agree with it."""
    partial = evidence["persisted_partial"]
    partial_id = partial.get("id")
    messages = state.get("messages") or []
    matches = [msg for msg in messages if msg.get("id") == partial_id]
    if not matches:
        failures.append(
            f"independent DB read found no chat_messages row with id "
            f"{partial_id!r} -- the persisted partial does not durably exist"
        )
    else:
        row = matches[0]
        if row.get("stopped") is not True:
            failures.append(
                f"durable message {partial_id!r} is not marked stopped=true"
            )
        if not str(row.get("content") or ""):
            failures.append(f"durable message {partial_id!r} has empty content")

    run = state.get("run") or {}
    if run.get("status") != "cancelled":
        failures.append(
            f"AgentRun status was {run.get('status')!r}, expected cancelled"
        )


def check_cancel_linkage(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    """Gate 2 + the tolerance. See module docstring."""
    partial_id = evidence["persisted_partial"].get("id")
    attempts = [
        attempt
        for attempt in evidence["finalize_attempts"]
        if attempt.get("event_type") == "run.cancelled"
    ]
    if not attempts:
        failures.append(
            "no run.cancelled finalize attempt recorded in evidence.finalize_attempts"
        )
    linked_attempts = [a for a in attempts if a.get("linked") is True]
    unlinked_attempts = [a for a in attempts if a.get("linked") is False]
    if not linked_attempts:
        failures.append(
            "no LINKED run.cancelled finalize attempt observed in the "
            "adapter's own log -- an unlinked-only duplicate is not "
            "sufficient (see task.md's tolerance)"
        )
    if len(linked_attempts) > 1:
        failures.append(
            f"more than one linked run.cancelled finalize attempt recorded: "
            f"{len(linked_attempts)}"
        )
    if len(unlinked_attempts) > 1:
        failures.append(
            "more than one unlinked run.cancelled finalize attempt recorded "
            f"-- the tolerance permits at most one absorbed duplicate, got "
            f"{len(unlinked_attempts)}"
        )
    for attempt in linked_attempts:
        if (attempt.get("payload") or {}).get("assistant_message_id") != partial_id:
            failures.append(
                "a linked finalize attempt's payload.assistant_message_id "
                f"{(attempt.get('payload') or {}).get('assistant_message_id')!r} "
                f"does not match the persisted partial id {partial_id!r}"
            )
    # The durable ledger stays authoritative (checked below), but the
    # adapter's own self-report must at least be internally coherent: an
    # unlinked attempt claiming a different disconnect reason, or carrying
    # an assistant_message_id that contradicts the persisted partial, is a
    # contradictory self-report even before the DB cross-check runs.
    for attempt in unlinked_attempts:
        payload = attempt.get("payload") or {}
        if payload.get("reason") != "client_disconnected":
            failures.append(
                "an unlinked run.cancelled finalize attempt's payload.reason "
                f"{payload.get('reason')!r} is not 'client_disconnected' -- "
                "the self-reported attempt log is internally incoherent"
            )
        reported_link = payload.get("assistant_message_id")
        if reported_link is not None and reported_link != partial_id:
            failures.append(
                "an unlinked run.cancelled finalize attempt nonetheless "
                f"carries payload.assistant_message_id={reported_link!r}, "
                f"inconsistent with the persisted partial id {partial_id!r} "
                "-- the self-reported attempt log is internally incoherent"
            )

    # The independent DB read is authoritative over the adapter's own log:
    # this is the check that actually catches "the unlinked one won the race".
    run_id = (evidence.get("accepted") or {}).get("run_id")
    run_job_id = (state.get("run") or {}).get("job_id")
    if run_id and run_job_id and run_id != run_job_id:
        failures.append(
            f"independent DB read's run.job_id {run_job_id!r} does not match "
            f"the accepted run id {run_id!r} under test"
        )
    events = state.get("events") or []
    mismatched_run_events = [
        event
        for event in events
        if run_id and event.get("run_id") not in (None, run_id)
    ]
    if mismatched_run_events:
        failures.append(
            f"independent DB read returned {len(mismatched_run_events)} "
            f"event(s) for a different run_id than the accepted run "
            f"{run_id!r} under test -- the state read is not correctly "
            "scoped to this trial"
        )
    terminal_events = [
        event
        for event in events
        if event.get("event_type") in {"run.completed", "run.failed", "run.cancelled"}
    ]
    if len(terminal_events) == 0:
        failures.append("durable ledger has no terminal event -- run was never closed")
    elif len(terminal_events) > 1:
        failures.append(
            f"durable ledger has {len(terminal_events)} terminal events -- "
            "the partial unique index should make this impossible"
        )
    else:
        terminal = terminal_events[0]
        if terminal.get("event_type") != "run.cancelled":
            failures.append(
                f"durable terminal event is {terminal.get('event_type')!r}, "
                "expected run.cancelled"
            )
        payload = terminal.get("payload") or {}
        if payload.get("assistant_message_id") != partial_id:
            failures.append(
                "durable run.cancelled event is missing the link to the "
                f"persisted partial: payload.assistant_message_id="
                f"{payload.get('assistant_message_id')!r}, expected "
                f"{partial_id!r} -- the durable event is not the linked one "
                "(THE trap: an unlinked-only durable event is a failure "
                "even when the adapter's log also shows a linked attempt)"
            )

    run = state.get("run") or {}
    if run.get("assistant_message_id") != partial_id:
        failures.append(
            f"AgentRun.assistant_message_id={run.get('assistant_message_id')!r} "
            f"does not match the persisted partial id {partial_id!r}"
        )
    if any(event.get("event_type") == "run.completed" for event in events):
        failures.append("durable ledger contains run.completed after a cancel")
    if evidence.get("termination_reason") != "cancelled":
        failures.append(
            f"termination_reason={evidence.get('termination_reason')!r}, "
            "expected cancelled"
        )


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    require_keys(evidence, state)  # raises InfrastructureFailure on structural defects

    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_emit_before_append(evidence, failures)
    check_prefix_retained(evidence, failures)
    check_partial_persisted(evidence, state, failures)
    check_cancel_linkage(evidence, state, failures)
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
