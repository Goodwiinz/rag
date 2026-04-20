"""Regression tests for the entity type enum Alembic migration."""

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
    / "add_entity_type_enum_values.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_entity_type_enum_migration",
    str(_MODULE_PATH),
)
entity_type_migration = importlib.util.module_from_spec(_SPEC)
sys.modules["_entity_type_enum_migration"] = entity_type_migration

if "alembic" not in sys.modules:
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = SimpleNamespace(execute=lambda sql: None)
    sys.modules["alembic"] = fake_alembic

_SPEC.loader.exec_module(entity_type_migration)  # type: ignore[union-attr]


@pytest.mark.unit
@pytest.mark.regression
def test_upgrade_bootstraps_entitytype_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The migration must be safe to run before the enum exists."""
    statements: list[str] = []

    monkeypatch.setattr(
        entity_type_migration,
        "op",
        SimpleNamespace(execute=lambda sql: statements.append(str(sql))),
    )

    entity_type_migration.upgrade()

    normalized = "\n".join(statements).lower()

    assert "create type entitytype as enum" in normalized
    assert "'document'" in normalized
