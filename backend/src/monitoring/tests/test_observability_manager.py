"""
Tests for Observability Manager
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.monitoring.services.observability_manager import ObservabilityManager
from src.monitoring.config.monitoring_config import MonitoringConfig
from src.monitoring.utils.exceptions import ObservabilityError


@pytest.fixture
def mock_config():
    """Create a mock monitoring configuration"""
    return MonitoringConfig(
        service_name="test-service",
        environment="test",
        debug=True
    )


@pytest.fixture
async def observability_manager(mock_config):
    """Create an observability manager instance"""
    manager = ObservabilityManager(mock_config)
    yield manager
    await manager.shutdown()


class TestObservabilityManager:
    """Test cases for ObservabilityManager"""

    @pytest.mark.asyncio
    async def test_initialization(self, observability_manager):
        """Test manager initialization"""
        await observability_manager.initialize()
        assert observability_manager._initialized

    @pytest.mark.asyncio
    async def test_start_stop(self, observability_manager):
        """Test starting and stopping the manager"""
        await observability_manager.start()
        assert observability_manager._running

        await observability_manager.stop()
        assert not observability_manager._running

    @pytest.mark.asyncio
    async def test_health_check(self, observability_manager):
        """Test health check functionality"""
        await observability_manager.start()

        health_status = await observability_manager.health_check()

        assert "manager" in health_status
        assert "services" in health_status
        assert health_status["manager"]["initialized"]
        assert health_status["manager"]["running"]

    @pytest.mark.asyncio
    async def test_record_metric(self, observability_manager):
        """Test metric recording"""
        await observability_manager.start()

        # Mock the metrics collector
        observability_manager.metrics_collector = AsyncMock()

        await observability_manager.record_metric(
            name="test_metric",
            value=42.5,
            labels={"test": "value"}
        )

        observability_manager.metrics_collector.record_metric.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_alert_rule(self, observability_manager):
        """Test alert rule creation"""
        await observability_manager.start()

        # Mock the alert handler
        observability_manager.alert_handler = AsyncMock()
        observability_manager.alert_handler.create_rule.return_value = "rule-123"

        rule_id = await observability_manager.create_alert_rule(
            name="Test Rule",
            conditions={"metric": "test_metric", "operator": ">", "value": 10},
            severity="high"
        )

        assert rule_id == "rule-123"
        observability_manager.alert_handler.create_rule.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_operation_context_manager(self, observability_manager):
        """Test trace operation context manager"""
        await observability_manager.start()

        # Mock the tracing collector
        observability_manager.tracing_collector = AsyncMock()
        mock_span_context = Mock()
        observability_manager.tracing_collector.start_span.return_value = mock_span_context

        async with observability_manager.trace_operation(
            operation_name="test_operation",
            service="test-service"
        ) as span_context:
            assert span_context == mock_span_context

        # Verify span was started and finished
        observability_manager.tracing_collector.start_span.assert_called_once()
        observability_manager.tracing_collector.finish_span.assert_called_once_with(
            mock_span_context, status="ok"
        )

    @pytest.mark.asyncio
    async def test_trace_operation_with_error(self, observability_manager):
        """Test trace operation context manager with error"""
        await observability_manager.start()

        # Mock the tracing collector
        observability_manager.tracing_collector = AsyncMock()
        mock_span_context = Mock()
        observability_manager.tracing_collector.start_span.return_value = mock_span_context

        with pytest.raises(ValueError):
            async with observability_manager.trace_operation(
                operation_name="test_operation",
                service="test-service"
            ):
                raise ValueError("Test error")

        # Verify span was finished with error status
        observability_manager.tracing_collector.finish_span.assert_called_once_with(
            mock_span_context, status="error", error="Test error"
        )

    @pytest.mark.asyncio
    async def test_get_metrics(self, observability_manager):
        """Test getting metrics"""
        await observability_manager.start()

        # Mock the metrics collector
        expected_metrics = {"metrics": {"test_metric": []}}
        observability_manager.metrics_collector = AsyncMock()
        observability_manager.metrics_collector.get_metrics.return_value = expected_metrics

        metrics = await observability_manager.get_metrics()

        assert metrics == expected_metrics
        observability_manager.metrics_collector.get_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_traces(self, observability_manager):
        """Test getting traces"""
        await observability_manager.start()

        # Mock the tracing collector
        expected_traces = {"traces": {"trace-123": {"spans": []}}}
        observability_manager.tracing_collector = AsyncMock()
        observability_manager.tracing_collector.get_traces.return_value = expected_traces

        traces = await observability_manager.get_traces()

        assert traces == expected_traces
        observability_manager.tracing_collector.get_traces.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_logs(self, observability_manager):
        """Test getting logs"""
        await observability_manager.start()

        # Mock the log aggregator
        expected_logs = {"logs": []}
        observability_manager.log_aggregator = AsyncMock()
        observability_manager.log_aggregator.get_logs.return_value = expected_logs

        logs = await observability_manager.get_logs()

        assert logs == expected_logs
        observability_manager.log_aggregator.get_logs.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_alerts(self, observability_manager):
        """Test getting alerts"""
        await observability_manager.start()

        # Mock the alert handler
        expected_alerts = {"alerts": {}}
        observability_manager.alert_handler = AsyncMock()
        observability_manager.alert_handler.get_alerts.return_value = expected_alerts

        alerts = await observability_manager.get_alerts()

        assert alerts == expected_alerts
        observability_manager.alert_handler.get_alerts.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, observability_manager):
        """Test alert acknowledgment"""
        await observability_manager.start()

        # Mock the alert handler
        observability_manager.alert_handler = AsyncMock()
        observability_manager.alert_handler.acknowledge_alert.return_value = True

        success = await observability_manager.acknowledge_alert(
            alert_id="alert-123",
            user="test-user",
            message="Acknowledged"
        )

        assert success
        observability_manager.alert_handler.acknowledge_alert.assert_called_once_with(
            alert_id="alert-123",
            user="test-user",
            message="Acknowledged"
        )

    @pytest.mark.asyncio
    async def test_resolve_alert(self, observability_manager):
        """Test alert resolution"""
        await observability_manager.start()

        # Mock the alert handler
        observability_manager.alert_handler = AsyncMock()
        observability_manager.alert_handler.resolve_alert.return_value = True

        success = await observability_manager.resolve_alert(
            alert_id="alert-123",
            user="test-user",
            message="Resolved"
        )

        assert success
        observability_manager.alert_handler.resolve_alert.assert_called_once_with(
            alert_id="alert-123",
            user="test-user",
            message="Resolved"
        )

    def test_create_correlation_id(self, observability_manager):
        """Test correlation ID creation"""
        correlation_id = observability_manager.create_correlation_id()

        assert isinstance(correlation_id, str)
        assert len(correlation_id) > 0

    @pytest.mark.asyncio
    async def test_initialization_failure(self, mock_config):
        """Test initialization failure handling"""
        # Mock a service to fail initialization
        with patch('src.monitoring.services.metrics_collector.MetricsCollector') as mock_metrics:
            mock_metrics.side_effect = Exception("Initialization failed")

            manager = ObservabilityManager(mock_config)

            with pytest.raises(ObservabilityError):
                await manager.initialize()

    @pytest.mark.asyncio
    async def test_double_initialization(self, observability_manager):
        """Test that double initialization is handled gracefully"""
        await observability_manager.initialize()

        # Should not raise an exception
        await observability_manager.initialize()

        assert observability_manager._initialized

    @pytest.mark.asyncio
    async def test_double_start(self, observability_manager):
        """Test that double start is handled gracefully"""
        await observability_manager.initialize()
        await observability_manager.start()

        # Should not raise an exception
        await observability_manager.start()

        assert observability_manager._running

    @pytest.mark.asyncio
    async def test_stop_without_start(self, observability_manager):
        """Test stopping without starting"""
        # Should not raise an exception
        await observability_manager.stop()

        assert not observability_manager._running

    @pytest.mark.asyncio
    async def test_get_service_health(self, observability_manager):
        """Test getting service health"""
        await observability_manager.start()

        # Mock the health check hub
        expected_health = {"overall_status": "healthy"}
        observability_manager.health_check_hub = AsyncMock()
        observability_manager.health_check_hub.get_overall_health.return_value = expected_health

        health = await observability_manager.get_service_health()

        assert health == expected_health
        observability_manager.health_check_hub.get_overall_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_background_task_management(self, observability_manager):
        """Test background task management"""
        await observability_manager.start()

        # Should have background tasks running
        assert len(observability_manager._background_tasks) > 0

        await observability_manager.stop()

        # Background tasks should be cleaned up
        assert len(observability_manager._background_tasks) == 0


if __name__ == "__main__":
    pytest.main([__file__])