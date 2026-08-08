#!/usr/bin/env python3
"""Plain-script selftest for evals.harbor_common (not pytest-collected).

Run with: cd /root/rag-verify && python evals/harbor_common/selftest.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.harbor_common.envelope import (  # noqa: E402
    InfrastructureFailure,
    load_inputs,
    run_verifier_main,
)
from evals.harbor_common.serialization import json_safe, utc_now  # noqa: E402


def test_json_safe_nested_with_datetime() -> None:
    naive = datetime(2026, 8, 7, 12, 30, 45)
    aware = datetime(2026, 8, 7, 12, 30, 45, tzinfo=timezone.utc)
    payload = {
        "when": aware,
        "naive": naive,
        "id": UUID("00000000-0000-4000-8000-000000000101"),
        "nested": {"items": [1, "two", None, True, {"deep": aware}]},
        "tuple": (1, 2),
    }
    out = json_safe(payload)
    # Must round-trip through json without a custom encoder.
    json.dumps(out)
    assert out["when"] == "2026-08-07T12:30:45Z", out["when"]
    assert out["naive"] == "2026-08-07T12:30:45Z", out["naive"]
    assert out["id"] == "00000000-0000-4000-8000-000000000101", out["id"]
    assert out["nested"]["items"] == [
        1,
        "two",
        None,
        True,
        {"deep": "2026-08-07T12:30:45Z"},
    ]
    assert out["tuple"] == [1, 2], out["tuple"]
    # Unknown objects degrade to str, never explode.
    assert isinstance(json_safe(object()), str)


def test_utc_now() -> None:
    stamp = utc_now()
    assert stamp.endswith("Z"), stamp
    assert "+00:00" not in stamp, stamp
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def test_load_inputs_fixture_path(tmp: Path) -> None:
    fixture = tmp / "fixture.json"
    fixture.write_text(
        json.dumps({"evidence": {"a": 1}, "state": {"b": 2}}), encoding="utf-8"
    )
    os.environ["BENCHMARK_CALIBRATION_FIXTURE"] = str(fixture)
    try:
        inputs = load_inputs("/nonexistent/evidence.json")
        assert inputs["evidence"] == {"a": 1}, inputs
        assert inputs["state"] == {"b": 2}, inputs
        assert inputs["input_source"] == str(fixture), inputs

        # state defaults to {} when the fixture omits it
        fixture.write_text(json.dumps({"evidence": {"a": 1}}), encoding="utf-8")
        assert load_inputs("/nonexistent/evidence.json")["state"] == {}

        # missing 'evidence' key is an infrastructure failure
        fixture.write_text(json.dumps({"state": {}}), encoding="utf-8")
        raised = False
        try:
            load_inputs("/nonexistent/evidence.json")
        except InfrastructureFailure:
            raised = True
        assert raised, "missing 'evidence' key must raise InfrastructureFailure"
    finally:
        os.environ.pop("BENCHMARK_CALIBRATION_FIXTURE", None)


def test_load_inputs_live_path(tmp: Path) -> None:
    evidence_path = tmp / "evidence.json"
    evidence_path.write_text(json.dumps({"live": True}), encoding="utf-8")
    inputs = load_inputs(str(evidence_path), live_reader=lambda: {"rows": 3})
    assert inputs == {
        "evidence": {"live": True},
        "state": {"rows": 3},
        "input_source": "live",
    }, inputs
    # no live_reader -> empty state
    assert load_inputs(str(evidence_path))["state"] == {}


def test_run_verifier_main(tmp: Path) -> None:
    report_path = tmp / "reports" / "audit.json"
    os.environ["VERIFIER_REPORT_PATH"] = str(report_path)
    fixture = tmp / "verifier-fixture.json"
    fixture.write_text(
        json.dumps({"evidence": {"e": 1}, "state": {"s": 2}}), encoding="utf-8"
    )
    os.environ["BENCHMARK_CALIBRATION_FIXTURE"] = str(fixture)
    try:
        # pass
        code = run_verifier_main("bench-x", lambda evidence, state: [])
        assert code == 0, code
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["passed"] is True, report
        assert report["failures"] == [], report
        assert report["benchmark_id"] == "bench-x", report
        assert report["input_source"] == str(fixture), report

        # scoreable failure
        code = run_verifier_main("bench-x", lambda evidence, state: ["boom"])
        assert code == 10, code
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["passed"] is False and report["failures"] == ["boom"], report

        # report_extra_fn merges into the report and sees both inputs
        code = run_verifier_main(
            "bench-x",
            lambda evidence, state: [],
            report_extra_fn=lambda evidence, state: {"extra": [evidence, state]},
        )
        assert code == 0, code
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["extra"] == [{"e": 1}, {"s": 2}], report

        # raising gate -> infrastructure error
        def exploding_gate(evidence, state):
            raise RuntimeError("gate exploded")

        code = run_verifier_main("bench-x", exploding_gate)
        assert code == 2, code
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert "verifier_error" in report, report
        assert "gate exploded" in report["verifier_error"], report
        assert "passed" not in report, report
    finally:
        os.environ.pop("VERIFIER_REPORT_PATH", None)
        os.environ.pop("BENCHMARK_CALIBRATION_FIXTURE", None)


def main() -> None:
    test_json_safe_nested_with_datetime()
    test_utc_now()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_load_inputs_fixture_path(tmp)
        test_load_inputs_live_path(tmp)
        test_run_verifier_main(tmp)
    print("selftest ok")


if __name__ == "__main__":
    main()
