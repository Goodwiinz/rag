#!/usr/bin/env python3
"""Run the knowledge-graph-flow benchmark against the production LangGraph graph.

The instruction asks for a single ``knowledge_graph``-intent turn covering
three DATA-subgraph tools in order: ``search_knowledge_graph`` (fulltext
lookup) -> ``explore_entity_neighborhood`` (1-hop traversal) ->
``get_graph_stats`` (tenant-scoped analytics), then a synthesized entity
answer. ``extract_entities`` is LLM-driven (non-deterministic parsing of
unstructured text) and is deliberately out of scope for this task -- see the
module docstring note in ``tests/verify.py``.

Landmine 1 (neo4j singleton trap): the DATA-subgraph tools import
``knowledge_graph_service`` -- the module-level ``KnowledgeGraphService()``
instance -- from ``src.services.knowledge_graph.knowledge_graph_service``.
This adapter seeds the SAME singleton (never a fresh ``KnowledgeGraphService()``)
so the class-level shared driver (``KnowledgeGraphService._driver_instance``)
the tools read from is guaranteed to already hold the seeded rows. A
``verify_seed_queryable`` self-check runs ``search_entities`` -- the exact
call ``_tool_search_knowledge_graph`` makes -- right after seeding and before
the graph runs, turning a dead-client false-negative into an
``InfrastructureFailure`` (exit 70) instead of a silent reward-0 run.
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

from evals.harbor_common.db import bootstrap_schema, initial_agent_state, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe, utc_now
from evals.harbor_common.trajectory import (
    build_atif_trajectory,
    collect_model_usage,
    final_assistant_message,
)

BENCHMARK_ID = "agent-knowledge-graph-flow-v1"
SOURCE_REVISION = "187973c4208f0895b43be3f8fa9766cf35c034a4"
AGENT_REVISION = "187973c4208f0895b43be3f8fa9766cf35c034a4"
EXPECTED_INSTRUCTION = (
    'Search our knowledge graph for the entity "Elena Vasquez", explore her '
    "neighborhood of connected entities and relationships, and pull the "
    "current knowledge graph statistics. Then tell me who she is connected "
    "to and summarize what the graph shows."
)
FOCUS_ENTITY_NAME = "Elena Vasquez"
SUCCESS_MILESTONE_TOOLS = (
    "search_knowledge_graph",
    "explore_entity_neighborhood",
    "get_graph_stats",
)

ORG_ID = UUID("00000000-0000-4000-8000-000000000801")
USER_ID = UUID("00000000-0000-4000-8000-000000000802")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000803")
OTHER_ORG_ID = UUID("00000000-0000-4000-8000-000000000810")
THREAD_ID = "00000000-0000-4000-8000-000000000809"

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"

# ---------------------------------------------------------------------------
# Deterministic ~20-entity graph seeded under ORG_ID, plus a disjoint 3-entity
# graph under OTHER_ORG_ID for the tenant-scoping negative probe (landmine 3).
# Kept in sync by hand with tests/truth.json -- both describe the same fixed
# fixture graph, one consumed by the adapter, the other by the verifier/judge.
# ---------------------------------------------------------------------------
GRAPH_ENTITIES: list[tuple[str, str]] = [
    ("Elena Vasquez", "PERSON"),
    ("Marcus Chen", "PERSON"),
    ("Aisha Rahman", "PERSON"),
    ("Liam O'Connor", "PERSON"),
    ("Priya Nair", "PERSON"),
    ("Tomas Berg", "PERSON"),
    ("Nova Research Institute", "ORGANIZATION"),
    ("Helion Labs", "ORGANIZATION"),
    ("Quantum Error Correction", "CONCEPT"),
    ("Topological Qubits", "CONCEPT"),
    ("Reinforcement Learning", "CONCEPT"),
    ("Protein Folding", "CONCEPT"),
    ("Surface Code Simulator", "TECHNOLOGY"),
    ("AlphaFold Pipeline", "TECHNOLOGY"),
    ("OpenQASM", "TECHNOLOGY"),
    ("QubitForge SDK", "PRODUCT"),
    ("Helion Cloud Platform", "PRODUCT"),
    ("Fault-Tolerant Quantum Computing Survey", "RESEARCH"),
    ("Quantum Computing Summit 2026", "EVENT"),
    ("Boston", "LOCATION"),
]

GRAPH_RELATIONSHIPS: list[tuple[str, str, str]] = [
    ("Elena Vasquez", "WORKS_FOR", "Nova Research Institute"),
    ("Marcus Chen", "WORKS_FOR", "Nova Research Institute"),
    ("Priya Nair", "WORKS_FOR", "Nova Research Institute"),
    ("Aisha Rahman", "WORKS_FOR", "Helion Labs"),
    ("Liam O'Connor", "WORKS_FOR", "Helion Labs"),
    ("Tomas Berg", "WORKS_FOR", "Helion Labs"),
    ("Elena Vasquez", "COLLABORATES_WITH", "Aisha Rahman"),
    ("Elena Vasquez", "RELATED_TO", "Quantum Error Correction"),
    ("Marcus Chen", "RELATED_TO", "Topological Qubits"),
    ("Aisha Rahman", "RELATED_TO", "Protein Folding"),
    ("Liam O'Connor", "RELATED_TO", "Reinforcement Learning"),
    ("Priya Nair", "RELATED_TO", "OpenQASM"),
    ("Nova Research Institute", "OWNS", "QubitForge SDK"),
    ("Helion Labs", "OWNS", "Helion Cloud Platform"),
    ("Surface Code Simulator", "PART_OF", "QubitForge SDK"),
    ("AlphaFold Pipeline", "PART_OF", "Helion Cloud Platform"),
    ("Quantum Error Correction", "RELATED_TO", "Topological Qubits"),
    ("Fault-Tolerant Quantum Computing Survey", "CITED", "Quantum Error Correction"),
    ("Elena Vasquez", "SPOKE_AT", "Quantum Computing Summit 2026"),
    ("Quantum Computing Summit 2026", "LOCATED_IN", "Boston"),
]

OTHER_ORG_ENTITIES: list[tuple[str, str]] = [
    ("Nadia Kessler", "PERSON"),
    ("Reyfield Analytics", "ORGANIZATION"),
    ("Predictive Churn Modeling", "CONCEPT"),
]

OTHER_ORG_RELATIONSHIPS: list[tuple[str, str, str]] = [
    ("Nadia Kessler", "WORKS_FOR", "Reyfield Analytics"),
    ("Nadia Kessler", "RELATED_TO", "Predictive Churn Modeling"),
]


def _seed_graph_sync() -> dict[str, str]:
    """Create entities + relationships through the module-level singleton.

    Runs on a worker thread (the driver is sync). Returns a name -> resolved
    entity-id map for both tenants so the caller can self-check queryability
    (landmine 1) without a second round-trip through search.
    """
    from src.models.graph import (
        CreateEntityRequest,
        CreateRelationshipRequest,
        EntityType,
        ExtractionMethod,
        RelationshipType,
    )
    from src.services.knowledge_graph.knowledge_graph_service import (
        knowledge_graph_service,
    )

    ids: dict[str, str] = {}

    def _seed_org(
        org_id: str,
        entities: list[tuple[str, str]],
        relationships: list[tuple[str, str, str]],
    ) -> None:
        for name, entity_type in entities:
            response = knowledge_graph_service.create_entity(
                CreateEntityRequest(
                    name=name,
                    entity_type=EntityType(entity_type),
                    confidence_score=0.95,
                    extraction_method=ExtractionMethod.LLM_EXTRACTION,
                    organization_id=org_id,
                )
            )
            ids[name] = response.id
        for source_name, rel_type, target_name in relationships:
            knowledge_graph_service.create_relationship(
                CreateRelationshipRequest(
                    source_entity_id=ids[source_name],
                    target_entity_id=ids[target_name],
                    relationship_type=RelationshipType(rel_type),
                    strength=1.0,
                    confidence_score=0.9,
                    organization_id=org_id,
                )
            )

    _seed_org(str(ORG_ID), GRAPH_ENTITIES, GRAPH_RELATIONSHIPS)
    _seed_org(str(OTHER_ORG_ID), OTHER_ORG_ENTITIES, OTHER_ORG_RELATIONSHIPS)
    return ids


def _verify_seed_queryable_sync(focus_entity_id: str) -> bool:
    """Landmine-1 self-check: the exact call ``_tool_search_knowledge_graph``
    makes, against the SAME singleton the adapter just seeded."""
    from src.services.knowledge_graph.knowledge_graph_service import (
        knowledge_graph_service,
    )

    found = knowledge_graph_service.search_entities(
        query=FOCUS_ENTITY_NAME,
        limit=10,
        organization_id=str(ORG_ID),
    )
    return any(entity.id == focus_entity_id for entity in found)


def _independent_graph_count_sync() -> dict[str, int]:
    """Direct cypher count mirroring ``get_graph_analytics``'s own predicate
    (entity: ``e.organization_id = $org``; relationship: RELATED_TO edges
    whose SOURCE endpoint carries ``$org`` -- the target is unfiltered,
    matching the production query exactly) -- landmine 2's cross-check."""
    from src.services.knowledge_graph.knowledge_graph_service import (
        knowledge_graph_service,
    )

    with knowledge_graph_service.get_session() as session:
        entity_count = session.run(
            "MATCH (e:Entity) WHERE e.organization_id = $org RETURN count(e) AS c",
            org=str(ORG_ID),
        ).single()["c"]
        relationship_count = session.run(
            "MATCH (source:Entity)-[r:RELATED_TO]->() "
            "WHERE source.organization_id = $org RETURN count(r) AS c",
            org=str(ORG_ID),
        ).single()["c"]
    return {"total_entities": entity_count, "total_relationships": relationship_count}


