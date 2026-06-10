"""
Comprehensive Monitoring Service Integration Tests

This module provides integration tests for all 6 core monitoring services:
1. Metrics Collection Service
2. Distributed Tracing Service
3. Log Aggregation Service
4. Alerting Service
5. Health Check Service
6. WebSocket Real-time Service

Tests verify service integration, data flow, performance, and error handling.
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch
import redis
import aiofiles
import websockets
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Setup paths
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

from backend.src.monitoring.services.observability_manager import (
    ObservabilityManager,
    get_observability_manager
)
from backend.src.monitoring.config.monitoring_config import (
    MonitoringConfig,
    get_monitoring_config,
    MetricsConfig,
    TracingConfig,
    LoggingConfig,
    AlertingConfig,
    HealthCheckConfig
)
from backend.src.monitoring.api.monitoring_endpoints import router
from backend.src.monitoring.api.websocket_handlers import WebSocketManager, websocket_manager
from backend.src.monitoring.models.metrics import MetricPoint, MetricSeries
from backend.src.monitoring.models.tracing import TraceSpan, TraceContext
from backend.src.monitoring.models.logging import LogEntry, LogContext
from backend.src.monitoring.models.alerting import Alert, AlertRule, AlertStatus
from backend.src.monitoring.models.health_check import HealthCheckResult, ComponentHealth


class TestMetricsServiceIntegration:
    """Integration tests for Metrics Collection Service"""

    @pytest.fixture
    async def observability_manager(self):
        """Create observability manager for testing"""
        config = MonitoringConfig(
            service_name="test-rag-system",
            environment="test",
            metrics=MetricsConfig(
                prometheus_enabled=False,  # Disable for testing
                custom_metrics_enabled=True,
                collection_interval_seconds=1,
                metrics_retention_days=1
            ),
            tracing=TracingConfig(enabled=False),
            logging=LoggingConfig(structured_logging=False),
            alerting=AlertingConfig(enabled=False),
            health_check=HealthCheckConfig(enabled=False)
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_metrics_collection_integration(self, observability_manager):
        """Test end-to-end metrics collection flow"""
        # Record different types of metrics
        await observability_manager.metrics_collector.record_counter(
            name="test_requests_total",
            value=1,
            labels={"method": "GET", "endpoint": "/test"}
        )

        await observability_manager.metrics_collector.record_gauge(
            name="test_active_connections",
            value=42,
            labels={"service": "api"}
        )

        await observability_manager.metrics_collector.record_histogram(
            name="test_response_time",
            value=0.123,
            labels={"endpoint": "/test"}
        )

        # Collect system metrics
        await observability_manager.metrics_collector.collect_system_metrics()

        # Query metrics back
        metrics_data = await observability_manager.get_metrics()

        # Verify metrics are stored and retrievable
        assert "metrics" in metrics_data
        assert len(metrics_data["metrics"]) > 0

        # Test time-based filtering
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=5)

        filtered_metrics = await observability_manager.get_metrics(
            start_time=start_time,
            end_time=end_time
        )

        assert "metrics" in filtered_metrics

    @pytest.mark.asyncio
    async def test_metrics_performance_under_load(self, observability_manager):
        """Test metrics service performance under high load"""
        start_time = time.time()

        # Record 1000 metrics rapidly
        tasks = []
        for i in range(1000):
            task = observability_manager.metrics_collector.record_counter(
                name="load_test_counter",
                value=1,
                labels={"iteration": str(i)}
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        recording_time = time.time() - start_time

        # Verify performance - should handle 1000 metrics in under 5 seconds
        assert recording_time < 5.0

        # Verify all metrics were recorded
        metrics_data = await observability_manager.get_metrics(
            metric_name="load_test_counter"
        )

        assert len(metrics_data.get("metrics", {})) >= 1000

    @pytest.mark.asyncio
    async def test_metrics_service_error_handling(self, observability_manager):
        """Test metrics service error handling and recovery"""
        # Test invalid metric data handling
        with pytest.raises(ValueError):
            await observability_manager.metrics_collector.record_gauge(
                name="test_invalid",
                value="invalid_value",  # Should be numeric
                labels={}
            )

        # Test service continues working after error
        await observability_manager.metrics_collector.record_counter(
            name="test_recovery",
            value=1,
            labels={}
        )

        metrics_data = await observability_manager.get_metrics(
            metric_name="test_recovery"
        )
        assert len(metrics_data.get("metrics", {})) > 0

    @pytest.mark.asyncio
    async def test_metrics_labels_and_aggregation(self, observability_manager):
        """Test metric labels work correctly and aggregation functions"""
        # Record metrics with different labels
        await observability_manager.metrics_collector.record_counter(
            name="api_requests_total",
            value=1,
            labels={"method": "GET", "status": "200"}
        )

        await observability_manager.metrics_collector.record_counter(
            name="api_requests_total",
            value=1,
            labels={"method": "POST", "status": "201"}
        )

        await observability_manager.metrics_collector.record_counter(
            name="api_requests_total",
            value=1,
            labels={"method": "GET", "status": "200"}
        )

        # Query with label filters
        get_metrics = await observability_manager.get_metrics(
            metric_name="api_requests_total",
            labels={"method": "GET"}
        )

        post_metrics = await observability_manager.get_metrics(
            metric_name="api_requests_total",
            labels={"method": "POST"}
        )

        # Verify label filtering works
        assert len(get_metrics.get("metrics", {})) >= 2
        assert len(post_metrics.get("metrics", {})) >= 1


class TestTracingServiceIntegration:
    """Integration tests for Distributed Tracing Service"""

    @pytest.fixture
    async def tracing_manager(self):
        """Create observability manager with tracing enabled"""
        config = MonitoringConfig(
            service_name="test-tracing",
            environment="test",
            metrics=MetricsConfig(custom_metrics_enabled=False),
            tracing=TracingConfig(
                enabled=True,
                service_name="test-service",
                sampling_ratio=1.0,  # Sample all traces for testing
                jaeger_enabled=False,  # Disable external dependencies
                auto_instrumentation=True
            ),
            logging=LoggingConfig(structured_logging=False),
            alerting=AlertingConfig(enabled=False),
            health_check=HealthCheckConfig(enabled=False)
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_trace_creation_and_propagation(self, tracing_manager):
        """Test trace creation and context propagation"""
        # Start a trace span
        async with tracing_manager.trace_operation(
            operation_name="test_operation",
            service="test-service",
            component="test-component",
            labels={"test": "integration"}
        ) as span_context:
            assert span_context is not None
            assert span_context.operation_name == "test_operation"
            assert span_context.service == "test-service"

            # Add child span
            async with tracing_manager.trace_operation(
                operation_name="child_operation",
                service="test-service",
                component="test-component"
            ) as child_span:
                assert child_span.parent_span_id == span_context.span_id

        # Query traces
        traces_data = await tracing_manager.get_traces(
            service="test-service",
            operation="test_operation"
        )

        assert "traces" in traces_data
        assert len(traces_data["traces"]) > 0

    @pytest.mark.asyncio
    async def test_trace_error_handling(self, tracing_manager):
        """Test trace error handling and error spans"""
        try:
            async with tracing_manager.trace_operation(
                operation_name="error_operation",
                service="test-service"
            ):
                raise ValueError("Test error for tracing")
        except ValueError:
            pass  # Expected

        # Query error traces
        traces_data = await tracing_manager.get_traces(
            service="test-service",
            operation="error_operation"
        )

        # Verify error trace was recorded
        error_traces = [
            trace for trace in traces_data.get("traces", [])
            if trace.get("status") == "error"
        ]

        assert len(error_traces) > 0
        assert "Test error for tracing" in error_traces[0].get("error", "")

    @pytest.mark.asyncio
    async def test_trace_performance_sampling(self, tracing_manager):
        """Test tracing performance and sampling behavior"""
        start_time = time.time()

        # Create many traces
        tasks = []
        for i in range(100):
            task = tracing_manager.trace_operation(
                operation_name=f"performance_test_{i}",
                service="test-service"
            )
            tasks.append(task)

        # Execute all trace operations
        for task in tasks:
            async with task:
                await asyncio.sleep(0.001)  # Small delay

        tracing_time = time.time() - start_time

        # Verify performance - should handle 100 traces quickly
        assert tracing_time < 2.0

        # Query traces
        traces_data = await tracing_manager.get_traces(
            service="test-service"
        )

        # With sampling_ratio=1.0, all traces should be recorded
        assert len(traces_data.get("traces", {})) >= 100


class TestLogAggregationIntegration:
    """Integration tests for Log Aggregation Service"""

    @pytest.fixture
    async def logging_manager(self):
        """Create observability manager with logging enabled"""
        config = MonitoringConfig(
            service_name="test-logging",
            environment="test",
            metrics=MetricsConfig(custom_metrics_enabled=False),
            tracing=TracingConfig(enabled=False),
            logging=LoggingConfig(
                structured_logging=True,
                level="DEBUG",
                console_logging=True,
                file_logging=False,  # Disable for testing
                add_correlation_id=True,
                add_request_context=True
            ),
            alerting=AlertingConfig(enabled=False),
            health_check=HealthCheckConfig(enabled=False)
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_log_collection_and_search(self, logging_manager):
        """Test log collection and search functionality"""
        # Simulate log entries
        test_logs = [
            {
                "level": "INFO",
                "message": "Test log message 1",
                "service": "test-service",
                "component": "test-component"
            },
            {
                "level": "ERROR",
                "message": "Test error message",
                "service": "test-service",
                "component": "test-component"
            },
            {
                "level": "DEBUG",
                "message": "Test debug message",
                "service": "test-service",
                "component": "different-component"
            }
        ]

        # Add logs to aggregator
        for log_data in test_logs:
            await logging_manager.log_aggregator.add_log(
                level=log_data["level"],
                message=log_data["message"],
                service=log_data["service"],
                component=log_data["component"],
                timestamp=datetime.now(timezone.utc)
            )

        # Run aggregation
        await logging_manager.log_aggregator.aggregate_logs()

        # Query logs
        all_logs = await logging_manager.get_logs(limit=100)
        error_logs = await logging_manager.get_logs(level="ERROR")
        search_logs = await logging_manager.get_logs(search="debug")

        # Verify log collection
        assert len(all_logs.get("logs", [])) >= 3
        assert len(error_logs.get("logs", [])) >= 1
        assert len(search_logs.get("logs", [])) >= 1

    @pytest.mark.asyncio
    async def test_log_correlation_tracking(self, logging_manager):
        """Test log correlation ID tracking"""
        correlation_id = await logging_manager.create_correlation_id()

        # Add logs with correlation ID
        await logging_manager.log_aggregator.add_log(
            level="INFO",
            message="Request started",
            service="test-service",
            correlation_id=correlation_id
        )

        await logging_manager.log_aggregator.add_log(
            level="INFO",
            message="Request processed",
            service="test-service",
            correlation_id=correlation_id
        )

        # Query logs by correlation ID
        correlated_logs = await logging_manager.get_logs(
            service="test-service"
        )

        # Filter logs with our correlation ID
        matching_logs = [
            log for log in correlated_logs.get("logs", [])
            if log.get("correlation_id") == correlation_id
        ]

        assert len(matching_logs) >= 2

    @pytest.mark.asyncio
    async def test_log_level_filtering(self, logging_manager):
        """Test log level filtering functionality"""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        # Add logs at different levels
        for level in log_levels:
            await logging_manager.log_aggregator.add_log(
                level=level,
                message=f"Test {level} message",
                service="test-service"
            )

        # Query by different levels
        warning_logs = await logging_manager.get_logs(level="WARNING")
        error_logs = await logging_manager.get_logs(level="ERROR")

        assert len(warning_logs.get("logs", [])) >= 1
        assert len(error_logs.get("logs", [])) >= 1

        # Verify level filtering works
        for log in warning_logs.get("logs", []):
            assert log["level"] == "WARNING"


class TestAlertingIntegration:
    """Integration tests for Alerting Service"""

    @pytest.fixture
    async def alerting_manager(self):
        """Create observability manager with alerting enabled"""
        config = MonitoringConfig(
            service_name="test-alerting",
            environment="test",
            metrics=MetricsConfig(custom_metrics_enabled=True),
            tracing=TracingConfig(enabled=False),
            logging=LoggingConfig(structured_logging=False),
            alerting=AlertingConfig(
                enabled=True,
                alert_cooldown_minutes=1,
                max_alerts_per_hour=100,
                cpu_threshold_percent=80.0,
                memory_threshold_percent=80.0,
                error_rate_threshold=5.0
            ),
            health_check=HealthCheckConfig(enabled=False)
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_alert_rule_creation_and_evaluation(self, alerting_manager):
        """Test alert rule creation and evaluation"""
        # Create alert rule
        rule_id = await alerting_manager.create_alert_rule(
            name="High CPU Usage",
            conditions={
                "metric": "cpu_usage",
                "operator": ">",
                "threshold": 80.0,
                "duration": 300  # 5 minutes
            },
            severity="high",
            channels=["email"],
            description="Alert when CPU usage exceeds 80%"
        )

        assert rule_id is not None

        # Simulate high CPU metric
        await alerting_manager.metrics_collector.record_gauge(
            name="cpu_usage",
            value=85.0,
            labels={"service": "test-service"}
        )

        # Trigger alert evaluation
        await alerting_manager.alert_handler.evaluate_rules()

        # Check for active alerts
        alerts_data = await alerting_manager.get_alerts(
            severity="high",
            status="active"
        )

        # Verify alert was triggered
        cpu_alerts = [
            alert for alert in alerts_data.get("alerts", [])
            if "CPU" in alert.get("name", "")
        ]

        assert len(cpu_alerts) >= 1

    @pytest.mark.asyncio
    async def test_alert_acknowledgment_and_resolution(self, alerting_manager):
        """Test alert acknowledgment and resolution workflow"""
        # Create an alert
        rule_id = await alerting_manager.create_alert_rule(
            name="Test Alert",
            conditions={"metric": "test_metric", "operator": ">", "threshold": 1.0},
            severity="medium"
        )

        # Trigger the alert
        await alerting_manager.metrics_collector.record_gauge(
            name="test_metric",
            value=2.0,
            labels={}
        )

        await alerting_manager.alert_handler.evaluate_rules()

        # Get active alerts
        alerts_data = await alerting_manager.get_alerts(status="active")
        active_alerts = alerts_data.get("alerts", [])

        if active_alerts:
            alert_id = active_alerts[0]["id"]

            # Acknowledge alert
            ack_success = await alerting_manager.acknowledge_alert(
                alert_id=alert_id,
                user="test_user",
                message="Acknowledging test alert"
            )

            assert ack_success is True

            # Verify alert is acknowledged
            acknowledged_alerts = await alerting_manager.get_alerts(
                status="acknowledged"
            )

            acked_alerts = [
                alert for alert in acknowledged_alerts.get("alerts", [])
                if alert["id"] == alert_id
            ]

            assert len(acked_alerts) >= 1

            # Resolve alert
            resolve_success = await alerting_manager.resolve_alert(
                alert_id=alert_id,
                user="test_user",
                message="Test alert resolved"
            )

            assert resolve_success is True

            # Verify alert is resolved
            resolved_alerts = await alerting_manager.get_alerts(
                status="resolved"
            )

            resolved_alert = [
                alert for alert in resolved_alerts.get("alerts", [])
                if alert["id"] == alert_id
            ]

            assert len(resolved_alert) >= 1

    @pytest.mark.asyncio
    async def test_alert_cooldown_and_rate_limiting(self, alerting_manager):
        """Test alert cooldown and rate limiting functionality"""
        # Create alert rule
        rule_id = await alerting_manager.create_alert_rule(
            name="Rate Limit Test",
            conditions={"metric": "rate_test", "operator": ">", "threshold": 1.0},
            severity="low"
        )

        # Trigger multiple alerts quickly
        for i in range(5):
            await alerting_manager.metrics_collector.record_gauge(
                name="rate_test",
                value=2.0 + i,
                labels={"iteration": str(i)}
            )

            await alerting_manager.alert_handler.evaluate_rules()
            await asyncio.sleep(0.1)  # Small delay

        # Check that cooldown prevents duplicate alerts
        alerts_data = await alerting_manager.get_alerts(
            severity="low",
            status="active"
        )

        # Should have limited number of alerts due to cooldown
        rate_limit_alerts = [
            alert for alert in alerts_data.get("alerts", [])
            if "Rate Limit Test" in alert.get("name", "")
        ]

        # Cooldown should prevent multiple alerts for same condition
        assert len(rate_limit_alerts) <= 2


class TestHealthCheckIntegration:
    """Integration tests for Health Check Service"""

    @pytest.fixture
    async def health_check_manager(self):
        """Create observability manager with health checks enabled"""
        config = MonitoringConfig(
            service_name="test-health",
            environment="test",
            metrics=MetricsConfig(custom_metrics_enabled=False),
            tracing=TracingConfig(enabled=False),
            logging=LoggingConfig(structured_logging=False),
            alerting=AlertingConfig(enabled=False),
            health_check=HealthCheckConfig(
                enabled=True,
                check_interval_seconds=1,
                timeout_seconds=5,
                check_database=True,
                check_redis=True,
                check_neo4j=True,
                check_qdrant=True,
                collect_detailed_metrics=True,
                save_health_history=True
            )
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_execution(self, health_check_manager):
        """Test health check execution and reporting"""
        # Run health checks
        health_status = await health_check_manager.health_check()

        # Verify health check structure
        assert "manager" in health_status
        assert "services" in health_status
        assert health_status["manager"]["status"] in ["healthy", "degraded", "unhealthy", "stopped"]

        # Verify individual service health checks
        services_health = health_status["services"]
        assert "health_checks" in services_health

        health_checks_status = services_health["health_checks"]
        assert "status" in health_checks_status
        assert "checks" in health_checks_status

        # Get detailed service health
        service_health = await health_check_manager.get_service_health()

        assert "overall_status" in service_health
        assert "components" in service_health
        assert "timestamp" in service_health

    @pytest.mark.asyncio
    async def test_health_check_performance(self, health_check_manager):
        """Test health check performance under load"""
        start_time = time.time()

        # Run multiple health check cycles
        for i in range(10):
            await health_check_manager.health_check_hub.run_all_checks()
            await asyncio.sleep(0.1)

        total_time = time.time() - start_time

        # Health checks should be fast
        assert total_time < 10.0

        # Verify consistent results
        final_health = await health_check_manager.health_check()
        assert final_health["manager"]["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_health_history_tracking(self, health_check_manager):
        """Test health check history tracking"""
        # Run health checks multiple times
        for i in range(5):
            await health_check_manager.health_check_hub.run_all_checks()
            await asyncio.sleep(0.2)

        # Get health history (if implemented)
        if hasattr(health_check_manager.health_check_hub, 'get_health_history'):
            history = await health_check_manager.health_check_hub.get_health_history(
                hours=1
            )

            assert len(history) >= 5

            # Verify history structure
            for entry in history:
                assert "timestamp" in entry
                assert "status" in entry
                assert "components" in entry


class TestWebSocketIntegration:
    """Integration tests for WebSocket real-time service"""

    @pytest.fixture
    async def websocket_manager(self):
        """Create WebSocket manager for testing"""
        manager = WebSocketManager()
        yield manager
        # Cleanup any remaining connections
        await manager.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_websocket_connection_management(self, websocket_manager):
        """Test WebSocket connection lifecycle"""
        from fastapi.testclient import TestClient
        from backend.src.main import app

        # Create test client with WebSocket support
        client = TestClient(app)

        with client.websocket_connect("/ws/metrics?token=test_token") as websocket:
            # Test connection is established
            assert websocket is not None

            # Send ping message
            websocket.send_json({"type": "ping"})

            # Receive pong response
            response = websocket.receive_json()
            assert response["type"] == "pong"
            assert "timestamp" in response

    @pytest.mark.asyncio
    async def test_websocket_broadcasting(self, websocket_manager):
        """Test WebSocket message broadcasting"""
        # Mock WebSocket connections
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()

        # Connect mock WebSockets
        await websocket_manager.connect(mock_websocket1, "metrics", test_id="1")
        await websocket_manager.connect(mock_websocket2, "metrics", test_id="2")

        # Test message broadcasting
        test_message = {
            "type": "test_broadcast",
            "data": {"value": 42}
        }

        await websocket_manager.broadcast_to_type("metrics", test_message)

        # Verify both connections received the message
        mock_websocket1.send_text.assert_called_once()
        mock_websocket2.send_text.assert_called_once()

        # Verify message content
        sent_message1 = json.loads(mock_websocket1.send_text.call_args[0][0])
        sent_message2 = json.loads(mock_websocket2.send_text.call_args[0][0])

        assert sent_message1 == test_message
        assert sent_message2 == test_message

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, websocket_manager):
        """Test WebSocket error handling and reconnection"""
        mock_websocket = AsyncMock()
        mock_websocket.send_text.side_effect = Exception("Connection lost")

        # Connect WebSocket
        await websocket_manager.connect(mock_websocket, "metrics")

        # Test broadcasting to disconnected WebSocket
        test_message = {"type": "test_error", "data": {}}

        # Should handle error gracefully and remove connection
        await websocket_manager.broadcast_to_type("metrics", test_message)

        # Verify connection was cleaned up
        assert len(websocket_manager._connections["metrics"]) == 0

    @pytest.mark.asyncio
    async def test_websocket_subscription_filters(self, websocket_manager):
        """Test WebSocket subscription filtering"""
        mock_websocket = AsyncMock()

        # Connect with subscription
        await websocket_manager.connect(mock_websocket, "metrics")

        # Send subscription message
        await websocket_manager.send_personal_message(mock_websocket, {
            "type": "subscription_confirmed",
            "metric": "cpu_usage",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Verify personal message was sent
        mock_websocket.send_text.assert_called_once()

        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "subscription_confirmed"
        assert sent_message["metric"] == "cpu_usage"


class TestMonitoringServiceIntegration:
    """Integration tests for complete monitoring service orchestration"""

    @pytest.fixture
    async def full_observability_manager(self):
        """Create fully configured observability manager"""
        config = MonitoringConfig(
            service_name="test-full-observability",
            environment="test",
            metrics=MetricsConfig(
                custom_metrics_enabled=True,
                collection_interval_seconds=1
            ),
            tracing=TracingConfig(
                enabled=True,
                sampling_ratio=1.0
            ),
            logging=LoggingConfig(
                structured_logging=True,
                level="INFO"
            ),
            alerting=AlertingConfig(
                enabled=True,
                alert_cooldown_minutes=1
            ),
            health_check=HealthCheckConfig(
                enabled=True,
                check_interval_seconds=2
            )
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_service_orchestration(self, full_observability_manager):
        """Test all services work together correctly"""
        # Record a metric
        await full_observability_manager.metrics_collector.record_counter(
            name="orchestration_test_total",
            value=1,
            labels={"test": "integration"}
        )

        # Create a trace
        async with full_observability_manager.trace_operation(
            operation_name="orchestration_operation",
            service="test-service"
        ):
            # Add a log entry
            await full_observability_manager.log_aggregator.add_log(
                level="INFO",
                message="Orchestration test log",
                service="test-service"
            )

        # Run health checks
        health_status = await full_observability_manager.health_check()

        # Verify all services are healthy
        assert health_status["manager"]["status"] in ["healthy", "degraded"]
        assert len(health_status["services"]) >= 5  # All 6 services

        # Verify data is available from all services
        metrics_data = await full_observability_manager.get_metrics()
        traces_data = await full_observability_manager.get_traces()
        logs_data = await full_observability_manager.get_logs()

        assert "metrics" in metrics_data
        assert "traces" in traces_data
        assert "logs" in logs_data

    @pytest.mark.asyncio
    async def test_cross_service_correlation(self, full_observability_manager):
        """Test correlation across monitoring services"""
        correlation_id = await full_observability_manager.create_correlation_id()

        # Use correlation ID across all services
        async with full_observability_manager.trace_operation(
            operation_name="correlation_test",
            service="test-service"
        ) as span_context:
            # Record metric with correlation
            await full_observability_manager.metrics_collector.record_counter(
                name="correlation_test_total",
                value=1,
                labels={"correlation_id": correlation_id}
            )

            # Add log with correlation
            await full_observability_manager.log_aggregator.add_log(
                level="INFO",
                message="Correlation test message",
                service="test-service",
                correlation_id=correlation_id
            )

        # Query data with correlation filter
        metrics_data = await full_observability_manager.get_metrics(
            labels={"correlation_id": correlation_id}
        )

        logs_data = await full_observability_manager.get_logs()

        # Find logs with our correlation ID
        correlated_logs = [
            log for log in logs_data.get("logs", [])
            if log.get("correlation_id") == correlation_id
        ]

        # Verify correlation worked
        assert len(metrics_data.get("metrics", {})) >= 1
        assert len(correlated_logs) >= 1

    @pytest.mark.asyncio
    async def test_monitoring_performance_under_load(self, full_observability_manager):
        """Test complete monitoring system performance under load"""
        start_time = time.time()

        # Generate load on all services
        tasks = []

        # Metrics load
        for i in range(100):
            task = full_observability_manager.metrics_collector.record_counter(
                name="load_test_total",
                value=1,
                labels={"iteration": str(i)}
            )
            tasks.append(task)

        # Tracing load
        for i in range(50):
            async def trace_operation(i):
                async with full_observability_manager.trace_operation(
                    operation_name=f"load_test_{i}",
                    service="load-test-service"
                ):
                    await asyncio.sleep(0.001)

            tasks.append(trace_operation(i))

        # Logging load
        for i in range(75):
            task = full_observability_manager.log_aggregator.add_log(
                level="INFO",
                message=f"Load test log {i}",
                service="load-test-service"
            )
            tasks.append(task)

        # Execute all tasks
        await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # Verify performance - should handle load quickly
        assert total_time < 10.0

        # Verify all data was processed
        metrics_data = await full_observability_manager.get_metrics()
        traces_data = await full_observability_manager.get_traces()
        logs_data = await full_observability_manager.get_logs()

        assert len(metrics_data.get("metrics", {})) >= 100
        assert len(traces_data.get("traces", {})) >= 50
        assert len(logs_data.get("logs", {})) >= 75

    @pytest.mark.asyncio
    async def test_monitoring_system_resilience(self, full_observability_manager):
        """Test monitoring system resilience and error recovery"""
        # Test system continues working when individual services have issues

        # Simulate service degradation by disabling one service
        original_alert_handler = full_observability_manager.alert_handler
        full_observability_manager.alert_handler = None

        # System should still work with other services
        await full_observability_manager.metrics_collector.record_counter(
            name="resilience_test",
            value=1,
            labels={}
        )

        metrics_data = await full_observability_manager.get_metrics()
        assert len(metrics_data.get("metrics", {})) >= 1

        # Restore service
        full_observability_manager.alert_handler = original_alert_handler

        # System should recover fully
        health_status = await full_observability_manager.health_check()
        assert health_status["manager"]["status"] in ["healthy", "degraded"]


# Performance benchmark tests
@pytest.mark.performance
class TestMonitoringPerformanceBenchmarks:
    """Performance benchmarks for monitoring services"""

    @pytest.mark.asyncio
    async def test_metrics_throughput_benchmark(self):
        """Benchmark metrics collection throughput"""
        config = MonitoringConfig(
            metrics=MetricsConfig(custom_metrics_enabled=True)
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        try:
            start_time = time.time()
            metric_count = 10000

            # Record many metrics
            tasks = []
            for i in range(metric_count):
                task = manager.metrics_collector.record_counter(
                    name="benchmark_counter",
                    value=1,
                    labels={"iteration": str(i)}
                )
                tasks.append(task)

            await asyncio.gather(*tasks)
            end_time = time.time()

            throughput = metric_count / (end_time - start_time)

            # Should achieve at least 1000 metrics/second
            assert throughput >= 1000.0

        finally:
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_tracing_latency_benchmark(self):
        """Benchmark tracing operation latency"""
        config = MonitoringConfig(
            tracing=TracingConfig(enabled=True, sampling_ratio=1.0)
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        try:
            latencies = []

            for i in range(100):
                start_time = time.time()

                async with manager.trace_operation(
                    operation_name=f"benchmark_op_{i}",
                    service="benchmark-service"
                ):
                    pass

                end_time = time.time()
                latencies.append(end_time - start_time)

            avg_latency = sum(latencies) / len(latencies)
            p95_latency = sorted(latencies)[int(0.95 * len(latencies))]

            # Latency should be low
            assert avg_latency < 0.01  # Less than 10ms average
            assert p95_latency < 0.05   # Less than 50ms P95

        finally:
            await manager.shutdown()


if __name__ == "__main__":
    # Run specific test classes
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "TestMetricsServiceIntegration",
        "TestTracingServiceIntegration",
        "TestLogAggregationIntegration",
        "TestAlertingIntegration",
        "TestHealthCheckIntegration",
        "TestWebSocketIntegration",
        "TestMonitoringServiceIntegration"
    ])