"""Regression tests for the analytics_kpis organization_id Alembic migration.

Production incident (2026-06-12): the migration's ``CREATE INDEX ... ON
analytics_kpis`` referenced the table unconditionally. ``analytics_kpis`` is an
ORM-only table with no create migration, so on migrate-only databases (dev) the
statement raised ``UndefinedTable: relation "analytics_kpis" does not exist``.
The run-migrations init container crash-looped (153 restarts), blocking every
backend deploy to the cluster.

The migration must be idempotent: add the column + index where the table
exists, and no-op (without erroring) where it does not.
"""

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "b7d4e9a1c3f2_add_organization_id_to_analytics_kpis.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_analytics_kpis_org_id_migration", str(_MODULE_PATH)
)
kpi_org_migration = importlib.util.module_from_spec(_SPEC)
sys.modules["_analytics_kpis_org_id_migration"] = kpi_org_migration

if "alembic" not in sys.modules:
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = SimpleNamespace(execute=lambda sql: None)
    sys.modules["alembic"] = fake_alembic

_SPEC.loader.exec_module(kpi_org_migration)  # type: ignore[union-attr]


def _capture_upgrade_sql(monkeypatch: pytest.MonkeyPatch) -> str:
    statements: list[str] = []
    monkeypatch.setattr(
        kpi_org_migration,
        "op",
        SimpleNamespace(execute=lambda sql: statements.append(str(sql))),
    )
    kpi_org_migration.upgrade()
    return "\n".join(statements).lower()


@pytest.mark.unit
@pytest.mark.regression
def test_upgrade_guards_index_on_table_existence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The DDL must be wrapped in a runtime table-existence guard so it is
    safe to run before analytics_kpis exists."""
    sql = _capture_upgrade_sql(monkeypatch)

    assert "to_regclass" in sql, (
        "upgrade() references analytics_kpis without a table-existence guard; "
        "this is the unguarded statement that crash-looped the migration"
    )
    assert "analytics_kpis" in sql


@pytest.mark.unit
@pytest.mark.regression
def test_upgrade_still_creates_org_id_column_and_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guarding must not drop the migration's actual job (tenant column + index)."""
    sql = _capture_upgrade_sql(monkeypatch)

    assert "add column if not exists organization_id" in sql
    assert "idx_analytics_kpis_organization_id" in sql
    assert "create index" in sql
