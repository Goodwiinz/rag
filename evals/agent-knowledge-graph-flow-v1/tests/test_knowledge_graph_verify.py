from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

TESTS_DIR = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "knowledge_graph_flow_verify", TESTS_DIR / "verify.py"
)
assert SPEC and SPEC.loader
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def _pass_fixture() -> dict:
    return json.loads((TESTS_DIR / "calibration" / "pass.json").read_text())


def _stats_result(evidence: dict) -> dict:
    return next(
        execution["result"]
        for execution in evidence["raw_tool_executions"]
        if execution["tool_name"] == VERIFY.STATS_TOOL
    )


def test_graph_stats_rejects_missing_distribution() -> None:
    fixture = _pass_fixture()
    del _stats_result(fixture["evidence"])["entity_type_distribution"]
    failures: list[str] = []

    VERIFY.check_get_graph_stats(fixture["evidence"], fixture["state"], failures)

    assert any("entity_type_distribution" in failure for failure in failures)


def test_graph_stats_rejects_strict_subset_distribution() -> None:
    fixture = _pass_fixture()
    expected = VERIFY.TRUTH["graph_stats"]["entity_type_distribution"]
    name, count = next(iter(expected.items()))
    _stats_result(fixture["evidence"])["entity_type_distribution"] = {name: count}
    failures: list[str] = []

    VERIFY.check_get_graph_stats(fixture["evidence"], fixture["state"], failures)

    assert any("entity_type_distribution" in failure for failure in failures)


def test_trusted_sources_omit_strict_subset_distribution() -> None:
    fixture = _pass_fixture()
    evidence = copy.deepcopy(fixture["evidence"])
    expected = VERIFY.TRUTH["graph_stats"]["relationship_type_distribution"]
    name, count = next(iter(expected.items()))
    _stats_result(evidence)["relationship_type_distribution"] = {name: count}

    sources = VERIFY.trusted_sources(
        evidence, fixture["state"], deterministic_failures=[]
    )
    stats = next(source for source in sources if source["kind"] == "graph_stats")

    assert "relationship_type_distribution" not in stats
