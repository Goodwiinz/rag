"""
Unit tests for Quality Metrics Service
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from src.services.quality_metrics_service import (
    QualityMetricsService,
    MetricType,
    MetricScope,
    MetricTimeRange,
    QualityMetric,
    QualityAlert
)
from src.schemas.quality_metrics import (
    MetricQuery,
    MetricCreate,
    AlertCreate,
    MetricAggregation
)


class TestQualityMetricsService:
    """Test suite for QualityMetricsService"""

    @pytest.fixture
    def service(self):
        """Create a QualityMetricsService instance for testing."""
        return QualityMetricsService()

    @pytest.fixture
    def sample_metric(self):
        """Sample metric data for testing."""
        return QualityMetric(
            id="metric-123",
            name="search_accuracy",
            value=0.94,
            metric_type=MetricType.CUSTOM,
            scope=MetricScope.QUERY,
            organization_id="org-123",
            search_query_id="query-123",
            metadata={"model": "gpt-4", "version": "v1.0"},
            timestamp=datetime.utcnow()
        )

    @pytest.fixture
    def sample_alert(self):
        """Sample alert data for testing."""
        return QualityAlert(
            id="alert-123",
            name="high_response_time",
            alert_type=MetricType.CUSTOM,
            threshold_value=1.0,
            current_value=1.5,
            severity="warning",
            organization_id="org-123",
            is_active=True,
            message="Response time exceeded threshold"
        )

    # Test Initialization
    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.cache_ttl == 3600
        assert service.metric_cache == {}
        assert service.alert_cache == {}
        assert service.redis_client is None

    # Test Metric Collection
    @pytest.mark.asyncio
    async def test_collect_metric_success(self, service, sample_metric):
        """Test successful metric collection."""
        with patch.object(service, '_store_metric') as mock_store:
            mock_store.return_value = sample_metric

            result = await service.collect_metric(
                name="search_accuracy",
                value=0.94,
                metric_type=MetricType.CUSTOM,
                scope=MetricScope.QUERY,
                organization_id="org-123",
                search_query_id="query-123",
                metadata={"model": "gpt-4"}
            )

            assert result.name == "search_accuracy"
            assert result.value == 0.94
            assert result.organization_id == "org-123"
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_metric_with_validation(self, service):
        """Test metric collection with validation."""
        # Test invalid metric name
        with pytest.raises(ValueError, match="Metric name cannot be empty"):
            await service.collect_metric(
                name="",
                value=0.94,
                metric_type=MetricType.CUSTOM,
                organization_id="org-123"
            )

        # Test invalid value type
        with pytest.raises(ValueError, match="Metric value must be numeric"):
            await service.collect_metric(
                name="test_metric",
                value="invalid",
                metric_type=MetricType.CUSTOM,
                organization_id="org-123"
            )

        # Test missing organization_id
        with pytest.raises(ValueError, match="Organization ID is required"):
            await service.collect_metric(
                name="test_metric",
                value=0.94,
                metric_type=MetricType.CUSTOM,
                organization_id=""
            )

    @pytest.mark.asyncio
    async def test_collect_metrics_batch(self, service):
        """Test batch metric collection."""
        metrics_data = [
            {
                "name": "search_accuracy",
                "value": 0.94,
                "metric_type": MetricType.CUSTOM,
                "organization_id": "org-123"
            },
            {
                "name": "response_time",
                "value": 245,
                "metric_type": MetricType.PERFORMANCE,
                "organization_id": "org-123"
            }
        ]

        with patch.object(service, 'collect_metric') as mock_collect:
            mock_collect.return_value = Mock()

            results = await service.collect_metrics_batch(metrics_data)

            assert len(results) == 2
            assert mock_collect.call_count == 2

    # Test Metric Retrieval
    @pytest.mark.asyncio
    async def test_get_metrics_by_organization(self, service):
        """Test retrieving metrics by organization."""
        organization_id = "org-123"
        time_range = MetricTimeRange.LAST_24H

        with patch.object(service, '_query_metrics_from_db') as mock_query:
            mock_metrics = [Mock(), Mock(), Mock()]
            mock_query.return_value = mock_metrics

            results = await service.get_metrics_by_organization(
                organization_id=organization_id,
                time_range=time_range,
                metric_type=MetricType.CUSTOM
            )

            assert len(results) == 3
            mock_query.assert_called_once_with(
                organization_id=organization_id,
                time_range=time_range,
                metric_type=MetricType.CUSTOM
            )

    @pytest.mark.asyncio
    async def test_get_metric_summary(self, service):
        """Test getting metric summary statistics."""
        organization_id = "org-123"

        with patch.object(service, 'get_metrics_by_organization') as mock_get_metrics:
            mock_metrics = [
                Mock(value=0.94, name="accuracy"),
                Mock(value=0.89, name="accuracy"),
                Mock(value=0.96, name="accuracy"),
                Mock(value=245, name="response_time"),
                Mock(value=220, name="response_time")
            ]
            mock_get_metrics.return_value = mock_metrics

            summary = await service.get_metric_summary(
                organization_id=organization_id,
                metric_type=MetricType.CUSTOM
            )

            assert summary["total_metrics"] == 5
            assert summary["unique_metric_names"] == 2
            assert "accuracy" in summary["metric_stats"]
            assert "response_time" in summary["metric_stats"]

            accuracy_stats = summary["metric_stats"]["accuracy"]
            assert accuracy_stats["count"] == 3
            assert accuracy_stats["avg"] == pytest.approx(0.93, rel=1e-2)

    @pytest.mark.asyncio
    async def test_get_metrics_aggregations(self, service):
        """Test metric aggregations."""
        organization_id = "org-123"
        aggregation = MetricAggregation(
            metric_name="search_accuracy",
            aggregation_type="avg",
            time_range=MetricTimeRange.LAST_7D
        )

        with patch.object(service, '_calculate_aggregation') as mock_calc:
            mock_calc.return_value = 0.92

            result = await service.get_metrics_aggregations(
                organization_id=organization_id,
                aggregations=[aggregation]
            )

            assert len(result) == 1
            assert result[0]["metric_name"] == "search_accuracy"
            assert result[0]["value"] == 0.92
            assert result[0]["aggregation_type"] == "avg"

    # Test Alert Management
    @pytest.mark.asyncio
    async def test_create_alert(self, service):
        """Test creating an alert."""
        alert_data = AlertCreate(
            name="high_response_time",
            metric_type=MetricType.PERFORMANCE,
            threshold_value=500.0,
            comparison_operator="gt",
            severity="warning",
            organization_id="org-123"
        )

        with patch.object(service, '_store_alert') as mock_store:
            mock_alert = Mock(id="alert-123")
            mock_store.return_value = mock_alert

            result = await service.create_alert(alert_data.dict())

            assert result.id == "alert-123"
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_alert_conditions(self, service, sample_alert):
        """Test checking alert conditions."""
        current_value = 600.0  # Above threshold of 500.0

        result = await service.check_alert_conditions(sample_alert, current_value)

        assert result["should_trigger"] is True
        assert result["current_value"] == current_value
        assert result["threshold"] == sample_alert.threshold_value

    @pytest.mark.asyncio
    async def test_check_alert_conditions_no_trigger(self, service, sample_alert):
        """Test alert conditions when threshold not exceeded."""
        current_value = 400.0  # Below threshold of 500.0

        result = await service.check_alert_conditions(sample_alert, current_value)

        assert result["should_trigger"] is False
        assert result["current_value"] == current_value

    @pytest.mark.asyncio
    async def test_get_active_alerts(self, service):
        """Test retrieving active alerts."""
        organization_id = "org-123"

        with patch.object(service, '_query_alerts_from_db') as mock_query:
            mock_alerts = [Mock(), Mock()]
            mock_query.return_value = mock_alerts

            result = await service.get_active_alerts(organization_id)

            assert len(result) == 2
            mock_query.assert_called_once_with(organization_id, active_only=True)

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, service, sample_alert):
        """Test acknowledging an alert."""
        user_id = "user-123"

        with patch.object(service, '_update_alert_status') as mock_update:
            mock_update.return_value = True

            result = await service.acknowledge_alert(
                alert_id=sample_alert.id,
                user_id=user_id
            )

            assert result is True
            mock_update.assert_called_once_with(
                alert_id=sample_alert.id,
                status="acknowledged",
                user_id=user_id
            )

    # Test Caching
    @pytest.mark.asyncio
    async def test_cache_hit(self, service, mock_redis_client):
        """Test cache hit scenario."""
        service.redis_client = mock_redis_client
        cache_key = "test_key"
        cached_data = json.dumps({"test": "data"})

        mock_redis_client.get.return_value = cached_data

        result = await service._get_from_cache(cache_key)

        assert result == {"test": "data"}
        mock_redis_client.get.assert_called_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_cache_miss(self, service, mock_redis_client):
        """Test cache miss scenario."""
        service.redis_client = mock_redis_client
        cache_key = "test_key"

        mock_redis_client.get.return_value = None

        result = await service._get_from_cache(cache_key)

        assert result is None
        mock_redis_client.get.assert_called_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_set_cache(self, service, mock_redis_client):
        """Test setting cache data."""
        service.redis_client = mock_redis_client
        cache_key = "test_key"
        data = {"test": "data"}
        ttl = 300

        await service._set_cache(cache_key, data, ttl)

        mock_redis_client.set.assert_called_once()
        mock_redis_client.expire.assert_called_once_with(cache_key, ttl)

    # Test Analytics
    @pytest.mark.asyncio
    async def test_get_quality_trends(self, service):
        """Test getting quality trends."""
        organization_id = "org-123"
        metric_name = "search_accuracy"
        time_range = MetricTimeRange.LAST_30D

        with patch.object(service, '_query_trends_from_db') as mock_query:
            mock_trends = [
                {"date": "2025-10-01", "value": 0.92},
                {"date": "2025-10-02", "value": 0.94},
                {"date": "2025-10-03", "value": 0.93}
            ]
            mock_query.return_value = mock_trends

            result = await service.get_quality_trends(
                organization_id=organization_id,
                metric_name=metric_name,
                time_range=time_range
            )

            assert len(result) == 3
            assert result[0]["date"] == "2025-10-01"
            assert result[0]["value"] == 0.92

    @pytest.mark.asyncio
    async def test_get_quality_insights(self, service):
        """Test getting quality insights."""
        organization_id = "org-123"

        with patch.object(service, '_analyze_quality_patterns') as mock_analyze:
            mock_insights = {
                "trends": {"improving": ["accuracy"], "declining": ["response_time"]},
                "anomalies": [{"date": "2025-10-01", "metric": "accuracy", "value": 0.65}],
                "recommendations": ["Optimize search parameters", "Update content"]
            }
            mock_analyze.return_value = mock_insights

            result = await service.get_quality_insights(organization_id)

            assert "trends" in result
            assert "anomalies" in result
            assert "recommendations" in result
            assert len(result["trends"]["improving"]) == 1

    # Test Error Handling
    @pytest.mark.asyncio
    async def test_database_error_handling(self, service):
        """Test handling of database errors."""
        with patch.object(service, '_store_metric') as mock_store:
            mock_store.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception, match="Database connection failed"):
                await service.collect_metric(
                    name="test_metric",
                    value=0.94,
                    metric_type=MetricType.CUSTOM,
                    organization_id="org-123"
                )

    @pytest.mark.asyncio
    async def test_invalid_time_range(self, service):
        """Test handling of invalid time range."""
        with pytest.raises(ValueError, match="Invalid time range"):
            await service.get_metrics_by_organization(
                organization_id="org-123",
                time_range="invalid_range"
            )

    # Test Data Validation
    @pytest.mark.asyncio
    async def test_metric_data_validation(self, service):
        """Test metric data validation."""
        # Test negative values for metrics that shouldn't be negative
        with pytest.raises(ValueError, match="Metric value cannot be negative"):
            await service.collect_metric(
                name="accuracy",
                value=-0.1,
                metric_type=MetricType.CUSTOM,
                organization_id="org-123"
            )

        # Test extremely large values
        with pytest.raises(ValueError, match="Metric value too large"):
            await service.collect_metric(
                name="response_time",
                value=1_000_000,  # 1 million seconds
                metric_type=MetricType.PERFORMANCE,
                organization_id="org-123"
            )

    # Test Performance
    @pytest.mark.asyncio
    async def test_batch_collection_performance(self, service):
        """Test performance of batch metric collection."""
        import time

        # Create 1000 metrics
        metrics_data = [
            {
                "name": f"metric_{i}",
                "value": i * 0.1,
                "metric_type": MetricType.CUSTOM,
                "organization_id": "org-123"
            }
            for i in range(1000)
        ]

        with patch.object(service, 'collect_metric') as mock_collect:
            mock_collect.return_value = Mock()

            start_time = time.time()
            results = await service.collect_metrics_batch(metrics_data)
            end_time = time.time()

            assert len(results) == 1000
            assert end_time - start_time < 5.0  # Should complete within 5 seconds

    # Test Integration with External Services
    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, service):
        """Test handling of Redis connection failure."""
        service.redis_client = AsyncMock()
        service.redis_client.get.side_effect = Exception("Redis connection failed")

        # Should not raise exception, should fall back to no cache
        result = await service._get_from_cache("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_metric_export(self, service):
        """Test exporting metrics data."""
        organization_id = "org-123"

        with patch.object(service, 'get_metrics_by_organization') as mock_get_metrics:
            mock_metrics = [
                Mock(
                    name="accuracy",
                    value=0.94,
                    timestamp=datetime.utcnow(),
                    metadata={"model": "gpt-4"}
                ),
                Mock(
                    name="response_time",
                    value=245,
                    timestamp=datetime.utcnow(),
                    metadata={"endpoint": "/search"}
                )
            ]
            mock_get_metrics.return_value = mock_metrics

            result = await service.export_metrics(
                organization_id=organization_id,
                format="json"
            )

            assert "metrics" in result
            assert "export_timestamp" in result
            assert "organization_id" in result
            assert len(result["metrics"]) == 2