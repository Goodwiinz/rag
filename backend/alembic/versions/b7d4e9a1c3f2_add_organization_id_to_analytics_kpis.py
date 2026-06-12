"""add organization_id to analytics_kpis (tenant isolation)

The ``analytics_kpis`` table had no tenant column, so ``list_kpis`` / ``get_kpi``
returned every organization's KPIs to any authenticated user (cross-tenant
read). This adds a nullable ``organization_id`` (FK to ``organizations``, with
an index) so the read endpoints can scope by the caller's org.

Nullable + no backfill: KPIs created before this column existed have no
derivable owner, so they stay NULL. The read endpoints reject NULL-org callers
up front and filter active rows by ``organization_id IS NOT NULL AND
= caller_org``, so legacy NULL rows are never returned (fail closed) rather than
world-readable. New KPIs are stamped with the creator's org (and the service
refuses to create a NULL-org KPI).

Revision ID: b7d4e9a1c3f2
Revises: z4a5b6c7d8e9
Create Date: 2026-06-10
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b7d4e9a1c3f2"
down_revision = "z4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guard the whole body on table existence.
    #
    # ``analytics_kpis`` is an ORM-only table (no create migration exists), so
    # it is present on databases bootstrapped via ``Base.metadata.create_all``
    # but ABSENT on migrate-only databases. The previous body added the column
    # with ``ALTER TABLE IF EXISTS`` (table-guarded, safe) but then ran a bare
    # ``CREATE INDEX ... ON analytics_kpis`` — and ``CREATE INDEX IF NOT EXISTS``
    # guards the index NAME, not the target table. On a DB without the table
    # that raised ``UndefinedTable`` and crash-looped the run-migrations init
    # container, blocking every deploy.
    #
    # ``to_regclass`` returns NULL for a missing table without erroring, so the
    # block runs once where the table exists and no-ops where it does not. The
    # missing create migration for the analytics_* schema is tracked separately.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.analytics_kpis') IS NOT NULL THEN
                ALTER TABLE analytics_kpis
                    ADD COLUMN IF NOT EXISTS organization_id UUID;
                CREATE INDEX IF NOT EXISTS idx_analytics_kpis_organization_id
                    ON analytics_kpis (organization_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_analytics_kpis_organization_id")
    op.execute(
        "ALTER TABLE IF EXISTS analytics_kpis DROP COLUMN IF EXISTS organization_id"
    )
