
import sys
from unittest.mock import MagicMock, AsyncMock, call

# Mock out broken dependencies BEFORE importing metrics_service
sys.modules['src.services.analytics.dashboard_service'] = MagicMock()
sys.modules['src.models.analytics.dashboard_models'] = MagicMock()
sys.modules['src.services.analytics.graph_analytics_service'] = MagicMock()
sys.modules['src.services.analytics.realtime_service'] = MagicMock()
sys.modules['src.services.analytics.report_service'] = MagicMock()

import pytest
from uuid import uuid4
from datetime import datetime
from src.services.analytics.metrics_service import MetricsService, MetricResolution, AggregationType
from src.models.analytics.analytics_models import AnalyticsMetric, MetricAggregation

@pytest.mark.asyncio
async def test_aggregate_and_store_n_plus_one():
    service = MetricsService()

    # Mock DB Session
    mock_db = AsyncMock()

    # Mock Metric Lookup Result
    metric_id = uuid4()
    mock_metric = AnalyticsMetric(id=metric_id, name="test_metric")

    # Mock the scalar_one_or_none return for the metric query
    # and then for the aggregation queries.
    # The first call to execute is for the metric.
    # The subsequent calls are for the aggregations.

    # We need to simulate the return values.
    # 1. Metric lookup -> returns Result with scalar_one_or_none returning metric
    metric_result = MagicMock()
    metric_result.scalar_one_or_none.return_value = mock_metric

    # 2. Aggregation batch lookup -> return Result with scalars().all() returning [] (to simulate new aggregations)
    agg_result = MagicMock()
    agg_result.scalars.return_value.all.return_value = []

    # Configure execute side_effect
    mock_db.execute.side_effect = [metric_result, agg_result]

    # Input data
    resolution = MetricResolution.HOUR.value
    bucket_time = datetime.utcnow()
    dimensions = {"env": "prod"}
    key = f"{metric_id}:{resolution}:{bucket_time.isoformat()}:{hash(str(dimensions)) % 10000}"

    values = [
        {"value": 10, "dimensions": dimensions, "timestamp": bucket_time},
        {"value": 20, "dimensions": dimensions, "timestamp": bucket_time}
    ]

    # Run the method
    await service._aggregate_and_store(key, values, mock_db)

    # Check call count
    # 1 metric lookup + 1 aggregation batch lookup = 2 calls
    assert mock_db.execute.call_count == 2, f"Expected 2 DB calls, got {mock_db.execute.call_count}"

    # Also verify that we tried to add 5 new aggregations
    assert mock_db.add.call_count == 5
    assert mock_db.commit.call_count == 1
