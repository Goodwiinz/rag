"""Contracts for local migration-gate classification and isolation."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
LOCAL_CI_PATH = REPO_ROOT / "scripts" / "ci" / "run_local_ci.sh"


def _script() -> str:
    return LOCAL_CI_PATH.read_text(encoding="utf-8")


def test_empty_replay_is_visible_advisory_and_never_a_pass() -> None:
    script = _script()

    assert "Alembic upgrade head from an empty DB (advisory measurement)" in script
    assert "alembic_upgrade_from_empty" in script
    assert "NOT VERIFIED: alembic upgrade head from an empty database" in script
    assert "advisory measurement failed" in script
    assert 'check "$ALEMBIC_RC" "alembic upgrade (from empty)"' not in script


def test_targeted_evidence_probe_is_blocking_and_separate() -> None:
    script = _script()

    assert "probe_evidence_migration.py" in script
    assert "targeted evidence migration delta" in script
    assert 'check "$TARGETED_EVIDENCE_RC" "targeted evidence migration delta"' in script
    assert "ci_evidence_delta_" in script


def test_targeted_probe_receives_standard_pg_fields_not_a_shell_url() -> None:
    script = _script()
    start = script.index("targeted_evidence_migration_probe()")
    end = script.index("alembic_upgrade_from_empty()", start)
    targeted_block = script[start:end]

    for field in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE"):
        assert f"{field}=" in targeted_block
    assert "--admin-database-url" not in targeted_block
    assert "postgresql://$PG_USER:$PG_PW" not in targeted_block
    assert "postgresql://$PG_USER:$PG_PW" not in script
