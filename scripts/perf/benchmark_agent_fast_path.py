#!/usr/bin/env python3
"""Bounded authenticated SSE benchmark for the NOUS Luna fast path.

The harness intentionally accepts only local or dev API targets. Supply a
short-lived bearer token through ``NOUS_BENCHMARK_TOKEN`` or ``--token``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
import uuid
from collections import Counter
from typing import Any, NamedTuple
from urllib.parse import urlparse

import httpx

ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "dev-api.gen-text.app"})
DEFAULT_PROMPTS = (
    "Explain why the sky appears blue in two sentences.",
    "Brainstorm five concise names for a research newsletter.",
    "Rewrite this sentence warmly: The proposal needs revision.",
    "What is the difference between precision and recall?",
)


class RunResult(NamedTuple):
    accepted_ms: float | None
    first_token_ms: float | None
    completion_ms: float | None
    route: str
    prompt_chars: int
    failure: str | None


def validate_non_production_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(
            "benchmark target must be an explicitly allowed non-production host"
        )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 2)


def percentile_95(values: list[float]) -> float | None:
    return _percentile(values, 0.95)


def _latency_summary(results: list[RunResult], field: str) -> dict[str, Any]:
    values = [
        float(value)
        for result in results
        if (value := getattr(result, field)) is not None
    ]
    return {
        "count": len(values),
        "p50": _percentile(values, 0.50),
        "p95": percentile_95(values),
        "max": round(max(values), 2) if values else None,
    }


def summarize(results: list[RunResult]) -> dict[str, Any]:
    prompt_sizes = [result.prompt_chars for result in results]
    return {
        "samples": len(results),
        "failures": sum(result.failure is not None for result in results),
        "failure_reasons": dict(
            Counter(result.failure for result in results if result.failure)
        ),
        "routes": dict(Counter(result.route for result in results)),
        "prompt_chars": {
            "min": min(prompt_sizes) if prompt_sizes else None,
            "max": max(prompt_sizes) if prompt_sizes else None,
        },
        "latency_ms": {
            "accepted": _latency_summary(results, "accepted_ms"),
            "first_token": _latency_summary(results, "first_token_ms"),
            "completion": _latency_summary(results, "completion_ms"),
        },
    }


def evaluate_release_gate(
    summary: dict[str, Any],
    *,
    accepted_p95_ms: float,
    first_token_p95_ms: float,
    completion_p95_ms: float,
    minimum_samples: int,
    required_route: str,
) -> dict[str, Any]:
    """Evaluate every P0 release criterion without short-circuiting.

    Returning all checks in one machine-readable object makes CI and humans
    see the complete failure set from a benchmark run instead of fixing one
    hidden threshold per rerun.
    """
    samples = int(summary["samples"])
    failures = int(summary["failures"])
    latency = summary["latency_ms"]
    routes = summary["routes"]

    def latency_check(name: str, phase: str, limit: float) -> dict[str, Any]:
        actual = latency[phase]["p95"]
        return {
            "name": name,
            "actual": actual,
            "limit": limit,
            "passed": actual is not None and float(actual) <= limit,
        }

    checks = [
        {
            "name": "minimum_samples",
            "actual": samples,
            "limit": minimum_samples,
            "passed": samples >= minimum_samples,
        },
        {
            "name": "zero_failures",
            "actual": failures,
            "limit": 0,
            "passed": failures == 0,
        },
        {
            "name": "accepted_event_per_sample",
            "actual": latency["accepted"]["count"],
            "limit": samples,
            "passed": latency["accepted"]["count"] == samples,
        },
        latency_check("accepted_p95_ms", "accepted", accepted_p95_ms),
        {
            "name": "first_token_per_sample",
            "actual": latency["first_token"]["count"],
            "limit": samples,
            "passed": latency["first_token"]["count"] == samples,
        },
        latency_check("first_token_p95_ms", "first_token", first_token_p95_ms),
        latency_check("completion_p95_ms", "completion", completion_p95_ms),
        {
            "name": "required_route",
            "actual": routes,
            "limit": {required_route: samples},
            "passed": routes == {required_route: samples},
        },
    ]
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


async def _run_sample(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    token: str,
    prompt: str,
    timeout_seconds: float,
) -> RunResult:
    started = time.perf_counter()
    accepted_ms: float | None = None
    first_token_ms: float | None = None
    completion_ms: float | None = None
    route = "unknown"
    failure: str | None = None
    event_name = ""
    data_lines: list[str] = []
    payload = {
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "client_message_id": str(uuid.uuid4()),
            }
        ],
        "page_context": {"type": "chat"},
        "use_rag": False,
    }

    def elapsed_ms() -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    try:
        async with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/api/v1/agent/stream",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "text/event-stream",
            },
            json=payload,
            timeout=timeout_seconds,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_name = line.removeprefix("event:").strip()
                    continue
                if line.startswith("data:"):
                    data_lines.append(line.removeprefix("data:").strip())
                    continue
                if line or not event_name:
                    continue

                try:
                    event_data = json.loads("\n".join(data_lines) or "{}")
                except json.JSONDecodeError:
                    event_data = {}
                now_ms = elapsed_ms()
                if event_name == "status":
                    phase = str(event_data.get("phase", ""))
                    detail = str(event_data.get("detail", "")).lower()
                    if phase == "accepted" and accepted_ms is None:
                        accepted_ms = now_ms
                    if phase == "routing":
                        route = (
                            "luna"
                            if "luna" in detail or "direct" in detail
                            else "graph"
                        )
                elif event_name == "token" and first_token_ms is None:
                    first_token_ms = now_ms
                elif event_name == "done":
                    completion_ms = now_ms
                    break
                elif event_name == "error":
                    failure = str(event_data.get("error") or "server_error")
                    completion_ms = now_ms
                    break
                event_name = ""
                data_lines = []
    except Exception as exc:  # noqa: BLE001 - benchmark records all failures
        failure = f"{type(exc).__name__}: {exc}"
        completion_ms = elapsed_ms()

    if completion_ms is None:
        completion_ms = elapsed_ms()
        failure = failure or "stream_ended_without_terminal_event"
    return RunResult(
        accepted_ms=accepted_ms,
        first_token_ms=first_token_ms,
        completion_ms=completion_ms,
        route=route,
        prompt_chars=len(prompt),
        failure=failure,
    )


async def run_benchmark(args: argparse.Namespace) -> list[RunResult]:
    semaphore = asyncio.Semaphore(args.concurrency)
    prompts = tuple(args.prompt or DEFAULT_PROMPTS)

    async with httpx.AsyncClient(http2=True) as client:

        async def one(index: int) -> RunResult:
            async with semaphore:
                return await _run_sample(
                    client,
                    base_url=args.base_url,
                    token=args.token,
                    prompt=prompts[index % len(prompts)],
                    timeout_seconds=args.timeout,
                )

        for index in range(args.warmups):
            await one(index)
        return await asyncio.gather(*(one(index) for index in range(args.samples)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://dev-api.gen-text.app")
    parser.add_argument(
        "--token",
        default=os.environ.get("NOUS_BENCHMARK_TOKEN", ""),
        help="short-lived bearer token; preferably use NOUS_BENCHMARK_TOKEN",
    )
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--target-p95-ms",
        type=float,
        default=None,
        help="compatibility alias: applies to first-token and completion p95",
    )
    parser.add_argument("--target-accepted-p95-ms", type=float, default=250.0)
    parser.add_argument("--target-first-token-p95-ms", type=float, default=5_000.0)
    parser.add_argument("--target-completion-p95-ms", type=float, default=5_000.0)
    parser.add_argument("--minimum-samples", type=int, default=20)
    parser.add_argument("--required-route", default="luna")
    parser.add_argument("--prompt", action="append")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_non_production_url(args.base_url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 64
    if not args.token:
        print("NOUS_BENCHMARK_TOKEN or --token is required", file=sys.stderr)
        return 64
    if not 1 <= args.samples <= 100:
        print("--samples must be between 1 and 100", file=sys.stderr)
        return 64
    if not 1 <= args.concurrency <= 5:
        print("--concurrency must be between 1 and 5", file=sys.stderr)
        return 64

    results = asyncio.run(run_benchmark(args))
    summary = summarize(results)
    first_token_target = (
        args.target_p95_ms
        if args.target_p95_ms is not None
        else args.target_first_token_p95_ms
    )
    completion_target = (
        args.target_p95_ms
        if args.target_p95_ms is not None
        else args.target_completion_p95_ms
    )
    summary["target"] = evaluate_release_gate(
        summary,
        accepted_p95_ms=args.target_accepted_p95_ms,
        first_token_p95_ms=first_token_target,
        completion_p95_ms=completion_target,
        minimum_samples=args.minimum_samples,
        required_route=args.required_route,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["target"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
