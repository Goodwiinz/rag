#!/usr/bin/env python3
"""Run the memory-roundtrip benchmark against the production LangGraph graph.

Three turns, one thread: state a durable fact, recall it, then forget it.

- Turn 1's fire-and-forget ``memory_save_node`` write is drained by polling
  the store for the deterministic key the node computes
  (``md5(f"{thread_id}:{turn_index}:{content[:100]}")[:12]``) — never a fixed
  sleep (landmine 4).
- ``forget_memory`` carries ``intents=frozenset()`` and ``subgraphs=frozenset()``
  (verified empirically against ``TOOL_REGISTRY`` — no classified intent
  (research/writing/knowledge_graph/general) ever binds it; it is only present
  in ``ALL_TOOLS``, the ``_get_tools_for_intent`` fallback for an intent string
  outside ``AgentIntent``). Since ``classify_intent_with_fallback`` is
  Literal-typed and always returns one of those four values, that fallback is
  unreachable through live chat. Turn 3 reaches it the same way LangGraph's
  own time-travel API does: ``graph.aupdate_state(..., as_node=
  "preprocessing_node")`` writes a sentinel intent into the checkpoint as if
  ``preprocessing_node`` had produced it (mirroring the per-turn resets that
  node performs), then ``astream(None, config)`` resumes the graph from
  ``route_by_intent`` — a real LangGraph API, not a monkeypatch — so
  ``llm_node`` binds ``ALL_TOOLS`` and the *production* ``interrupt_node`` /
  ``tool_node`` handle the resulting destructive call exactly as they would
  for any other tool (landmine 5).
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

BENCHMARK_ID = "agent-memory-roundtrip-v1"
SOURCE_REVISION = "ecc30ede203061b9440cbab1d2cfad23fa9abf1c"
AGENT_REVISION = "ecc30ede203061b9440cbab1d2cfad23fa9abf1c"
APPROVAL_TEXT = "Yes, forget it."

# Byte-identical across instruction.md / run_agent.py / verify.py. Turn 1 only
# — turns 2-3 are adapter-scripted follow-ups, not part of the task contract.
EXPECTED_INSTRUCTION = (
    "Please remember this for my arXiv research going forward: my recovery "
    "contact email is jordan.avery@example.com."
)
TURN2_INSTRUCTION = "What contact email do you have on file for my arXiv research?"
TURN3_INSTRUCTION = (
    "Please forget what I told you about my arXiv research contact email."
)

CONTACT_EMAIL = "jordan.avery@example.com"
REDACTED_EMAIL_SENTINEL = "<email>"

# Any string outside AgentIntent ("research"/"writing"/"knowledge_graph"/
# "general") — forces the ALL_TOOLS fallback in _get_tools_for_intent so
# forget_memory (subgraphs=frozenset(), intents=frozenset()) is bindable.
FORGET_TURN_SENTINEL_INTENT = "memory_management"

# A query guaranteed to substring-miss every stored memory value — the
# near-boundary "fake success" probe (empty deletion is a success, not an
# error).
NEAR_BOUNDARY_QUERY = "xyzzy-no-such-benchmark-topic-000901"

ORG_ID = UUID("00000000-0000-4000-8000-000000000901")
USER_ID = UUID("00000000-0000-4000-8000-000000000902")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000903")
THREAD_ID = "00000000-0000-4000-8000-000000000904"
SECOND_THREAD_ID = "00000000-0000-4000-8000-000000000905"
SECOND_USER_ID = UUID("00000000-0000-4000-8000-000000000906")

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"


def memory_key(thread_id: str, turn_index: int, content: str) -> str:
    """Mirror ``_nodes_memory.memory_save_node``'s key derivation exactly."""
    return hashlib.md5(
        f"{thread_id}:{turn_index}:{content[:100]}".encode(),
        usedforsecurity=False,
    ).hexdigest()[:12]


async def database_state() -> dict[str, Any]:
    """Not a mutation-bearing task — identity rows only, for the record."""
    from src.core.database import AsyncSessionLocal
    from src.models.user import User

    async with AsyncSessionLocal() as session:
        user = await session.get(User, USER_ID)
    return {"user_id": str(USER_ID), "user_seeded": user is not None}


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
    if isinstance(tools, list):
        return [tool for tool in tools if isinstance(tool, dict)]
    return []


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


