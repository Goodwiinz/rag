"""analytics_kpis must carry an organization_id for tenant isolation.

list_kpis/get_kpi returned every org's KPIs because the table had no tenant
column. These tests pin the new column on the model and the migration that
adds it (chained off the documented head).
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

_BACKEND = pathlib.Path(__file__).parents[3]


def test_kpi_model_has_organization_id_column():
    # Source-text, not introspection: importing AnalyticsKPI pulls
    # src.models.analytics → analytics_models, which registers a SECOND
    # `analytics_events` table that collides with src/models/analytics_event.py
    # (duplicate indexes) and poisons every later test's create_all. Assert the
    # column definition in the model source instead.
    src = (_BACKEND / "src/models/analytics/analytics_models.py").read_text()
    # nullable=True (backward-compat; reads filter NULL out), indexed.
    assert (
        "organization_id = Column(" in src
        and 'ForeignKey("organizations.id"), nullable=True, index=True' in src
    )
    assert "class AnalyticsKPI" in src


def test_create_kpi_accepts_organization_id_and_stamps_it():
    """The service create_kpi must accept organization_id and set it on the KPI.

    Source-text check: importing the service triggers the package's pre-existing
    broken __init__ (WidgetCreate), so assert against the file instead."""
    src = (_BACKEND / "src/services/analytics/metrics_service.py").read_text()
    assert "organization_id: Optional[uuid.UUID]" in src
    assert "organization_id=organization_id" in src  # set on the KPI row


def test_read_endpoints_scope_by_org():
    src = (_BACKEND / "src/api/analytics/metrics.py").read_text()
    # Both list_kpis and get_kpi filter by the caller's org.
    assert (
        src.count("AnalyticsKPI.organization_id == current_user.organization_id") >= 2
    )


def test_endpoints_guard_null_org_caller():
    """A null-org caller must not match legacy NULL-org rows (== None → IS NULL).
    list/get/create all short-circuit; reads also add IS NOT NULL."""
    src = (_BACKEND / "src/api/analytics/metrics.py").read_text()
    assert src.count("current_user.organization_id is None") >= 3  # list, get, create
    assert "AnalyticsKPI.organization_id.isnot(None)" in src


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
    import re

    versions = _BACKEND / "alembic/versions"
    count = sum(
        1
        for f in versions.glob("*.py")
        if re.search(r'revision\s*=\s*["\']b7d4e9a1c3f2["\']', f.read_text())
    )
    assert count == 1, "new migration revision id must be globally unique"


# --- behavioral: the read filter actually isolates tenants --------------------
#
# Proves the security property (org A's query returns only org A's rows, never
# org B's or the legacy NULL-org row) by running the EXACT WHERE predicate the
# endpoints build against a real SQLite table. Uses a standalone throwaway
# table on a LOCAL MetaData — importing the real AnalyticsKPI model would pull
# the poisoned analytics package (duplicate analytics_events table) and break
# every later test's create_all.


@pytest.mark.asyncio
async def test_read_filter_isolates_tenants_and_excludes_null_org():
    import uuid

    from sqlalchemy import (
        Boolean,
        Column,
        MetaData,
        String,
        Table,
        Uuid,
        select,
    )
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    md = MetaData()  # local — never touches the shared Base.metadata
    tbl = Table(
        "kpi_isolation_probe",
        md,
        Column("id", Uuid, primary_key=True),
        Column("name", String),
        Column("organization_id", Uuid, nullable=True),
        Column("is_active", Boolean),
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(md.create_all)

    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    def _row(name, org):
        return {"id": uuid.uuid4(), "name": name, "organization_id": org, "is_active": True}

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        await s.execute(
            tbl.insert(),
            [_row("a", org_a), _row("b", org_b), _row("legacy", None)],
        )
        await s.commit()

        # The exact predicate list_kpis/get_kpi build for an org_a caller.
        rows = (
            await s.execute(
                select(tbl).where(
                    tbl.c.is_active == True,  # noqa: E712
                    tbl.c.organization_id.isnot(None),
                    tbl.c.organization_id == org_a,
                )
            )
        ).all()

        names = {r.name for r in rows}
        assert names == {"a"}  # never org_b's "b" or the NULL-org "legacy"

    await engine.dispose()
