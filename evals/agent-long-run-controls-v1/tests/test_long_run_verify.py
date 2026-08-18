from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

TESTS_DIR = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "long_run_verify", TESTS_DIR / "verify.py"
)
assert SPEC and SPEC.loader
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def test_chain_rejects_contiguous_prefix_that_stops_before_stage_five() -> None:
    fixture = json.loads((TESTS_DIR / "calibration" / "pass.json").read_text())
    evidence = deepcopy(fixture["evidence"])
    state = deepcopy(fixture["state"])
    evidence["raw_tool_executions"] = [
        execution
        for execution in evidence["raw_tool_executions"]
        if (execution.get("args") or {}).get("query") != "NOUS-LONG-5"
    ]
    evidence["environment_events"] = evidence["environment_events"][:-1]
    state["events"] = state["events"][:-1]
    failures: list[str] = []

    VERIFY.check_chain(evidence, state, failures)

    assert "completed tool query chain was [1, 2, 3, 4], expected stages 1-5" in (
        failures
    )


def test_forced_partial_rejects_conflicting_stage_markers() -> None:
    fixture = json.loads(
        (TESTS_DIR / "calibration" / "pass-forced-partial-stage5.json").read_text()
    )
    evidence = fixture["evidence"]
    for message in evidence["messages"]:
        for call in message.get("tool_calls") or []:
            if call.get("id") == "t6":
                call["args"]["query"] = "NOUS-LONG-5 NOUS-LONG-6"
    failures = VERIFY.objective_failures(evidence, fixture["state"])
    assert (
        "forced synthesis did not handle exactly the next requested KB stage"
        in failures
    )
