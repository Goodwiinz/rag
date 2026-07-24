"""Regression tests for the agent_run_events Alembic migration.

House pattern (mirrors test_satellite_status_migration.py): load the revision
module by path, stub ``alembic.op``, and assert on the emitted SQL — the
migration performs Postgres-only data conversion (thread_id string → uuid),
so it cannot run against SQLite.

The assertions pin the deployment-safety properties, not the cosmetics:

- idempotent re-run (IF NOT EXISTS / to_regclass guards — bootstrap DBs
  already have the tables via Base.metadata.create_all);
- thread_id conversion nulls invalid/dangling correlations BEFORE the type
  change and adds the FK only AFTER conversion;
- duplicate non-terminal runs per thread are terminalized BEFORE the unique
  active-run index is created (else index creation fails deployment);
- the status CHECK constraint is rebuilt to admit queued/stopping;
- downgrade drops everything upgrade added.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "d5e6f7a8b9c0_add_agent_run_events.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_agent_run_events_migration",
    str(_MODULE_PATH),
)
# spec_from_file_location returns Optional; a missing revision module is a
# broken checkout, not a test condition.
assert _SPEC is not None and _SPEC.loader is not None
run_events_migration = importlib.util.module_from_spec(_SPEC)
sys.modules["_agent_run_events_migration"] = run_events_migration

if "alembic" not in sys.modules:
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = SimpleNamespace(  # type: ignore[attr-defined]
        execute=lambda sql: None
    )
    sys.modules["alembic"] = fake_alembic

_SPEC.loader.exec_module(run_events_migration)


@pytest.fixture
def statements(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []
    monkeypatch.setattr(
        run_events_migration,
        "op",
        SimpleNamespace(execute=lambda sql: captured.append(str(sql))),
    )
    return captured


def test_chains_off_project_skills_head() -> None:
    assert run_events_migration.revision == "d5e6f7a8b9c0"
    assert run_events_migration.down_revision == "c4d5e6f7g8h9"


def _normalize(statements: list[str]) -> str:
    """Lowercase, collapse whitespace, strip identifier quotes."""
    return " ".join("\n".join(statements).lower().replace('"', "").split())


def _upgrade_sql(statements: list[str]) -> str:
    run_events_migration.upgrade()
    return _normalize(statements)


def test_upgrade_creates_event_table_and_indexes(statements: list[str]) -> None:
    sql = _upgrade_sql(statements)
    assert "create table if not exists agent_run_events" in sql
    assert "uq_agent_run_events_run_seq" in sql
    assert "idx_agent_run_events_run_seq" in sql
    assert "idx_agent_run_events_created_at" in sql
    assert "references agent_runs" in sql
    assert "on delete cascade" in sql


def test_upgrade_expands_agent_runs_idempotently(statements: list[str]) -> None:
    sql = _upgrade_sql(statements)
    for column in (
        "conversation_id",
        "project_id",
        "user_message_id",
        "assistant_message_id",
        "runtime_snapshot_id",
        "client_message_id",
        "last_event_seq",
        "started_at",
        "completed_at",
        "cancel_requested_at",
        "error_code",
        "usage",
        "run_metadata",
        "lease_generation",
    ):
        assert f"add column if not exists {column}" in sql, column
    assert "to_regclass('public.agent_runs')" in sql


def test_upgrade_converts_thread_id_honestly(statements: list[str]) -> None:
    sql = _upgrade_sql(statements)
    # Invalid strings and dangling uuids (the job-id fallback) are nulled
    # BEFORE the type change; FK is added only after conversion.
    null_out = sql.index("set thread_id = null")
    alter_type = sql.index("alter column thread_id type uuid")
    add_fk = sql.index("fk_agent_runs_thread_id")
    assert null_out < alter_type < add_fk
    assert "using thread_id::uuid" in sql
    assert "not exists ( select 1 from threads" in sql


def test_upgrade_rebuilds_status_check_with_new_lifecycle(
    statements: list[str],
) -> None:
    sql = _upgrade_sql(statements)
    assert "drop constraint if exists ck_agent_runs_status" in sql
    assert "'queued'" in sql
    assert "'stopping'" in sql


def test_upgrade_terminalizes_duplicate_active_runs_before_unique_index(
    statements: list[str],
) -> None:
    sql = _upgrade_sql(statements)
    supersede = sql.index("superseded_by_migration")
    unique_index = sql.index("uq_agent_runs_active_thread")
    assert supersede < unique_index
    assert "create unique index if not exists uq_agent_runs_active_thread" in sql


def test_upgrade_rescopes_idempotency_index(statements: list[str]) -> None:
    sql = _upgrade_sql(statements)
    assert "drop index if exists uq_agent_runs_idempotency_key" in sql
    assert "create unique index if not exists uq_agent_runs_user_idempotency_key" in sql


def test_downgrade_drops_everything_it_added(statements: list[str]) -> None:
    run_events_migration.downgrade()
    sql = _normalize(statements)
    assert "drop table if exists agent_run_events" in sql
    assert "drop index if exists uq_agent_runs_active_thread" in sql
    assert "drop index if exists uq_agent_runs_user_idempotency_key" in sql
    for column in ("conversation_id", "last_event_seq", "run_metadata"):
        assert f"drop column if exists {column}" in sql
