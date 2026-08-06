#!/usr/bin/env python3
"""Fail closed unless every release-gate dependency finished successfully.

GitHub exposes direct dependency results through the ``needs`` context.  This
script accepts that context as JSON and deliberately treats *only* the exact
string ``success`` as releasable.  A missing or malformed result is therefore
blocking in the same way as failure, cancellation, timeout, or a skipped job.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REQUIRED_JOBS: tuple[str, ...] = (
    "lint-backend",
    "lint-frontend",
    "migration-check",
    "openapi-contract",
    "unit-tests",
    "golden-replay",
    "integration-tests",
    "resilience-tests",
    "frontend-tests",
    "security-scan",
    "e2e-tests",
)

JOB_LABELS: dict[str, str] = {
    "lint-backend": "Lint Backend",
    "lint-frontend": "Lint Frontend",
    "migration-check": "Alembic Migration Check",
    "openapi-contract": "OpenAPI Contract Ratchet",
    "unit-tests": "Unit Tests",
    "golden-replay": "Golden Replay",
    "integration-tests": "Integration Tests",
    "resilience-tests": "Resilience Tests",
    "frontend-tests": "Frontend Tests",
    "security-scan": "Security Scan",
    "e2e-tests": "E2E Tests",
}

MISSING_RESULT = "<missing>"
INVALID_RESULT = "<invalid>"


def normalize_results(payload: Mapping[str, Any]) -> dict[str, str]:
    """Return one normalized result for every required job.

    ``toJSON(needs)`` produces ``{job: {result, outputs}}``.  Flat
    ``{job: result}`` maps are also accepted so the decision function remains
    easy to exercise outside GitHub Actions.
    """

    normalized: dict[str, str] = {}
    for job in REQUIRED_JOBS:
        if job not in payload:
            normalized[job] = MISSING_RESULT
            continue

        value = payload[job]
        if isinstance(value, Mapping):
            value = value.get("result")

        normalized[job] = value if isinstance(value, str) else INVALID_RESULT
    return normalized


def blocking_results(results: Mapping[str, str]) -> dict[str, str]:
    """Return every job whose result is not exactly ``success``."""

    return {
        job: results.get(job, MISSING_RESULT)
        for job in REQUIRED_JOBS
        if results.get(job) != "success"
    }


def render_summary(results: Mapping[str, str]) -> str:
    """Render the same fail-closed decision as a GitHub step-summary table."""

    lines = [
        "## Release Gate",
        "",
        "| Required job | Result |",
        "|---|---|",
    ]
    for job in REQUIRED_JOBS:
        result = results.get(job, MISSING_RESULT)
        marker = ":white_check_mark:" if result == "success" else ":x:"
        safe_result = result.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {JOB_LABELS[job]} | {marker} `{safe_result}` |")
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-json",
        default=os.environ.get("REQUIRED_JOB_RESULTS"),
        help=(
            "JSON job-result map. Defaults to REQUIRED_JOB_RESULTS, which the "
            "workflow populates from toJSON(needs)."
        ),
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="Optional file to append the Markdown result table to.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.results_json is None:
        print(
            "Release gate configuration error: no job-result JSON was supplied.",
            file=sys.stderr,
        )
        return 2

    try:
        payload = json.loads(args.results_json)
    except json.JSONDecodeError as exc:
        print(f"Release gate configuration error: invalid JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, Mapping):
        print(
            "Release gate configuration error: job results must be a JSON object.",
            file=sys.stderr,
        )
        return 2

    results = normalize_results(payload)
    summary = render_summary(results)
    print(summary, end="")
    if args.summary_file is not None:
        with args.summary_file.open("a", encoding="utf-8") as handle:
            handle.write(summary)

    blocked = blocking_results(results)
    if blocked:
        detail = ", ".join(f"{job}={result}" for job, result in blocked.items())
        print(f"Release gate blocked: {detail}", file=sys.stderr)
        return 1

    print("Release gate passed: every required job succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
