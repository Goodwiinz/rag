from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

TESTS_DIR = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "memory_roundtrip_verify", TESTS_DIR / "verify.py"
)
assert SPEC and SPEC.loader
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
PASS_EVIDENCE = json.loads((TESTS_DIR / "calibration" / "pass.json").read_text())[
    "evidence"
]


def failures_with(mutator):
    evidence = copy.deepcopy(PASS_EVIDENCE)
    mutator(evidence)
    return VERIFY.objective_failures(evidence, {})


def test_rejects_wrong_recalled_key() -> None:
    failures = failures_with(
        lambda evidence: evidence["turn2"]["user_memories"][0].__setitem__(
            "key", "wrong-memory-key"
        )
    )
    assert "turn 2 did not recall the exact turn-1 memory row" in failures


def test_rejects_wrong_recalled_value() -> None:
    failures = failures_with(
        lambda evidence: evidence["turn2"]["user_memories"][0]["value"].__setitem__(
            "intent", "mutated-not-the-recorded-intent"
        )
    )
    assert "turn 2 did not recall the exact turn-1 memory row" in failures


def test_rejects_wrong_preapproval_value() -> None:
    failures = failures_with(
        lambda evidence: evidence["preapproval_snapshot"]["memory_value"].__setitem__(
            "intent", "mutated-not-the-recorded-intent"
        )
    )
    assert "pre-approval snapshot does not match the turn-1 memory row" in failures
