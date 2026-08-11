#!/usr/bin/env python3
"""Deterministic verifier for ``agent-external-databases-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``). Layer B (semantic)
is N/A for this task — no judge is configured or consumed; the final message
is checked by deterministic containment against the doubled fixtures, not by
an LLM judge.

Pass condition (design doc, external-databases capability): a real classified
turn reaches ``list_external_databases`` (discovering the real 11-connector
registry, with only key-gated connectors reporting unavailable) and
``search_external_database`` against PubMed and FRED explicitly — neither
tool is DESTRUCTIVE, so no HITL interrupt is expected — and the results
genuinely came from the connector double (recorded request events), not a
fabricated string.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import run_verifier_main
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import run_verifier_main

BENCHMARK_ID = "agent-external-databases-v1"
EXPECTED_SOURCE_REVISION = "7d48eca8438ef643e7e3c33b644b68256b2c065b"
EXPECTED_INSTRUCTION = (
    "First call list_external_databases to see which external database "
    "connectors are available. Then call search_external_database with "
    'connector="pubmed" for the topic "telomere shortening senescent '
    'cells", and call search_external_database with connector="fred" for '
    'the economic series "unemployment rate". Report what you found from '
    "each source."
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
TOTAL_CONNECTORS = int(TRUTH["total_connectors"])
AVAILABLE_KEY_GATED = set(TRUTH["available_key_gated_connectors"])
UNAVAILABLE_KEY_GATED = set(TRUTH["unavailable_key_gated_connectors"])
MAX_RESULTS_CAP = int(TRUTH["max_results_impl_cap"])
PUBMED_PMIDS = set(TRUTH["pubmed_pmids"])
FRED_SERIES_IDS = set(TRUTH["fred_series_ids"])

LIST_TOOL = "list_external_databases"
SEARCH_TOOL = "search_external_database"
SUCCESS_STATUSES = {"completed", "success"}
KNOWN_AGENT_INTENTS = {"research", "writing", "knowledge_graph", "general"}
CONNECTOR_INTENTS = {"general"}
RETIRED_SENTINEL_INTENT = SENTINEL_INTENT
EXPECTED_KEYWORD_INTENT = "general"


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


def executions_for(evidence: dict[str, Any], tool: str) -> list[dict[str, Any]]:
    return [
        item
        for item in evidence.get("tool_executions") or []
        if isinstance(item, dict) and item.get("tool_name") == tool
    ]


def successful_results(executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item.get("result")
        for item in executions
        if item.get("status") in SUCCESS_STATUSES
        and isinstance(item.get("result"), dict)
        and not item["result"].get("error")
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
    elif intent not in CONNECTOR_INTENTS:
        failures.append(
            f"observed_intent={intent!r} does not legitimately bind the connector tools "
            "(only general does)"
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

    if not any(
        isinstance(item, dict) and item.get("milestone") == "turn:completed"
        for item in evidence.get("milestones") or []
    ):
        failures.append("milestone 'turn:completed' is missing")


def check_connector_patch(evidence: dict[str, Any], failures: list[str]) -> None:
    patch = evidence.get("connector_patch") or {}
    for key in (
        "pubmed_esearch_patched_to",
        "pubmed_efetch_patched_to",
        "fred_base_url_patched_to",
    ):
        if "mock-services" not in str(patch.get(key) or ""):
            failures.append(f"connector seam not redirected to the mock double: {key}")


def check_no_hitl(evidence: dict[str, Any], failures: list[str]) -> None:
    """Neither tool is DESTRUCTIVE — this turn must never interrupt."""
    if evidence.get("interrupts"):
        failures.append(
            "unexpected HITL interrupt recorded — neither tool in this task is "
            f"destructive: {evidence.get('interrupts')}"
        )
    if evidence.get("termination_reason") != "completed":
        failures.append(
            f"termination_reason={evidence.get('termination_reason')!r}, "
            "expected 'completed' (no interrupt should ever pend here)"
        )


def check_list_external_databases(
    evidence: dict[str, Any], failures: list[str]
) -> None:
    executions = executions_for(evidence, LIST_TOOL)
    if not executions:
        failures.append(f"{LIST_TOOL} was never executed")
        return
    results = successful_results(executions)
    if not results:
        failures.append(f"{LIST_TOOL} did not return a successful result")
        return
    result = results[-1]
    if result.get("total") != TOTAL_CONNECTORS:
        failures.append(
            f"{LIST_TOOL} total={result.get('total')!r}, expected the real "
            f"registered connector count {TOTAL_CONNECTORS}"
        )
    by_name = {
        c.get("name"): c for c in result.get("connectors") or [] if isinstance(c, dict)
    }
    for name in AVAILABLE_KEY_GATED:
        entry = by_name.get(name)
        if entry is None:
            failures.append(f"{LIST_TOOL} result is missing connector {name!r}")
        elif entry.get("available") is not True:
            failures.append(
                f"{LIST_TOOL} reports {name!r} unavailable, but the benchmark "
                "provisions its API key — expected available=true"
            )
    for name in UNAVAILABLE_KEY_GATED:
        entry = by_name.get(name)
        if entry is None:
            failures.append(f"{LIST_TOOL} result is missing connector {name!r}")
            continue
        if entry.get("requires_api_key") is not True:
            failures.append(f"{LIST_TOOL} reports {name!r} requires_api_key != true")
        if entry.get("available") is not False:
            failures.append(
                f"{LIST_TOOL} reports {name!r} available=true, but its API key "
                "is deliberately unset — the fake-success trap for the "
                "unavailable-connector-returned-as-success gate"
            )


def check_search_results(
    evidence: dict[str, Any], connector: str, fixture_ids: set[str], failures: list[str]
) -> dict[str, Any] | None:
    executions = [
        item
        for item in executions_for(evidence, SEARCH_TOOL)
        if isinstance(item.get("result"), dict)
        and (item["result"].get("connectors_searched") or []) == [connector]
    ]
    if not executions:
        failures.append(
            f"{SEARCH_TOOL} was never executed with connectors_searched == [{connector!r}] "
            "(instruction requires an explicit connector= call, not a domain fan-out)"
        )
        return None
    results = successful_results(executions)
    if not results:
        failures.append(
            f"{SEARCH_TOOL}({connector}) did not return a successful result"
        )
        return None
    result = results[-1]
    if result.get("connectors_searched") != [connector]:
        failures.append(
            f"{SEARCH_TOOL}({connector}) connectors_searched="
            f"{result.get('connectors_searched')!r}, expected exactly [{connector!r}]"
        )
    rows = result.get("results") or []
    if not rows:
        failures.append(f"{SEARCH_TOOL}({connector}) returned zero results")
        return result
    if len(rows) > MAX_RESULTS_CAP:
        failures.append(
            f"{SEARCH_TOOL}({connector}) returned {len(rows)} rows, "
            f"impl cap is {MAX_RESULTS_CAP}"
        )
    row_ids = {str(row.get("id")) for row in rows if isinstance(row, dict)}
    if not row_ids <= fixture_ids:
        failures.append(
            f"{SEARCH_TOOL}({connector}) returned ids not in the fixture corpus "
            f"(fabricated-result trap): {row_ids - fixture_ids}"
        )
    return result


def check_mock_events(evidence: dict[str, Any], failures: list[str]) -> None:
    events = evidence.get("mock_events") or []
    unknown = [
        item
        for item in events
        if isinstance(item, dict) and item.get("type") == "unknown_host_or_path"
    ]
    if unknown:
        failures.append(f"mock double received unexpected requests: {unknown}")

    esearches = events_of_type(events, "pubmed_esearch")
    efetches = events_of_type(events, "pubmed_efetch")
    fred_searches = events_of_type(events, "fred_series_search")

    if not esearches:
        failures.append(
            "no PubMed esearch request reached the double — search_external_database "
            "results cannot have genuinely come from the connector (fake-success trap)"
        )
    if not efetches:
        failures.append("no PubMed efetch request reached the double")
    if not fred_searches:
        failures.append(
            "no FRED series/search request reached the double — search_external_database "
            "results cannot have genuinely come from the connector (fake-success trap)"
        )
    else:
        api_keys = {str(item.get("api_key") or "") for item in fred_searches}
        if "benchmark-fred-token" not in api_keys:
            failures.append(
                "no FRED request carried the benchmark's provisioned FRED_API_KEY — "
                f"observed api_key values: {api_keys}"
            )


def check_final_message(
    evidence: dict[str, Any],
    pubmed_result: dict[str, Any] | None,
    fred_result: dict[str, Any] | None,
    failures: list[str],
) -> None:
    message = evidence.get("final_assistant_message") or {}
    content = str(message.get("content") or "").strip()
    if not content:
        failures.append("no user-visible final assistant message")
        return
    if message.get("tool_calls"):
        failures.append("final assistant message still contains pending tool calls")

    # Deterministic containment check (semantic N/A): the final message must
    # ground itself in at least one title or identifier genuinely returned by
    # each double rather than a fabricated citation.
    for label, result in (("pubmed", pubmed_result), ("fred", fred_result)):
        if not result:
            continue
        anchors = [
            str(row.get(key) or "")
            for row in result.get("results") or []
            if isinstance(row, dict)
            for key in ("title", "id")
        ]
        if anchors and not any(anchor and anchor in content for anchor in anchors):
            failures.append(
                f"final assistant message cites no title or id actually returned by "
                f"the {label} double (fabricated-citation trap): anchors={anchors}"
            )


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_real_routing(evidence, failures)
    check_turn_sent(evidence, failures)
    check_connector_patch(evidence, failures)
    check_no_hitl(evidence, failures)
    check_list_external_databases(evidence, failures)
    pubmed_result = check_search_results(evidence, "pubmed", PUBMED_PMIDS, failures)
    fred_result = check_search_results(evidence, "fred", FRED_SERIES_IDS, failures)
    check_mock_events(evidence, failures)
    check_final_message(evidence, pubmed_result, fred_result, failures)
    return failures


objective_failures.live_reader = live_state  # type: ignore[attr-defined]


def main() -> int:
    return run_verifier_main(BENCHMARK_ID, objective_failures)


if __name__ == "__main__":
    sys.exit(main())
