"""Workflow-contract test for the Alembic migration-check job (PR 5, Task 5.1).

The migration-check job historically ran only the *static* guard
(``scripts/ci/check_alembic.py``): single head + revision-id length, read via
Alembic's ``ScriptDirectory`` with ``env.py`` never executed and no engine
created. Task 5.1 adds three *execution-depth* checks — from-empty
``upgrade head``, ``alembic check`` drift, and a ``downgrade -1`` /
``upgrade head`` smoke — as **advisory** (``continue-on-error: true``) probes,
because the schema is known to have drift/create-migration debt today and a
from-empty upgrade may legitimately fail. They MEASURE reality without blocking;
promotion to blocking is a later task (5.2) driven by the measured results.

This is a pure YAML-parse contract test (no app import, no DB), mirroring
``test_generate_openapi.py::test_contract_job_verifies_generated_typescript``.
"""

from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]  # CI lint gate installs no types-PyYAML

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "test-pipeline.yml"


def _load_job() -> dict:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return cast(dict, workflow["jobs"]["migration-check"])


def _steps() -> list[dict]:
    return cast("list[dict]", _load_job()["steps"])


def _step_running(fragment: str) -> dict | None:
    """Return the first step whose ``run`` block contains ``fragment``."""
    for step in _steps():
        if fragment in (step.get("run") or ""):
            return step
    return None


def test_job_has_postgres_15_service_with_healthcheck() -> None:
    """The advisory execution checks need a real Postgres to upgrade against."""
    job = _load_job()
    services = job.get("services") or {}
    assert "postgres" in services, "migration-check must define a postgres service"
    postgres = services["postgres"]
    assert str(postgres.get("image", "")).startswith(
        "postgres:15"
    ), f"expected postgres:15 image, got {postgres.get('image')!r}"
    options = postgres.get("options") or ""
    assert "pg_isready" in options and "--health" in options, (
        "postgres service must declare a pg_isready health check so the upgrade "
        "steps run against a ready DB"
    )


def test_static_check_remains_blocking_and_untouched() -> None:
    """The original static guard stays: same script, and NOT advisory."""
    step = _step_running("scripts/ci/check_alembic.py")
    assert step is not None, "static check_alembic.py step must remain in the job"
    assert "continue-on-error" not in step, (
        "the static single-head / revision-length guard is the BLOCKING contract "
        "and must not be made advisory"
    )


def test_upgrade_from_empty_is_advisory() -> None:
    """From-empty ``upgrade head`` runs but cannot block (known drift debt)."""
    step = _step_running("alembic upgrade head")
    assert step is not None, "an `alembic upgrade head` step must exist"
    assert step.get("continue-on-error") is True, (
        "from-empty upgrade must be advisory (continue-on-error: true) until "
        "measured green — see Task 5.2"
    )
    assert (
        "advisory" in (step.get("name") or "").lower()
    ), "label the upgrade step Advisory so its non-blocking intent is obvious"


def test_alembic_check_drift_is_advisory() -> None:
    """``alembic check`` (models-vs-migrations drift) runs advisory."""
    step = _step_running("alembic check")
    assert step is not None, "an `alembic check` drift step must exist"
    assert step.get("continue-on-error") is True, (
        "drift check must be advisory (continue-on-error: true) — the schema is "
        "known to carry create-migration debt today"
    )
    assert "advisory" in (step.get("name") or "").lower()


def test_downgrade_smoke_is_advisory() -> None:
    """A ``downgrade -1`` then re-``upgrade head`` smoke, advisory."""
    step = _step_running("alembic downgrade -1")
    assert step is not None, "a downgrade smoke step must exist"
    run = step.get("run") or ""
    assert "alembic upgrade head" in run, (
        "downgrade smoke must re-apply `upgrade head` to prove the last "
        "migration round-trips"
    )
    assert (
        step.get("continue-on-error") is True
    ), "downgrade smoke must be advisory (continue-on-error: true)"
    assert "advisory" in (step.get("name") or "").lower()


def test_db_url_passed_via_env_to_advisory_steps() -> None:
    """env.py reads DATABASE_URL/SUPABASE_DB_URL; the advisory steps must set it.

    Service-container credentials are CI-local throwaways, so a plain env value
    (postgres/postgres against localhost) is fine and conventional — no secrets
    interpolation is expected here.
    """
    for fragment in ("alembic upgrade head", "alembic check", "alembic downgrade -1"):
        step = _step_running(fragment)
        assert step is not None, f"step running {fragment!r} must exist"
        env = step.get("env") or {}
        assert "DATABASE_URL" in env, (
            f"step {fragment!r} must pass DATABASE_URL so alembic/env.py can build "
            "its engine URL"
        )
        assert "localhost" in str(
            env["DATABASE_URL"]
        ), "the advisory steps should target the CI service container on localhost"


def test_each_probe_writes_to_step_summary() -> None:
    """Each of the three probes must annotate the measurement record."""
    for fragment in ("alembic upgrade head", "alembic check", "alembic downgrade -1"):
        step = _step_running(fragment)
        assert step is not None, f"step running {fragment!r} must exist"
        assert "GITHUB_STEP_SUMMARY" in (step.get("run") or ""), (
            f"probe {fragment!r} must write a PASS/FAIL line to "
            "$GITHUB_STEP_SUMMARY so the outcome is captured in the run record"
        )


def test_install_step_annotates_outcome_in_summary() -> None:
    """The probe-deps install writes its own outcome line so a failed install is
    visible in the record and readers know the probes below are unreliable."""
    step = _step_running("pip install --build-constraint")
    assert step is not None, "the backend-requirements install step must exist"
    assert step.get("continue-on-error") is True, (
        "install must stay advisory (continue-on-error: true) so a dependency "
        "hiccup never fails the blocking static guard that already ran"
    )
    assert "GITHUB_STEP_SUMMARY" in (
        step.get("run") or ""
    ), "install step must write a PASS/FAIL line to $GITHUB_STEP_SUMMARY"
