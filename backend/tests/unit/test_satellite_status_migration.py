"""Regression tests for the satellite-sync-status Alembic migration (audit D1).

House pattern (mirrors test_entity_type_enum_migration.py): load the revision
module by path, stub ``alembic.op``, and assert on the emitted SQL — the
migration is a Postgres ``DO $$`` block, so it cannot run against SQLite.
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
    / "b8s2a4t7e0l3_add_satellite_sync_status.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_satellite_status_migration",
    str(_MODULE_PATH),
)
satellite_migration = importlib.util.module_from_spec(_SPEC)
sys.modules["_satellite_status_migration"] = satellite_migration

if "alembic" not in sys.modules:
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = SimpleNamespace(execute=lambda sql: None)
    sys.modules["alembic"] = fake_alembic

_SPEC.loader.exec_module(satellite_migration)  # type: ignore[union-attr]


@pytest.fixture
def statements(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []
    monkeypatch.setattr(
        satellite_migration,
        "op",
        SimpleNamespace(execute=lambda sql: captured.append(str(sql))),
    )
    return captured


def test_chains_off_agent_runs_head():
    """Single-head discipline: must chain off a7r2u9n4s1t6 with a short id."""
    assert satellite_migration.revision == "b8s2a4t7e0l3"
    assert satellite_migration.down_revision == "a7r2u9n4s1t6"
    assert len(satellite_migration.revision) <= 32


def test_upgrade_adds_columns_indexes_and_honest_backfill(statements):
    satellite_migration.upgrade()
    sql = "\n".join(statements).lower()

    assert "add column if not exists neo4j_index_status varchar(20)" in sql
    assert "add column if not exists neo4j_indexed_at timestamptz" in sql
    assert "add column if not exists do_kb_sync_status varchar(20)" in sql
    assert "ix_documents_neo4j_index_status" in sql
    assert "ix_documents_do_kb_sync_status" in sql

    # Backfill is keyed on the truthful DO KB marker (a persisted data-source
    # uuid), NOT on is_indexed (which records tsvector searchability), and only
    # fills NULLs (idempotent re-run safe).
    assert "set do_kb_sync_status = 'completed'" in sql
    assert "where do_kb_data_source_uuid is not null" in sql
    assert "and do_kb_sync_status is null" in sql
    assert "is_indexed" not in sql

    # Neo4j history is unknown — stays NULL (no neo4j backfill statement).
    assert "set neo4j_index_status" not in sql

    # Idempotence guards (house to_regclass / IF NOT EXISTS pattern).
    assert "to_regclass('public.documents')" in sql
    assert "information_schema.columns" in sql


def test_downgrade_drops_everything_it_added(statements):
    satellite_migration.downgrade()
    sql = "\n".join(statements).lower()

    assert "drop index if exists ix_documents_neo4j_index_status" in sql
    assert "drop index if exists ix_documents_do_kb_sync_status" in sql
    assert "drop column if exists neo4j_index_status" in sql
    assert "drop column if exists neo4j_indexed_at" in sql
    assert "drop column if exists do_kb_sync_status" in sql
