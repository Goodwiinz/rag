"""add organization_id to analytics_metrics (tenant isolation)

The ``analytics_metrics`` table had no tenant column at all (unlike its
sibling ``analytics_kpis``, fixed in b7d4e9a1c3f2), so ``list_metrics`` /
``get_metric`` returned every organization's metric definitions — including
free-text ``name``/``display_name``/``description``/``calculation_config`` —
to any authenticated user (cross-tenant read, R5-M21). This adds a nullable
``organization_id`` (FK to ``organizations``, with an index) so the read
endpoints can scope by the caller's org, mirroring the KPI migration.

Nullable + no backfill: metrics created before this column existed have no
derivable owner, so they stay NULL. The read endpoints reject NULL-org
callers up front and filter rows by ``organization_id IS NOT NULL AND =
caller_org``, so legacy NULL rows are never returned (fail closed) rather
than world-readable. New metrics are stamped with the creator's org.

Revision ID: add_org_id_to_analytics_metrics
Revises: add_chat_messages_ttft_ms
Create Date: 2026-08-20
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_org_id_to_analytics_metrics"
down_revision = "add_chat_messages_ttft_ms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guard the whole body on table existence, same as b7d4e9a1c3f2: analytics_*
    # tables are ORM-only (no create migration), present via create_all on some
    # DBs and absent on migrate-only ones. ``to_regclass`` no-ops safely when
    # the table is missing instead of raising ``UndefinedTable``.
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.analytics_metrics') IS NOT NULL THEN
                ALTER TABLE analytics_metrics
                    ADD COLUMN IF NOT EXISTS organization_id UUID;
                CREATE INDEX IF NOT EXISTS idx_analytics_metrics_organization_id
                    ON analytics_metrics (organization_id);
            END IF;
        END $$;
        """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_analytics_metrics_organization_id")
    op.execute(
        "ALTER TABLE IF EXISTS analytics_metrics DROP COLUMN IF EXISTS organization_id"
    )
