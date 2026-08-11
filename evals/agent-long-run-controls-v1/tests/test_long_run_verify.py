from __future__ import annotations

import importlib.util
import json
from pathlib import Path

TESTS_DIR = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "long_run_verify", TESTS_DIR / "verify.py"
)
assert SPEC and SPEC.loader
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def test_forced_partial_rejects_conflicting_stage_markers() -> None:
    fixture = json.loads(
        (TESTS_DIR / "calibration" / "pass-forced-partial-stage5.json").read_text()
    )
    evidence = fixture["evidence"]
    for message in evidence["messages"]:
        for call in message.get("tool_calls") or []:
            if call.get("id") == "t5":
                call["args"]["query"] = "NOUS-LONG-5 NOUS-LONG-6"
    failures = VERIFY.objective_failures(evidence, fixture["state"])
    assert (
        "forced synthesis did not handle exactly the next requested KB stage"
        in failures
    )
