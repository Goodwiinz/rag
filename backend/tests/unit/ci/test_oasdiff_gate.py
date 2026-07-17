"""Workflow-contract test for the advisory oasdiff breaking-change gate.

The raw both-artifact diff in ``openapi-contract`` is stricter on *freshness*
but blind to *compatibility*: a breaking change that regenerates both committed
artifacts sails through it. Task 2.1 adds an advisory ``oasdiff breaking`` step
that compares the PR base's committed spec against this branch's. This test
pins the shape of that step so it cannot silently regress (drop the PR guard,
lose ``continue-on-error``, stop materializing the base spec, etc.).

Like ``test_generate_openapi.py`` this only parses the workflow YAML — no CI
runner, no network — so it is fast and infra-free.
"""

from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "test-pipeline.yml"


def _load_job() -> dict[str, Any]:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return cast("dict[str, Any]", workflow["jobs"]["openapi-contract"])


def _advisory_step() -> dict[str, Any] | None:
    for step in _load_job()["steps"]:
        if "Advisory" in str(step.get("name", "")):
            return cast("dict[str, Any]", step)
    return None


def test_openapi_contract_checkout_has_full_history() -> None:
    """oasdiff resolves the PR base's spec via ``git show <base-sha>:…``, which
    needs the base commit present — so the checkout must fetch full history."""
    checkout_steps = [
        s
        for s in _load_job()["steps"]
        if str(s.get("uses", "")).startswith("actions/checkout")
    ]
    assert checkout_steps, "openapi-contract must check out the repo"
    assert any(
        str(s.get("with", {}).get("fetch-depth", "")) == "0" for s in checkout_steps
    ), "checkout must set fetch-depth: 0 so the PR base spec is reachable via git show"


def test_advisory_oasdiff_step_is_non_blocking() -> None:
    """The compatibility gate is advisory at this stage (Task 2.2 makes
    ERR-level changes blocking); it must never fail the job."""
    step = _advisory_step()
    assert step is not None, "openapi-contract must have an 'Advisory' oasdiff step"
    assert (
        step.get("continue-on-error") is True
    ), "advisory oasdiff step must set continue-on-error: true"


def test_advisory_oasdiff_step_runs_only_on_pull_requests() -> None:
    """On push-to-develop the PR base sha is meaningless, so the step is guarded
    to pull_request events only."""
    step = _advisory_step()
    assert step is not None
    assert (
        step.get("if") == "github.event_name == 'pull_request'"
    ), "advisory oasdiff step must be guarded to pull_request events"


def test_advisory_step_materializes_base_spec_and_runs_oasdiff_breaking() -> None:
    """The step must (a) materialize the PR base's committed spec via git show
    against the base sha (passed by env indirection, not interpolated into the
    run block), and (b) run ``oasdiff breaking`` base-vs-working-tree."""
    step = _advisory_step()
    assert step is not None
    run = step.get("run") or ""

    # (a) base spec materialized from the PR base commit
    assert "git show" in run, "must materialize the base spec with git show"
    assert (
        ":backend/openapi.json" in run
    ), "git show must reference <sha>:backend/openapi.json"

    # base sha reaches the run block through env indirection (repo security
    # convention: never interpolate github.event.* directly into run:)
    env_values = " ".join(str(v) for v in (step.get("env") or {}).values())
    assert (
        "github.event.pull_request.base.sha" in env_values
    ), "base sha must be passed via env indirection, not interpolated in run:"
    assert (
        "${{ github.event" not in run
    ), "run block must not interpolate github.event.* directly"

    # (b) semantic compatibility check
    assert "oasdiff breaking" in run, "must run `oasdiff breaking`"
    assert (
        "backend/openapi.json" in run
    ), "oasdiff must diff against the working-tree backend/openapi.json"


def test_advisory_step_pins_oasdiff_release_and_verifies_checksum() -> None:
    """The binary must come from a pinned release tarball with a verified
    sha256 — not `go install` at CI time and not curl|sh."""
    step = _advisory_step()
    assert step is not None
    run = step.get("run") or ""
    env = step.get("env") or {}

    assert "go install" not in run, "do not `go install` oasdiff at CI time"
    assert "sha256sum" in run, "must verify the downloaded tarball's checksum"
    assert any(
        "OASDIFF_VERSION" in k for k in env
    ), "pin the oasdiff version in an env var"
    assert any(
        "OASDIFF_SHA256" in k for k in env
    ), "pin the tarball sha256 in an env var"
