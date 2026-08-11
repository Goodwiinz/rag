#!/usr/bin/env python3
"""Deterministic + semantic verifier for ``agent-knowledge-graph-flow-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``).

Layer A (deterministic, this file's ``check_*`` functions) gates identity,
the network boundary triple plus a private-network probe proving Neo4j is
reachable only inside the benchmark network, the ``knowledge_graph`` intent
classification, each DATA-subgraph tool's arguments against the impl caps
(``search_knowledge_graph`` limit ``min(arg,50)``; ``explore_entity_neighborhood``
``max_depth`` ``min(arg,3)`` / limit ``min(arg,50)``; ``find_entity_paths``
``max_depth`` ``min(arg,5)``), tool execution order, the DATA loop ceiling
(8, ``data_agent.py::MAX_DATA_TOOL_LOOPS``), that no destructive tool ran and
no HITL interrupt fired (none of the five KG tools carry the destructive
policy tag), **tenant scoping** (landmine 3 -- no entity seeded under the
second organization ever appears in a tool result), and **``get_graph_stats``
totals against an independent cypher count** (landmine 2) run directly by
this verifier against the same Neo4j container, bypassing
``knowledge_graph_service`` entirely so the cross-check is genuinely
independent of the code under test. Layer B (``harbor_common.judge``) is
folded in only after every Layer A check has run.

``extract_entities`` is LLM-driven (unstructured-text NER) and is out of
scope for this task -- see the deferral note in
``evals/specs/agent-knowledge-graph-flow-v1/task.md``; it is judged/diffed by
no check here, deliberately.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import run_verifier_main
    from evals.harbor_common.judge import run_semantic_judge
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import run_verifier_main
    from evals.harbor_common.judge import run_semantic_judge

BENCHMARK_ID = "agent-knowledge-graph-flow-v1"
EXPECTED_SOURCE_REVISION = "bb8fc2863613f98e58907de59f08d8a64b875f1c"
EXPECTED_INSTRUCTION = (
    'Search our knowledge graph for the entity "Elena Vasquez", explore her '
    "neighborhood of connected entities and relationships, and pull the "
    "current knowledge graph statistics. Then tell me who she is connected "
    "to and summarize what the graph shows."
)

ORG_ID = "00000000-0000-4000-8000-000000000801"
FOCUS_ENTITY_NAME = "Elena Vasquez"

SEARCH_TOOL = "search_knowledge_graph"
NEIGHBORHOOD_TOOLS = ("explore_entity_neighborhood", "find_entity_paths")
STATS_TOOL = "get_graph_stats"
SUCCESS_STATUSES = {"completed", "success"}
SEARCH_LIMIT_CAP = 50
NEIGHBORHOOD_DEPTH_CAP = 3
NEIGHBORHOOD_LIMIT_CAP = 50
FIND_PATHS_DEPTH_CAP = 5
MAX_DATA_TOOL_LOOPS = 8

# Mirror of the production destructive-tool registry (see
# agent-writing-flow-v1/tests/verify.py) -- none of the five KG tools carry
# the destructive policy tag, so none of these may run at all in this task.
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

JUDGE_RUBRIC = (
    "The candidate answer describes a knowledge-graph entity (Elena Vasquez) "
    "and her connections. Every named entity and every relationship the "
    "answer asserts must be consistent with the seeded graph contents "
    "(trusted_sources) -- real entity names, types, and relationships "
    "actually present in the graph. The answer may not invent an entity or a "
    "relationship that is not in trusted_sources."
)


def _load_truth() -> dict[str, Any]:
    path = Path("/tests/truth.json")
    if not path.exists():
        path = Path(__file__).resolve().parent / "truth.json"
    return json.loads(path.read_text())


TRUTH = _load_truth()
OTHER_ORG_ENTITY_NAMES = {row["name"] for row in TRUTH.get("other_org_entities", [])}
TRUTH_RELATIONSHIPS = {
    (row["source"], row["type"], row["target"])
    for row in TRUTH.get("relationships", [])
}
TRUTH_ENTITY_TYPES = {row["name"]: row["type"] for row in TRUTH.get("entities", [])}
JUDGE_AUDIT_KEY = "_verifier_semantic_judge_verdict"


# --------------------------------------------------------------------------
# live state (in-container only; the neo4j driver may be absent on the
# calibration host, so it is imported lazily inside this function)
# --------------------------------------------------------------------------
def live_graph_state() -> dict[str, Any]:
    """Independent cypher count -- deliberately bypasses
    ``knowledge_graph_service`` so the cross-check (landmine 2) does not
    reuse the very code path it is meant to validate."""
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "")
    user = os.environ.get("NEO4J_USER", "")
    password = os.environ.get("NEO4J_PASSWORD", "")
    if not uri:
        raise RuntimeError("NEO4J_URI is missing")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            entities = session.run(
                "MATCH (e:Entity) WHERE e.organization_id = $org "
                "RETURN e.id AS id, e.name AS name, e.type AS type",
                org=ORG_ID,
            ).data()
            relationships = session.run(
                "MATCH (source:Entity)-[r:RELATED_TO]->(target:Entity) "
                "WHERE source.organization_id = $org "
                "RETURN source.id AS source_id, coalesce(r.type, type(r)) AS type, "
                "target.id AS target_id",
                org=ORG_ID,
            ).data()
            entity_count = session.run(
                "MATCH (e:Entity) WHERE e.organization_id = $org RETURN count(e) AS c",
                org=ORG_ID,
            ).single()["c"]
            relationship_count = session.run(
                "MATCH (source:Entity)-[r:RELATED_TO]->() "
                "WHERE source.organization_id = $org RETURN count(r) AS c",
                org=ORG_ID,
            ).single()["c"]
    finally:
        driver.close()
    return {
        "total_entities": entity_count,
        "total_relationships": relationship_count,
        "entities_by_id": {
            str(row["id"]): {"name": row["name"], "type": row["type"]}
            for row in entities
        },
        "relationships": [
            {
                "source_id": str(row["source_id"]),
                "type": row["type"],
                "target_id": str(row["target_id"]),
            }
            for row in relationships
        ],
    }


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def executions_for(evidence: dict[str, Any], tool: str) -> list[dict[str, Any]]:
    return [
        item
        for item in evidence.get("raw_tool_executions") or []
        if isinstance(item, dict) and item.get("tool_name") == tool
    ]


def executed_tools(evidence: dict[str, Any]) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    for item in evidence.get("raw_tool_executions") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool_name") or "").strip()
        if name:
            seen.append((name, str(item.get("status") or "")))
    return seen


def first_success_index(evidence: dict[str, Any], tool: str) -> int | None:
    for index, item in enumerate(evidence.get("raw_tool_executions") or []):
        if not isinstance(item, dict) or item.get("tool_name") != tool:
            continue
        if item.get("status") not in SUCCESS_STATUSES:
            continue
        result = item.get("result")
        if not isinstance(result, dict) or result.get("error"):
            continue
        return index
    return None


def first_success_index_any(
    evidence: dict[str, Any], tools: tuple[str, ...]
) -> int | None:
    indices = [
        index
        for tool in tools
        if (index := first_success_index(evidence, tool)) is not None
    ]
    return min(indices) if indices else None


def successful_graph_executions(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    relevant = {SEARCH_TOOL, *NEIGHBORHOOD_TOOLS}
    return [
        execution
        for execution in evidence.get("raw_tool_executions") or []
        if isinstance(execution, dict)
        and execution.get("tool_name") in relevant
        and execution.get("status") in SUCCESS_STATUSES
    ]


def result_entities(result: Any) -> list[dict[str, Any]]:
    """Collect entity rows across all three KG result shapes."""
    rows: list[dict[str, Any]] = []
    if not isinstance(result, dict):
        return rows
    for key in ("entities", "connected_entities"):
        for row in result.get(key) or []:
            if isinstance(row, dict):
                rows.append(row)
    for path in result.get("paths") or []:
        if not isinstance(path, dict):
            continue
        for row in path.get("entities") or []:
            if isinstance(row, dict):
                rows.append(row)
    return rows


def validated_graph_rows(
    execution: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[Any]] | None:
    """Return rows only when a successful graph tool has valid collections."""
    if execution.get("status") not in SUCCESS_STATUSES:
        return None
    result = execution.get("result")
    if not isinstance(result, dict) or result.get("error"):
        return None
    tool_name = execution.get("tool_name")
    if tool_name == SEARCH_TOOL:
        entities = result.get("entities")
        if not isinstance(entities, list):
            return None
        return [row for row in entities if isinstance(row, dict)], []
    if tool_name == "explore_entity_neighborhood":
        entities = result.get("connected_entities")
        relationships = result.get("relationships")
        if not isinstance(entities, list) or not isinstance(relationships, list):
            return None
        return [row for row in entities if isinstance(row, dict)], relationships
    if tool_name == "find_entity_paths":
        paths = result.get("paths")
        if not isinstance(paths, list):
            return None
        entities: list[dict[str, Any]] = []
        relationships: list[Any] = []
        for path in paths:
            if (
                not isinstance(path, dict)
                or not isinstance(path.get("entities"), list)
                or not isinstance(path.get("relationships"), list)
            ):
                return None
            entities.extend(row for row in path["entities"] if isinstance(row, dict))
            relationships.extend(path["relationships"])
        return entities, relationships
    return None


def result_entity_names(result: Any) -> set[str]:
    return {str(row["name"]) for row in result_entities(result) if row.get("name")}


def entity_names_by_id(evidence: dict[str, Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    for execution in successful_graph_executions(evidence):
        rows = validated_graph_rows(execution)
        if rows is None:
            continue
        for row in rows[0]:
            if row.get("id") and row.get("name"):
                names[str(row["id"])] = str(row["name"])
    return names


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


def check_network_boundary(evidence: dict[str, Any], failures: list[str]) -> None:
    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
        "neo4j_reachable_via_internal",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")


def check_classification(evidence: dict[str, Any], failures: list[str]) -> None:
    intent = (evidence.get("classification") or {}).get("intent")
    if intent != "knowledge_graph":
        failures.append(
            f"turn classified as intent={intent!r}, expected 'knowledge_graph'"
        )


def check_search_knowledge_graph(evidence: dict[str, Any], failures: list[str]) -> None:
    index = first_success_index(evidence, SEARCH_TOOL)
    if index is None:
        failures.append(f"no successful {SEARCH_TOOL} execution was observed")
        return
    execution = (evidence.get("raw_tool_executions") or [])[index]
    for current in successful_graph_executions(evidence):
        if current.get("tool_name") != SEARCH_TOOL:
            continue
        if not isinstance(current.get("result"), dict):
            failures.append(f"{SEARCH_TOOL} result must be a JSON object")
        elif validated_graph_rows(current) is None:
            failures.append(f"{SEARCH_TOOL} entities must be present as a list")
    args = execution.get("args") or {}
    limit = args.get("limit")
    if limit is not None and (
        not isinstance(limit, int) or not (1 <= limit <= SEARCH_LIMIT_CAP)
    ):
        failures.append(
            f"{SEARCH_TOOL} args limit={limit!r} outside the impl cap "
            f"[1, {SEARCH_LIMIT_CAP}]"
        )
    result = execution.get("result") or {}
    rows = validated_graph_rows(execution)
    if rows is None:
        return
    names = {str(row["name"]) for row in rows[0] if row.get("name")}
    if FOCUS_ENTITY_NAME not in names:
        failures.append(
            f"{SEARCH_TOOL} did not surface the seeded entity {FOCUS_ENTITY_NAME!r} "
            f"(found {sorted(names)!r})"
        )


def check_neighborhood_tool(evidence: dict[str, Any], failures: list[str]) -> None:
    index = first_success_index_any(evidence, NEIGHBORHOOD_TOOLS)
    if index is None:
        failures.append(
            "no successful explore_entity_neighborhood or find_entity_paths "
            "execution was observed"
        )
        return
    execution = (evidence.get("raw_tool_executions") or [])[index]
    tool_name = execution.get("tool_name")
    args = execution.get("args") or {}
    if tool_name == "explore_entity_neighborhood":
        max_depth = args.get("max_depth")
        if max_depth is not None and (
            not isinstance(max_depth, int)
            or not (1 <= max_depth <= NEIGHBORHOOD_DEPTH_CAP)
        ):
            failures.append(
                f"explore_entity_neighborhood args max_depth={max_depth!r} outside "
                f"the impl cap [1, {NEIGHBORHOOD_DEPTH_CAP}]"
            )
        limit = args.get("limit")
        if limit is not None and (
            not isinstance(limit, int) or not (1 <= limit <= NEIGHBORHOOD_LIMIT_CAP)
        ):
            failures.append(
                f"explore_entity_neighborhood args limit={limit!r} outside the "
                f"impl cap [1, {NEIGHBORHOOD_LIMIT_CAP}]"
            )
    else:
        max_depth = args.get("max_depth")
        if max_depth is not None and (
            not isinstance(max_depth, int)
            or not (1 <= max_depth <= FIND_PATHS_DEPTH_CAP)
        ):
            failures.append(
                f"find_entity_paths args max_depth={max_depth!r} outside the impl "
                f"cap [1, {FIND_PATHS_DEPTH_CAP}]"
            )

    for current in successful_graph_executions(evidence):
        current_tool = current.get("tool_name")
        if current_tool not in NEIGHBORHOOD_TOOLS:
            continue
        result = current.get("result")
        if not isinstance(result, dict):
            failures.append(f"{current_tool} result must be a JSON object")
            continue
        if current_tool == "explore_entity_neighborhood":
            for count_key, rows_key in (
                ("total_entities", "connected_entities"),
                ("total_relationships", "relationships"),
            ):
                rows = result.get(rows_key)
                if not isinstance(rows, list):
                    failures.append(
                        f"explore_entity_neighborhood {rows_key} must be present as a list"
                    )
                    continue
                if count_key in result and result[count_key] != len(rows):
                    failures.append(
                        f"explore_entity_neighborhood {count_key}="
                        f"{result[count_key]!r} does not match {rows_key} length "
                        f"{len(rows)}"
                    )
        elif validated_graph_rows(current) is None:
            failures.append(
                "find_entity_paths paths and nested entity/relationship "
                "collections must be present as lists"
            )


def check_relationship_direction(evidence: dict[str, Any], failures: list[str]) -> None:
    names = entity_names_by_id(evidence)
    for execution in successful_graph_executions(evidence):
        tool_name = str(execution.get("tool_name"))
        if tool_name not in NEIGHBORHOOD_TOOLS:
            continue
        rows = validated_graph_rows(execution)
        if rows is None:
            continue  # collection failures are reported by check_neighborhood_tool
        for row in rows[1]:
            if not isinstance(row, dict):
                failures.append(f"{tool_name} emitted a malformed relationship")
                continue
            source_id = row.get("source")
            target_id = row.get("target")
            source = names.get(str(source_id))
            target = names.get(str(target_id))
            if not source or not target:
                unresolved = []
                if not source:
                    unresolved.append(f"source id {source_id!r}")
                if not target:
                    unresolved.append(f"target id {target_id!r}")
                failures.append(
                    f"{tool_name} relationship has unresolvable endpoint(s): "
                    f"{', '.join(unresolved)}"
                )
                continue
            relationship_type = str(row.get("type") or "")
            if not relationship_type:
                failures.append(f"{tool_name} relationship is missing its type")
                continue
            triple = (source, relationship_type, target)
            if triple in TRUTH_RELATIONSHIPS:
                continue
            reverse = (target, relationship_type, source)
            if reverse in TRUTH_RELATIONSHIPS:
                failures.append(
                    f"{tool_name} reversed seeded relationship direction: "
                    f"{source} --{relationship_type}--> {target}"
                )
            else:
                failures.append(
                    f"{tool_name} emitted relationship absent from seeded truth: "
                    f"{source} --{relationship_type}--> {target}"
                )


def check_get_graph_stats(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    index = first_success_index(evidence, STATS_TOOL)
    if index is None:
        failures.append(f"no successful {STATS_TOOL} execution was observed")
        return
    execution = (evidence.get("raw_tool_executions") or [])[index]
    result = execution.get("result") or {}
    expected_entities = state.get("total_entities")
    expected_relationships = state.get("total_relationships")
    if expected_entities is None or expected_relationships is None:
        failures.append("independent cypher count is unavailable to cross-check")
        return
    if result.get("total_entities") != expected_entities:
        failures.append(
            f"{STATS_TOOL} total_entities={result.get('total_entities')!r} does "
            f"not match the independent cypher count {expected_entities!r}"
        )
    if result.get("total_relationships") != expected_relationships:
        failures.append(
            f"{STATS_TOOL} total_relationships={result.get('total_relationships')!r} "
            f"does not match the independent cypher count {expected_relationships!r}"
        )
    truth_stats = TRUTH["graph_stats"]
    for key in ("entity_type_distribution", "relationship_type_distribution"):
        observed = result.get(key)
        if observed is None:
            continue
        expected = truth_stats[key]
        if not isinstance(observed, dict) or any(
            expected.get(name) != count for name, count in observed.items()
        ):
            failures.append(f"{STATS_TOOL} {key} is inconsistent with seeded truth")
    if (
        "average_degree" in result
        and result["average_degree"] != truth_stats["average_degree"]
    ):
        failures.append(
            f"{STATS_TOOL} average_degree is inconsistent with seeded truth"
        )


def check_tool_execution_order(evidence: dict[str, Any], failures: list[str]) -> None:
    search_index = first_success_index(evidence, SEARCH_TOOL)
    neighborhood_index = first_success_index_any(evidence, NEIGHBORHOOD_TOOLS)
    stats_index = first_success_index(evidence, STATS_TOOL)
    if None in (search_index, neighborhood_index, stats_index):
        return  # reported by the per-tool checks
    if not (search_index < neighborhood_index < stats_index):
        failures.append(
            f"tool execution order is not {SEARCH_TOOL} ({search_index}) < "
            f"neighborhood tool ({neighborhood_index}) < {STATS_TOOL} ({stats_index})"
        )


def check_tenant_scope(evidence: dict[str, Any], failures: list[str]) -> None:
    for tool_name in (SEARCH_TOOL, *NEIGHBORHOOD_TOOLS):
        for execution in executions_for(evidence, tool_name):
            leaked = (
                result_entity_names(execution.get("result")) & OTHER_ORG_ENTITY_NAMES
            )
            if leaked:
                failures.append(
                    f"{tool_name} result leaked cross-tenant entity/entities "
                    f"{sorted(leaked)!r} from the second organization "
                    f"({TRUTH.get('other_organization_id')})"
                )


def check_data_loop_ceiling(evidence: dict[str, Any], failures: list[str]) -> None:
    loop_count = evidence.get("tool_loop_count")
    if isinstance(loop_count, int) and loop_count > MAX_DATA_TOOL_LOOPS:
        failures.append(
            f"tool_loop_count={loop_count} exceeds the DATA subgraph ceiling "
            f"{MAX_DATA_TOOL_LOOPS}"
        )


def check_no_destructive_tools(evidence: dict[str, Any], failures: list[str]) -> None:
    for name, _status in executed_tools(evidence):
        if name in DESTRUCTIVE_REGISTRY:
            failures.append(
                f"destructive tool {name!r} executed although this task "
                "sanctions only the read-only knowledge-graph tools"
            )


def check_no_pending_interrupt(evidence: dict[str, Any], failures: list[str]) -> None:
    if evidence.get("pending_interrupt") is not None:
        failures.append(
            "graph paused on an unexpected HITL interrupt; no tool in scope "
            "for this task is destructive"
        )


def check_final_message(evidence: dict[str, Any], failures: list[str]) -> None:
    message = evidence.get("final_assistant_message") or {}
    content = str(message.get("content") or "").strip()
    if not content:
        failures.append("no user-visible final assistant message")
    if message.get("tool_calls"):
        failures.append("final assistant message still contains pending tool calls")
    if evidence.get("termination_reason") != "completed":
        failures.append(
            f"termination_reason={evidence.get('termination_reason')!r}, "
            "expected 'completed'"
        )


def _assert_later_search_endpoint_calibration() -> None:
    evidence = {
        "raw_tool_executions": [
            {
                "tool_name": SEARCH_TOOL,
                "status": "completed",
                "result": {
                    "entities": [
                        {"id": "elena", "name": "Elena Vasquez", "type": "PERSON"}
                    ]
                },
            },
            {
                "tool_name": "explore_entity_neighborhood",
                "status": "completed",
                "result": {
                    "scope": "entity_neighborhood",
                    "requested_max_depth": 2,
                    "result_limit": 30,
                    "connected_entities": [
                        {
                            "id": "nova",
                            "name": "Nova Research Institute",
                            "type": "ORGANIZATION",
                        }
                    ],
                    "relationships": [
                        {
                            "source": "marcus",
                            "target": "nova",
                            "type": "WORKS_FOR",
                        }
                    ],
                    "total_entities": 1,
                    "total_relationships": 1,
                    "returned_counts_scope": "entity_neighborhood",
                },
            },
            {
                "tool_name": SEARCH_TOOL,
                "status": "completed",
                "result": {
                    "entities": [
                        {"id": "marcus", "name": "Marcus Chen", "type": "PERSON"}
                    ]
                },
            },
        ]
    }
    failures: list[str] = []
    check_relationship_direction(evidence, failures)
    assert not failures, failures
    calibration_state = {
        "entities_by_id": {
            "marcus": {"name": "Marcus Chen", "type": "PERSON"},
            "nova": {"name": "Nova Research Institute", "type": "ORGANIZATION"},
        },
        "relationships": [
            {"source_id": "marcus", "type": "WORKS_FOR", "target_id": "nova"}
        ],
    }
    sources = trusted_sources(evidence, calibration_state, deterministic_failures=[])
    assert {
        "kind": "entity",
        "name": "Elena Vasquez",
        "type": "PERSON",
    } in sources
    assert {
        "kind": "relationship",
        "source": "Marcus Chen",
        "source_id": "marcus",
        "type": "WORKS_FOR",
        "target": "Nova Research Institute",
        "target_id": "nova",
    } in sources
    mismatched_state = {
        **calibration_state,
        "entities_by_id": {
            **calibration_state["entities_by_id"],
            "marcus": {"name": "Elena Vasquez", "type": "PERSON"},
        },
    }
    mismatched_sources = trusted_sources(
        evidence, mismatched_state, deterministic_failures=[]
    )
    assert not any(
        item.get("kind") == "relationship" and item.get("source_id") == "marcus"
        for item in mismatched_sources
    )
    assert {
        "kind": "neighborhood_stats",
        "scope": "entity_neighborhood",
        "requested_max_depth": 2,
        "result_limit": 30,
        "connected_entity_count": 1,
        "relationship_count": 1,
        "counts_describe_validated_returned_rows": True,
        "bounded_query_note": (
            "requested depth and result limit do not prove exact hop distance "
            "or completeness"
        ),
    } in sources


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    _assert_later_search_endpoint_calibration()
    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_classification(evidence, failures)
    check_search_knowledge_graph(evidence, failures)
    check_neighborhood_tool(evidence, failures)
    check_relationship_direction(evidence, failures)
    check_get_graph_stats(evidence, state, failures)
    check_tool_execution_order(evidence, failures)
    check_tenant_scope(evidence, failures)
    check_data_loop_ceiling(evidence, failures)
    check_no_destructive_tools(evidence, failures)
    check_no_pending_interrupt(evidence, failures)
    check_final_message(evidence, failures)
    return failures


# Consumed by ``load_inputs`` for live (non-calibration) runs only.
objective_failures.live_reader = live_graph_state  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# Layer B: semantic judge, folded in after every Layer A gate has run.
# --------------------------------------------------------------------------
class _StubJudgeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _StubJudgeClient:
    """Calibration-only stand-in for the Azure client. Same ``_client_factory``
    seam as ``agent-kb-retrieval-v1``; live runs never carry
    ``_judge_stub_verdict`` in the evidence."""

    def __init__(self, verdict: dict[str, Any]) -> None:
        self._verdict = verdict

    def invoke(self, _messages: Any) -> _StubJudgeResponse:
        return _StubJudgeResponse(json.dumps(self._verdict))


def trusted_sources(
    evidence: dict[str, Any],
    state: dict[str, Any] | None = None,
    deterministic_failures: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Expose only current-trial facts that also agree with seeded truth."""
    if deterministic_failures is None and state is not None:
        deterministic_failures = objective_failures(evidence, state)
    if deterministic_failures:
        return [{"kind": "trial_evidence", "note": "no approved KG facts observed"}]
    sources: list[dict[str, Any]] = []
    seen_entities: set[tuple[str, str]] = set()
    names = entity_names_by_id(evidence)
    live_entities = (state or {}).get("entities_by_id") or {}
    live_relationships = {
        (str(row.get("source_id")), str(row.get("type")), str(row.get("target_id")))
        for row in (state or {}).get("relationships") or []
        if isinstance(row, dict)
    }
    entity_confidence = TRUTH["seed_confidence"]["entity"]

    for execution in successful_graph_executions(evidence):
        rows = validated_graph_rows(execution)
        if rows is None:
            continue
        for row in rows[0]:
            name = str(row.get("name") or "")
            entity_type = str(row.get("type") or "")
            key = (name, entity_type)
            if TRUTH_ENTITY_TYPES.get(name) != entity_type or key in seen_entities:
                continue
            seen_entities.add(key)
            fact: dict[str, Any] = {
                "kind": "entity",
                "name": name,
                "type": entity_type,
            }
            row_id = str(row.get("id") or "")
            if live_entities.get(row_id) == {"name": name, "type": entity_type}:
                fact["id"] = row_id
            if row.get("confidence") == entity_confidence:
                fact["confidence"] = row["confidence"]
            sources.append(fact)

    seen_relationships: set[tuple[str, str, str]] = set()
    for execution in successful_graph_executions(evidence):
        if execution.get("tool_name") not in NEIGHBORHOOD_TOOLS:
            continue
        rows = validated_graph_rows(execution)
        if rows is None:
            continue
        for row in rows[1]:
            if not isinstance(row, dict):
                continue
            triple = (
                names.get(str(row.get("source")), ""),
                str(row.get("type") or ""),
                names.get(str(row.get("target")), ""),
            )
            if triple in TRUTH_RELATIONSHIPS and triple not in seen_relationships:
                seen_relationships.add(triple)
                fact = {
                    "kind": "relationship",
                    "source": triple[0],
                    "type": triple[1],
                    "target": triple[2],
                }
                id_triple = (
                    str(row.get("source")),
                    triple[1],
                    str(row.get("target")),
                )
                source_identity = {
                    "name": triple[0],
                    "type": TRUTH_ENTITY_TYPES.get(triple[0]),
                }
                target_identity = {
                    "name": triple[2],
                    "type": TRUTH_ENTITY_TYPES.get(triple[2]),
                }
                if (
                    id_triple in live_relationships
                    and live_entities.get(id_triple[0]) == source_identity
                    and live_entities.get(id_triple[2]) == target_identity
                ):
                    fact["source_id"] = id_triple[0]
                    fact["target_id"] = id_triple[2]
                sources.append(fact)
        if execution.get("tool_name") == "explore_entity_neighborhood":
            result = execution.get("result") or {}
            fact = {"kind": "neighborhood_stats"}
            if result.get("scope") == "entity_neighborhood":
                fact["scope"] = result["scope"]
            for key in ("requested_max_depth", "result_limit"):
                if isinstance(result.get(key), int):
                    fact[key] = result[key]
            for count_key, rows_key, fact_key in (
                ("total_entities", "connected_entities", "connected_entity_count"),
                ("total_relationships", "relationships", "relationship_count"),
            ):
                if count_key in result and result[count_key] == len(result[rows_key]):
                    fact[fact_key] = result[count_key]
            if (
                result.get("returned_counts_scope") == "entity_neighborhood"
                and "connected_entity_count" in fact
                and "relationship_count" in fact
            ):
                fact["counts_describe_validated_returned_rows"] = True
                fact["bounded_query_note"] = (
                    "requested depth and result limit do not prove exact hop "
                    "distance or completeness"
                )
            if len(fact) > 1:
                sources.append(fact)

    stats_index = first_success_index(evidence, STATS_TOOL)
    if stats_index is not None:
        execution = (evidence.get("raw_tool_executions") or [])[stats_index]
        result = execution.get("result") or {}
        fact = {"kind": "graph_stats"}
        if state is not None:
            for key in ("total_entities", "total_relationships"):
                if result.get(key) == state.get(key):
                    fact[key] = result[key]
        truth_stats = TRUTH["graph_stats"]
        for key in ("entity_type_distribution", "relationship_type_distribution"):
            observed = result.get(key)
            if isinstance(observed, dict) and all(
                truth_stats[key].get(name) == count for name, count in observed.items()
            ):
                fact[key] = observed
        if result.get("average_degree") == truth_stats["average_degree"]:
            fact["average_degree"] = result["average_degree"]
        if len(fact) > 1:
            sources.append(fact)

    return sources or [
        {"kind": "trial_evidence", "note": "no approved KG facts observed"}
    ]


