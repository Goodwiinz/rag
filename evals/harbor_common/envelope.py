"""Shared adapter/verifier envelopes for Harbor eval tasks.

Consumed only by tasks added after 2026-08-07; the three original tasks
are digest-pinned and keep their inline copies.
"""

import json
import os
import sys
import traceback


class InfrastructureFailure(RuntimeError):
    """Environment/harness defect — exit 70 (adapter) / 2 (verifier), no reward."""


def load_inputs(default_evidence_path, live_reader=None):
    """Return {'evidence': ..., 'state': ...}.

    BENCHMARK_CALIBRATION_FIXTURE set -> load that JSON instead of live state.
    Fixture envelope is unified: {"evidence": {...}, "state": {...}}.
    live_reader() supplies the independent state read for live runs.
    """
    fixture = os.environ.get("BENCHMARK_CALIBRATION_FIXTURE")
    if fixture:
        with open(fixture, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if "evidence" not in data:
            raise InfrastructureFailure(
                "calibration fixture missing 'evidence' key (unified envelope required)"
            )
        return {
            "evidence": data["evidence"],
            "state": data.get("state", {}),
            "input_source": fixture,
        }
    with open(default_evidence_path, "r", encoding="utf-8") as fh:
        evidence = json.load(fh)
    state = live_reader() if live_reader else {}
    return {"evidence": evidence, "state": state, "input_source": "live"}


def run_verifier_main(benchmark_id, gate_fn, report_extra_fn=None):
    """0 = pass, 10 = scoreable failure, 2 = verifier infrastructure error."""
    report_path = os.environ.get("VERIFIER_REPORT_PATH", "/logs/verifier/audit.json")
    try:
        inputs = load_inputs(
            os.environ.get("EVIDENCE_PATH", "/logs/agent/evidence.json"),
            live_reader=(
                gate_fn.live_reader if hasattr(gate_fn, "live_reader") else None
            ),
        )
        failures = gate_fn(inputs["evidence"], inputs["state"])
        report = {
            "benchmark_id": benchmark_id,
            "input_source": inputs["input_source"],
            "passed": not failures,
            "failures": failures,
        }
        if report_extra_fn:
            report.update(report_extra_fn(inputs["evidence"], inputs["state"]))
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
        print(json.dumps(report, sort_keys=True))
        return 0 if not failures else 10
    except Exception:  # noqa: BLE001 - anything unexpected is infra, not reward 0
        err = {"benchmark_id": benchmark_id, "verifier_error": traceback.format_exc()}
        print(json.dumps(err), file=sys.stderr)
        try:
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as fh:
                json.dump(err, fh, indent=2)
        except OSError:
            pass
        return 2
