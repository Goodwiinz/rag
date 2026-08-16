"""Regression proof for the historical document-processing migration."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "f931599b6b5b_enhance_document_processing.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_document_processing_migration",
    str(_MODULE_PATH),
)
assert _SPEC is not None and _SPEC.loader is not None
document_processing_migration = importlib.util.module_from_spec(_SPEC)
sys.modules["_document_processing_migration"] = document_processing_migration
_SPEC.loader.exec_module(document_processing_migration)


@pytest.fixture
def created_tables(monkeypatch: pytest.MonkeyPatch) -> dict[str, tuple[Any, ...]]:
    tables: dict[str, tuple[Any, ...]] = {}

    def create_table(name: str, *columns: Any, **kwargs: Any) -> None:
        del kwargs
        tables[name] = columns

    monkeypatch.setattr(
        document_processing_migration,
        "op",
        SimpleNamespace(
            execute=lambda statement: None,
            create_table=create_table,
            create_index=lambda *args, **kwargs: None,
            add_column=lambda *args, **kwargs: None,
            f=lambda name: name,
        ),
    )
    document_processing_migration.upgrade()
    return tables


@pytest.mark.unit
@pytest.mark.regression
def test_enum_columns_reuse_the_explicitly_created_postgres_types(
    created_tables: dict[str, tuple[Any, ...]],
) -> None:
    expected = (
        ("processing_history", "stage", "processingstage"),
        ("multimodal_content", "content_type", "contenttype"),
        ("document_quality_metrics", "metric_type", "qualitymetrictype"),
    )

    for table_name, column_name, enum_name in expected:
        columns = [
            column
            for column in created_tables[table_name]
            if getattr(column, "name", None) == column_name
        ]
        assert len(columns) == 1
        enum_type = columns[0].type
        assert isinstance(enum_type, postgresql.ENUM)
        assert enum_type.name == enum_name
        assert enum_type.create_type is False
