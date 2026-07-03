"""Change quality_metrics.metric_type from enum to varchar

Revision ID: quality_metric_type_to_string
Revises: add_search_quality_metric_cols
Create Date: 2026-07-03 18:30:00

quality_metrics.metric_type was Column(Enum(MetricType)) — a native PG enum
whose members (precision/recall/latency/…) do NOT include the labels the
search-analytics writer emits (response_time, result_count, result_diversity,
avg_relevance_score, freshness). Inserting one raised
``invalid input value for enum`` -> POST /metrics/search 500'd. The column is
really a free-form label (the API response types it str, the standalone table
shape uses varchar), so convert it to varchar(50).

Only this column changes; the shared ``metrictype`` enum type stays in place for
the other tables (ab_testing_analytics, evaluation_metrics, …) that still use it.
Idempotent: the ALTER is guarded to run only while the column is still an enum.
"""

from alembic import op

revision = "quality_metric_type_to_string"
down_revision = "add_search_quality_metric_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert enum -> varchar only if it hasn't been converted already.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'quality_metrics'
                  AND column_name = 'metric_type'
                  AND data_type = 'USER-DEFINED'
            ) THEN
                ALTER TABLE quality_metrics
                    ALTER COLUMN metric_type TYPE varchar(50)
                    USING metric_type::text;
            END IF;
        END
        $$;
        """)


def downgrade() -> None:
    # No-op: values written while varchar (e.g. "result_count") are not valid
    # metrictype enum members, so casting back would fail. Deliberate no-op.
    pass
