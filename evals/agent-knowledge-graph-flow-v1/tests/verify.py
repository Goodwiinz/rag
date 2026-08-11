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
EXPECTED_SOURCE_REVISION = "838075c12fe0829ea9635c87fd855c6a21d44081"
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
    return {"total_entities": entity_count, "total_relationships": relationship_count}


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
        if isinstance(result, dict) and result.get("error"):
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


def result_entity_names(result: Any) -> set[str]:
    """Collect every entity name a KG tool result could surface, across all
    three result shapes (``entities``, ``connected_entities``, and the
    ``entities`` nested inside each ``find_entity_paths`` path)."""
    names: set[str] = set()
    if not isinstance(result, dict):
        return names
    for key in ("entities", "connected_entities"):
        for row in result.get(key) or []:
            if isinstance(row, dict) and row.get("name"):
                names.add(str(row["name"]))
    for path in result.get("paths") or []:
        if not isinstance(path, dict):
            continue
        for row in path.get("entities") or []:
            if isinstance(row, dict) and row.get("name"):
                names.add(str(row["name"]))
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
    names = result_entity_names(result)
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


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_classification(evidence, failures)
    check_search_knowledge_graph(evidence, failures)
    check_neighborhood_tool(evidence, failures)
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


def trusted_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = [
        {"kind": "entity", **row} for row in TRUTH.get("entities", [])
    ]
    sources.extend(
        {"kind": "relationship", **row} for row in TRUTH.get("relationships", [])
    )
    sources.append({"kind": "graph_stats", **TRUTH["graph_stats"]})
    return sources


def run_judge(evidence: dict[str, Any]) -> dict[str, Any]:
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
        trusted_sources=trusted_sources(),
        candidate_answer=answer,
        rubric=JUDGE_RUBRIC,
        _client_factory=client_factory,
    )


def gate_with_judge(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    """Layer A first; Layer B judge verdict is appended only after Layer A runs."""
    failures = objective_failures(evidence, state)
    judge = run_judge(evidence)
    if judge.get("supported") is not True:
        failures.append("semantic judge marked the entity answer unsupported")
    if judge.get("contradictions"):
        failures.append("semantic judge found contradictions")
    if judge.get("unsupported_material_claims"):
        failures.append("semantic judge found unsupported material claims")
    return failures


gate_with_judge.live_reader = live_graph_state  # type: ignore[attr-defined]


def graph_snapshot(evidence: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"independent_graph_count": state}


def main() -> int:
    return run_verifier_main(
        BENCHMARK_ID, gate_with_judge, report_extra_fn=graph_snapshot
    )


if __name__ == "__main__":
    sys.exit(main())
