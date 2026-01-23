"""
Unit tests for Performance Dashboard Service
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from src.services.quality.performance_dashboard_service import (
    PerformanceDashboardService,
    MetricTimeRange,
    SystemHealthMetrics,
    PerformanceMetrics,
    WidgetType,
    DashboardWidget
)
from src.schemas.performance_dashboard import (
    WidgetCreate,
    WidgetUpdate,
    PerformanceMetricData
)


class TestPerformanceDashboardService:
    """Test suite for PerformanceDashboardService"""

    @pytest.fixture
    def service(self):
        """Create a PerformanceDashboardService instance for testing."""
        return PerformanceDashboardService()

    @pytest.fixture
    def sample_system_health(self):
        """Sample system health metrics for testing."""
        return SystemHealthMetrics(
            cpu_usage=45.2,
            memory_usage=67.8,
            disk_usage=34.1,
            network_io=1024.5,
            active_connections=156,
            uptime_seconds=86400,
            load_average=[0.5, 0.7, 0.9],
            timestamp=datetime.utcnow()
        )

    @pytest.fixture
    def sample_performance_metrics(self):
        """Sample performance metrics for testing."""
        return PerformanceMetrics(
            total_searches=1234,
            avg_response_time=245.5,
            success_rate=0.985,
            error_rate=0.015,
            requests_per_second=45.6,
            p50_response_time=200,
            p95_response_time=500,
            p99_response_time=800,
            timestamp=datetime.utcnow()
        )

    @pytest.fixture
    def sample_widget(self):
        """Sample dashboard widget for testing."""
        return DashboardWidget(
            id="widget-123",
            name="Response Time Chart",
            widget_type=WidgetType.TIME_SERIES,
            metric_names=["response_time", "p95_response_time"],
            time_range=MetricTimeRange.LAST_24H,
            config={"refresh_interval": 60, "chart_type": "line"},
            organization_id="org-123",
            user_id="user-123",
            is_active=True,
            position={"x": 0, "y": 0, "width": 6, "height": 4}
        )

    # Test Initialization
    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.cache_ttl == 300
        assert service.metric_cache == {}
        assert service.widget_cache == {}
        assert service.redis_client is None

    # Test System Health Monitoring
    @pytest.mark.asyncio
    async def test_get_system_health_metrics(self, service, sample_system_health):
        """Test getting system health metrics."""
        with patch.object(service, '_collect_system_metrics') as mock_collect:
            mock_collect.return_value = sample_system_health

            result = await service.get_system_health_metrics()

            assert result.cpu_usage == 45.2
            assert result.memory_usage == 67.8
            assert result.disk_usage == 34.1
            assert result.active_connections == 156
            mock_collect.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_system_metrics_with_psutil(self, service, mock_psutil):
        """Test collecting system metrics with psutil available."""
        with patch('src.services.performance_dashboard_service.PSUTIL_AVAILABLE', True):
            with patch('src.services.performance_dashboard_service.psutil', mock_psutil):
                result = await service._collect_system_metrics()

                assert result.cpu_usage == 45.2
                assert result.memory_usage == 67.8
                assert result.disk_usage == 34.1
                assert result.network_io == 1024.5

    @pytest.mark.asyncio
    async def test_collect_system_metrics_fallback(self, service):
        """Test collecting system metrics with fallback (no psutil)."""
        with patch('src.services.performance_dashboard_service.PSUTIL_AVAILABLE', False):
            result = await service._collect_system_metrics()

            # Should return fallback values
            assert isinstance(result.cpu_usage, (int, float))
            assert isinstance(result.memory_usage, (int, float))
            assert isinstance(result.disk_usage, (int, float))
            assert 0 <= result.cpu_usage <= 100
            assert 0 <= result.memory_usage <= 100
            assert 0 <= result.disk_usage <= 100

    @pytest.mark.asyncio
    async def test_check_system_health_status(self, service, sample_system_health):
        """Test checking system health status."""
        result = await service.check_system_health_status(sample_system_health)

        assert "status" in result
        assert "issues" in result
        assert "recommendations" in result
        assert isinstance(result["status"], str)
        assert isinstance(result["issues"], list)

    @pytest.mark.asyncio
    async def test_check_system_health_critical_issues(self, service):
        """Test system health check with critical issues."""
        unhealthy_metrics = SystemHealthMetrics(
            cpu_usage=95.0,  # Critical
            memory_usage=98.0,  # Critical
            disk_usage=99.0,  # Critical
            network_io=5000.0,
            active_connections=1000,
            uptime_seconds=86400,
            load_average=[2.5, 2.7, 2.9],
            timestamp=datetime.utcnow()
        )

        result = await service.check_system_health_status(unhealthy_metrics)

        assert result["status"] in ["warning", "critical"]
        assert len(result["issues"]) > 0
        assert any("CPU" in issue for issue in result["issues"])

    # Test Performance Metrics
    @pytest.mark.asyncio
    async def test_get_search_performance_metrics(self, service, sample_performance_metrics):
        """Test getting search performance metrics."""
        organization_id = "org-123"
        time_range = MetricTimeRange.LAST_24H

        with patch.object(service, '_query_performance_metrics') as mock_query:
            mock_query.return_value = sample_performance_metrics

            result = await service.get_search_performance_metrics(
                organization_id=organization_id,
                time_range=time_range
            )

            assert result.total_searches == 1234
            assert result.avg_response_time == 245.5
            assert result.success_rate == 0.985
            mock_query.assert_called_once_with(organization_id, time_range)

    @pytest.mark.asyncio
    async def test_get_performance_trends(self, service):
        """Test getting performance trends."""
        organization_id = "org-123"
        metric_name = "response_time"
        time_range = MetricTimeRange.LAST_7D

        with patch.object(service, '_query_performance_trends') as mock_query:
            mock_trends = [
                {"timestamp": "2025-10-01T00:00:00Z", "value": 200},
                {"timestamp": "2025-10-02T00:00:00Z", "value": 220},
                {"timestamp": "2025-10-03T00:00:00Z", "value": 210}
            ]
            mock_query.return_value = mock_trends

            result = await service.get_performance_trends(
                organization_id=organization_id,
                metric_name=metric_name,
                time_range=time_range
            )

            assert len(result) == 3
            assert result[0]["value"] == 200
            assert result[0]["timestamp"] == "2025-10-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_calculate_performance_percentiles(self, service):
        """Test calculating performance percentiles."""
        response_times = [100, 150, 200, 250, 300, 350, 400, 450, 500, 1000]

        result = await service.calculate_performance_percentiles(response_times)

        assert result["p50"] == 275
        assert result["p95"] == 925
        assert result["p99"] == 1000
        assert result["min"] == 100
        assert result["max"] == 1000
        assert result["avg"] == 370

    @pytest.mark.asyncio
    async def test_get_slow_queries_analysis(self, service):
        """Test getting slow queries analysis."""
        organization_id = "org-123"
        threshold_ms = 1000

        with patch.object(service, '_query_slow_queries') as mock_query:
            mock_slow_queries = [
                {
                    "query": "complex search query",
                    "response_time": 1500,
                    "timestamp": "2025-10-09T21:41:00Z",
                    "user_id": "user-123",
                    "result_count": 500
                },
                {
                    "query": "another slow query",
                    "response_time": 1200,
                    "timestamp": "2025-10-09T20:30:00Z",
                    "user_id": "user-456",
                    "result_count": 300
                }
            ]
            mock_query.return_value = mock_slow_queries

            result = await service.get_slow_queries_analysis(
                organization_id=organization_id,
                threshold_ms=threshold_ms
            )

            assert len(result["slow_queries"]) == 2
            assert result["total_slow_queries"] == 2
            assert result["avg_response_time"] == 1350
            assert result["threshold_ms"] == threshold_ms

    # Test Dashboard Management
    @pytest.mark.asyncio
    async def test_get_dashboard_overview(self, service):
        """Test getting dashboard overview."""
        organization_id = "org-123"
        time_range = MetricTimeRange.LAST_24H

        with patch.object(service, 'get_system_health_metrics') as mock_health:
            with patch.object(service, 'get_search_performance_metrics') as mock_perf:
                with patch.object(service, 'get_quality_metrics_summary') as mock_quality:
                    with patch.object(service, 'get_user_engagement_metrics') as mock_engagement:

                        mock_health.return_value = Mock(cpu_usage=45.2, memory_usage=67.8)
                        mock_perf.return_value = Mock(total_searches=1234, avg_response_time=245.5)
                        mock_quality.return_value = Mock(accuracy_score=0.94, error_rate=0.015)
                        mock_engagement.return_value = Mock(active_users=89, satisfaction_rate=0.92)

                        result = await service.get_dashboard_overview(
                            organization_id=organization_id,
                            time_range=time_range
                        )

                        assert "system_health" in result
                        assert "search_performance" in result
                        assert "quality_metrics" in result
                        assert "user_engagement" in result

    @pytest.mark.asyncio
    async def test_create_dashboard_widget(self, service, sample_widget):
        """Test creating a dashboard widget."""
        widget_data = WidgetCreate(
            name="Response Time Chart",
            widget_type=WidgetType.TIME_SERIES,
            metric_names=["response_time"],
            time_range=MetricTimeRange.LAST_24H,
            config={"refresh_interval": 60}
        )

        with patch.object(service, '_store_widget') as mock_store:
            mock_store.return_value = sample_widget

            result = await service.create_dashboard_widget(
                organization_id="org-123",
                user_id="user-123",
                widget_data=widget_data.dict()
            )

            assert result.name == "Response Time Chart"
            assert result.widget_type == WidgetType.TIME_SERIES
            assert result.organization_id == "org-123"
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_widgets(self, service):
        """Test getting user widgets."""
        user_id = "user-123"

        with patch.object(service, '_query_user_widgets') as mock_query:
            mock_widgets = [Mock(), Mock(), Mock()]
            mock_query.return_value = mock_widgets

            result = await service.get_user_widgets(user_id)

            assert len(result) == 3
            mock_query.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_update_widget(self, service, sample_widget):
        """Test updating a widget."""
        update_data = WidgetUpdate(
            name="Updated Chart Name",
            config={"refresh_interval": 120}
        )

        with patch.object(service, '_update_widget_in_db') as mock_update:
            mock_update.return_value = True

            result = await service.update_dashboard_widget(
                widget_id=sample_widget.id,
                update_data=update_data.dict()
            )

            assert result is True
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_widget(self, service, sample_widget):
        """Test deleting a widget."""
        with patch.object(service, '_delete_widget_from_db') as mock_delete:
            mock_delete.return_value = True

            result = await service.delete_dashboard_widget(sample_widget.id)

            assert result is True
            mock_delete.assert_called_once_with(sample_widget.id)

    # Test Widget Data Generation
    @pytest.mark.asyncio
    async def test_get_widget_data(self, service, sample_widget):
        """Test getting widget data."""
        with patch.object(service, '_generate_widget_data') as mock_generate:
            mock_data = {
                "type": "time_series",
                "data": [
                    {"timestamp": "2025-10-09T20:00:00Z", "value": 200},
                    {"timestamp": "2025-10-09T21:00:00Z", "value": 220}
                ],
                "metadata": {"refresh_interval": 60}
            }
            mock_generate.return_value = mock_data

            result = await service.get_widget_data(sample_widget.id)

            assert result["type"] == "time_series"
            assert len(result["data"]) == 2
            assert "metadata" in result
            mock_generate.assert_called_once_with(sample_widget)

    @pytest.mark.asyncio
    async def test_generate_time_series_data(self, service):
        """Test generating time series data."""
        metric_name = "response_time"
        time_range = MetricTimeRange.LAST_24H

        with patch.object(service, '_query_time_series_data') as mock_query:
            mock_data = [
                {"timestamp": datetime.utcnow() - timedelta(hours=i), "value": 200 + i}
                for i in range(24)
            ]
            mock_query.return_value = mock_data

            result = await service._generate_time_series_data(metric_name, time_range)

            assert "data_points" in result
            assert "time_range" in result
            assert "metric_name" in result
            assert len(result["data_points"]) == 24

    @pytest.mark.asyncio
    async def test_generate_gauge_data(self, service):
        """Test generating gauge data."""
        metric_name = "cpu_usage"
        current_value = 45.2
        max_value = 100

        result = await service._generate_gauge_data(metric_name, current_value, max_value)

        assert result["type"] == "gauge"
        assert result["current_value"] == current_value
        assert result["max_value"] == max_value
        assert result["percentage"] == 45.2
        assert "status" in result

    @pytest.mark.asyncio
    async def test_generate_table_data(self, service):
        """Test generating table data."""
        metric_names = ["response_time", "error_rate", "throughput"]
        time_range = MetricTimeRange.LAST_24H

        with patch.object(service, '_query_metrics_summary') as mock_query:
            mock_summary = {
                "response_time": {"current": 245, "avg": 220, "trend": "up"},
                "error_rate": {"current": 0.015, "avg": 0.012, "trend": "down"},
                "throughput": {"current": 45.6, "avg": 42.3, "trend": "stable"}
            }
            mock_query.return_value = mock_summary

            result = await service._generate_table_data(metric_names, time_range)

            assert result["type"] == "table"
            assert "columns" in result
            assert "rows" in result
            assert len(result["rows"]) == 3

    # Test Caching
    @pytest.mark.asyncio
    async def test_cache_widget_data(self, service, mock_redis_client):
        """Test caching widget data."""
        service.redis_client = mock_redis_client
        widget_id = "widget-123"
        data = {"type": "time_series", "data": []}

        await service._cache_widget_data(widget_id, data, ttl=300)

        mock_redis_client.set.assert_called_once()
        mock_redis_client.expire.assert_called_once_with(widget_id, 300)

    @pytest.mark.asyncio
    async def test_get_cached_widget_data(self, service, mock_redis_client):
        """Test getting cached widget data."""
        service.redis_client = mock_redis_client
        widget_id = "widget-123"
        cached_data = json.dumps({"type": "time_series", "data": []})

        mock_redis_client.get.return_value = cached_data

        result = await service._get_cached_widget_data(widget_id)

        assert result["type"] == "time_series"
        mock_redis_client.get.assert_called_once_with(widget_id)

    # Test Alerting
    @pytest.mark.asyncio
    async def test_check_performance_alerts(self, service):
        """Test checking performance alerts."""
        organization_id = "org-123"

        with patch.object(service, 'get_system_health_metrics') as mock_health:
            with patch.object(service, 'get_search_performance_metrics') as mock_perf:
                mock_health.return_value = Mock(cpu_usage=95.0, memory_usage=98.0)
                mock_perf.return_value = Mock(avg_response_time=1500, error_rate=0.05)

                alerts = await service.check_performance_alerts(organization_id)

                assert isinstance(alerts, list)
                # Should generate alerts for high CPU, memory, response time, and error rate
                assert len(alerts) >= 2

    @pytest.mark.asyncio
    async def test_create_performance_alert(self, service):
        """Test creating a performance alert."""
        alert_data = {
            "type": "performance",
            "severity": "warning",
            "title": "High CPU Usage",
            "message": "CPU usage exceeded 90%",
            "threshold": 90.0,
            "current_value": 95.0,
            "organization_id": "org-123"
        }

        with patch.object(service, '_store_alert') as mock_store:
            mock_store.return_value = Mock(id="alert-123")

            result = await service.create_performance_alert(alert_data)

            assert result.id == "alert-123"
            mock_store.assert_called_once()

    # Test Data Export
    @pytest.mark.asyncio
    async def test_export_performance_data(self, service):
        """Test exporting performance data."""
        organization_id = "org-123"
        time_range = MetricTimeRange.LAST_7D
        format_type = "json"

        with patch.object(service, 'get_performance_trends') as mock_trends:
            with patch.object(service, 'get_search_performance_metrics') as mock_metrics:
                mock_trends.return_value = [
                    {"timestamp": "2025-10-01T00:00:00Z", "value": 200}
                ]
                mock_metrics.return_value = Mock(total_searches=1234, avg_response_time=245.5)

                result = await service.export_performance_data(
                    organization_id=organization_id,
                    time_range=time_range,
                    format=format_type
                )

                assert "data" in result
                assert "metadata" in result
                assert result["metadata"]["organization_id"] == organization_id
                assert result["metadata"]["time_range"] == time_range.value

    # Test Error Handling
    @pytest.mark.asyncio
    async def test_database_error_handling(self, service):
        """Test handling of database errors."""
        with patch.object(service, '_store_widget') as mock_store:
            mock_store.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception, match="Database connection failed"):
                await service.create_dashboard_widget(
                    organization_id="org-123",
                    user_id="user-123",
                    widget_data={"name": "test", "widget_type": "time_series"}
                )

    @pytest.mark.asyncio
    async def test_invalid_widget_type(self, service):
        """Test handling of invalid widget type."""
        with pytest.raises(ValueError, match="Invalid widget type"):
            await service._generate_widget_data(
                Mock(widget_type="invalid_type", metric_names=["test"])
            )

    # Test Performance
    @pytest.mark.asyncio
    async def test_concurrent_widget_data_generation(self, service):
        """Test concurrent widget data generation."""
        import asyncio

        widgets = [
            Mock(id=f"widget-{i}", widget_type=WidgetType.TIME_SERIES, metric_names=["test"])
            for i in range(10)
        ]

        with patch.object(service, '_generate_time_series_data') as mock_generate:
            mock_generate.return_value = {"data_points": []}

            start_time = asyncio.get_event_loop().time()
            tasks = [service.get_widget_data(widget.id) for widget in widgets]
            results = await asyncio.gather(*tasks)
            end_time = asyncio.get_event_loop().time()

            assert len(results) == 10
            assert end_time - start_time < 5.0  # Should complete within 5 seconds

    # Test Default Widgets
    @pytest.mark.asyncio
    async def test_get_default_widgets(self, service):
        """Test getting default widgets."""
        result = await service.get_default_widgets()

        assert isinstance(result, list)
        assert len(result) > 0

        # Check for expected default widgets
        widget_types = [widget.widget_type for widget in result]
        assert WidgetType.TIME_SERIES in widget_types
        assert WidgetType.GAUGE in widget_types
        assert WidgetType.TABLE in widget_types

    @pytest.mark.asyncio
    async def test_create_default_widgets_for_user(self, service):
        """Test creating default widgets for a new user."""
        user_id = "user-123"
        organization_id = "org-123"

        with patch.object(service, 'create_dashboard_widget') as mock_create:
            mock_create.return_value = Mock(id="widget-123")

            result = await service.create_default_widgets_for_user(user_id, organization_id)

            assert isinstance(result, list)
            assert len(result) > 0
            assert mock_create.call_count > 0