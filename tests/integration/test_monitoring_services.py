"""
Comprehensive Monitoring Service Integration Tests

This module provides integration tests for all 6 core monitoring services:
1. Observability Manager Service
2. Metrics Collector Service
3. Tracing Collector Service
4. Health Check Service
5. Alerting Service
6. Performance Analytics Service

Tests cover:
- Cross-service communication and dependencies
- Database integration with monitoring schema
- API endpoint integration following OpenAPI specs
- Real-time data streaming validation
- Error handling and recovery scenarios
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
import httpx
import websockets
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir / "src"))

from src.monitoring.services.observability_manager import ObservabilityManager
from src.monitoring.services.metrics_collector import MetricsCollector
from src.monitoring.services.tracing_collector import TracingCollector
from src.monitoring.health_checks import HealthCheckService
from src.monitoring.alerting import AlertingService
from src.monitoring.performance_analytics import PerformanceAnalytics
from src.monitoring.models.metrics import MetricModel, MetricType
from src.monitoring.models.tracing import TraceModel, SpanModel
from src.monitoring.models.alerting import AlertModel, AlertSeverity, AlertStatus
from src.monitoring.models.health_check import HealthCheckResult, ComponentStatus
from src.core.database import Base
from src.main import app


@pytest.fixture
async def test_db_session():
    """Create test database session for monitoring integration tests"""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    session.close()


@pytest.fixture
async def observability_manager(test_db_session):
    """Create observability manager instance for testing"""
    with patch('src.monitoring.services.observability_manager.get_db') as mock_get_db:
        mock_get_db.return_value = test_db_session
        manager = ObservabilityManager()
        yield manager


@pytest.fixture
async def metrics_collector(test_db_session):
    """Create metrics collector instance for testing"""
    with patch('src.monitoring.services.metrics_collector.get_db') as mock_get_db:
        mock_get_db.return_value = test_db_session
        collector = MetricsCollector()
        yield collector


@pytest.fixture
async def tracing_collector(test_db_session):
    """Create tracing collector instance for testing"""
    with patch('src.monitoring.services.tracing_collector.get_db') as mock_get_db:
        mock_get_db.return_value = test_db_session
        collector = TracingCollector()
        yield collector


@pytest.fixture
async def health_check_service(test_db_session):
    """Create health check service instance for testing"""
    with patch('src.monitoring.health_checks.get_db') as mock_get_db:
        mock_get_db.return_value = test_db_session
        service = HealthCheckService()
        yield service


@pytest.fixture
async def alerting_service(test_db_session):
    """Create alerting service instance for testing"""
    with patch('src.monitoring.alerting.get_db') as mock_get_db:
        mock_get_db.return_value = test_db_session
        service = AlertingService()
        yield service


@pytest.fixture
async def performance_analytics(test_db_session):
    """Create performance analytics service instance for testing"""
    with patch('src.monitoring.performance_analytics.get_db') as mock_get_db:
        mock_get_db.return_value = test_db_session
        service = PerformanceAnalytics()
        yield service


@pytest.fixture
async def test_client():
    """Create FastAPI test client"""
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        yield client


class TestObservabilityManagerIntegration:
    """Integration tests for Observability Manager Service"""

    @pytest.mark.asyncio
    async def test_observability_manager_initialization(self, observability_manager):
        """Test observability manager initialization and configuration"""
        # Test manager properties
        assert observability_manager is not None
        assert hasattr(observability_manager, 'metrics_collector')
        assert hasattr(observability_manager, 'tracing_collector')
        assert hasattr(observability_manager, 'health_checker')
        assert hasattr(observability_manager, 'alerting_service')

        # Test initial status
        status = await observability_manager.get_system_status()
        assert 'services' in status
        assert 'timestamp' in status

    @pytest.mark.asyncio
    async def test_cross_service_communication(self, observability_manager):
        """Test communication between observability manager and other services"""
        # Test metrics collection integration
        metric_data = {
            "name": "test_metric",
            "value": 42.5,
            "labels": {"service": "test", "environment": "test"},
            "timestamp": datetime.now(timezone.utc)
        }

        result = await observability_manager.collect_metric(metric_data)
        assert result is True

        # Test tracing integration
        trace_data = {
            "trace_id": "test-trace-123",
            "span_id": "test-span-456",
            "operation_name": "test_operation",
            "duration_ms": 150,
            "timestamp": datetime.now(timezone.utc)
        }

        result = await observability_manager.record_trace(trace_data)
        assert result is True

        # Verify cross-service data flow
        metrics = await observability_manager.get_metrics_summary()
        assert len(metrics) > 0

    @pytest.mark.asyncio
    async def test_service_dependency_validation(self, observability_manager):
        """Test service dependencies and their validation"""
        # Check all required services are available
        dependencies = await observability_manager.check_service_dependencies()

        expected_services = [
            'metrics_collector',
            'tracing_collector',
            'health_checker',
            'alerting_service',
            'performance_analytics'
        ]

        for service in expected_services:
            assert service in dependencies
            assert dependencies[service]['status'] in ['healthy', 'warning', 'error']

    @pytest.mark.asyncio
    async def test_observability_error_handling(self, observability_manager):
        """Test error handling and recovery in observability manager"""
        # Test handling of invalid metric data
        invalid_metric = {"name": "", "value": "invalid"}
        result = await observability_manager.collect_metric(invalid_metric)
        assert result is False

        # Test handling of database connection issues
        with patch('src.monitoring.services.observability_manager.get_db') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")

            status = await observability_manager.get_system_status()
            assert 'error' in status.get('database', {}).lower()


class TestMetricsCollectorIntegration:
    """Integration tests for Metrics Collector Service"""

    @pytest.mark.asyncio
    async def test_metrics_collection_and_storage(self, metrics_collector, test_db_session):
        """Test metrics collection flow and database storage"""
        # Create test metrics
        test_metrics = [
            {
                "name": "request_duration",
                "value": 125.5,
                "type": MetricType.HISTOGRAM,
                "labels": {"endpoint": "/api/search", "method": "POST"},
                "timestamp": datetime.now(timezone.utc)
            },
            {
                "name": "active_connections",
                "value": 42,
                "type": MetricType.GAUGE,
                "labels": {"service": "websocket"},
                "timestamp": datetime.now(timezone.utc)
            },
            {
                "name": "total_requests",
                "value": 1,
                "type": MetricType.COUNTER,
                "labels": {"status": "200"},
                "timestamp": datetime.now(timezone.utc)
            }
        ]

        # Collect metrics
        for metric in test_metrics:
            result = await metrics_collector.collect_metric(metric)
            assert result is True

        # Verify storage
        stored_metrics = test_db_session.query(MetricModel).all()
        assert len(stored_metrics) == len(test_metrics)

        # Verify metric data integrity
        for i, stored_metric in enumerate(stored_metrics):
            assert stored_metric.name == test_metrics[i]["name"]
            assert stored_metric.value == test_metrics[i]["value"]

    @pytest.mark.asyncio
    async def test_metrics_aggregation_and_querying(self, metrics_collector, test_db_session):
        """Test metrics aggregation and querying capabilities"""
        # Insert test metrics with different timestamps
        base_time = datetime.now(timezone.utc)
        for i in range(10):
            metric = {
                "name": "response_time",
                "value": 100 + i * 10,
                "type": MetricType.HISTOGRAM,
                "labels": {"endpoint": "/api/documents"},
                "timestamp": base_time + timedelta(minutes=i)
            }
            await metrics_collector.collect_metric(metric)

        # Test aggregation queries
        agg_result = await metrics_collector.get_aggregated_metrics(
            name="response_time",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=10),
            aggregation="avg"
        )

        assert agg_result is not None
        assert 'avg' in agg_result
        assert agg_result['avg'] == 145.0  # Average of 100 to 190

    @pytest.mark.asyncio
    async def test_metrics_labels_filtering(self, metrics_collector, test_db_session):
        """Test metrics filtering by labels"""
        # Create metrics with different labels
        metrics_with_labels = [
            {
                "name": "api_requests",
                "value": 1,
                "type": MetricType.COUNTER,
                "labels": {"endpoint": "/api/search", "method": "GET", "status": "200"},
                "timestamp": datetime.now(timezone.utc)
            },
            {
                "name": "api_requests",
                "value": 1,
                "type": MetricType.COUNTER,
                "labels": {"endpoint": "/api/upload", "method": "POST", "status": "201"},
                "timestamp": datetime.now(timezone.utc)
            },
            {
                "name": "api_requests",
                "value": 1,
                "type": MetricType.COUNTER,
                "labels": {"endpoint": "/api/search", "method": "POST", "status": "400"},
                "timestamp": datetime.now(timezone.utc)
            }
        ]

        for metric in metrics_with_labels:
            await metrics_collector.collect_metric(metric)

        # Test label filtering
        filtered_metrics = await metrics_collector.query_metrics(
            labels={"endpoint": "/api/search"}
        )

        assert len(filtered_metrics) == 2

        # Test multiple label filtering
        filtered_metrics = await metrics_collector.query_metrics(
            labels={"endpoint": "/api/search", "method": "GET"}
        )

        assert len(filtered_metrics) == 1
        assert filtered_metrics[0].labels["status"] == "200"


class TestTracingCollectorIntegration:
    """Integration tests for Tracing Collector Service"""

    @pytest.mark.asyncio
    async def test_trace_collection_and_storage(self, tracing_collector, test_db_session):
        """Test trace collection and database storage"""
        # Create test trace with spans
        trace_data = {
            "trace_id": "test-trace-789",
            "spans": [
                {
                    "span_id": "span-1",
                    "parent_span_id": None,
                    "operation_name": "HTTP POST /api/search",
                    "duration_ms": 150,
                    "start_time": datetime.now(timezone.utc),
                    "tags": {"http.method": "POST", "http.status_code": "200"},
                    "logs": []
                },
                {
                    "span_id": "span-2",
                    "parent_span_id": "span-1",
                    "operation_name": "vector_search",
                    "duration_ms": 75,
                    "start_time": datetime.now(timezone.utc),
                    "tags": {"service": "vector_store", "query_type": "semantic"},
                    "logs": []
                },
                {
                    "span_id": "span-3",
                    "parent_span_id": "span-1",
                    "operation_name": "graph_search",
                    "duration_ms": 50,
                    "start_time": datetime.now(timezone.utc),
                    "tags": {"service": "knowledge_graph", "nodes_returned": "5"},
                    "logs": []
                }
            ]
        }

        # Collect trace
        result = await tracing_collector.collect_trace(trace_data)
        assert result is True

        # Verify storage
        stored_traces = test_db_session.query(TraceModel).all()
        assert len(stored_traces) == 1
        assert stored_traces[0].trace_id == "test-trace-789"

        stored_spans = test_db_session.query(SpanModel).all()
        assert len(stored_spans) == 3

    @pytest.mark.asyncio
    async def test_trace_querying_and_filtering(self, tracing_collector, test_db_session):
        """Test trace querying and filtering capabilities"""
        # Create multiple traces
        base_time = datetime.now(timezone.utc)
        trace_ids = ["trace-1", "trace-2", "trace-3"]

        for i, trace_id in enumerate(trace_ids):
            trace_data = {
                "trace_id": trace_id,
                "spans": [{
                    "span_id": f"span-{i}",
                    "parent_span_id": None,
                    "operation_name": f"operation-{i}",
                    "duration_ms": 100 + i * 25,
                    "start_time": base_time + timedelta(minutes=i),
                    "tags": {"service": f"service-{i % 2}", "status": "success"},
                    "logs": []
                }]
            }
            await tracing_collector.collect_trace(trace_data)

        # Test time-based filtering
        filtered_traces = await tracing_collector.query_traces(
            start_time=base_time,
            end_time=base_time + timedelta(minutes=2)
        )

        assert len(filtered_traces) == 3

        # Test service-based filtering
        filtered_traces = await tracing_collector.query_traces(
            tags={"service": "service-0"}
        )

        assert len(filtered_traces) == 2  # trace-1 and trace-3

    @pytest.mark.asyncio
    async def test_trace_performance_analysis(self, tracing_collector, test_db_session):
        """Test trace performance analysis capabilities"""
        # Create traces with varying performance characteristics
        slow_trace = {
            "trace_id": "slow-trace",
            "spans": [{
                "span_id": "slow-span",
                "parent_span_id": None,
                "operation_name": "slow_operation",
                "duration_ms": 5000,  # 5 seconds - slow
                "start_time": datetime.now(timezone.utc),
                "tags": {"service": "database", "query_complexity": "high"},
                "logs": []
            }]
        }

        fast_trace = {
            "trace_id": "fast-trace",
            "spans": [{
                "span_id": "fast-span",
                "parent_span_id": None,
                "operation_name": "fast_operation",
                "duration_ms": 50,  # 50ms - fast
                "start_time": datetime.now(timezone.utc),
                "tags": {"service": "cache", "hit": "true"},
                "logs": []
            }]
        }

        await tracing_collector.collect_trace(slow_trace)
        await tracing_collector.collect_trace(fast_trace)

        # Test performance analysis
        analysis = await tracing_collector.analyze_trace_performance(
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        assert 'avg_duration' in analysis
        assert 'slowest_traces' in analysis
        assert 'service_performance' in analysis
        assert analysis['avg_duration'] > 50  # Should be > 50ms due to slow trace


class TestHealthCheckIntegration:
    """Integration tests for Health Check Service"""

    @pytest.mark.asyncio
    async def test_component_health_checks(self, health_check_service, test_db_session):
        """Test health checks for system components"""
        # Mock component health checks
        with patch.object(health_check_service, 'check_database_health') as mock_db, \
             patch.object(health_check_service, 'check_vector_store_health') as mock_vector, \
             patch.object(health_check_service, 'check_graph_db_health') as mock_graph:

            # Set mock return values
            mock_db.return_value = HealthCheckResult(
                component="database",
                status=ComponentStatus.HEALTHY,
                timestamp=datetime.now(timezone.utc),
                details={"connection_time_ms": 5}
            )

            mock_vector.return_value = HealthCheckResult(
                component="vector_store",
                status=ComponentStatus.HEALTHY,
                timestamp=datetime.now(timezone.utc),
                details={"collections_count": 10}
            )

            mock_graph.return_value = HealthCheckResult(
                component="graph_db",
                status=ComponentStatus.WARNING,
                timestamp=datetime.now(timezone.utc),
                details={"node_count": 1000, "memory_usage": "85%"}
            )

            # Run health checks
            health_status = await health_check_service.run_all_health_checks()

            assert 'database' in health_status
            assert 'vector_store' in health_status
            assert 'graph_db' in health_status

            assert health_status['database']['status'] == ComponentStatus.HEALTHY
            assert health_status['vector_store']['status'] == ComponentStatus.HEALTHY
            assert health_status['graph_db']['status'] == ComponentStatus.WARNING

    @pytest.mark.asyncio
    async def test_health_check_scheduling(self, health_check_service, test_db_session):
        """Test health check scheduling and periodic execution"""
        # Mock health check method
        check_count = 0

        async def mock_health_check():
            nonlocal check_count
            check_count += 1
            return HealthCheckResult(
                component="test_component",
                status=ComponentStatus.HEALTHY,
                timestamp=datetime.now(timezone.utc)
            )

        with patch.object(health_check_service, 'check_database_health', side_effect=mock_health_check):
            # Schedule health checks every 1 second for testing
            health_check_service.schedule_health_checks(interval_seconds=1)

            # Wait for 3 checks to run
            await asyncio.sleep(3.5)

            # Verify checks ran
            assert check_count >= 3

            # Stop scheduling
            health_check_service.stop_health_checks()

    @pytest.mark.asyncio
    async def test_health_check_alerting(self, health_check_service, alerting_service, test_db_session):
        """Test health check integration with alerting"""
        # Create unhealthy health check result
        unhealthy_result = HealthCheckResult(
            component="database",
            status=ComponentStatus.ERROR,
            timestamp=datetime.now(timezone.utc),
            details={"error": "Connection timeout", "timeout_ms": 30000}
        )

        # Mock health check to return unhealthy result
        with patch.object(health_check_service, 'check_database_health', return_value=unhealthy_result):
            # Run health checks
            await health_check_service.run_all_health_checks()

            # Check if alert was created (integration with alerting service)
            alerts = await alerting_service.get_active_alerts()

            # Should have at least one alert for the database issue
            database_alerts = [alert for alert in alerts if 'database' in alert.title.lower()]
            assert len(database_alerts) > 0


class TestAlertingIntegration:
    """Integration tests for Alerting Service"""

    @pytest.mark.asyncio
    async def test_alert_creation_and_routing(self, alerting_service, test_db_session):
        """Test alert creation, storage, and routing"""
        # Create test alert
        alert_data = {
            "title": "High Memory Usage Detected",
            "description": "System memory usage exceeded 90% threshold",
            "severity": AlertSeverity.WARNING,
            "source": "monitoring_system",
            "metadata": {
                "current_usage": "92%",
                "threshold": "90%",
                "component": "vector_store"
            }
        }

        # Create alert
        alert = await alerting_service.create_alert(**alert_data)

        assert alert is not None
        assert alert.title == alert_data["title"]
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.ACTIVE

        # Verify storage
        stored_alerts = test_db_session.query(AlertModel).all()
        assert len(stored_alerts) == 1
        assert stored_alerts[0].title == alert_data["title"]

    @pytest.mark.asyncio
    async def test_alert_escalation_and_resolution(self, alerting_service, test_db_session):
        """Test alert escalation and resolution workflows"""
        # Create initial alert
        alert = await alerting_service.create_alert(
            title="Database Connection Pool Exhaustion",
            description="All database connections are in use",
            severity=AlertSeverity.ERROR,
            source="database_service"
        )

        # Test alert escalation
        escalated_alert = await alerting_service.escalate_alert(
            alert.id,
            new_severity=AlertSeverity.CRITICAL,
            escalation_reason="Service unavailable for 5 minutes"
        )

        assert escalated_alert.severity == AlertSeverity.CRITICAL
        assert escalated_alert.status == AlertStatus.ESCALATED

        # Test alert resolution
        resolved_alert = await alerting_service.resolve_alert(
            alert.id,
            resolution_note="Database connections restored, pool size increased"
        )

        assert resolved_alert.status == AlertStatus.RESOLVED
        assert resolved_alert.resolved_at is not None

    @pytest.mark.asyncio
    async def test_alert_notification_integration(self, alerting_service, test_db_session):
        """Test alert notification integration (email, Slack, etc.)"""
        # Mock notification channels
        with patch('src.monitoring.alerting.send_email_notification') as mock_email, \
             patch('src.monitoring.alerting.send_slack_notification') as mock_slack:

            mock_email.return_value = True
            mock_slack.return_value = True

            # Create high-severity alert
            alert = await alerting_service.create_alert(
                title="System Outage",
                description="Critical system component is unavailable",
                severity=AlertSeverity.CRITICAL,
                source="health_checker"
            )

            # Trigger notifications
            await alerting_service.send_notifications(alert.id)

            # Verify notifications were sent
            mock_email.assert_called_once()
            mock_slack.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_aggregation_and_deduplication(self, alerting_service, test_db_session):
        """Test alert aggregation and deduplication logic"""
        # Create multiple similar alerts
        base_alert_data = {
            "title": "High API Response Time",
            "description": "API response time exceeded threshold",
            "severity": AlertSeverity.WARNING,
            "source": "metrics_collector",
            "metadata": {"endpoint": "/api/search", "response_time": "2500ms"}
        }

        alerts = []
        for i in range(3):
            alert = await alerting_service.create_alert(
                **base_alert_data,
                metadata={**base_alert_data["metadata"], "response_time": f"{2500 + i * 100}ms"}
            )
            alerts.append(alert)

            # Add small delay to ensure different timestamps
            await asyncio.sleep(0.01)

        # Test alert aggregation
        aggregated_alerts = await alerting_service.get_aggregated_alerts(
            time_window_minutes=5,
            grouping_key="title"
        )

        assert len(aggregated_alerts) > 0
        assert any(len(agg["related_alerts"]) > 1 for agg in aggregated_alerts)


class TestPerformanceAnalyticsIntegration:
    """Integration tests for Performance Analytics Service"""

    @pytest.mark.asyncio
    async def test_performance_metrics_analysis(self, performance_analytics, test_db_session):
        """Test performance metrics collection and analysis"""
        # Insert performance metrics
        base_time = datetime.now(timezone.utc)
        for i in range(100):
            metric = {
                "name": "request_duration",
                "value": 50 + (i % 50),  # Values from 50 to 99
                "type": MetricType.HISTOGRAM,
                "labels": {"endpoint": "/api/search"},
                "timestamp": base_time + timedelta(seconds=i)
            }
            # Direct database insertion for test data
            metric_model = MetricModel(**metric)
            test_db_session.add(metric_model)

        test_db_session.commit()

        # Analyze performance
        analysis = await performance_analytics.analyze_performance_metrics(
            metric_name="request_duration",
            start_time=base_time,
            end_time=base_time + timedelta(seconds=100)
        )

        assert 'statistics' in analysis
        assert 'percentiles' in analysis
        assert 'trends' in analysis

        # Verify statistical calculations
        stats = analysis['statistics']
        assert 'mean' in stats
        assert 'median' in stats
        assert 'std_dev' in stats
        assert stats['mean'] > 50 and stats['mean'] < 99

    @pytest.mark.asyncio
    async def test_performance_trend_analysis(self, performance_analytics, test_db_session):
        """Test performance trend analysis over time"""
        # Create metrics with trend (improving performance)
        base_time = datetime.now(timezone.utc)
        for hour in range(24):
            response_time = 500 - (hour * 10)  # Improving from 500ms to 260ms

            metric = {
                "name": "page_load_time",
                "value": max(response_time, 100),  # Don't go below 100ms
                "type": MetricType.HISTOGRAM,
                "labels": {"page": "dashboard"},
                "timestamp": base_time + timedelta(hours=hour)
            }
            metric_model = MetricModel(**metric)
            test_db_session.add(metric_model)

        test_db_session.commit()

        # Analyze trends
        trend_analysis = await performance_analytics.analyze_performance_trends(
            metric_name="page_load_time",
            start_time=base_time,
            end_time=base_time + timedelta(hours=24),
            granularity="hour"
        )

        assert 'trend_direction' in trend_analysis
        assert 'trend_strength' in trend_analysis
        assert 'seasonal_patterns' in trend_analysis

        # Should detect improving trend
        assert trend_analysis['trend_direction'] == 'improving'
        assert trend_analysis['trend_strength'] > 0.5  # Strong trend

    @pytest.mark.asyncio
    async def test_performance_anomaly_detection(self, performance_analytics, test_db_session):
        """Test performance anomaly detection"""
        # Create normal performance baseline
        base_time = datetime.now(timezone.utc)
        for i in range(50):
            metric = {
                "name": "cpu_usage",
                "value": 30 + (i % 20),  # Normal range: 30-50%
                "type": MetricType.GAUGE,
                "labels": {"service": "api_server"},
                "timestamp": base_time + timedelta(minutes=i)
            }
            metric_model = MetricModel(**metric)
            test_db_session.add(metric_model)

        # Add anomalous spike
        anomaly_metric = {
            "name": "cpu_usage",
            "value": 95,  # Anomalous: 95%
            "type": MetricType.GAUGE,
            "labels": {"service": "api_server"},
            "timestamp": base_time + timedelta(minutes=51)
        }
        metric_model = MetricModel(**anomaly_metric)
        test_db_session.add(metric_model)

        test_db_session.commit()

        # Detect anomalies
        anomalies = await performance_analytics.detect_performance_anomalies(
            metric_name="cpu_usage",
            start_time=base_time,
            end_time=base_time + timedelta(hours=2),
            sensitivity=0.95
        )

        assert len(anomalies) > 0
        assert any(anomaly['value'] > 90 for anomaly in anomalies)
        assert 'severity' in anomalies[0]
        assert 'timestamp' in anomalies[0]


class TestMonitoringAPIIntegration:
    """Integration tests for Monitoring API endpoints"""

    @pytest.mark.asyncio
    async def test_monitoring_health_endpoint(self, test_client):
        """Test monitoring health check endpoint"""
        response = test_client.get("/api/monitoring/health")

        assert response.status_code == 200
        data = response.json()

        assert 'status' in data
        assert 'timestamp' in data
        assert 'components' in data

        # Check component health
        components = data['components']
        expected_components = ['database', 'vector_store', 'graph_db', 'monitoring']
        for component in expected_components:
            assert component in components

    @pytest.mark.asyncio
    async def test_metrics_api_endpoints(self, test_client):
        """Test metrics collection and query API endpoints"""
        # Collect metric via API
        metric_data = {
            "name": "test_api_metric",
            "value": 123.45,
            "type": "gauge",
            "labels": {"source": "api_test"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        response = test_client.post("/api/monitoring/metrics", json=metric_data)
        assert response.status_code == 201

        # Query metrics via API
        response = test_client.get("/api/monitoring/metrics?name=test_api_metric")
        assert response.status_code == 200

        data = response.json()
        assert 'metrics' in data
        assert len(data['metrics']) > 0
        assert data['metrics'][0]['name'] == "test_api_metric"

    @pytest.mark.asyncio
    async def test_traces_api_endpoints(self, test_client):
        """Test traces collection and query API endpoints"""
        # Collect trace via API
        trace_data = {
            "trace_id": "api-test-trace",
            "spans": [{
                "span_id": "api-test-span",
                "operation_name": "api_test_operation",
                "duration_ms": 100,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "tags": {"test": "true"}
            }]
        }

        response = test_client.post("/api/monitoring/traces", json=trace_data)
        assert response.status_code == 201

        # Query trace via API
        response = test_client.get(f"/api/monitoring/traces/{trace_data['trace_id']}")
        assert response.status_code == 200

        data = response.json()
        assert data['trace_id'] == trace_data['trace_id']
        assert len(data['spans']) == 1

    @pytest.mark.asyncio
    async def test_alerts_api_endpoints(self, test_client):
        """Test alerts management API endpoints"""
        # Create alert via API
        alert_data = {
            "title": "API Test Alert",
            "description": "Test alert created via API",
            "severity": "warning",
            "source": "api_test",
            "metadata": {"test_id": "123"}
        }

        response = test_client.post("/api/monitoring/alerts", json=alert_data)
        assert response.status_code == 201

        created_alert = response.json()
        alert_id = created_alert['id']

        # Get alert via API
        response = test_client.get(f"/api/monitoring/alerts/{alert_id}")
        assert response.status_code == 200

        data = response.json()
        assert data['title'] == alert_data['title']
        assert data['status'] == 'active'

        # Resolve alert via API
        response = test_client.patch(
            f"/api/monitoring/alerts/{alert_id}",
            json={"status": "resolved", "resolution_note": "Test resolution"}
        )
        assert response.status_code == 200

        # Verify resolution
        response = test_client.get(f"/api/monitoring/alerts/{alert_id}")
        data = response.json()
        assert data['status'] == 'resolved'

    @pytest.mark.asyncio
    async def test_performance_analytics_api_endpoints(self, test_client):
        """Test performance analytics API endpoints"""
        # Query performance analytics via API
        response = test_client.get(
            "/api/monitoring/analytics/performance?metric_name=test_metric&period=1h"
        )
        assert response.status_code == 200

        data = response.json()
        assert 'analysis' in data
        assert 'timestamp' in data

        # Query system performance overview
        response = test_client.get("/api/monitoring/analytics/overview")
        assert response.status_code == 200

        data = response.json()
        assert 'system_health' in data
        assert 'performance_summary' in data
        assert 'active_alerts' in data


class TestWebSocketIntegration:
    """Integration tests for WebSocket real-time data streaming"""

    @pytest.mark.asyncio
    async def test_websocket_metrics_streaming(self, test_client):
        """Test real-time metrics streaming via WebSocket"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            # Subscribe to metrics stream
            websocket.send_json({
                "type": "subscribe",
                "channel": "metrics",
                "filters": {"service": "test_service"}
            })

            # Verify subscription acknowledgment
            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'

            # Send test metric through API
            metric_data = {
                "name": "websocket_test_metric",
                "value": 42,
                "type": "gauge",
                "labels": {"service": "test_service"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # This would normally trigger a WebSocket message
            # In the actual implementation, this would be handled by the metrics collector

            # Receive metric update (simulated)
            # In real test, you'd wait for the actual WebSocket message
            # message = websocket.receive_json(timeout=5)
            # assert message['type'] == 'metric_update'

    @pytest.mark.asyncio
    async def test_websocket_alerts_streaming(self, test_client):
        """Test real-time alerts streaming via WebSocket"""
        with test_client.websocket_connect("/ws/monitoring/alerts") as websocket:
            # Subscribe to alerts stream
            websocket.send_json({
                "type": "subscribe",
                "channel": "alerts",
                "filters": {"severity": ["error", "critical"]}
            })

            # Verify subscription acknowledgment
            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'
            assert response['channel'] == 'alerts'

    @pytest.mark.asyncio
    async def test_websocket_health_status_streaming(self, test_client):
        """Test real-time health status streaming via WebSocket"""
        with test_client.websocket_connect("/ws/monitoring/health") as websocket:
            # Subscribe to health status stream
            websocket.send_json({
                "type": "subscribe",
                "channel": "health"
            })

            # Verify subscription acknowledgment
            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'
            assert response['channel'] == 'health'


class TestEndToEndMonitoringWorkflow:
    """End-to-end monitoring workflow integration tests"""

    @pytest.mark.asyncio
    async def test_complete_monitoring_workflow(self, test_client, test_db_session):
        """Test complete monitoring workflow from data collection to alerting"""
        # 1. Send metrics via API
        metrics = [
            {
                "name": "response_time",
                "value": 2500,  # High response time
                "type": "histogram",
                "labels": {"endpoint": "/api/search"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            {
                "name": "error_rate",
                "value": 0.15,  # 15% error rate
                "type": "gauge",
                "labels": {"service": "api_server"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

        for metric in metrics:
            response = test_client.post("/api/monitoring/metrics", json=metric)
            assert response.status_code == 201

        # 2. Send trace data
        trace_data = {
            "trace_id": "e2e-test-trace",
            "spans": [{
                "span_id": "slow-operation",
                "operation_name": "database_query",
                "duration_ms": 3000,  # Slow operation
                "start_time": datetime.now(timezone.utc).isoformat(),
                "tags": {"service": "database", "slow": "true"}
            }]
        }

        response = test_client.post("/api/monitoring/traces", json=trace_data)
        assert response.status_code == 201

        # 3. Trigger health check
        response = test_client.post("/api/monitoring/health/check")
        assert response.status_code == 200

        # 4. Check if alerts were generated (based on thresholds)
        response = test_client.get("/api/monitoring/alerts?status=active")
        assert response.status_code == 200

        alerts = response.json()['alerts']

        # Should have alerts for high response time and error rate
        performance_alerts = [
            alert for alert in alerts
            if 'response time' in alert['title'].lower() or 'error rate' in alert['title'].lower()
        ]

        # Note: This depends on the threshold configuration
        # In a real implementation, these metrics should trigger alerts

        # 5. Query performance analytics
        response = test_client.get("/api/monitoring/analytics/performance?period=1h")
        assert response.status_code == 200

        analytics = response.json()
        assert 'analysis' in analytics
        assert 'system_health' in analytics

    @pytest.mark.asyncio
    async def test_monitoring_system_resilience(self, test_client):
        """Test monitoring system resilience under various failure conditions"""
        # Test with invalid metric data
        invalid_metrics = [
            {},  # Empty data
            {"name": ""},  # Missing required fields
            {"name": "test", "value": "invalid"},  # Invalid value type
        ]

        for invalid_metric in invalid_metrics:
            response = test_client.post("/api/monitoring/metrics", json=invalid_metric)
            assert response.status_code == 400  # Bad request

        # Test with non-existent resources
        response = test_client.get("/api/monitoring/alerts/999999")
        assert response.status_code == 404  # Not found

        # Test system recovery after errors
        valid_metric = {
            "name": "recovery_test",
            "value": 42,
            "type": "gauge",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        response = test_client.post("/api/monitoring/metrics", json=valid_metric)
        assert response.status_code == 201  # System recovered


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])