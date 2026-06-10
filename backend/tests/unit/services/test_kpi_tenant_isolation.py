"""analytics_kpis must carry an organization_id for tenant isolation.

list_kpis/get_kpi returned every org's KPIs because the table had no tenant
column. These tests pin the new column on the model and the migration that
adds it (chained off the documented head).
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit


def test_kpi_model_has_organization_id_column():
    from src.models.analytics.analytics_models import AnalyticsKPI

    col = AnalyticsKPI.__table__.columns.get("organization_id")
    assert col is not None, "AnalyticsKPI needs an organization_id column"
    assert col.nullable is True  # backward-compat; reads filter NULL out
    assert col.index is True


_BACKEND = pathlib.Path(__file__).parents[3]


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
