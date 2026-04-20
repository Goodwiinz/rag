"""Unit tests for the schema drift audit script."""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "audit_schema_drift.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_audit_schema_drift",
    str(_MODULE_PATH),
)
audit_schema_drift = importlib.util.module_from_spec(_SPEC)
sys.modules["_audit_schema_drift"] = audit_schema_drift
_SPEC.loader.exec_module(audit_schema_drift)  # type: ignore[union-attr]


@pytest.mark.unit
@pytest.mark.regression
def test_diff_table_columns_reports_missing_extra_and_mismatched_fields() -> None:
    """The diff should report missing, extra, type, and nullability drift."""
    model_columns = {
        "id": audit_schema_drift.ColumnShape(
            name="id",
            type_name="UUID",
            nullable=False,
        ),
        "value": audit_schema_drift.ColumnShape(
            name="value",
            type_name="DOUBLE PRECISION",
            nullable=False,
        ),
        "created_at": audit_schema_drift.ColumnShape(
            name="created_at",
            type_name="TIMESTAMP WITH TIME ZONE",
            nullable=False,
        ),
    }
    db_columns = {
        "id": audit_schema_drift.ColumnShape(
            name="id",
            type_name="uuid",
            nullable=False,
        ),
        "value": audit_schema_drift.ColumnShape(
            name="value",
            type_name="jsonb",
            nullable=True,
        ),
        "measured_at": audit_schema_drift.ColumnShape(
            name="measured_at",
            type_name="timestamptz",
            nullable=False,
        ),
    }

    drifts = audit_schema_drift.diff_table_columns(
        table_name="quality_metrics",
        model_columns=model_columns,
        db_columns=db_columns,
    )

    summary = {(row.column, row.drift_kind) for row in drifts}
    assert ("created_at", "missing_in_db") in summary
    assert ("measured_at", "missing_in_model") in summary
    assert ("value", "type_mismatch") in summary
    assert ("value", "nullability_mismatch") in summary


@pytest.mark.unit
def test_render_markdown_report_includes_summary_and_rows() -> None:
    """Markdown output should include metadata, headers, and drift rows."""
    rows = [
        audit_schema_drift.DriftRow(
            table="quality_metrics",
            column="measured_at",
            in_model=False,
            in_db=True,
            model_type="",
            db_type="timestamp with time zone",
            model_nullable=None,
            db_nullable=False,
            drift_kind="missing_in_model",
        ),
    ]

    report = audit_schema_drift.render_markdown_report(
        rows=rows,
        generated_at=datetime(2026, 4, 20, 12, 30, tzinfo=timezone.utc),
        database_label="postgres@db.example.com/rag_dev",
        schema_name="public",
    )

    assert "# Schema Drift Audit" in report
    assert "postgres@db.example.com/rag_dev" in report
    assert "| table | column | in_model | in_db | model_type | db_type | model_nullable | db_nullable | drift_kind |" in report
    assert "| quality_metrics | measured_at | no | yes |  | timestamp with time zone | n/a | no | missing_in_model |" in report


@pytest.mark.unit
def test_canonical_type_name_normalizes_dialect_equivalents() -> None:
    """Equivalent Postgres spellings should not produce false drift."""
    assert audit_schema_drift.canonical_type_name("FLOAT") == "float8"
    assert audit_schema_drift.canonical_type_name("double precision") == "float8"
    assert audit_schema_drift.canonical_type_name("UUID[]") == "uuid[]"