async def seed_knowledge_graph() -> dict[str, str]:
    try:
        ids = await asyncio.to_thread(_seed_graph_sync)
    except Exception as exc:
        raise InfrastructureFailure(
            f"neo4j seed failed: {type(exc).__name__}: {exc}"
        ) from exc
    focus_id = ids.get(FOCUS_ENTITY_NAME)
    if not focus_id:
        raise InfrastructureFailure("seed did not produce the focus entity id")
    try:
        queryable = await asyncio.to_thread(_verify_seed_queryable_sync, focus_id)
    except Exception as exc:
        raise InfrastructureFailure(
            f"landmine-1 seed-queryable self-check failed: {type(exc).__name__}: {exc}"
        ) from exc
    if not queryable:
        raise InfrastructureFailure(
            "seeded entities are not visible through knowledge_graph_service."
            "search_entities -- the adapter and the tools are hitting different "
            "Neo4j drivers/singletons (landmine 1)"
        )
    return ids


async def independent_graph_count() -> dict[str, int]:
    try:
        return await asyncio.to_thread(_independent_graph_count_sync)
    except Exception as exc:
        raise InfrastructureFailure(
            f"independent cypher count failed: {type(exc).__name__}: {exc}"
        ) from exc


async def neo4j_reachable_via_internal() -> bool:
    """Private-network probe: main can open a bolt session to ``neo4j`` even
    though it has no public egress path (bolt is not HTTP/proxied; reachability
    alone proves the internal-only network attachment, matching the mock's
    ``trust_env=False`` probe pattern in the sibling KB-retrieval task)."""

    def _check() -> bool:
        from src.services.knowledge_graph.knowledge_graph_service import (
            knowledge_graph_service,
        )

        with knowledge_graph_service.get_session() as session:
            record = session.run("RETURN 1 AS ok").single()
            return bool(record and record["ok"] == 1)

    try:
        return await asyncio.to_thread(_check)
    except Exception as exc:
        raise InfrastructureFailure(
            f"neo4j preflight failed: {type(exc).__name__}: {exc}"
        ) from exc


