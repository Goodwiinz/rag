"""Regression tests for the internal agent-table RLS boundary.

The browser uses Supabase for authentication, not direct access to these
backend-owned tables. Keep the Alembic and Supabase migration paths aligned so
neither deployment order leaves the tables exposed through PostgREST.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = (
    _BACKEND_ROOT
    / "alembic"
    / "versions"
    / "h8i9j0k1l2m3_secure_internal_agent_tables_rls.py"
)
_SUPABASE_MIGRATION_PATH = (
    _BACKEND_ROOT.parent
    / "supabase"
    / "migrations"
    / "20260803232313_secure_internal_agent_tables_rls.sql"
)
_EXPECTED_TABLES = (
    "agent_outbox",
    "agent_run_events",
    "agent_runs",
    "agent_runtime_snapshots",
    "project_skill_change_requests",
    "project_skill_version_scans",
    "project_skill_versions",
    "project_skills",
)

_SPEC = importlib.util.spec_from_file_location(
    "_internal_agent_tables_rls_migration",
    str(_MODULE_PATH),
)
assert _SPEC is not None and _SPEC.loader is not None
rls_migration = importlib.util.module_from_spec(_SPEC)
sys.modules["_internal_agent_tables_rls_migration"] = rls_migration

if "alembic" not in sys.modules:
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = SimpleNamespace(  # type: ignore[attr-defined]
        execute=lambda sql: None
    )
    sys.modules["alembic"] = fake_alembic

_SPEC.loader.exec_module(rls_migration)


@pytest.fixture
def statements(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []
    monkeypatch.setattr(
        rls_migration,
        "op",
        SimpleNamespace(execute=lambda sql: captured.append(str(sql))),
    )
    return captured


def _normalize(sql: str) -> str:
    return " ".join(sql.lower().replace('"', "").split())


def test_chains_off_current_head_with_a_storable_revision_id() -> None:
    assert rls_migration.revision == "h8i9j0k1l2m3"
    assert rls_migration.down_revision == "e6f7a8b9c0d1"
    assert len(rls_migration.revision) <= 32


def test_upgrade_enables_rls_and_revokes_both_postgrest_roles(
    statements: list[str],
) -> None:
    rls_migration.upgrade()

    assert rls_migration._TABLES == _EXPECTED_TABLES
    assert len(statements) == len(_EXPECTED_TABLES) * 3
    for table in _EXPECTED_TABLES:
        table_statements = [statement for statement in statements if table in statement]
        assert len(table_statements) == 3
        normalized = _normalize("\n".join(table_statements))
        assert f"alter table public.{table} enable row level security" in normalized
        for role in ("anon", "authenticated"):
            assert f"rolname = '{role}'" in normalized
            assert f"revoke all on table public.{table} from {role}" in normalized


def test_upgrade_does_not_silently_skip_expected_tables(
    statements: list[str],
) -> None:
    rls_migration.upgrade()
    alter_statements = [
        _normalize(statement)
        for statement in statements
        if "enable row level security" in statement.lower()
    ]
    assert len(alter_statements) == len(_EXPECTED_TABLES)
    assert all("if exists" not in statement for statement in alter_statements)


def test_downgrade_preserves_the_security_boundary(statements: list[str]) -> None:
    rls_migration.downgrade()
    assert statements == []


def test_supabase_migration_secures_the_same_tables() -> None:
    sql = _SUPABASE_MIGRATION_PATH.read_text(encoding="utf-8")
    array_match = re.search(r"tables text\[\] := ARRAY\[(.*?)\];", sql, re.DOTALL)
    assert array_match is not None
    listed_tables = tuple(re.findall(r"'([a-z0-9_]+)'", array_match.group(1)))

    assert listed_tables == _EXPECTED_TABLES
    normalized = _normalize(sql)
    assert "enable row level security" in normalized
    assert "revoke all on table public.%i from anon, authenticated" in normalized
    assert "to_regclass" in normalized
    assert "create policy" not in normalized
