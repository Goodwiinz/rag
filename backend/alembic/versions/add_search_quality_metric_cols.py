"""Add search-quality-metric columns to quality_metrics + relax legacy NOT NULLs

Revision ID: add_search_quality_metric_cols
Revises: repair_invalid_chat_msg_idx
Create Date: 2026-07-03 04:00:00

The /analytics/quality endpoints + QualityMetricsService.collect_search_metrics
were written against a QualityMetric shape (metric_value, metric_unit, query,
search_type, measured_at, is_threshold_violation, user_id, search_query_id) that
never existed on the ``quality_metrics`` table, so every read/write 500'd
(AttributeError on the ORM query, non-column kwargs on insert). This adds those
columns to match the model + API contract.

The legacy evaluation-oriented NOT NULL columns (metric_name, value,
evaluation_type, scope) are relaxed to nullable so a search-metric row — which
populates the new columns but not those — can be inserted. Both row shapes now
coexist in the same table.

Idempotent: ADD COLUMN IF NOT EXISTS + DROP NOT NULL are no-ops when already
applied (matches this repo's create_all-vs-alembic drift posture).
"""

from alembic import op

revision = "add_search_quality_metric_cols"
down_revision = "repair_invalid_chat_msg_idx"
branch_labels = None
depends_on = None

TABLE = "quality_metrics"
ADD_COLUMNS = [
    ("metric_value", "double precision"),
    ("metric_unit", "varchar(50)"),
    ("query", "text"),
    ("search_type", "varchar(50)"),
    ("search_query_id", "uuid"),
    ("user_id", "uuid"),
    ("is_threshold_violation", "boolean"),
]
RELAX_NOT_NULL = ["metric_name", "value", "evaluation_type", "scope"]


def upgrade() -> None:
    for name, coltype in ADD_COLUMNS:
        op.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS {name} {coltype}")
    for col in RELAX_NOT_NULL:
        op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN {col} DROP NOT NULL")


def downgrade() -> None:
    for name, _ in ADD_COLUMNS:
        op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS {name}")
    # NOT NULL is intentionally NOT re-added on downgrade — rows created while
    # relaxed may hold nulls, so re-imposing it could fail. Deliberate no-op.
