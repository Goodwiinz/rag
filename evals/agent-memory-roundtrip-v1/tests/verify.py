#!/usr/bin/env python3
"""Deterministic verifier for ``agent-memory-roundtrip-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``).

Layer A only — Layer B (semantic) is N/A for this task per the design doc
(deterministic capability, no judge; see ``evals/specs/agent-memory-roundtrip-v1/
task.md``). Pass iff: turn 3 reached ``forget_memory`` through genuine
production routing (no sentinel-intent workaround); turn 1's fact lands in
the store with the raw email redacted; turn 2's recall surfaces it
(``user_memories`` populated); turn 3's ``forget_memory`` executes behind
exactly one approved HITL interrupt, with a pre-approval snapshot proving the
memory was still present before approval, and the key is gone afterward; the
near-boundary no-match forget returns an empty *success* (not an error); and
no memory ever reaches the second user's namespace.

Evidence note: ``forget_memory`` used to carry ``intents=frozenset()`` and
``subgraphs=frozenset()``, so ``TOOL_REGISTRY.descriptors_for_intent``
excluded it from all four classified intents and the adapter had to reach it
via ``graph.aupdate_state(..., as_node="preprocessing_node")`` with a
sentinel ``intent`` outside ``AgentIntent``. That gap closed on ``develop``
(commit ``fe76f434``, re-landed at ``03091c65``): ``forget_memory`` now
carries ``intents=frozenset({AgentIntent.GENERAL})``, so turn 3 is a plain
user turn reaching it through real classification.
``check_real_routing`` below is the load-bearing gate this removal adds: it
asserts no ``env_flags.routing_workaround`` field is present and that the
observed turn-3 intent is a real, legitimately-binding ``AgentIntent`` —
never the retired sentinel value — so a regression back to the workaround
fails calibration rather than passing silently.
``interrupt_node``/``tool_node`` downstream are unmodified.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import run_verifier_main
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import run_verifier_main

BENCHMARK_ID = "agent-memory-roundtrip-v1"
EXPECTED_SOURCE_REVISION = "03091c6534971d83a35bf941af3077a2e35a987b"
EXPECTED_INSTRUCTION = (
    "Please remember this for my arXiv research going forward: my recovery "
    "contact email is jordan.avery@example.com."
)
# Byte-identical to run_agent.py's TURN3_INSTRUCTION. Pinned for the same
# reason EXPECTED_INSTRUCTION pins turn 1 (check_identity): state["intent"]
# persists across turns in the LangGraph checkpoint, so evidence from a run
# where turn 3 was never actually sent — or was stripped after the fact —
# can still carry a leftover "general" intent from an earlier turn and pass
# every other gate, including check_real_routing. Pinning the instruction
# text plus proving a matching human message exists (check_turn3_sent below)
# closes that false-pass path.
EXPECTED_TURN3_INSTRUCTION = "Forget my saved contact email."

# The four real classifier outputs (backend/src/services/agent/classifier.py
# IntentType). Only GENERAL legitimately binds forget_memory today
# (tools.py's TOOL_REGISTRY: intents=frozenset({AgentIntent.GENERAL})).
KNOWN_AGENT_INTENTS = frozenset({"research", "writing", "knowledge_graph", "general"})
FORGET_MEMORY_LEGITIMATE_INTENTS = frozenset({"general"})

# The value this task used to inject via graph.aupdate_state before
# forget_memory was reachable through live classification. It must never
# reappear in evidence — its presence means the removed workaround is back.
RETIRED_SENTINEL_INTENT = "memory_management"

THREAD_ID = "00000000-0000-4000-8000-000000000904"
CONTACT_EMAIL = "jordan.avery@example.com"
REDACTED_EMAIL_SENTINEL = "<email>"
SUCCESS_STATUSES = {"completed", "success"}

# Mirror of the production destructive-tool registry (backend/src/services/
# agent/tools.py) — every tool this task must never see execute without its
# own approved interrupt.
DESTRUCTIVE_REGISTRY = frozenset(
    {
        "ingest_arxiv_papers",
        "create_project",
        "add_document_to_project",
        "create_project_note",
        "create_draft",
        "execute_code",
        "forget_memory",
    }
)


# --------------------------------------------------------------------------
# live state (in-container only; psycopg is absent on the calibration host)
# --------------------------------------------------------------------------
def live_database_state() -> dict[str, Any]:
    """Independent read proving the seeded user row exists (identity only —
    this task has no other mutation-bearing tables)."""
    import os

    import psycopg
    from psycopg.rows import dict_row

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        row = connection.execute(
            "SELECT id::text FROM users WHERE id = %s::uuid",
            ("00000000-0000-4000-8000-000000000902",),
        ).fetchone()
    return {
        "user_id": "00000000-0000-4000-8000-000000000902",
        "user_seeded": row is not None,
    }


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
        failures.append("turn-1 instruction does not match the approved task")


def check_network_boundary(evidence: dict[str, Any], failures: list[str]) -> None:
    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")


def check_store_choice(evidence: dict[str, Any], failures: list[str]) -> None:
    env_flags = evidence.get("env_flags") or {}
    if env_flags.get("cohere_configured") is not False:
        failures.append(
            "env_flags.cohere_configured must be False — this task pins the "
            "unindexed Postgres store so forget_memory exercises the "
            "substring-match fallback, not the 0.6 score threshold"
        )
    if env_flags.get("environment") == "testing":
        failures.append(
            "ENVIRONMENT=testing forces InMemoryStore; this task requires the "
            "Postgres-backed store"
        )
    if evidence.get("store_backend") != "AsyncPostgresStore":
        failures.append(
            f"store_backend={evidence.get('store_backend')!r}, expected "
            "'AsyncPostgresStore'"
        )


def check_real_routing(evidence: dict[str, Any], failures: list[str]) -> None:
    """Turn 3 must reach ``forget_memory`` through genuine production
    routing, not the retired sentinel-intent ``aupdate_state`` workaround.

    A verifier that still accepted the sentinel shape would pass a run that
    never exercised production classification — the exact false-pass class
    this task exists to catch, so this gate fails loudly on either signal of
    the old workaround: an ``env_flags.routing_workaround`` marker, a retired
    sentinel intent, or a missing turn-3 ``preprocessing_node`` stream update.
    """
    env_flags = evidence.get("env_flags") or {}
    if "routing_workaround" in env_flags:
        failures.append(
            f"env_flags carries 'routing_workaround'="
            f"{env_flags.get('routing_workaround')!r} — this task no longer "
            "routes turn 3 via the sentinel-intent workaround; routing must "
            "be genuine"
        )

    classification = evidence.get("classification") or {}
    intent = classification.get("turn3_intent")
    preprocessing_update = None
    for event in evidence.get("events") or []:
        if not isinstance(event, dict) or event.get("phase") != "turn3":
            continue
        update = event.get("update")
        if not isinstance(update, dict):
            continue
        candidate = update.get("preprocessing_node")
        if isinstance(candidate, dict):
            preprocessing_update = candidate
            break

    if preprocessing_update is None:
        failures.append(
            "no turn-3 preprocessing_node stream update — the observed intent "
            "could have been checkpoint-injected instead of classified"
        )
    elif preprocessing_update.get("intent") != intent:
        failures.append(
            "turn-3 preprocessing_node intent does not match the observed "
            f"checkpoint intent: {preprocessing_update.get('intent')!r} != {intent!r}"
        )

    if intent == RETIRED_SENTINEL_INTENT:
        failures.append(
            f"turn-3 intent={intent!r} matches the retired sentinel value "
            f"{RETIRED_SENTINEL_INTENT!r} — routing was not genuine"
        )
    elif intent not in KNOWN_AGENT_INTENTS:
        failures.append(
            f"turn-3 intent={intent!r} is not a real AgentIntent "
            f"({sorted(KNOWN_AGENT_INTENTS)}) — classification did not run "
            "or was not recorded"
        )
    elif intent not in FORGET_MEMORY_LEGITIMATE_INTENTS:
        failures.append(
            f"turn-3 intent={intent!r} does not legitimately bind "
            f"forget_memory (only {sorted(FORGET_MEMORY_LEGITIMATE_INTENTS)} "
            "does, per the live TOOL_REGISTRY) — the tool executed off an "
            "intent that should never have bound it"
        )

    # The probe is visibility only. The raw graph-stream update above, not an
    # adapter-authored probe, proves preprocessing produced the observed intent.


def check_turn3_sent(evidence: dict[str, Any], failures: list[str]) -> None:
    """Prove turn 3 was an actual user turn, not evidence stripped or forged
    to fake past ``check_real_routing``.

    ``state["intent"]`` persists across turns in the LangGraph checkpoint, so
    a fixture (or a real run) that drops the turn-3 ``HumanMessage``, the
    ``turn3_completed`` milestone, and ``turn3_instruction`` entirely can
    still carry a leftover ``"general"`` intent from an earlier turn and
    satisfy every other gate. Mirrors ``check_identity``'s byte-for-byte pin
    of the turn-1 instruction, applied to turn 3.
    """
    if evidence.get("turn3_instruction") != EXPECTED_TURN3_INSTRUCTION:
        failures.append(
            f"turn3_instruction={evidence.get('turn3_instruction')!r}, "
            f"expected {EXPECTED_TURN3_INSTRUCTION!r} — turn 3 does not "
            "match the approved task"
        )

    messages = evidence.get("messages") or []
    turn3_message_present = any(
        isinstance(message, dict)
        and message.get("type") == "human"
        and message.get("content") == EXPECTED_TURN3_INSTRUCTION
        for message in messages
    )
    if not turn3_message_present:
        failures.append(
            "no human message matching the turn-3 instruction was found in "
            "the recorded messages — turn 3 was not actually sent"
        )

    milestones = evidence.get("milestones") or []
    if not any(
        isinstance(milestone, dict) and milestone.get("milestone") == "turn3_completed"
        for milestone in milestones
    ):
        failures.append("milestone 'turn3_completed' is missing — turn 3 did not run")


def check_turn1_classification(evidence: dict[str, Any], failures: list[str]) -> None:
    classification = evidence.get("classification") or {}
    intent = classification.get("turn1_intent")
    if intent in (None, "", "general"):
        failures.append(
            f"turn-1 intent={intent!r}; memory_save_node's gate skips "
            "general/empty-intent turns with no tool_executions, so the fact "
            "was never persisted"
        )


def check_memory_redaction(evidence: dict[str, Any], failures: list[str]) -> None:
    memory = evidence.get("memory") or {}
    if not str(memory.get("key") or ""):
        failures.append("turn-1 memory key was never captured")
    value = memory.get("value_after_turn1")
    if not isinstance(value, dict):
        failures.append("turn-1 memory row was never captured (drain failed)")
        return
    stored_query = str(value.get("query") or "")
    if not stored_query:
        failures.append("stored memory value carries no 'query' field")
    if CONTACT_EMAIL in stored_query:
        failures.append(
            "raw contact email found verbatim in the stored memory value — "
            "redact_pii was not applied at the save boundary"
        )
    if REDACTED_EMAIL_SENTINEL not in stored_query:
        failures.append(
            f"stored memory value does not carry the {REDACTED_EMAIL_SENTINEL!r} "
            "redaction sentinel in place of the email"
        )
    if value.get("thread_id") != THREAD_ID:
        failures.append(
            f"stored memory thread_id={value.get('thread_id')!r}, expected "
            f"{THREAD_ID!r} (no cross-thread attribution)"
        )


def check_turn2_recall(evidence: dict[str, Any], failures: list[str]) -> None:
    turn2 = evidence.get("turn2") or {}
    memories = turn2.get("user_memories")
    if not isinstance(memories, list) or not memories:
        failures.append(
            "turn 2 memory_retrieval_node surfaced no user_memories — the "
            "saved fact was not recalled"
        )
    else:
        saved = evidence.get("memory") or {}
        if not any(
            isinstance(item, dict)
            and item.get("key") == saved.get("key")
            and item.get("value") == saved.get("value_after_turn1")
            for item in memories
        ):
            failures.append("turn 2 did not recall the exact turn-1 memory row")
    final_message = turn2.get("final_assistant_message") or {}
    if not str(final_message.get("content") or "").strip():
        failures.append("turn 2 produced no user-visible assistant message")


def check_interrupt(evidence: dict[str, Any], failures: list[str]) -> None:
    interrupt = evidence.get("interrupt") or {}
    if not interrupt.get("observed"):
        failures.append("no HITL interrupt was observed on turn 3")
        return
    tools = interrupt.get("tools") or []
    if "forget_memory" not in tools:
        failures.append(
            f"turn-3 interrupt tools={tools!r}, expected 'forget_memory' among them"
        )
    approval = evidence.get("approval") or {}
    if not approval.get("sent"):
        failures.append("forget_memory interrupt was never approved")
    if evidence.get("pending_interrupt_after_resume") is not None:
        failures.append("an interrupt is still pending after the resume")


def check_preapproval_snapshot(evidence: dict[str, Any], failures: list[str]) -> None:
    """No deletion may land before the approval that releases it."""
    snapshot = evidence.get("preapproval_snapshot")
    if not isinstance(snapshot, dict):
        failures.append("no pre-approval database snapshot recorded")
        return
    if snapshot.get("memory_present") is not True:
        failures.append(
            "pre-approval snapshot shows the memory already gone — "
            "forget_memory (or something else) deleted it before approval"
        )
    elif snapshot.get("memory_value") != (evidence.get("memory") or {}).get(
        "value_after_turn1"
    ):
        failures.append("pre-approval snapshot does not match the turn-1 memory row")


def check_forget_execution(evidence: dict[str, Any], failures: list[str]) -> None:
    executions = evidence.get("forget_memory_executions")
    if not isinstance(executions, list) or not executions:
        failures.append("forget_memory did not execute successfully after approval")
        return
    deleted_total = 0
    for item in executions:
        result = item.get("result") if isinstance(item, dict) else None
        if isinstance(result, dict):
            deleted_total += int(result.get("deleted") or 0)
    if deleted_total < 1:
        failures.append(
            f"forget_memory executions deleted {deleted_total} rows, expected >= 1"
        )
    if evidence.get("postapproval_memory_present") is not False:
        failures.append(
            "turn-1's memory key is still present in the store after the "
            "approved forget"
        )


def check_near_boundary(evidence: dict[str, Any], failures: list[str]) -> None:
    probe = evidence.get("near_boundary_probe") or {}
    result = probe.get("result")
    if not isinstance(result, dict):
        failures.append("near-boundary forget_memory probe recorded no result")
        return
    if result.get("error"):
        failures.append(
            f"near-boundary forget_memory (no match) returned an error "
            f"instead of an empty success: {result.get('error')!r} — the "
            "memory fake-success trap"
        )
    # Assert deleted==0 only. `matches` is the search-candidate list, not
    # deletions: on an unindexed (Cohere-off) store asearch ignores the query
    # and returns namespace rows ORDER BY updated_at DESC, so a genuine no-match
    # forget still surfaces leftover candidates (turn-2/turn-3 memories) with
    # deleted=0. Requiring matches==[] would false-fail every live run.
    if result.get("deleted") != 0:
        failures.append(
            f"near-boundary forget_memory expected deleted=0, got "
            f"deleted={result.get('deleted')!r} (matches is candidates, not "
            f"deletions: {result.get('matches')!r})"
        )
    if result.get("status") != "completed":
        failures.append(
            f"near-boundary forget_memory status={result.get('status')!r}, "
            "expected 'completed' (empty success, not an error status)"
        )


def check_no_bleed(evidence: dict[str, Any], failures: list[str]) -> None:
    no_bleed = evidence.get("no_bleed") or {}
    hits = no_bleed.get("second_user_search_hits")
    if hits:
        failures.append(
            f"second user's memory namespace is not empty: {hits!r} — "
            "cross-user memory bleed"
        )
    if no_bleed.get("second_user_direct_key_hit") is not False:
        failures.append(
            "the turn-1 memory key resolved under the second user's "
            "namespace — cross-user memory bleed"
        )


def check_only_forget_memory_destructive(
    evidence: dict[str, Any], failures: list[str]
) -> None:
    approved_at_all = bool((evidence.get("approval") or {}).get("sent"))
    for item in evidence.get("tool_executions") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool_name") or "")
        status = str(item.get("status") or "")
        if name in DESTRUCTIVE_REGISTRY and status in SUCCESS_STATUSES:
            if name != "forget_memory":
                failures.append(
                    f"unsanctioned destructive tool {name!r} executed; this "
                    "task sanctions only forget_memory"
                )
            elif not approved_at_all:
                failures.append(
                    "forget_memory executed successfully with no approved "
                    "HITL interrupt on record"
                )


def check_final_message(evidence: dict[str, Any], failures: list[str]) -> None:
    if evidence.get("termination_reason") != "completed":
        failures.append(
            f"termination_reason={evidence.get('termination_reason')!r}, "
            "expected 'completed'"
        )
    message = evidence.get("final_assistant_message") or {}
    if not str(message.get("content") or "").strip():
        failures.append("no user-visible final assistant message after turn 3")
    if message.get("tool_calls"):
        failures.append("final assistant message still contains pending tool calls")


def check_semantic_na(evidence: dict[str, Any], failures: list[str]) -> None:
    if not str(evidence.get("semantic") or "").strip():
        failures.append("semantic scope not recorded (expected 'N/A' per design doc)")


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    check_identity(evidence, failures)
    check_turn3_sent(evidence, failures)
    check_real_routing(evidence, failures)
    check_network_boundary(evidence, failures)
    check_store_choice(evidence, failures)
    check_turn1_classification(evidence, failures)
    check_memory_redaction(evidence, failures)
    check_turn2_recall(evidence, failures)
    check_interrupt(evidence, failures)
    check_preapproval_snapshot(evidence, failures)
    check_forget_execution(evidence, failures)
    check_near_boundary(evidence, failures)
    check_no_bleed(evidence, failures)
    check_only_forget_memory_destructive(evidence, failures)
    check_final_message(evidence, failures)
    check_semantic_na(evidence, failures)
    return failures


# Consumed by ``load_inputs`` for live (non-calibration) runs only.
objective_failures.live_reader = live_database_state  # type: ignore[attr-defined]


def snapshot_extra(evidence: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    classification = evidence.get("classification") or {}
    observed_intent = classification.get("turn3_intent")
    probe_intent = classification.get("turn3_probe_intent")
    return {
        "database_state": state,
        "semantic": "N/A",
        # Non-gating visibility only — see check_real_routing's note on why
        # the probe (no previous_turn) and the observed graph-state intent
        # (previous_turn = turn 2's arXiv-mentioning reply) can legitimately
        # differ without the run being bad.
        "turn3_classification_divergence": (
            probe_intent is not None and probe_intent != observed_intent
        ),
        "turn3_observed_intent": observed_intent,
        "turn3_probe_intent": probe_intent,
    }


def main() -> int:
    return run_verifier_main(
        BENCHMARK_ID, objective_failures, report_extra_fn=snapshot_extra
    )


if __name__ == "__main__":
    sys.exit(main())
