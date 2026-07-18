"""Workflow-contract test for the oasdiff API-compatibility gate.

The raw both-artifact diff in ``openapi-contract`` is stricter on *freshness*
but blind to *compatibility*: a breaking change that regenerates both committed
artifacts sails through it. This gate closes that hole in three steps within the
same job:

1. a **setup** step (pull_request-only) that installs a pinned, checksum-verified
   oasdiff and materializes the PR base's committed spec via ``git show``;
2. a **blocking** step that runs ``oasdiff breaking --fail-on ERR`` and fails the
   job on ERR-level breaking changes — with a labeled escape hatch
   (``api-breaking-approved``) for reviewed, intentional breaks;
3. an **informational** step that runs ``oasdiff changelog`` into the job summary
   (``continue-on-error``) so every PR shows what changed.

These tests pin the shape of those steps so they cannot silently regress (drop
the PR guard, lose ``--fail-on ERR``, stop verifying the checksum, sneak
``continue-on-error`` onto the blocking step, etc.).

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


def _step_named(substr: str) -> dict[str, Any] | None:
    for step in _load_job()["steps"]:
        if substr in str(step.get("name", "")):
            return cast("dict[str, Any]", step)
    return None


def _setup_step() -> dict[str, Any] | None:
    return _step_named("Set up oasdiff")


def _blocking_step() -> dict[str, Any] | None:
    return _step_named("breaking-change gate")


def _changelog_step() -> dict[str, Any] | None:
    return _step_named("changelog")


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


# ---------------------------------------------------------------------------
# Setup step: install pinned oasdiff + materialize the PR base spec.
# ---------------------------------------------------------------------------


def test_setup_step_runs_only_on_pull_requests() -> None:
    """On push-to-develop the PR base sha is meaningless, so the setup step is
    guarded to pull_request events only."""
    step = _setup_step()
    assert step is not None, "openapi-contract must have a 'Set up oasdiff' step"
    assert "pull_request" in str(
        step.get("if") or ""
    ), "setup step must be guarded to pull_request events"


def test_setup_step_materializes_base_spec_via_git_show_with_env_indirection() -> None:
    """The setup step must materialize the PR base's committed spec via git show
    against the base sha, passed by env indirection (never interpolated into the
    run block — repo security convention)."""
    step = _setup_step()
    assert step is not None
    run = step.get("run") or ""

    assert "git show" in run, "must materialize the base spec with git show"
    assert (
        ":backend/openapi.json" in run
    ), "git show must reference <sha>:backend/openapi.json"

    env_values = " ".join(str(v) for v in (step.get("env") or {}).values())
    assert (
        "github.event.pull_request.base.sha" in env_values
    ), "base sha must be passed via env indirection, not interpolated in run:"
    assert (
        "${{ github.event" not in run
    ), "run block must not interpolate github.event.* directly"


def test_setup_step_pins_oasdiff_release_and_verifies_checksum() -> None:
    """The binary must come from a pinned release tarball with a *verified*
    sha256 — not `go install` at CI time and not curl|sh."""
    step = _setup_step()
    assert step is not None
    run = step.get("run") or ""
    env = step.get("env") or {}

    assert "go install" not in run, "do not `go install` oasdiff at CI time"
    assert (
        "sha256sum -c" in run
    ), "must VERIFY the tarball's checksum (sha256sum -c), not just compute it"
    assert any(
        "OASDIFF_VERSION" in k for k in env
    ), "pin the oasdiff version in an env var"
    assert any(
        "OASDIFF_SHA256" in k for k in env
    ), "pin the tarball sha256 in an env var"


# ---------------------------------------------------------------------------
# Blocking step: `oasdiff breaking --fail-on ERR` with the escape hatch.
# ---------------------------------------------------------------------------


def test_blocking_step_exists_and_is_not_advisory() -> None:
    """The gate must be genuinely blocking: a distinct step that is NOT named
    'Advisory' and does NOT carry continue-on-error."""
    step = _blocking_step()
    assert (
        step is not None
    ), "openapi-contract must have a blocking breaking-change gate"
    assert "Advisory" not in str(
        step.get("name", "")
    ), "the blocking gate must not be named 'Advisory'"
    assert (
        "continue-on-error" not in step
    ), "the blocking gate must not set continue-on-error"


def test_blocking_step_runs_oasdiff_breaking_fail_on_err() -> None:
    """The gate runs ``oasdiff breaking --fail-on ERR`` base-vs-working-tree so
    ERR-level breaking changes fail the job."""
    step = _blocking_step()
    assert step is not None
    run = step.get("run") or ""
    assert "oasdiff breaking" in run, "must run `oasdiff breaking`"
    assert "--fail-on ERR" in run, "breaking gate must use --fail-on ERR"
    assert (
        "backend/openapi.json" in run
    ), "oasdiff must diff against the working-tree backend/openapi.json"


def test_blocking_step_is_pull_request_only_with_label_escape_hatch() -> None:
    """The gate runs on pull_request events, and is skipped when the PR carries
    the ``api-breaking-approved`` label (reviewed, intentional break)."""
    step = _blocking_step()
    assert step is not None
    cond = str(step.get("if") or "")
    assert (
        "pull_request" in cond
    ), "blocking gate must be guarded to pull_request events"
    assert (
        "!contains(github.event.pull_request.labels.*.name, 'api-breaking-approved')"
        in cond
    ), "blocking gate must NEGATE the label check (skip when labelled, not run only-when-labelled)"


def test_blocking_step_skips_cleanly_when_base_missing() -> None:
    """A missing base spec (empty sha / new file) must not fail the blocking
    gate: the step exits 0 and notes the skip in the job summary."""
    step = _blocking_step()
    assert step is not None
    run = step.get("run") or ""
    assert "exit 0" in run, "missing-base skip must exit 0 explicitly, never fail"
    assert (
        "GITHUB_STEP_SUMMARY" in run
    ), "the skip path must record a note in the job summary"


# ---------------------------------------------------------------------------
# Informational step: `oasdiff changelog` into the summary (non-blocking).
# ---------------------------------------------------------------------------


def test_changelog_step_is_informational_and_writes_summary() -> None:
    """A separate changelog step reports every change into the job summary and
    stays non-blocking (continue-on-error)."""
    step = _changelog_step()
    assert (
        step is not None
    ), "openapi-contract must have an informational changelog step"
    assert (
        step.get("continue-on-error") is True
    ), "changelog step must set continue-on-error: true"
    run = step.get("run") or ""
    assert "oasdiff changelog" in run, "informational step must run `oasdiff changelog`"
    assert "GITHUB_STEP_SUMMARY" in run, "changelog must be written to the job summary"


def test_no_advisory_oasdiff_step_remains() -> None:
    """Task 2.2 supersedes the advisory breaking step with the blocking gate; no
    'Advisory ... oasdiff' step may linger in the job."""
    for step in _load_job()["steps"]:
        name = str(step.get("name", ""))
        if "Advisory" in name:
            assert "oasdiff" not in name.lower(), (
                "the advisory oasdiff step is superseded by the blocking gate; "
                f"remove it (found: {name!r})"
            )