async def drain_memory_write(
    store: Any,
    namespace: tuple[str, str],
    key: str,
    timeout_s: float = 20.0,
    interval_s: float = 0.25,
) -> Any:
    """Poll the store for *key* until it lands or the bounded drain expires.

    Landmine 4: ``memory_save_node`` dispatches the embed+PG write as a
    background ``asyncio.Task`` and returns immediately. A fixed sleep is not
    acceptable — poll the deterministic key the node computed instead.
    """
    started = time.monotonic()
    while time.monotonic() - started < timeout_s:
        item = await store.aget(namespace, key)
        if item is not None:
            return item
        await asyncio.sleep(interval_s)
    return None


def tool_succeeded(tool_executions: list[Any], tool_name: str) -> list[dict[str, Any]]:
    return [
        item
        for item in tool_executions
        if isinstance(item, dict)
        and item.get("tool_name") == tool_name
        and item.get("status") in {"completed", "success"}
    ]


def hitl_steps(steps: list[dict[str, Any]], evidence: dict[str, Any]) -> list[Any]:
    """Splice the single forget_memory HITL approval into the trajectory."""
    if steps and steps[-1].get("source") == "agent":
        approved = [
            call.get("function_name")
            for call in steps[-1].get("tool_calls") or []
            if call.get("function_name") == "forget_memory"
        ]
        if approved and not any(
            (step.get("extra") or {}).get("hitl_resume") for step in steps
        ):
            return steps + [
                {
                    "source": "user",
                    "message": APPROVAL_TEXT,
                    "extra": {"hitl_resume": {"confirmed": True}},
                }
            ]
    injected = any((step.get("extra") or {}).get("hitl_resume") for step in steps)
    expected_turns = 3
    derived = sum(
        1
        for step in steps
        if step.get("source") == "agent"
        or (
            step.get("source") == "user"
            and not (step.get("extra") or {}).get("hitl_resume")
        )
    )
    if derived >= expected_turns and not injected:
        if not (steps and steps[-1].get("source") == "system"):
            return steps + [
                {"source": "system", "message": "No HITL approval was observed."}
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

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "")
    )
    await bootstrap_schema()
    await seed_tenant(
        org_id=ORG_ID,
        user_id=USER_ID,
        workspace_id=WORKSPACE_ID,
        name_prefix="Benchmark",
        email="benchmark-route@example.invalid",
    )

    env_flags = {
        "environment": os.environ.get("ENVIRONMENT", ""),
        "cohere_configured": bool(os.environ.get("COHERE_API_KEY", "").strip()),
        "allow_memory_fallback": os.environ.get("ALLOW_MEMORY_FALLBACK", ""),
        "store_choice": "postgres-unindexed (Cohere off -> substring-match forget fallback)",
    }

    from src.services.agent._builders import RECURSION_LIMIT
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.classifier import classify_intent_with_fallback
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store
    from src.services.agent.tools_impl import _tool_forget_memory

    checkpointer = await get_checkpointer()
    store = await get_memory_store()
    graph = compile_agent_graph(checkpointer=checkpointer, store=store)
    store_backend = type(store).__name__

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

    namespace = ("user", str(USER_ID))

    # ---------------------------------------------------------------
    # Turn 1 — state the durable fact.
    # ---------------------------------------------------------------
    turn1_classification_probe = await classify_intent_with_fallback(instruction, {})
    await collect_updates(
        graph,
        initial_agent_state(instruction, THREAD_ID, user_id=str(USER_ID)),
        config,
        "turn1",
        events,
        sequence,
    )
    turn1_snapshot = await graph.aget_state(config)
    turn1_interrupt = extract_interrupt(turn1_snapshot)
    if turn1_interrupt is not None:
        raise InfrastructureFailure(
            f"unexpected HITL interrupt after turn 1: {turn1_interrupt}"
        )
    turn1_values = dict(getattr(turn1_snapshot, "values", {}) or {})
    turn1_intent = turn1_values.get("intent")
    record_milestone(milestones, sequence, "turn1_completed")

    mem_key = memory_key(THREAD_ID, 1, instruction)
    memory_item = await drain_memory_write(store, namespace, mem_key)
    record_milestone(
        milestones,
        sequence,
        "memory_drained" if memory_item is not None else "memory_not_persisted",
    )
    memory_value_after_turn1 = json_safe(getattr(memory_item, "value", None))

    # ---------------------------------------------------------------
    # Turn 2 — recall.
    # ---------------------------------------------------------------
    from langchain_core.messages import HumanMessage

    await collect_updates(
        graph,
        {"messages": [HumanMessage(content=TURN2_INSTRUCTION)]},
        config,
        "turn2",
        events,
        sequence,
    )
    turn2_snapshot = await graph.aget_state(config)
    turn2_interrupt = extract_interrupt(turn2_snapshot)
    if turn2_interrupt is not None:
        raise InfrastructureFailure(
            f"unexpected HITL interrupt after turn 2: {turn2_interrupt}"
        )
    turn2_values = dict(getattr(turn2_snapshot, "values", {}) or {})
    turn2_user_memories = json_safe(turn2_values.get("user_memories") or [])
    turn2_final_message = final_assistant_message(
        list(turn2_values.get("messages") or [])
    )
    record_milestone(milestones, sequence, "turn2_completed")

    # ---------------------------------------------------------------
    # Turn 3 — forget, via the ALL_TOOLS sentinel-intent path (landmine 5).
    # ---------------------------------------------------------------
    await graph.aupdate_state(
        config,
        {
            # Mirrors preprocessing_node's own per-turn reset dict
            # (_nodes_classify.py) plus the sentinel intent that routes
            # llm_node to ALL_TOOLS instead of a curated per-intent subset.
            "intent": FORGET_TURN_SENTINEL_INTENT,
            "intent_confidence": 1.0,
            "messages": [HumanMessage(content=TURN3_INSTRUCTION)],
            "plan": [],
            "reflection_count": 0,
            "_reflection_result": None,
            "tool_loop_count": 0,
            "error_count": 0,
            "last_error": "",
            "last_error_info": {},
            "user_confirmed": False,
            "pending_confirmation": {},
            "compaction_count": 0,
            "_force_synthesis_fired": False,
            "retrieved_contexts": [],
        },
        as_node="preprocessing_node",
    )
    record_milestone(milestones, sequence, "turn3_state_injected")
    await collect_updates(graph, None, config, "turn3", events, sequence)

    paused_snapshot = await graph.aget_state(config)
    interrupt_payload = extract_interrupt(paused_snapshot)
    record_milestone(milestones, sequence, "turn3_interrupt")

    preapproval_memory = await store.aget(namespace, mem_key)
    preapproval_snapshot = {
        "observed_at": utc_now(),
        "phase": "before_approval",
        "memory_present": preapproval_memory is not None,
        "memory_value": json_safe(getattr(preapproval_memory, "value", None)),
    }
    record_milestone(milestones, sequence, "preapproval_snapshot")

    approval_sent = interrupt_payload is not None
    interrupt_tool_names = [
        tool.get("name") for tool in interrupt_tools(interrupt_payload)
    ]
    if approval_sent:
        record_milestone(milestones, sequence, "approval:forget_memory")
        await collect_updates(
            graph,
            Command(resume={"confirmed": True}),
            config,
            "turn3-resume",
            events,
            sequence,
        )

    final_snapshot = await graph.aget_state(config)
    final_values = dict(getattr(final_snapshot, "values", {}) or {})
    pending_interrupt = extract_interrupt(final_snapshot)
    tool_executions = list(final_values.get("tool_executions") or [])
    forget_calls = tool_succeeded(tool_executions, "forget_memory")
    if forget_calls:
        record_milestone(milestones, sequence, "forget_memory_success")

    postapproval_memory = await store.aget(namespace, mem_key)
    record_milestone(milestones, sequence, "postapproval_read")

    messages = list(final_values.get("messages") or [])
    final_message = final_assistant_message(messages)
    if final_message:
        record_milestone(milestones, sequence, "final_assistant_message")

    # ---------------------------------------------------------------
    # Near-boundary probe — forget_memory with a query that matches
    # nothing. Called directly (same production handler, not through the
    # LLM) so the trial does not depend on the model choosing to issue a
    # second, deliberately-empty forget call.
    # ---------------------------------------------------------------
    near_boundary_result = await _tool_forget_memory(
        query=NEAR_BOUNDARY_QUERY, user_id=str(USER_ID), page_context=None
    )
    record_milestone(milestones, sequence, "near_boundary_probe")

    # ---------------------------------------------------------------
    # No-bleed probes.
    # ---------------------------------------------------------------
    second_user_namespace = ("user", str(SECOND_USER_ID))
    second_user_hits = await store.asearch(second_user_namespace, query="", limit=50)
    second_user_direct = await store.aget(second_user_namespace, mem_key)
    record_milestone(milestones, sequence, "no_bleed_probe")

    after = await database_state()

    termination_reason = (
        "awaiting_confirmation"
        if pending_interrupt is not None
        else "completed" if not getattr(final_snapshot, "next", ()) else "incomplete"
    )

    evidence = {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": AGENT_REVISION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "instruction": instruction,
        "turn2_instruction": TURN2_INSTRUCTION,
        "turn3_instruction": TURN3_INSTRUCTION,
        "synthetic_actor": {
            "organization_id": str(ORG_ID),
            "user_id": str(USER_ID),
            "workspace_id": str(WORKSPACE_ID),
            "thread_id": THREAD_ID,
            "second_thread_id": SECOND_THREAD_ID,
            "second_user_id": str(SECOND_USER_ID),
        },
        "network_boundary": network_boundary,
        "env_flags": env_flags,
        "store_backend": store_backend,
        "classification": {
            "turn1_intent": turn1_intent,
            "turn1_probe_intent": getattr(turn1_classification_probe, "intent", None),
            "turn1_probe_source": getattr(turn1_classification_probe, "source", None),
            "turn3_forced_intent": FORGET_TURN_SENTINEL_INTENT,
        },
        "memory": {
            "namespace": list(namespace),
            "key": mem_key,
            "value_after_turn1": memory_value_after_turn1,
            "raw_turn1_content": instruction,
            "contact_email": CONTACT_EMAIL,
            "redacted_sentinel": REDACTED_EMAIL_SENTINEL,
        },
        "turn2": {
            "user_memories": turn2_user_memories,
            "final_assistant_message": turn2_final_message,
        },
        "interrupt": {
            "observed": interrupt_payload is not None,
            "payload": interrupt_payload,
            "tools": interrupt_tool_names,
        },
        "approval": {
            "sent": approval_sent,
            "text": APPROVAL_TEXT if approval_sent else None,
            "resume": {"confirmed": True} if approval_sent else None,
        },
        "pending_interrupt_after_resume": pending_interrupt,
        "preapproval_snapshot": preapproval_snapshot,
        "postapproval_memory_present": postapproval_memory is not None,
        "forget_memory_executions": json_safe(forget_calls),
        "near_boundary_probe": {
            "query": NEAR_BOUNDARY_QUERY,
            "result": json_safe(near_boundary_result),
        },
        "no_bleed": {
            "second_user_namespace": list(second_user_namespace),
            "second_user_search_hits": json_safe(second_user_hits),
            "second_user_direct_key_hit": second_user_direct is not None,
        },
        "database": {"after": after},
        "tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "events": events,
        "milestones": milestones,
        "suppress_observation_for": ["forget_memory"],
        "notes": (
            "Production graph, one thread, three turns. Turn 3 reaches "
            "forget_memory via graph.aupdate_state(as_node='preprocessing_node') "
            "to force the ALL_TOOLS fallback intent path; the interrupt_node/"
            "tool_node/HITL machinery afterward is unmodified production code."
        ),
        "semantic": "N/A (deterministic; design doc reconciliation, see task.md)",
        "final_assistant_message": final_message,
        "termination_reason": termination_reason,
        "model_usage": collect_model_usage(messages),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }
    return evidence


async def async_main() -> int:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        evidence = await run_benchmark()
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        TRAJECTORY_PATH.write_text(
            json.dumps(
                build_atif_trajectory(
                    evidence,
                    BENCHMARK_ID,
                    THREAD_ID,
                    extra_steps_hook=hitl_steps,
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
