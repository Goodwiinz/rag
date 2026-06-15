"""add measured_at to quality_metrics (schema-drift fix)

The ``quality_metrics`` table predates the ``measured_at`` column on deployments
where the table was first created without it. The column-adding logic lived only
in an off-chain standalone migration (``alembic/standalone/add_quality_metrics.py``)
that uses ``CREATE TABLE IF NOT EXISTS`` — so on a DB where the table already
existed, the column was never added. ``performance_dashboard_service`` queries
``measured_at`` (e.g. quality trends), so the analytics dashboard endpoints fail
with ``column "measured_at" does not exist``, which aborts the transaction and
cascades ``InFailedSQLTransactionError`` to every other dashboard query.

This migration adds the column (and its index) idempotently so it is safe on
DBs that already have it and on fresh DBs alike.

Revision ID: z4a5b6c7d8e9
Revises: y3z4a5b6c7d8
Create Date: 2026-06-09
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "z4a5b6c7d8e9"
down_revision = "y3z4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: ALTER TABLE IF EXISTS + ADD COLUMN IF NOT EXISTS are no-ops
    # when the table is missing or the column already present.
    op.execute(
        "ALTER TABLE IF EXISTS quality_metrics "
        "ADD COLUMN IF NOT EXISTS measured_at TIMESTAMP NOT NULL DEFAULT now()"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_quality_metrics_measured_at "
        "ON quality_metrics (measured_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_quality_metrics_measured_at")
    op.execute(
        "ALTER TABLE IF EXISTS quality_metrics DROP COLUMN IF EXISTS measured_at"
    )
