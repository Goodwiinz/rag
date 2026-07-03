"""QualityMetric must carry the search-metric columns the API + writer use.

collect_search_metrics constructs QualityMetric with metric_value/metric_unit/
query/search_type/search_query_id/user_id/measured_at/is_threshold_violation/
evaluation_metadata, and the /analytics/quality endpoints read them. Before this
change none existed on the model -> every read/write 500'd. This pins that the
model exposes them (and that the reserved `.metadata` trap is avoided by using
evaluation_metadata) and that the legacy NOT-NULL columns are relaxed so a
search-metric row constructs cleanly.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

from src.models.quality import QualityMetric

NEW_COLUMNS = {
    "metric_value",
    "metric_unit",
    "query",
    "search_type",
    "search_query_id",
    "user_id",
    "measured_at",
    "is_threshold_violation",
}


def test_model_exposes_search_metric_columns():
    cols = set(QualityMetric.__table__.columns.keys())
    missing = NEW_COLUMNS - cols
    assert not missing, f"QualityMetric missing columns: {missing}"


def test_legacy_notnull_columns_relaxed():
    # metric_name/value/evaluation_type/scope must be nullable so a search-metric
    # row (which doesn't populate them) can insert.
    for name in ("metric_name", "value", "evaluation_type", "scope"):
        assert QualityMetric.__table__.columns[name].nullable is True, name


def test_construct_with_search_metric_kwargs():
    # mirrors collect_search_metrics — must not raise on unknown kwargs
    m = QualityMetric(
        metric_type="latency",
        metric_value=12.5,
        metric_unit="ms",
        search_query_id=None,
        query="what is rag",
        search_type="hybrid",
        user_id=None,
        organization_id="00000000-0000-0000-0000-000000000000",
        evaluation_metadata={"model_used": "x"},
        measured_at=datetime.now(timezone.utc),
        is_threshold_violation=False,
    )
    assert m.metric_value == 12.5
    # `.evaluation_metadata` is a real column (not the reserved MetaData registry)
    assert m.evaluation_metadata == {"model_used": "x"}


def test_metadata_attr_is_reserved_not_a_column():
    # sanity: `.metadata` is SQLAlchemy's registry, not our data — hence we route
    # through evaluation_metadata everywhere.
    assert "metadata" not in QualityMetric.__table__.columns.keys()
