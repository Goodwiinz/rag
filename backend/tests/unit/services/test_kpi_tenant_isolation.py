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


def test_migration_chains_off_documented_head():
    mig = (
        _BACKEND
        / "alembic/versions/a1b2c3d4e5f6_add_organization_id_to_analytics_kpis.py"
    )
    text = mig.read_text()
    assert 'revision = "a1b2c3d4e5f6"' in text
    assert 'down_revision = "z4a5b6c7d8e9"' in text
    # Adds the column + index, and is idempotent / reversible.
    assert "ADD COLUMN IF NOT EXISTS organization_id" in text
    assert "idx_analytics_kpis_organization_id" in text
    assert "def downgrade" in text
