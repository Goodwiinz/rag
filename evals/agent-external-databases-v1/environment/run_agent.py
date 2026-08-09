#!/usr/bin/env python3
"""Run the external-databases benchmark against the production LangGraph graph.

``search_external_database`` and ``list_external_databases`` are unreachable
via live intent classification on the pinned image: both have
``intents=frozenset()`` and ``subgraphs=frozenset()`` (``tools.py:1083-1096``)
— dead metadata under subgraph-scoped routing, in the same boat as
``execute_code`` (see "Routing reality" in the plan). This adapter reuses
Task 2's sentinel-intent workaround verbatim: it seeds the checkpoint as if
``preprocessing_node`` had just produced a non-``AgentIntent`` intent via
``aupdate_state(..., as_node="preprocessing_node")``, so ``route_by_intent``
falls through to the general path and ``_get_tools_for_intent`` binds
``ALL_TOOLS`` (``_nodes_llm.py:122-127``). Production tool implementations,
``tool_node``, and connector registry all run unmodified; only the routing
entry point is synthesized.

Neither tool is DESTRUCTIVE (both are CONTEXT_FREE), so — unlike Task 2 —
this turn never interrupts: no HITL approval is exercised or expected.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from evals.harbor_common.db import bootstrap_schema, initial_agent_state, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe, utc_now
from evals.harbor_common.trajectory import (
    build_atif_trajectory,
    collect_model_usage,
    final_assistant_message,
)

BENCHMARK_ID = "agent-external-databases-v1"
SOURCE_REVISION = "c19b1aeafa50507e9aa827eac966b1c6dece446c"
AGENT_REVISION = SOURCE_REVISION

INSTRUCTION_TEXT = (
    "First call list_external_databases to see which external database "
    "connectors are available. Then call search_external_database with "
    'connector="pubmed" for research on "telomere shortening senescent '
    'cells", and call search_external_database with connector="fred" for '
    'the economic series "unemployment rate". Report what you found from '
    "each source."
)
EXPECTED_INSTRUCTION = INSTRUCTION_TEXT

ORG_ID = UUID("00000000-0000-4000-8000-000000001201")
USER_ID = UUID("00000000-0000-4000-8000-000000001202")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000001203")
THREAD_ID = "00000000-0000-4000-8000-000000001204"

SENTINEL_INTENT = "benchmark_all_tools"

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
        email="benchmark-external-db@example.invalid",
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


def patch_connector_clients() -> dict[str, Any]:
    """Redirect PubMed + FRED to the mock double before the graph compiles.

    ``pubmed.py``'s ``_ESEARCH``/``_EFETCH`` are f-string-baked from
    ``_BASE_URL`` at import time, so patching ``_BASE_URL`` alone would do
    nothing — the module attributes read at call time must be patched
    directly (Landmine 8). ``fred.py`` reads ``_BASE_URL`` at call time via
    an f-string inside ``search()``/``fetch_by_id()``, so patching the
    module constant is sufficient there.
    """
    import src.services.connectors.fred as fred
    import src.services.connectors.pubmed as pubmed

    pubmed._ESEARCH = f"{MOCK_HOST}/entrez/eutils/esearch.fcgi"
    pubmed._EFETCH = f"{MOCK_HOST}/entrez/eutils/efetch.fcgi"
    fred._BASE_URL = f"{MOCK_HOST}/fred"
    return {
        "pubmed_esearch_patched_to": pubmed._ESEARCH,
        "pubmed_efetch_patched_to": pubmed._EFETCH,
        "fred_base_url_patched_to": fred._BASE_URL,
    }


def record_milestone(
    milestones: list[dict[str, Any]], sequence: list[int], name: str
) -> None:
    sequence[0] += 1
    milestones.append(
        {"milestone": name, "sequence": sequence[0], "observed_at": utc_now()}
    )


def tool_executions_for(
    tool_executions: list[Any], tool_name: str
) -> list[dict[str, Any]]:
    return [
        item
        for item in tool_executions
        if isinstance(item, dict) and item.get("tool_name") == tool_name
    ]


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

    connector_patch = patch_connector_clients()
    await bootstrap_schema()
    await seed_database()

    from src.services.agent._builders import RECURSION_LIMIT
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store

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

    # Sentinel-intent seed: write the checkpoint as if `preprocessing_node`
    # had just run and classified this turn to a non-AgentIntent string.
    # `route_by_intent` then falls through to `llm_node`, which binds
    # ALL_TOOLS for any intent outside the classifier's Literal type
    # (Routing reality, Consequence 2 — same mechanics as Task 2).
    seed_state = initial_agent_state(
        instruction,
        THREAD_ID,
        user_id=str(USER_ID),
        intent=SENTINEL_INTENT,
    )
    await graph.aupdate_state(config, seed_state, as_node="preprocessing_node")
    record_milestone(milestones, sequence, "sentinel_state_seeded")

    sequence[0] += 1
    async for event in graph.astream(None, config=config, stream_mode="updates"):
        events.append(
            {
                "sequence": sequence[0],
                "phase": "sentinel:initial",
                "observed_at": utc_now(),
                "update": json_safe(event),
            }
        )
        sequence[0] += 1

    final_snapshot = await graph.aget_state(config)
    final_values = dict(getattr(final_snapshot, "values", {}) or {})

    messages = list(final_values.get("messages") or [])
    tool_executions = list(final_values.get("tool_executions") or [])
    list_executions = tool_executions_for(tool_executions, "list_external_databases")
    search_executions = tool_executions_for(tool_executions, "search_external_database")

    final_message = final_assistant_message(messages)
    if final_message:
        record_milestone(milestones, sequence, "final_assistant_message")

    pending_interrupt = bool(getattr(final_snapshot, "next", ()))
    termination_reason = "incomplete" if pending_interrupt else "completed"

    return {
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
            "thread_id": THREAD_ID,
        },
        "env_flags": {"routing_workaround": "sentinel_intent"},
        "sentinel_intent": SENTINEL_INTENT,
        "observed_intent": final_values.get("intent"),
        "connector_patch": connector_patch,
        "network_boundary": network_boundary,
        # Neither tool is DESTRUCTIVE (both CONTEXT_FREE) — this turn never
        # interrupts, so there is no HITL section here (unlike Task 2).
        "interrupts": [],
        "mock_events": mock_events(),
        "list_external_databases_executions": json_safe(list_executions),
        "search_external_database_executions": json_safe(search_executions),
        "tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "events": events,
        "milestones": milestones,
        "suppress_observation_for": [],
        "notes": (
            "Production graph with an isolated database, a PubMed + FRED "
            "connector protocol double, and the sentinel-intent routing "
            "workaround (search_external_database/list_external_databases "
            "are otherwise unreachable via live classification on this "
            "pinned image). Neither tool is destructive, so no HITL "
            "approval is exercised."
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
                build_atif_trajectory(evidence, BENCHMARK_ID, THREAD_ID),
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