def record_milestone(
    milestones: list[dict[str, Any]], sequence: list[int], name: str
) -> None:
    sequence[0] += 1
    milestones.append(
        {"milestone": name, "sequence": sequence[0], "observed_at": utc_now()}
    )


def tool_succeeded(tool_executions: list[Any], tool_name: str) -> bool:
    for item in tool_executions:
        if not isinstance(item, dict) or item.get("tool_name") != tool_name:
            continue
        if item.get("status") not in {"completed", "success"}:
            continue
        result = item.get("result")
        if isinstance(result, dict) and result.get("error"):
            continue
        return True
    return False


def summarize_tool_executions(tool_executions: list[Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in tool_executions:
        if not isinstance(item, dict):
            continue
        result = item.get("result")
        summary.append(
            {
                "tool": item.get("tool_name"),
                "status": item.get("status"),
                "result_keys": (
                    sorted(result.keys()) if isinstance(result, dict) else []
                ),
            }
        )
    return summary


async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure(
            f"instruction contract drift: expected {EXPECTED_INSTRUCTION!r}"
        )

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", ""),
        extra_probes={"neo4j_reachable_via_internal": neo4j_reachable_via_internal},
    )
    await bootstrap_schema()
    await seed_tenant(
        org_id=ORG_ID,
        user_id=USER_ID,
        workspace_id=WORKSPACE_ID,
        name_prefix="Benchmark Knowledge Graph",
        email="benchmark-knowledge-graph@example.invalid",
    )
    entity_ids = await seed_knowledge_graph()
    seed_counts_before = await independent_graph_count()
    if seed_counts_before["total_entities"] != len(GRAPH_ENTITIES):
        raise InfrastructureFailure(
            "seed failed: expected "
            f"{len(GRAPH_ENTITIES)} ORG_ID entities, got "
            f"{seed_counts_before['total_entities']}"
        )
    if seed_counts_before["total_relationships"] != len(GRAPH_RELATIONSHIPS):
        raise InfrastructureFailure(
            "seed failed: expected "
            f"{len(GRAPH_RELATIONSHIPS)} ORG_ID relationships, got "
            f"{seed_counts_before['total_relationships']}"
        )

    from src.services.agent._builders import RECURSION_LIMIT
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.classifier import classify_intent_with_fallback
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store

    classification_probe = await classify_intent_with_fallback(instruction, {})
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

    graph_input = initial_agent_state(instruction, THREAD_ID, user_id=str(USER_ID))
    async for event in graph.astream(graph_input, config=config, stream_mode="updates"):
        sequence[0] += 1
        events.append(
            {
                "sequence": sequence[0],
                "observed_at": utc_now(),
                "update": json_safe(event),
            }
        )

    final_snapshot = await graph.aget_state(config)
    final_values = dict(getattr(final_snapshot, "values", {}) or {})
    pending_interrupt = None
    for task in getattr(final_snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            payload = getattr(item, "value", None)
            if isinstance(payload, dict):
                pending_interrupt = json_safe(payload)

    messages = list(final_values.get("messages") or [])
    tool_executions = list(final_values.get("tool_executions") or [])
    for tool_name in SUCCESS_MILESTONE_TOOLS:
        if tool_succeeded(tool_executions, tool_name):
            record_milestone(milestones, sequence, f"{tool_name}_success")

    seed_counts_after = await independent_graph_count()
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
        "synthetic_actor": {
            "organization_id": str(ORG_ID),
            "user_id": str(USER_ID),
            "workspace_id": str(WORKSPACE_ID),
            "other_organization_id": str(OTHER_ORG_ID),
            "thread_id": THREAD_ID,
            "focus_entity_name": FOCUS_ENTITY_NAME,
            "focus_entity_id": entity_ids.get(FOCUS_ENTITY_NAME),
        },
        "network_boundary": network_boundary,
        "classification": {
            "intent": final_values.get("intent"),
            "confidence": final_values.get("intent_confidence"),
            "source_probe": getattr(classification_probe, "source", None),
            "probe_reasoning": getattr(classification_probe, "reasoning", None),
        },
        "plan": json_safe(final_values.get("plan") or []),
        "pending_interrupt": pending_interrupt,
        "independent_graph_count": {
            "before_run": seed_counts_before,
            "after_run": seed_counts_after,
        },
        "tool_loop_count": final_values.get("tool_loop_count"),
        "tool_executions": summarize_tool_executions(tool_executions),
        "raw_tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "events": events,
        "milestones": milestones,
        "notes": (
            "Production graph with an isolated database and a real neo4j:5 "
            "container seeded via the same knowledge_graph_service singleton "
            "the DATA-subgraph tools import; no destructive tool is in scope, "
            "so no HITL interrupt is expected."
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
            from src.services.knowledge_graph.knowledge_graph_service import (
                KnowledgeGraphService,
            )

            KnowledgeGraphService.close_driver()
        except Exception:
            pass
        try:
            from src.services.agent._pool_utils import close_shared_langgraph_pool

            await close_shared_langgraph_pool()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
