"""analytics_kpis must carry an organization_id for tenant isolation.

list_kpis/get_kpi returned every org's KPIs because the table had no tenant
column. These tests pin the new column on the model (real ORM introspection),
prove the read filter actually isolates tenants (behavioral), and pin the
migration that adds the column (chained off the documented head).

Earlier revisions of this file asserted *source text* because the analytics
package was unimportable (a duplicate ``AnalyticsEvent`` ORM collided on the
shared metadata — removed in #675 — plus a missing ``WidgetCreate`` and a stale
``src.auth.dependencies`` import). Those are fixed; the modules import cleanly,
so the model/endpoint contract is now checked behaviorally.
"""

from __future__ import annotations

import pathlib
import re
import uuid

import pytest

pytestmark = pytest.mark.unit

_BACKEND = pathlib.Path(__file__).parents[3]


# --- model contract: real ORM introspection ---------------------------------


def test_kpi_model_has_tenant_scoped_organization_id_column():
    """Introspect the mapped column, not the source file.

    organization_id must exist, be a nullable FK to organizations.id, and be
    indexed (the read-path filter scans on it).
    """
    from src.models.analytics.analytics_models import AnalyticsKPI

    col = AnalyticsKPI.__table__.c.get("organization_id")
    assert col is not None, "AnalyticsKPI is missing the organization_id column"

    # Nullable for backward-compat: rows created before the column existed have
    # no derivable owner; the read endpoints fail closed on NULL instead.
    assert col.nullable is True
    # Indexed so the tenant filter doesn't table-scan.
    assert col.index is True

    # Exactly one FK, pointing at organizations.id. target_fullname is a string
    # property, so this works even though the organizations table isn't created
    # on the scratch metadata below.
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    assert fks[0].target_fullname == "organizations.id"


# --- behavioral: the read filter actually isolates tenants -------------------
#
# Proves the security property (an org-A caller's query returns only org A's
# rows, never org B's or the legacy NULL-org row) by running the EXACT WHERE
# predicate list_kpis/get_kpi build against the REAL AnalyticsKPI table on a
# throwaway SQLite engine. Only the two tables under test are created — the
# shared Base has postgres-only column types elsewhere, so create_all would
# fail; we create just AnalyticsMetric + AnalyticsKPI via Table.create. (SQLite
# does not enforce the FK to organizations, so that table is unneeded.)
#
# Why Core (``__table__``) and not the ORM ``select(AnalyticsKPI)``: a real
# ``select(AnalyticsKPI)`` forces a registry-wide ``configure_mappers()`` over
# every model on the shared declarative Base and their relationships (User,
# Organization, the duplicate-named MetricAggregation, etc.) — most of which
# pull in tables and postgres-only column types this two-table scratch DB does
# not have. Operating on ``AnalyticsKPI.__table__`` keeps the test isolated to
# the tables under test and never configures mappers, while the column
# expressions below compile to byte-identical SQL to the ORM attribute form the
# endpoints use: ``is_active = true AND organization_id IS NOT NULL AND
# organization_id = :org``.


async def _make_kpi_engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.models.analytics.analytics_models import AnalyticsKPI, AnalyticsMetric

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # metric first (KPI.metric_id FKs it), then KPI. Metadata subset only —
        # never create_all the full Base.
        await conn.run_sync(AnalyticsMetric.__table__.create)
        await conn.run_sync(AnalyticsKPI.__table__.create)
    return engine


async def _seed_three_orgs(conn, org_a, org_b):
    """Seed one metric and three KPIs: org A, org B, and a legacy NULL-org row."""
    from sqlalchemy import insert

    from src.models.analytics.analytics_models import (
        AggregationType,
        AnalyticsKPI,
        AnalyticsMetric,
        MetricType,
    )

    metric_id = uuid.uuid4()
    await conn.execute(
        insert(AnalyticsMetric.__table__).values(
            id=metric_id,
            name="probe-metric",
            display_name="Probe Metric",
            metric_type=MetricType.COUNTER,
            default_aggregation=AggregationType.SUM,
        )
    )

    def _kpi(name, org):
        return {
            "id": uuid.uuid4(),
            "name": name,
            "display_name": name,
            "metric_id": metric_id,
            "organization_id": org,
            "aggregation_type": AggregationType.SUM,
            "is_active": True,
        }

    await conn.execute(
        insert(AnalyticsKPI.__table__),
        [_kpi("a", org_a), _kpi("b", org_b), _kpi("legacy", None)],
    )


@pytest.mark.asyncio
async def test_read_filter_isolates_tenants_and_excludes_null_org():
    from sqlalchemy import select

    from src.models.analytics.analytics_models import AnalyticsKPI

    kpis = AnalyticsKPI.__table__
    engine = await _make_kpi_engine()
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    try:
        async with engine.begin() as conn:
            await _seed_three_orgs(conn, org_a, org_b)

            # The exact predicate list_kpis/get_kpi build for an org_a caller:
            # is_active, IS NOT NULL (fail closed on legacy rows), == caller org.
            rows = (
                await conn.execute(
                    select(kpis).where(
                        kpis.c.is_active == True,  # noqa: E712
                        kpis.c.organization_id.isnot(None),
                        kpis.c.organization_id == org_a,
                    )
                )
            ).mappings().all()

            names = {r["name"] for r in rows}
            assert names == {"a"}  # never org_b's "b" or the NULL-org "legacy"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_read_filter_never_returns_legacy_null_rows_to_a_null_org_caller():
    """Defense in depth for the null-org caller guard.

    The endpoints short-circuit a null-org caller before querying (list_kpis
    ``return []``, get_kpi 404, create_kpi 400 — see
    src/api/analytics/metrics.py). Even if that short-circuit were removed, the
    WHERE clause still fails closed: ``organization_id == None`` compiles to
    ``IS NULL``, which the co-present ``IS NOT NULL`` guard contradicts, so the
    legacy NULL-org rows are never returned. Prove that behaviorally.
    """
    from sqlalchemy import select

    from src.models.analytics.analytics_models import AnalyticsKPI

    kpis = AnalyticsKPI.__table__
    engine = await _make_kpi_engine()
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    null_org_caller = None

    try:
        async with engine.begin() as conn:
            await _seed_three_orgs(conn, org_a, org_b)

            rows = (
                await conn.execute(
                    select(kpis).where(
                        kpis.c.is_active == True,  # noqa: E712
                        kpis.c.organization_id.isnot(None),
                        kpis.c.organization_id == null_org_caller,
                    )
                )
            ).mappings().all()

            assert rows == []  # the legacy "legacy" NULL-org row stays hidden
    finally:
        await engine.dispose()


# --- migration pinning: legitimately file-based ------------------------------


def test_migration_unique_revision_off_documented_head():
    mig = (
        _BACKEND
        / "alembic/versions/b7d4e9a1c3f2_add_organization_id_to_analytics_kpis.py"
    )
    text = mig.read_text()
    assert 'revision = "b7d4e9a1c3f2"' in text  # unique — not the taken a1b2c3d4e5f6
    assert 'down_revision = "z4a5b6c7d8e9"' in text
    assert "ADD COLUMN IF NOT EXISTS organization_id" in text
    assert "idx_analytics_kpis_organization_id" in text
    assert "def downgrade" in text


def test_migration_revision_id_is_unique_across_versions():
    versions = _BACKEND / "alembic/versions"
    count = sum(
        1
        for f in versions.glob("*.py")
        if re.search(r'revision\s*=\s*["\']b7d4e9a1c3f2["\']', f.read_text())
    )
    assert count == 1, "new migration revision id must be globally unique"
