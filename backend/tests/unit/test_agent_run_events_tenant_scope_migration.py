"""Regression tests for the agent_run_events tenant-scope migration (P0-B).

House pattern (mirrors test_agent_run_events_migration.py): load the revision
module by path, stub ``alembic.op``, assert on the emitted SQL.

The assertions pin deployment-safety and the D2 decisions:

- expand-only (ADD COLUMN / CREATE INDEX only, all IF NOT EXISTS) so the
  revision is safe to run against the live dev database and re-runnable;
- ``organization_id`` is nullable and never backfilled (the table has no
  producers yet) and is NOT added to ``uq_agent_run_events_run_seq`` — NULLs
  are distinct in a PostgreSQL unique constraint, so an org in the key would
  permit duplicate ``seq`` values for org-less rows;
- no ``chat_messages`` column is added (explicitly out of scope);
- the terminal-event predicate is byte-identical to the model's and covers
  exactly ``TERMINAL_RUN_EVENTS``;
- the revision id fits ``alembic_version.version_num`` (VARCHAR(32)).
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.models.agent_run_event import _TERMINAL_EVENT_PREDICATE
from src.services.agent.run_event_types import TERMINAL_RUN_EVENTS

pytestmark = pytest.mark.unit

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "f2a3b4c5d6e7_agent_run_events_tenant_scope.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_agent_run_events_tenant_scope_migration",
    str(_MODULE_PATH),
)
assert _SPEC is not None and _SPEC.loader is not None
tenant_scope_migration = importlib.util.module_from_spec(_SPEC)
sys.modules["_agent_run_events_tenant_scope_migration"] = tenant_scope_migration

if "alembic" not in sys.modules:
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = SimpleNamespace(  # type: ignore[attr-defined]
        execute=lambda sql: None
    )
    sys.modules["alembic"] = fake_alembic

_SPEC.loader.exec_module(tenant_scope_migration)


@pytest.fixture
def statements(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []
    monkeypatch.setattr(
        tenant_scope_migration,
        "op",
        SimpleNamespace(execute=lambda sql: captured.append(str(sql))),
    )
    return captured


def _normalize(statements: list[str]) -> str:
    return " ".join("\n".join(statements).lower().replace('"', "").split())


def _upgrade_sql(statements: list[str]) -> str:
    tenant_scope_migration.upgrade()
    return _normalize(statements)


def test_chains_off_the_single_head_with_a_storable_revision_id() -> None:
    assert tenant_scope_migration.revision == "f2a3b4c5d6e7"
    assert tenant_scope_migration.down_revision == "d5e6f7a8b9c0"
    # alembic_version.version_num is VARCHAR(32); a longer id crash-loops
    # the deploy on first upgrade.
    assert len(tenant_scope_migration.revision) <= 32


def test_upgrade_adds_nullable_org_column_and_tenant_index(
    statements: list[str],
) -> None:
    sql = _upgrade_sql(statements)
    assert "add column if not exists organization_id uuid" in sql
    # Nullable: no NOT NULL, no default, no backfill.
    assert "organization_id uuid not null" not in sql
    assert "update agent_run_events" not in sql
    assert (
        "create index if not exists idx_agent_run_events_org_run "
        "on agent_run_events (organization_id, run_id)" in sql
    )


def test_upgrade_does_not_touch_the_run_seq_unique_key(statements: list[str]) -> None:
    sql = _upgrade_sql(statements)
    assert "uq_agent_run_events_run_seq" not in sql


def test_upgrade_is_expand_only(statements: list[str]) -> None:
    sql = _upgrade_sql(statements)
    for destructive in ("drop ", "delete ", "alter column", "truncate"):
        assert destructive not in sql, destructive
    # Re-runnable against a database that already has the shape.
    assert sql.count("if not exists") == 3


def test_upgrade_does_not_touch_chat_messages(statements: list[str]) -> None:
    # Decision D2: run ↔ message correlation stays on agent_runs.
    assert "chat_messages" not in _upgrade_sql(statements)


def test_upgrade_enforces_one_terminal_event_per_run(statements: list[str]) -> None:
    sql = _upgrade_sql(statements)
    assert (
        "create unique index if not exists uq_agent_run_events_one_terminal "
        "on agent_run_events (run_id) where" in sql
    )
    for event in TERMINAL_RUN_EVENTS:
        assert f"'{event.value}'" in sql


def test_terminal_predicate_matches_the_model() -> None:
    assert tenant_scope_migration._TERMINAL_PREDICATE == _TERMINAL_EVENT_PREDICATE


def test_downgrade_drops_exactly_what_upgrade_added(statements: list[str]) -> None:
    tenant_scope_migration.downgrade()
    sql = _normalize(statements)
    assert "drop index if exists uq_agent_run_events_one_terminal" in sql
    assert "drop index if exists idx_agent_run_events_org_run" in sql
    assert "drop column if exists organization_id" in sql
