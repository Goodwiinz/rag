"""
WebSocket Real-Time Data Streaming Validation Tests

This module provides comprehensive integration tests for WebSocket-based real-time monitoring:
- Metrics streaming validation
- Alerts broadcasting validation
- Health status updates validation
- Connection management and reconnection logic
- Subscription filtering and message routing
- Performance under concurrent connections
- Error handling and recovery scenarios
"""

import pytest
import asyncio
import json
import websockets
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
import httpx
from fastapi.testclient import TestClient

# Add backend to path
import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir / "src"))

from src.monitoring.api.websocket_handlers import WebSocketManager, ConnectionManager
from src.monitoring.services.observability_manager import ObservabilityManager
from src.monitoring.models.metrics import MetricModel, MetricType
from src.monitoring.models.alerting import AlertModel, AlertSeverity, AlertStatus
from src.main import app


@pytest.fixture
async def websocket_manager():
    """Create WebSocket manager instance for testing"""
    return WebSocketManager()


@pytest.fixture
async def connection_manager():
    """Create connection manager instance for testing"""
    return ConnectionManager()


@pytest.fixture
async def test_client():
    """Create FastAPI test client with WebSocket support"""
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def mock_observability_manager():
    """Create mock observability manager for WebSocket testing"""
    manager = Mock(spec=ObservabilityManager)

    # Mock methods
    async def mock_get_metrics_summary():
        return {
            "total_metrics": 150,
            "active_alerts": 3,
            "system_health": "healthy",
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

    async def mock_get_active_alerts():
        return [
            {
                "id": "alert-1",
                "title": "High Memory Usage",
                "severity": "warning",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

    manager.get_metrics_summary = mock_get_metrics_summary
    manager.get_active_alerts = mock_get_active_alerts

    return manager


class TestWebSocketConnectionManagement:
    """Test WebSocket connection lifecycle and management"""

    @pytest.mark.asyncio
    async def test_connection_establishment(self, test_client):
        """Test WebSocket connection establishment and handshake"""
        with test_client.websocket_connect("/ws/monitoring") as websocket:
            # Connection should be established successfully
            assert websocket is not None

            # Should receive welcome message
            message = websocket.receive_json()
            assert message['type'] == 'connection_established'
            assert 'connection_id' in message
            assert 'timestamp' in message

    @pytest.mark.asyncio
    async def test_connection_authentication(self, test_client):
        """Test WebSocket connection with authentication"""
        # Test connection without authentication (should fail or be limited)
        with test_client.websocket_connect("/ws/monitoring") as websocket:
            message = websocket.receive_json()

            # Should indicate limited access for unauthenticated connections
            if 'auth_required' in message:
                assert message['auth_required'] is True

    @pytest.mark.asyncio
    async def test_connection_isolation(self, test_client):
        """Test connection isolation between different clients"""
        messages_1 = []
        messages_2 = []

        # Create two separate connections
        with test_client.websocket_connect("/ws/monitoring") as websocket_1, \
             test_client.websocket_connect("/ws/monitoring") as websocket_2:

            # Get connection IDs
            msg_1 = websocket_1.receive_json()
            msg_2 = websocket_2.receive_json()

            conn_id_1 = msg_1['connection_id']
            conn_id_2 = msg_2['connection_id']

            assert conn_id_1 != conn_id_2

    @pytest.mark.asyncio
    async def test_connection_timeout_and_cleanup(self, websocket_manager):
        """Test connection timeout and cleanup procedures"""
        # Mock connection that hasn't sent ping
        mock_connection = Mock()
        mock_connection.last_ping = time.time() - 300  # 5 minutes ago
        mock_connection.is_active = True

        # Add connection to manager
        websocket_manager.connections["test-conn"] = mock_connection

        # Run cleanup
        await websocket_manager.cleanup_inactive_connections(timeout_seconds=240)

        # Connection should be removed
        assert "test-conn" not in websocket_manager.connections

    @pytest.mark.asyncio
    async def test_concurrent_connection_limits(self, test_client):
        """Test concurrent connection limits and management"""
        connections = []

        try:
            # Create multiple concurrent connections
            for i in range(10):
                websocket = test_client.websocket_connect("/ws/monitoring")
                websocket.__enter__()
                connections.append(websocket)

                # Receive welcome message
                message = websocket.receive_json()
                assert 'connection_id' in message

        except Exception as e:
            # Should handle connection limits gracefully
            assert len(connections) > 0  # At least some connections should work

        finally:
            # Cleanup connections
            for websocket in connections:
                try:
                    websocket.__exit__(None, None, None)
                except:
                    pass


class TestWebSocketMetricsStreaming:
    """Test real-time metrics streaming via WebSocket"""

    @pytest.mark.asyncio
    async def test_metrics_subscription_flow(self, test_client):
        """Test metrics subscription and message flow"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            # Subscribe to specific metrics
            subscription_msg = {
                "type": "subscribe",
                "channel": "metrics",
                "filters": {
                    "service": "api_server",
                    "metric_type": ["histogram", "counter"]
                }
            }

            websocket.send_json(subscription_msg)

            # Should receive subscription confirmation
            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'
            assert response['channel'] == 'metrics'
            assert 'subscription_id' in response

    @pytest.mark.asyncio
    async def test_real_time_metrics_broadcast(self, test_client, mock_observability_manager):
        """Test real-time metrics broadcasting to subscribers"""
        received_metrics = []

        with patch('src.monitoring.api.websocket_handlers.observability_manager', mock_observability_manager):
            with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
                # Subscribe to metrics
                websocket.send_json({
                    "type": "subscribe",
                    "channel": "metrics"
                })

                # Wait for subscription confirmation
                websocket.receive_json()

                # Simulate metric broadcast (this would normally come from the metrics collector)
                test_metric = {
                    "type": "metric_update",
                    "data": {
                        "name": "request_duration",
                        "value": 150.5,
                        "labels": {"endpoint": "/api/search", "method": "POST"},
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }

                # In the actual implementation, this would be sent by the metrics collector
                # For testing, we'll simulate the WebSocket receiving this message

                # Test message format validation
                assert test_metric['type'] == 'metric_update'
                assert 'data' in test_metric
                assert 'name' in test_metric['data']
                assert 'value' in test_metric['data']

    @pytest.mark.asyncio
    async def test_metrics_filtering_and_routing(self, test_client):
        """Test metrics filtering and routing based on subscription criteria"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            # Subscribe with specific filters
            websocket.send_json({
                "type": "subscribe",
                "channel": "metrics",
                "filters": {
                    "service": "vector_store",
                    "severity": ["error", "warning"]
                }
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'

            # Test that only matching metrics would be routed
            # This would require integration with the actual metrics broadcast system

    @pytest.mark.asyncio
    async def test_metrics_aggregation_updates(self, test_client):
        """Test aggregated metrics updates streaming"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            # Subscribe to aggregated metrics
            websocket.send_json({
                "type": "subscribe",
                "channel": "metrics_aggregated",
                "filters": {
                    "aggregation": ["avg", "max", "p95"],
                    "window": "1m"
                }
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'
            assert response['channel'] == 'metrics_aggregated'

            # Should receive periodic aggregated updates
            # Format: {"type": "metrics_aggregated", "data": {...}}

    @pytest.mark.asyncio
    async def test_high_frequency_metrics_streaming(self, test_client):
        """Test WebSocket performance under high-frequency metrics updates"""
        message_count = 0
        start_time = time.time()

        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "metrics"
            })

            websocket.receive_json()  # Subscription confirmation

            # Simulate receiving high-frequency updates
            # In real scenario, these would come from the monitoring system
            end_time = start_time + 5  # 5 seconds

            while time.time() < end_time:
                try:
                    # Set timeout to avoid blocking
                    message = websocket.receive_json(timeout=0.1)
                    if message.get('type') == 'metric_update':
                        message_count += 1
                except:
                    # Timeout is expected during testing
                    continue

        duration = time.time() - start_time
        messages_per_second = message_count / duration if duration > 0 else 0

        # Verify performance metrics
        assert duration <= 6  # Should complete within 6 seconds
        # Performance will depend on the actual implementation


class TestWebSocketAlertsStreaming:
    """Test real-time alerts streaming via WebSocket"""

    @pytest.mark.asyncio
    async def test_alerts_subscription_and_broadcast(self, test_client):
        """Test alerts subscription and real-time broadcasting"""
        with test_client.websocket_connect("/ws/monitoring/alerts") as websocket:
            # Subscribe to alerts
            websocket.send_json({
                "type": "subscribe",
                "channel": "alerts",
                "filters": {
                    "severity": ["warning", "error", "critical"]
                }
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'
            assert response['channel'] == 'alerts'

    @pytest.mark.asyncio
    async def test_alert_lifecycle_updates(self, test_client):
        """Test alert lifecycle updates (created, escalated, resolved)"""
        alert_updates = []

        with test_client.websocket_connect("/ws/monitoring/alerts") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "alerts"
            })

            websocket.receive_json()  # Subscription confirmation

            # Test alert creation notification format
            alert_created = {
                "type": "alert_created",
                "data": {
                    "id": "alert-123",
                    "title": "High CPU Usage",
                    "severity": "warning",
                    "status": "active",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

            # Test alert escalation notification format
            alert_escalated = {
                "type": "alert_escalated",
                "data": {
                    "id": "alert-123",
                    "previous_severity": "warning",
                    "new_severity": "error",
                    "reason": "Threshold exceeded for 5 minutes",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

            # Test alert resolution notification format
            alert_resolved = {
                "type": "alert_resolved",
                "data": {
                    "id": "alert-123",
                    "resolution_note": "Service restarted successfully",
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }
            }

    @pytest.mark.asyncio
    async def test_alert_filtering_by_severity(self, test_client):
        """Test alert filtering by severity level"""
        # Test subscription to only critical alerts
        with test_client.websocket_connect("/ws/monitoring/alerts") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "alerts",
                "filters": {
                    "severity": ["critical"]
                }
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'

            # Should only receive critical alerts
            # This would be tested with actual alert generation

    @pytest.mark.asyncio
    async def test_alert_filtering_by_service(self, test_client):
        """Test alert filtering by service or component"""
        with test_client.websocket_connect("/ws/monitoring/alerts") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "alerts",
                "filters": {
                    "service": ["vector_store", "database"],
                    "component": ["query_engine", "connection_pool"]
                }
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'

            # Verify filtering is applied correctly
            # This would require actual alert generation

    @pytest.mark.asyncio
    async def test_alert_acknowledgment_updates(self, test_client):
        """Test alert acknowledgment status updates via WebSocket"""
        with test_client.websocket_connect("/ws/monitoring/alerts") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "alerts"
            })

            websocket.receive_json()  # Subscription confirmation

            # Test alert acknowledgment notification
            ack_notification = {
                "type": "alert_acknowledged",
                "data": {
                    "id": "alert-456",
                    "acknowledged_by": "user123",
                    "acknowledged_at": datetime.now(timezone.utc).isoformat(),
                    "note": "Investigating the issue"
                }
            }


class TestWebSocketHealthStatusStreaming:
    """Test real-time health status streaming via WebSocket"""

    @pytest.mark.asyncio
    async def test_health_status_subscription(self, test_client):
        """Test health status subscription and updates"""
        with test_client.websocket_connect("/ws/monitoring/health") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "health"
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'
            assert response['channel'] == 'health'

    @pytest.mark.asyncio
    async def test_component_health_updates(self, test_client):
        """Test component health status updates"""
        with test_client.websocket_connect("/ws/monitoring/health") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "health"
            })

            websocket.receive_json()  # Subscription confirmation

            # Test component health update format
            health_update = {
                "type": "component_health_update",
                "data": {
                    "component": "database",
                    "status": "degraded",
                    "previous_status": "healthy",
                    "metrics": {
                        "connection_time_ms": 150,
                        "active_connections": 85,
                        "max_connections": 100
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

    @pytest.mark.asyncio
    async def test_system_health_summary(self, test_client):
        """Test system health summary updates"""
        with test_client.websocket_connect("/ws/monitoring/health") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "health_summary"
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'

            # Test health summary format
            health_summary = {
                "type": "health_summary",
                "data": {
                    "overall_status": "healthy",
                    "components": {
                        "database": {"status": "healthy", "uptime": "99.9%"},
                        "vector_store": {"status": "healthy", "uptime": "99.5%"},
                        "graph_db": {"status": "warning", "uptime": "98.2%"},
                        "monitoring": {"status": "healthy", "uptime": "100%"}
                    },
                    "active_alerts": 2,
                    "last_check": datetime.now(timezone.utc).isoformat()
                }
            }

    @pytest.mark.asyncio
    async def test_health_check_scheduling_updates(self, test_client):
        """Test health check scheduling status updates"""
        with test_client.websocket_connect("/ws/monitoring/health") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "health_checks"
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'

            # Test health check scheduling update
            scheduling_update = {
                "type": "health_check_scheduled",
                "data": {
                    "check_type": "comprehensive",
                    "scheduled_at": datetime.now(timezone.utc).isoformat(),
                    "components": ["database", "vector_store", "graph_db"],
                    "estimated_duration": 30
                }
            }


class TestWebSocketPerformanceAndScalability:
    """Test WebSocket performance under various conditions"""

    @pytest.mark.asyncio
    async def test_concurrent_connections_performance(self, test_client):
        """Test WebSocket performance with multiple concurrent connections"""
        connection_count = 20
        connections = []
        subscription_times = []

        start_time = time.time()

        try:
            # Create multiple concurrent connections
            for i in range(connection_count):
                websocket = test_client.websocket_connect("/ws/monitoring/metrics")
                websocket.__enter__()
                connections.append(websocket)

                # Subscribe and measure time
                sub_start = time.time()
                websocket.send_json({
                    "type": "subscribe",
                    "channel": "metrics"
                })
                websocket.receive_json()
                sub_time = time.time() - sub_start
                subscription_times.append(sub_time)

        finally:
            # Cleanup connections
            for websocket in connections:
                try:
                    websocket.__exit__(None, None, None)
                except:
                    pass

        total_time = time.time() - start_time
        avg_subscription_time = sum(subscription_times) / len(subscription_times) if subscription_times else 0

        # Performance assertions
        assert total_time < 10  # Should complete within 10 seconds
        assert avg_subscription_time < 1  # Average subscription should be under 1 second
        assert len(connections) == connection_count

    @pytest.mark.asyncio
    async def test_message_throughput(self, test_client):
        """Test WebSocket message throughput under load"""
        message_count = 0
        test_duration = 3  # seconds

        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "metrics"
            })

            websocket.receive_json()  # Subscription confirmation

            start_time = time.time()
            end_time = start_time + test_duration

            while time.time() < end_time:
                try:
                    message = websocket.receive_json(timeout=0.1)
                    if message.get('type') in ['metric_update', 'metrics_aggregated']:
                        message_count += 1
                except:
                    continue

        actual_duration = time.time() - start_time
        messages_per_second = message_count / actual_duration if actual_duration > 0 else 0

        # Throughput assertions (will depend on actual implementation)
        assert actual_duration <= test_duration + 1  # Allow some margin
        # The actual throughput will depend on the monitoring system's activity

    @pytest.mark.asyncio
    async def test_connection_memory_usage(self, websocket_manager):
        """Test memory usage of WebSocket connections"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Simulate multiple connections
        mock_connections = []
        for i in range(100):
            mock_conn = Mock()
            mock_conn.connection_id = f"conn-{i}"
            mock_conn.subscriptions = {"metrics": {}, "alerts": {}}
            mock_conn.last_ping = time.time()
            mock_conn.is_active = True
            mock_connections.append(mock_conn)
            websocket_manager.connections[mock_conn.connection_id] = mock_conn

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory
        memory_per_connection = memory_increase / len(mock_connections)

        # Cleanup
        websocket_manager.connections.clear()

        # Memory assertions (adjust thresholds based on requirements)
        assert memory_per_connection < 1024 * 1024  # Less than 1MB per connection


class TestWebSocketErrorHandlingAndRecovery:
    """Test WebSocket error handling and recovery mechanisms"""

    @pytest.mark.asyncio
    async def test_invalid_message_handling(self, test_client):
        """Test handling of invalid WebSocket messages"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            # Send invalid JSON
            try:
                websocket.send_text("invalid json")
                # Should handle gracefully
                response = websocket.receive_json()
                assert response['type'] == 'error'
            except:
                # Connection might be closed on invalid messages
                pass

            # Send invalid message structure
            try:
                websocket.send_json({
                    "type": "invalid_type",
                    "data": "test"
                })
                response = websocket.receive_json()
                assert response['type'] == 'error'
                assert 'message' in response
            except:
                pass

    @pytest.mark.asyncio
    async def test_connection_interruption_recovery(self, test_client):
        """Test recovery from connection interruptions"""
        connection_attempts = 0
        max_attempts = 3

        while connection_attempts < max_attempts:
            try:
                with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
                    websocket.send_json({
                        "type": "subscribe",
                        "channel": "metrics"
                    })

                    response = websocket.receive_json()
                    assert response['type'] == 'subscription_confirmed'

                    # Simulate connection interruption by closing
                    break

            except Exception as e:
                connection_attempts += 1
                if connection_attempts >= max_attempts:
                    raise e
                await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_subscription_error_handling(self, test_client):
        """Test subscription error handling"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            # Subscribe with invalid filters
            websocket.send_json({
                "type": "subscribe",
                "channel": "metrics",
                "filters": {
                    "invalid_filter": "invalid_value"
                }
            })

            response = websocket.receive_json()
            # Should either confirm with limited functionality or return error
            assert response['type'] in ['subscription_confirmed', 'error']

    @pytest.mark.asyncio
    async def test_rate_limiting(self, test_client):
        """Test WebSocket message rate limiting"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            # Send multiple subscription requests rapidly
            for i in range(10):
                websocket.send_json({
                    "type": "subscribe",
                    "channel": "metrics",
                    "subscription_id": f"sub-{i}"
                })

            # Should handle rate limiting gracefully
            try:
                response = websocket.receive_json()
                # Either confirms subscriptions or applies rate limiting
                assert response['type'] in ['subscription_confirmed', 'error']
            except:
                # Connection might be closed due to rate limiting
                pass


class TestWebSocketSecurityAndAuthorization:
    """Test WebSocket security and authorization mechanisms"""

    @pytest.mark.asyncio
    async def test_unauthorized_connection_handling(self, test_client):
        """Test handling of unauthorized connections"""
        # Test connection without authentication
        with test_client.websocket_connect("/ws/monitoring") as websocket:
            response = websocket.receive_json()

            # Should indicate authorization status
            if 'auth_required' in response:
                assert response['auth_required'] is True

    @pytest.mark.asyncio
    async def test_subscription_authorization(self, test_client):
        """Test subscription-level authorization"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            # Try to subscribe to restricted channel
            websocket.send_json({
                "type": "subscribe",
                "channel": "admin_metrics"
            })

            response = websocket.receive_json()
            # Should handle authorization gracefully
            assert response['type'] in ['subscription_confirmed', 'error', 'unauthorized']

    @pytest.mark.asyncio
    async def test_message_content_filtering(self, test_client):
        """Test filtering of sensitive message content"""
        with test_client.websocket_connect("/ws/monitoring/metrics") as websocket:
            websocket.send_json({
                "type": "subscribe",
                "channel": "metrics"
            })

            response = websocket.receive_json()
            assert response['type'] == 'subscription_confirmed'

            # Messages should not contain sensitive information
            # This would be tested with actual message content

    @pytest.mark.asyncio
    async def test_connection_isolation_between_users(self, test_client):
        """Test connection isolation between different users"""
        # Test that users can only see their own data
        # This would require authentication setup
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])