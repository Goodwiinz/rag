from __future__ import annotations

import importlib.util
import json
from pathlib import Path

TESTS_DIR = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "fast_path_cancel_verify", TESTS_DIR / "verify.py"
)
assert SPEC and SPEC.loader
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def test_persisted_partial_must_end_on_emitted_token_boundary() -> None:
    fixture = json.loads((TESTS_DIR / "calibration" / "pass.json").read_text())
    evidence = fixture["evidence"]
    evidence["persisted_partial"]["content"] = "The"
    failures: list[str] = []

    VERIFY.check_prefix_retained(evidence, failures)

    assert "persisted partial ends inside an emitted server token" in failures
