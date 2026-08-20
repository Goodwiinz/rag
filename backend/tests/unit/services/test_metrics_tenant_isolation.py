"""analytics_metrics must carry an organization_id for tenant isolation.

R5-M21: list_metrics returned every org's metric definitions — including
free-text name/display_name/description/calculation_config — because the
table had no tenant column at all (unlike its sibling analytics_kpis, fixed
in b7d4e9a1c3f2). These tests pin the new column on the model (real ORM
introspection), prove the read filter actually isolates tenants
(behavioral), and pin the migration that adds the column (chained off the
documented head). Modeled directly on
tests/unit/services/test_kpi_tenant_isolation.py.
"""

from __future__ import annotations

import pathlib
import re
import uuid
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_BACKEND = pathlib.Path(__file__).parents[3]


# --- model contract: real ORM introspection ---------------------------------


def test_metric_model_has_tenant_scoped_organization_id_column() -> None:
    """Introspect the mapped column, not the source file.

    organization_id must exist, be a nullable FK to organizations.id, and be
    indexed (the read-path filter scans on it).
    """
    from src.models.analytics.analytics_models import AnalyticsMetric

    col = AnalyticsMetric.__table__.c.get("organization_id")
    assert col is not None, "AnalyticsMetric is missing the organization_id column"

    # Nullable for backward-compat: rows created before the column existed have
    # no derivable owner; the read endpoints fail closed on NULL instead.
    assert col.nullable is True
    # Indexed so the tenant filter doesn't table-scan.
    assert col.index is True

    fks = list(col.foreign_keys)
    assert len(fks) == 1
    assert fks[0].target_fullname == "organizations.id"


# --- behavioral: the read filter actually isolates tenants -------------------
#
# Proves the security property (an org-A caller's query returns only org A's
# rows, never org B's or the legacy NULL-org row) by running the EXACT WHERE
# predicate list_metrics builds against the REAL AnalyticsMetric table on a
# throwaway SQLite engine. Core (__table__), not the ORM select(), for the same
# configure_mappers()-avoidance reason as the KPI test.


async def _make_metric_engine() -> Any:
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.models.analytics.analytics_models import AnalyticsMetric

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AnalyticsMetric.__table__.create)
    return engine


async def _seed_three_orgs(conn: Any, org_a: uuid.UUID, org_b: uuid.UUID) -> None:
    """Seed three metrics: org A, org B, and a legacy NULL-org row."""
    from sqlalchemy import insert

    from src.models.analytics.analytics_models import (
        AggregationType,
        AnalyticsMetric,
        MetricType,
    )

    def _metric(name: str, org: uuid.UUID | None) -> dict[str, Any]:
        return {
            "id": uuid.uuid4(),
            "name": name,
            "display_name": name,
            "metric_type": MetricType.COUNTER,
            "default_aggregation": AggregationType.SUM,
            "organization_id": org,
            "is_deleted": False,
        }

    await conn.execute(
        insert(AnalyticsMetric.__table__),
        [_metric("a", org_a), _metric("b", org_b), _metric("legacy", None)],
    )


@pytest.mark.asyncio
async def test_read_filter_isolates_tenants_and_excludes_null_org() -> None:
    from sqlalchemy import select

    from src.models.analytics.analytics_models import AnalyticsMetric

    metrics = AnalyticsMetric.__table__
    engine = await _make_metric_engine()
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    try:
        async with engine.begin() as conn:
            await _seed_three_orgs(conn, org_a, org_b)

            # The exact predicate list_metrics builds for an org_a caller:
            # is_deleted == False, IS NOT NULL (fail closed), == caller org.
            rows = (
                (
                    await conn.execute(
                        select(metrics).where(
                            metrics.c.is_deleted == False,  # noqa: E712
                            metrics.c.organization_id.isnot(None),
                            metrics.c.organization_id == org_a,
                        )
                    )
                )
                .mappings()
                .all()
            )

            names = {r["name"] for r in rows}
            assert names == {"a"}  # never org_b's "b" or the NULL-org "legacy"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_read_filter_never_returns_legacy_null_rows_to_a_null_org_caller() -> (
    None
):
    """Defense in depth for the null-org caller guard.

    The list_metrics endpoint short-circuits a null-org caller before querying
    (return []). Even if that short-circuit were removed, the WHERE clause
    still fails closed: organization_id == None compiles to IS NULL, which the
    co-present IS NOT NULL guard contradicts, so legacy NULL-org rows are
    never returned. Prove that behaviorally.
    """
    from sqlalchemy import select

    from src.models.analytics.analytics_models import AnalyticsMetric

    metrics = AnalyticsMetric.__table__
    engine = await _make_metric_engine()
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    null_org_caller = None

    try:
        async with engine.begin() as conn:
            await _seed_three_orgs(conn, org_a, org_b)

            rows = (
                (
                    await conn.execute(
                        select(metrics).where(
                            metrics.c.is_deleted == False,  # noqa: E712
                            metrics.c.organization_id.isnot(None),
                            metrics.c.organization_id == null_org_caller,
                        )
                    )
                )
                .mappings()
                .all()
            )

            assert rows == []  # the legacy "legacy" NULL-org row stays hidden
    finally:
        await engine.dispose()


# --- migration pinning: legitimately file-based ------------------------------


def test_migration_chains_off_documented_head() -> None:
    mig = _BACKEND / "alembic/versions/add_org_id_to_analytics_metrics.py"
    text = mig.read_text()
    assert 'revision = "add_org_id_to_analytics_metrics"' in text
    assert 'down_revision = "add_chat_messages_ttft_ms"' in text
    assert "ADD COLUMN IF NOT EXISTS organization_id" in text
    assert "idx_analytics_metrics_organization_id" in text
    assert "def downgrade" in text


def test_migration_revision_id_is_unique_across_versions() -> None:
    versions = _BACKEND / "alembic/versions"
    count = sum(
        1
        for f in versions.glob("*.py")
        if re.search(
            r'^revision\s*=\s*["\']add_org_id_to_analytics_metrics["\']',
            f.read_text(),
            re.MULTILINE,
        )
    )
    assert count == 1, "new migration revision id must be globally unique"
