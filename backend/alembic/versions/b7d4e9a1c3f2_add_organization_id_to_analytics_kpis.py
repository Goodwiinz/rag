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
    # Idempotent so it is safe on DBs that already have the column and on
    # fresh DBs alike. FK left implicit (the column references organizations.id
    # via the ORM); the index is what the read-path filter needs.
    op.execute(
        "ALTER TABLE IF EXISTS analytics_kpis "
        "ADD COLUMN IF NOT EXISTS organization_id UUID"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_analytics_kpis_organization_id "
        "ON analytics_kpis (organization_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_analytics_kpis_organization_id")
    op.execute(
        "ALTER TABLE IF EXISTS analytics_kpis DROP COLUMN IF EXISTS organization_id"
    )
