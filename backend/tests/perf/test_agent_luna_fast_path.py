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
