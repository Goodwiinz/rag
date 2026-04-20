"""Read-only audit of SQLAlchemy metadata versus the live database schema."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ColumnShape:
    """Comparable column shape for model and database columns."""

    name: str
    type_name: str
    nullable: bool | None


@dataclass(frozen=True)
class DriftRow:
    """A single drift finding."""

    table: str
    column: str
    in_model: bool
    in_db: bool
    model_type: str
    db_type: str
    model_nullable: bool | None
    db_nullable: bool | None
    drift_kind: str


def canonical_type_name(type_name: str) -> str:
    """Normalize type names for drift comparisons."""
    normalized = type_name.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\(.*\)", "", normalized)

    if normalized.endswith("[]"):
        item_type = canonical_type_name(normalized[:-2])
        return f"{item_type}[]"

    aliases = {
        "character varying": "varchar",
        "float": "float8",
        "double precision": "float8",
        "boolean": "bool",
        "integer": "int4",
        "bigint": "int8",
        "smallint": "int2",
        "timestamp with time zone": "timestamptz",
        "timestamp without time zone": "timestamp",
    }
    return aliases.get(normalized, normalized)


def diff_table_columns(
    table_name: str,
    model_columns: dict[str, ColumnShape],
    db_columns: dict[str, ColumnShape],
) -> list[DriftRow]:
    """Return column-level drift rows for a single table."""
    rows: list[DriftRow] = []
    all_columns = sorted(set(model_columns) | set(db_columns))

    for column_name in all_columns:
        model_column = model_columns.get(column_name)
        db_column = db_columns.get(column_name)

        if model_column is None:
            rows.append(
                DriftRow(
                    table=table_name,
                    column=column_name,
                    in_model=False,
                    in_db=True,
                    model_type="",
                    db_type=db_column.type_name,
                    model_nullable=None,
                    db_nullable=db_column.nullable,
                    drift_kind="missing_in_model",
                )
            )
            continue

        if db_column is None:
            rows.append(
                DriftRow(
                    table=table_name,
                    column=column_name,
                    in_model=True,
                    in_db=False,
                    model_type=model_column.type_name,
                    db_type="",
                    model_nullable=model_column.nullable,
                    db_nullable=None,
                    drift_kind="missing_in_db",
                )
            )
            continue

        if canonical_type_name(model_column.type_name) != canonical_type_name(
            db_column.type_name
        ):
            rows.append(
                DriftRow(
                    table=table_name,
                    column=column_name,
                    in_model=True,
                    in_db=True,
                    model_type=model_column.type_name,
                    db_type=db_column.type_name,
                    model_nullable=model_column.nullable,
                    db_nullable=db_column.nullable,
                    drift_kind="type_mismatch",
                )
            )

        if model_column.nullable != db_column.nullable:
            rows.append(
                DriftRow(
                    table=table_name,
                    column=column_name,
                    in_model=True,
                    in_db=True,
                    model_type=model_column.type_name,
                    db_type=db_column.type_name,
                    model_nullable=model_column.nullable,
                    db_nullable=db_column.nullable,
                    drift_kind="nullability_mismatch",
                )
            )

    return rows


def render_markdown_report(
    rows: Iterable[DriftRow],
    generated_at: datetime,
    database_label: str,
    schema_name: str,
) -> str:
    """Render drift findings as a markdown report."""
    row_list = list(rows)
    lines = [
        "# Schema Drift Audit",
        "",
        f"- Generated: {generated_at.astimezone(timezone.utc).isoformat()}",
        f"- Database: `{database_label}`",
        f"- Schema: `{schema_name}`",
        f"- Drift rows: `{len(row_list)}`",
        "",
        "| table | column | in_model | in_db | model_type | db_type | model_nullable | db_nullable | drift_kind |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    if not row_list:
        lines.append("| _none_ | _none_ | n/a | n/a |  |  | n/a | n/a | no_drift |")
        return "\n".join(lines) + "\n"

    for row in row_list:
        lines.append(
            "| {table} | {column} | {in_model} | {in_db} | {model_type} | {db_type} | {model_nullable} | {db_nullable} | {drift_kind} |".format(
                table=row.table,
                column=row.column,
                in_model=_format_bool(row.in_model),
                in_db=_format_bool(row.in_db),
                model_type=row.model_type,
                db_type=row.db_type,
                model_nullable=_format_nullable(row.model_nullable),
                db_nullable=_format_nullable(row.db_nullable),
                drift_kind=row.drift_kind,
            )
        )

    return "\n".join(lines) + "\n"


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_nullable(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return _format_bool(value)


def _load_model_metadata():
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    import src.models  # noqa: F401  # Register models on Base.metadata
    from src.core.database import Base, DATABASE_URL

    return Base.metadata, DATABASE_URL


def _model_column_shapes(metadata, dialect) -> dict[str, dict[str, ColumnShape]]:
    tables: dict[str, dict[str, ColumnShape]] = {}

    for table_name, table in sorted(metadata.tables.items()):
        table_columns: dict[str, ColumnShape] = {}
        for column in table.columns:
            table_columns[column.name] = ColumnShape(
                name=column.name,
                type_name=str(column.type.compile(dialect=dialect)),
                nullable=column.nullable,
            )
        tables[table_name] = table_columns

    return tables


def _db_column_shapes(engine, schema_name: str) -> dict[str, dict[str, ColumnShape]]:
    from sqlalchemy import text

    query = text(
        """
        SELECT
            table_name,
            column_name,
            data_type,
            udt_name,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = :schema_name
        ORDER BY table_name, ordinal_position
        """
    )
    rows = engine.execute(query, {"schema_name": schema_name}).fetchall()
    grouped: dict[str, dict[str, ColumnShape]] = defaultdict(dict)

    for row in rows:
        if row.data_type == "USER-DEFINED":
            db_type = row.udt_name
        elif row.data_type == "ARRAY" and row.udt_name.startswith("_"):
            db_type = f"{row.udt_name[1:]}[]"
        else:
            db_type = row.data_type
        grouped[row.table_name][row.column_name] = ColumnShape(
            name=row.column_name,
            type_name=str(db_type),
            nullable=row.is_nullable == "YES",
        )

    return dict(grouped)


def _database_label(database_url: str) -> str:
    from sqlalchemy.engine import make_url

    try:
        url = make_url(database_url)
    except Exception:
        return "<unparsed>"

    username = url.username or "unknown"
    host = url.host or "unknown"
    database = url.database or "unknown"
    return f"{username}@{host}/{database}"


def build_drift_rows(schema_name: str = "public") -> tuple[list[DriftRow], str]:
    """Load metadata, inspect the live DB, and return drift rows."""
    from sqlalchemy import create_engine

    metadata, database_url = _load_model_metadata()
    engine = create_engine(database_url)

    with engine.connect() as connection:
        model_tables = _model_column_shapes(metadata, connection.dialect)
        db_tables = _db_column_shapes(connection, schema_name)

    drift_rows: list[DriftRow] = []
    for table_name, model_columns in model_tables.items():
        drift_rows.extend(
            diff_table_columns(
                table_name=table_name,
                model_columns=model_columns,
                db_columns=db_tables.get(table_name, {}),
            )
        )

    drift_rows.sort(key=lambda row: (row.table, row.column, row.drift_kind))
    return drift_rows, _database_label(database_url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema",
        default="public",
        help="Database schema to inspect (default: public)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the markdown report",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    drift_rows, database_label = build_drift_rows(schema_name=args.schema)
    report = render_markdown_report(
        rows=drift_rows,
        generated_at=datetime.now(timezone.utc),
        database_label=database_label,
        schema_name=args.schema,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")

    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
