"""Unit contracts for the bounded Luna SSE benchmark harness."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts/perf/benchmark_agent_fast_path.py"
)


def _load_benchmark_module():
    spec = importlib.util.spec_from_file_location("benchmark_agent_fast_path", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_benchmark_refuses_production_and_unknown_hosts():
    benchmark = _load_benchmark_module()

    benchmark.validate_non_production_url("https://dev-api.gen-text.app")
    benchmark.validate_non_production_url("http://127.0.0.1:8000")
    with pytest.raises(ValueError, match="non-production"):
        benchmark.validate_non_production_url("https://api.gen-text.app")
    with pytest.raises(ValueError, match="non-production"):
        benchmark.validate_non_production_url("https://example.com")


def test_p95_uses_nearest_rank():
    benchmark = _load_benchmark_module()

    assert benchmark.percentile_95([]) is None
    assert benchmark.percentile_95([1.0]) == 1.0
    assert benchmark.percentile_95([float(value) for value in range(1, 21)]) == 19.0


def test_summarize_reports_latency_route_prompt_and_failures():
    benchmark = _load_benchmark_module()
    results = [
        benchmark.RunResult(
            accepted_ms=10.0,
            first_token_ms=900.0,
            completion_ms=1200.0,
            route="luna",
            prompt_chars=12,
            failure=None,
        ),
        benchmark.RunResult(
            accepted_ms=20.0,
            first_token_ms=None,
            completion_ms=1500.0,
            route="unknown",
            prompt_chars=20,
            failure="timeout",
        ),
    ]

    summary = benchmark.summarize(results)

    assert summary["samples"] == 2
    assert summary["failures"] == 1
    assert summary["routes"] == {"luna": 1, "unknown": 1}
    assert summary["prompt_chars"] == {"min": 12, "max": 20}
    assert summary["latency_ms"]["accepted"]["p95"] == 20.0
    assert summary["latency_ms"]["first_token"]["count"] == 1


def test_release_gate_requires_all_latency_route_sample_and_failure_contracts():
    benchmark = _load_benchmark_module()
    results = [
        benchmark.RunResult(
            accepted_ms=100.0,
            first_token_ms=2_000.0,
            completion_ms=4_000.0,
            route="luna",
            prompt_chars=20,
            failure=None,
        )
        for _ in range(20)
    ]

    gate = benchmark.evaluate_release_gate(
        benchmark.summarize(results),
        accepted_p95_ms=250.0,
        first_token_p95_ms=5_000.0,
        completion_p95_ms=5_000.0,
        minimum_samples=20,
        required_route="luna",
    )

    assert gate["passed"] is True
    assert all(check["passed"] for check in gate["checks"])


def test_release_gate_reports_every_failed_criterion():
    benchmark = _load_benchmark_module()
    summary = benchmark.summarize(
        [
            benchmark.RunResult(
                accepted_ms=None,
                first_token_ms=None,
                completion_ms=6_000.0,
                route="graph",
                prompt_chars=20,
                failure="timeout",
            )
        ]
    )

    gate = benchmark.evaluate_release_gate(
        summary,
        accepted_p95_ms=250.0,
        first_token_p95_ms=5_000.0,
        completion_p95_ms=5_000.0,
        minimum_samples=20,
        required_route="luna",
    )

    assert gate["passed"] is False
    failed_names = {
        check["name"] for check in gate["checks"] if check["passed"] is False
    }
    assert failed_names == {
        "minimum_samples",
        "zero_failures",
        "accepted_event_per_sample",
        "accepted_p95_ms",
        "first_token_per_sample",
        "first_token_p95_ms",
        "completion_p95_ms",
        "required_route",
    }
