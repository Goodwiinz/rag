"""quality_metrics.metric_type must be a free-form string, not a bound enum.

The search-analytics writer stores labels ("response_time", "result_count",
"result_diversity", "avg_relevance_score", "freshness") that are NOT members of
the MetricType enum. A native PG enum column rejected them and 500'd
POST /metrics/search. metric_type is now String(50), so any label persists and
the str-typed API response serializes cleanly.
"""

from __future__ import annotations

import pytest
from sqlalchemy import String
from sqlalchemy.sql.sqltypes import Enum as SAEnum

pytestmark = pytest.mark.unit

from src.models.quality import QualityMetric


def test_metric_type_column_is_string_not_enum():
    col = QualityMetric.__table__.columns["metric_type"]
    assert isinstance(col.type, String), f"metric_type is {col.type!r}, expected String"
    assert not isinstance(col.type, SAEnum)


@pytest.mark.parametrize(
    "label",
    [
        "response_time",
        "result_count",
        "result_diversity",
        "avg_relevance_score",
        "freshness",
        "precision",  # legacy MetricType member still fine as a plain string
    ],
)
def test_construct_with_writer_labels(label):
    m = QualityMetric(
        metric_type=label,
        metric_value=1.0,
        organization_id="00000000-0000-0000-0000-000000000000",
    )
    assert m.metric_type == label