def run_judge(
    evidence: dict[str, Any],
    state: dict[str, Any] | None = None,
    deterministic_failures: list[str] | None = None,
) -> dict[str, Any]:
    answer = str((evidence.get("final_assistant_message") or {}).get("content") or "")
    # The stub is honored ONLY in calibration mode; a live evidence file cannot
    # self-certify Layer B by carrying a _judge_stub_verdict.
    stub_verdict = (
        evidence.get("_judge_stub_verdict")
        if os.environ.get("BENCHMARK_CALIBRATION_FIXTURE")
        else None
    )
    client_factory = (
        (lambda: _StubJudgeClient(stub_verdict)) if stub_verdict is not None else None
    )
    return run_semantic_judge(
        question=EXPECTED_INSTRUCTION,
        trusted_sources=trusted_sources(evidence, state, deterministic_failures),
        candidate_answer=answer,
        rubric=JUDGE_RUBRIC,
        _client_factory=client_factory,
    )


def gate_with_judge(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    """Layer A first; Layer B judge verdict is appended only after Layer A runs."""
    failures = objective_failures(evidence, state)
    judge = run_judge(evidence, state, failures)
    evidence[JUDGE_AUDIT_KEY] = judge
    if judge.get("supported") is not True:
        failures.append("semantic judge marked the entity answer unsupported")
    if judge.get("contradictions"):
        failures.append("semantic judge found contradictions")
    if judge.get("unsupported_material_claims"):
        failures.append("semantic judge found unsupported material claims")
    return failures


gate_with_judge.live_reader = live_graph_state  # type: ignore[attr-defined]


def graph_snapshot(evidence: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {
        "independent_graph_count": state,
        "semantic_judge_verdict": evidence.get(JUDGE_AUDIT_KEY),
    }


def main() -> int:
    return run_verifier_main(
        BENCHMARK_ID, gate_with_judge, report_extra_fn=graph_snapshot
    )


if __name__ == "__main__":
    sys.exit(main())
