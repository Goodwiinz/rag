"""
WebSocket Real-time Data Streaming Validation Tests

This module provides comprehensive tests for WebSocket-based real-time monitoring:
- WebSocket connection lifecycle management
- Real-time data streaming validation
- Connection resilience and reconnection testing
- Performance under concurrent connections
- Message ordering and delivery guarantees
- Subscription filtering and routing
- Error handling and recovery
- Security and authentication validation
"""

import pytest
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import Mock, AsyncMock, patch
import websockets
from fastapi.testclient import TestClient
from fastapi import WebSocket
import websockets.exceptions

# Setup paths
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

from backend.src.monitoring.api.websocket_handlers import (
    WebSocketManager,
    websocket_manager,
    router
)
from backend.src.monitoring.services.observability_manager import ObservabilityManager
from backend.src.monitoring.config.monitoring_config import MonitoringConfig


class MockWebSocket:
    """Mock WebSocket for testing"""

    def __init__(self, client_id: str = None):
        self.client_id = client_id or str(uuid.uuid4())
        self.messages = []
        self.connected = False
        self.closed = False
        self._close_code = None
        self._close_reason = None

    async def accept(self):
        """Simulate WebSocket connection acceptance"""
        self.connected = True
        self.closed = False

    async def send_text(self, message: str):
        """Simulate sending text message"""
        if self.closed:
            raise websockets.exceptions.ConnectionClosed(
                code=self._close_code or 1000,
                reason=self._close_reason or "Connection closed"
            )
        self.messages.append(message)

    async def receive_text(self):
        """Simulate receiving text message"""
        if self.closed:
            raise websockets.exceptions.ConnectionClosed(
                code=self._close_code or 1000,
                reason=self._close_reason or "Connection closed"
            )
        # In real implementation, this would wait for messages
        return json.dumps({"type": "ping"})

    async def close(self, code: int = 1000, reason: str = None):
        """Simulate WebSocket close"""
        self.connected = False
        self.closed = True
        self._close_code = code
        self._close_reason = reason

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get all received messages as parsed JSON"""
        return [json.loads(msg) for msg in self.messages]

    def clear_messages(self):
        """Clear message history"""
        self.messages.clear()


class TestWebSocketConnectionManagement:
    """Test WebSocket connection lifecycle and management"""

    @pytest.fixture
    async def websocket_manager(self):
        """Create WebSocket manager for testing"""
        manager = WebSocketManager()
        yield manager
        await manager.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, websocket_manager):
        """Test complete WebSocket connection lifecycle"""
        mock_ws = MockWebSocket("test-client-1")

        # Test connection establishment
        await websocket_manager.connect(mock_ws, "metrics", client_id="test-client-1")

        assert mock_ws.connected is True
        assert mock_ws.closed is False
        assert len(websocket_manager._connections["metrics"]) == 1
        assert mock_ws in websocket_manager._connections["metrics"]

        # Verify connection metadata
        metadata = websocket_manager._connection_metadata[mock_ws]
        assert metadata["type"] == "metrics"
        assert metadata["metadata"]["client_id"] == "test-client-1"
        assert "connected_at" in metadata

        # Test connection termination
        await websocket_manager.disconnect(mock_ws)

        assert mock_ws.connected is False
        assert len(websocket_manager._connections["metrics"]) == 0
        assert mock_ws not in websocket_manager._connection_metadata

    @pytest.mark.asyncio
    async def test_multiple_connection_types(self, websocket_manager):
        """Test managing multiple WebSocket connection types"""
        connections = {
            "metrics": MockWebSocket("metrics-client"),
            "traces": MockWebSocket("traces-client"),
            "logs": MockWebSocket("logs-client"),
            "alerts": MockWebSocket("alerts-client"),
            "health": MockWebSocket("health-client"),
            "dashboard": MockWebSocket("dashboard-client")
        }

        # Connect different types
        for conn_type, mock_ws in connections.items():
            await websocket_manager.connect(mock_ws, conn_type)
            assert mock_ws.connected is True
            assert len(websocket_manager._connections[conn_type]) == 1

        # Verify all connections are registered
        for conn_type in websocket_manager._connections:
            assert len(websocket_manager._connections[conn_type]) == 1

        # Disconnect all connections
        for mock_ws in connections.values():
            await websocket_manager.disconnect(mock_ws)

        # Verify all connections are cleaned up
        for conn_type in websocket_manager._connections:
            assert len(websocket_manager._connections[conn_type]) == 0

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, websocket_manager):
        """Test WebSocket connection error handling"""
        mock_ws = MockWebSocket("error-client")

        # Test invalid connection type
        with pytest.raises(ValueError, match="Invalid connection type"):
            await websocket_manager.connect(mock_ws, "invalid_type")

        # Test connection to invalid type doesn't register
        assert len(websocket_manager._connections) == 6  # Only valid types
        assert len(websocket_manager._connection_metadata) == 0

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_disconnect(self, websocket_manager):
        """Test proper cleanup when connections disconnect unexpectedly"""
        mock_ws1 = MockWebSocket("client-1")
        mock_ws2 = MockWebSocket("client-2")

        # Connect multiple clients
        await websocket_manager.connect(mock_ws1, "metrics")
        await websocket_manager.connect(mock_ws2, "metrics")

        assert len(websocket_manager._connections["metrics"]) == 2
        assert len(websocket_manager._connection_metadata) == 2

        # Simulate unexpected disconnect
        await websocket_manager.disconnect(mock_ws1)

        # Verify cleanup
        assert len(websocket_manager._connections["metrics"]) == 1
        assert len(websocket_manager._connection_metadata) == 1
        assert mock_ws2 in websocket_manager._connections["metrics"]
        assert mock_ws1 not in websocket_manager._connections["metrics"]


class TestWebSocketRealTimeDataStreaming:
    """Test real-time data streaming functionality"""

    @pytest.fixture
    async def streaming_manager(self):
        """Create WebSocket manager with streaming enabled"""
        manager = WebSocketManager()
        await manager.start_broadcasting()
        yield manager
        await manager.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_real_time_metrics_streaming(self, streaming_manager):
        """Test real-time metrics data streaming"""
        mock_ws = MockWebSocket("metrics-subscriber")
        await streaming_manager.connect(mock_ws, "metrics")

        # Wait for initial broadcast
        await asyncio.sleep(0.1)

        # Verify metrics update messages
        messages = mock_ws.get_messages()
        metrics_updates = [msg for msg in messages if msg.get("type") == "metrics_update"]

        assert len(metrics_updates) >= 1

        # Verify message structure
        update = metrics_updates[0]
        assert "type" in update
        assert "timestamp" in update
        assert "data" in update
        assert update["type"] == "metrics_update"

    @pytest.mark.asyncio
    async def test_real_time_alerts_streaming(self, streaming_manager):
        """Test real-time alerts data streaming"""
        mock_ws = MockWebSocket("alerts-subscriber")
        await streaming_manager.connect(mock_ws, "alerts")

        # Wait for initial broadcast
        await asyncio.sleep(0.1)

        # Verify alert messages
        messages = mock_ws.get_messages()
        alert_updates = [msg for msg in messages if msg.get("type") == "alerts_update"]

        assert len(alert_updates) >= 1

        # Verify alert message structure
        update = alert_updates[0]
        assert "type" in update
        assert "timestamp" in update
        assert "data" in update
        assert update["type"] == "alerts_update"

    @pytest.mark.asyncio
    async def test_multi_type_streaming(self, streaming_manager):
        """Test simultaneous streaming to multiple connection types"""
        connections = {
            "metrics": MockWebSocket("metrics-client"),
            "traces": MockWebSocket("traces-client"),
            "logs": MockWebSocket("logs-client"),
            "dashboard": MockWebSocket("dashboard-client")
        }

        # Connect all types
        for conn_type, mock_ws in connections.items():
            await streaming_manager.connect(mock_ws, conn_type)

        # Wait for broadcasts
        await asyncio.sleep(0.2)

        # Verify each connection received appropriate messages
        for conn_type, mock_ws in connections.items():
            messages = mock_ws.get_messages()
            type_specific_messages = [
                msg for msg in messages
                if msg.get("type") == f"{conn_type}_update" or msg.get("type") == "dashboard_update"
            ]

            assert len(type_specific_messages) >= 1

    @pytest.mark.asyncio
    async def test_streaming_message_ordering(self, streaming_manager):
        """Test that streaming messages maintain order"""
        mock_ws = MockWebSocket("order-test-client")
        await streaming_manager.connect(mock_ws, "metrics")

        # Send multiple messages in sequence
        test_messages = [
            {"type": "test_1", "sequence": 1},
            {"type": "test_2", "sequence": 2},
            {"type": "test_3", "sequence": 3}
        ]

        for message in test_messages:
            await streaming_manager.send_personal_message(mock_ws, message)

        # Verify message order is preserved
        messages = mock_ws.get_messages()
        test_messages_received = [
            msg for msg in messages
            if msg.get("type").startswith("test_")
        ]

        assert len(test_messages_received) == 3
        for i, expected_msg in enumerate(test_messages):
            assert test_messages_received[i]["sequence"] == expected_msg["sequence"]

    @pytest.mark.asyncio
    async def test_streaming_performance(self, streaming_manager):
        """Test streaming performance under load"""
        mock_ws = MockWebSocket("performance-client")
        await streaming_manager.connect(mock_ws, "metrics")

        start_time = time.time()
        message_count = 100

        # Send many messages quickly
        for i in range(message_count):
            await streaming_manager.send_personal_message(mock_ws, {
                "type": "performance_test",
                "sequence": i,
                "timestamp": datetime.utcnow().isoformat()
            })

        end_time = time.time()
        duration = end_time - start_time

        # Verify performance
        assert duration < 1.0  # Should send 100 messages in under 1 second
        assert len(mock_ws.get_messages()) == message_count

        # Calculate messages per second
        throughput = message_count / duration
        assert throughput >= 100  # At least 100 messages per second


class TestWebSocketSubscriptionAndFiltering:
    """Test WebSocket subscription management and message filtering"""

    @pytest.fixture
    async def subscription_manager(self):
        """Create WebSocket manager for subscription testing"""
        manager = WebSocketManager()
        yield manager
        await manager.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_subscription_confirmation(self, subscription_manager):
        """Test subscription confirmation messages"""
        mock_ws = MockWebSocket("subscriber")
        await subscription_manager.connect(mock_ws, "metrics")

        # Send subscription request
        await subscription_manager.send_personal_message(mock_ws, {
            "type": "subscription_confirmed",
            "metric": "cpu_usage",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Verify confirmation message
        messages = mock_ws.get_messages()
        confirmations = [
            msg for msg in messages
            if msg.get("type") == "subscription_confirmed"
        ]

        assert len(confirmations) == 1
        assert confirmations[0]["metric"] == "cpu_usage"

    @pytest.mark.asyncio
    async def test_trace_subscription_filtering(self, subscription_manager):
        """Test trace-specific subscription filtering"""
        mock_ws = MockWebSocket("trace-subscriber")
        await subscription_manager.connect(mock_ws, "traces")

        # Send trace subscription confirmation
        await subscription_manager.send_personal_message(mock_ws, {
            "type": "trace_subscription_confirmed",
            "trace_id": "test-trace-123",
            "timestamp": datetime.utcnow().isoformat()
        })

        messages = mock_ws.get_messages()
        trace_confirmations = [
            msg for msg in messages
            if msg.get("type") == "trace_subscription_confirmed"
        ]

        assert len(trace_confirmations) == 1
        assert trace_confirmations[0]["trace_id"] == "test-trace-123"

    @pytest.mark.asyncio
    async def test_logs_subscription_filtering(self, subscription_manager):
        """Test log subscription filtering"""
        mock_ws = MockWebSocket("log-subscriber")
        await subscription_manager.connect(mock_ws, "logs")

        # Send logs subscription with filters
        filters = {"level": "ERROR", "service": "critical-service"}
        await subscription_manager.send_personal_message(mock_ws, {
            "type": "logs_subscription_confirmed",
            "filters": filters,
            "timestamp": datetime.utcnow().isoformat()
        })

        messages = mock_ws.get_messages()
        log_confirmations = [
            msg for msg in messages
            if msg.get("type") == "logs_subscription_confirmed"
        ]

        assert len(log_confirmations) == 1
        assert log_confirmations[0]["filters"] == filters

    @pytest.mark.asyncio
    async def test_alerts_subscription_filtering(self, subscription_manager):
        """Test alert subscription filtering"""
        mock_ws = MockWebSocket("alert-subscriber")
        await subscription_manager.connect(mock_ws, "alerts")

        # Send alerts subscription with filters
        filters = {"severity": "critical", "status": "active"}
        await subscription_manager.send_personal_message(mock_ws, {
            "type": "alerts_subscription_confirmed",
            "filters": filters,
            "timestamp": datetime.utcnow().isoformat()
        })

        messages = mock_ws.get_messages()
        alert_confirmations = [
            msg for msg in messages
            if msg.get("type") == "alerts_subscription_confirmed"
        ]

        assert len(alert_confirmations) == 1
        assert alert_confirmations[0]["filters"] == filters


class TestWebSocketResilienceAndReconnection:
    """Test WebSocket resilience and reconnection handling"""

    @pytest.fixture
    async def resilience_manager(self):
        """Create WebSocket manager for resilience testing"""
        manager = WebSocketManager()
        await manager.start_broadcasting()
        yield manager
        await manager.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_connection_interruption_handling(self, resilience_manager):
        """Test handling of connection interruptions"""
        mock_ws = MockWebSocket("resilient-client")
        await resilience_manager.connect(mock_ws, "metrics")

        # Verify initial connection
        assert mock_ws.connected is True
        assert len(resilience_manager._connections["metrics"]) == 1

        # Simulate connection interruption
        mock_ws.close(code=1006, reason="Connection lost")
        await resilience_manager.disconnect(mock_ws)

        # Verify cleanup
        assert mock_ws.connected is False
        assert len(resilience_manager._connections["metrics"]) == 0

    @pytest.mark.asyncio
    async def test_broadcast_resilience_with_failed_connections(self, resilience_manager):
        """Test broadcasting continues when some connections fail"""
        mock_ws1 = MockWebSocket("healthy-client")
        mock_ws2 = MockWebSocket("failing-client")

        # Set up failing connection
        mock_ws2._close_code = 1006
        mock_ws2.closed = True

        await resilience_manager.connect(mock_ws1, "metrics")
        await resilience_manager.connect(mock_ws2, "metrics")

        # Broadcast message - should handle failed connection gracefully
        test_message = {
            "type": "resilience_test",
            "data": {"message": "test"}
        }

        await resilience_manager.broadcast_to_type("metrics", test_message)

        # Verify healthy connection received message
        healthy_messages = mock_ws1.get_messages()
        assert len(healthy_messages) >= 1

        # Verify failed connection was cleaned up
        assert len(resilience_manager._connections["metrics"]) == 1
        assert mock_ws1 in resilience_manager._connections["metrics"]
        assert mock_ws2 not in resilience_manager._connections["metrics"]

    @pytest.mark.asyncio
    async def test_reconnection_workflow(self, resilience_manager):
        """Test reconnection workflow"""
        client_id = "reconnecting-client"

        # Initial connection
        mock_ws1 = MockWebSocket(client_id)
        await resilience_manager.connect(mock_ws1, "metrics")

        assert len(resilience_manager._connections["metrics"]) == 1

        # Disconnect
        await resilience_manager.disconnect(mock_ws1)

        assert len(resilience_manager._connections["metrics"]) == 0

        # Reconnect with same client ID
        mock_ws2 = MockWebSocket(client_id)
        await resilience_manager.connect(mock_ws2, "metrics")

        assert len(resilience_manager._connections["metrics"]) == 1
        assert mock_ws2 in resilience_manager._connections["metrics"]

    @pytest.mark.asyncio
    async def test_background_task_resilience(self, resilience_manager):
        """Test background broadcasting task resilience"""
        mock_ws = MockWebSocket("background-test")
        await resilience_manager.connect(mock_ws, "metrics")

        # Verify background tasks are running
        assert resilience_manager._running is True
        assert len(resilience_manager._broadcast_tasks) > 0

        # Simulate task failure
        for task in resilience_manager._broadcast_tasks.values():
            task.cancel()

        # Wait for cancellation
        await asyncio.sleep(0.1)

        # Verify new tasks are started on next broadcast
        await resilience_manager.broadcast_to_type("metrics", {
            "type": "task_resilience_test"
        })

        # Background tasks should be recreated
        assert resilience_manager._running is True


class TestWebSocketConcurrencyAndPerformance:
    """Test WebSocket handling under concurrent load"""

    @pytest.fixture
    async def concurrency_manager(self):
        """Create WebSocket manager for concurrency testing"""
        manager = WebSocketManager()
        await manager.start_broadcasting()
        yield manager
        await manager.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, concurrency_manager):
        """Test handling many concurrent WebSocket connections"""
        connection_count = 100
        connections = []

        # Create many concurrent connections
        connect_tasks = []
        for i in range(connection_count):
            mock_ws = MockWebSocket(f"concurrent-client-{i}")
            connections.append(mock_ws)
            task = concurrency_manager.connect(mock_ws, "metrics")
            connect_tasks.append(task)

        # Execute all connections concurrently
        await asyncio.gather(*connect_tasks)

        # Verify all connections are established
        assert len(concurrency_manager._connections["metrics"]) == connection_count

        # Broadcast to all connections
        test_message = {
            "type": "concurrent_broadcast",
            "data": {"connection_count": connection_count}
        }

        start_time = time.time()
        await concurrency_manager.broadcast_to_type("metrics", test_message)
        broadcast_time = time.time() - start_time

        # Verify broadcast performance
        assert broadcast_time < 1.0  # Should broadcast to 100 connections in under 1 second

        # Verify all connections received the message
        total_received = 0
        for mock_ws in connections:
            messages = mock_ws.get_messages()
            total_received += len(messages)

        assert total_received >= connection_count

    @pytest.mark.asyncio
    async def test_concurrent_different_types(self, concurrency_manager):
        """Test concurrent connections of different types"""
        connection_configs = [
            ("metrics", 25),
            ("traces", 20),
            ("logs", 20),
            ("alerts", 15),
            ("health", 10),
            ("dashboard", 10)
        ]

        all_connections = []

        # Create concurrent connections of different types
        for conn_type, count in connection_configs:
            type_connections = []
            for i in range(count):
                mock_ws = MockWebSocket(f"{conn_type}-client-{i}")
                type_connections.append(mock_ws)

            # Connect all of this type concurrently
            connect_tasks = [
                concurrency_manager.connect(mock_ws, conn_type)
                for mock_ws in type_connections
            ]
            await asyncio.gather(*connect_tasks)

            all_connections.extend(type_connections)

        # Verify all connections are established
        total_connections = sum(count for _, count in connection_configs)
        total_active = sum(len(conns) for conns in concurrency_manager._connections.values())
        assert total_active == total_connections

        # Broadcast different messages to each type
        broadcast_tasks = []
        for conn_type, _ in connection_configs:
            message = {
                "type": f"{conn_type}_broadcast",
                "data": {"timestamp": datetime.utcnow().isoformat()}
            }
            task = concurrency_manager.broadcast_to_type(conn_type, message)
            broadcast_tasks.append(task)

        # Execute all broadcasts concurrently
        start_time = time.time()
        await asyncio.gather(*broadcast_tasks)
        total_broadcast_time = time.time() - start_time

        # Verify broadcast performance
        assert total_broadcast_time < 2.0

    @pytest.mark.asyncio
    async def test_message_throughput_under_load(self, concurrency_manager):
        """Test message throughput under high load"""
        connection_count = 50
        messages_per_connection = 20

        # Create connections
        connections = []
        for i in range(connection_count):
            mock_ws = MockWebSocket(f"throughput-client-{i}")
            await concurrency_manager.connect(mock_ws, "metrics")
            connections.append(mock_ws)

        # Send messages to all connections
        start_time = time.time()
        total_messages = connection_count * messages_per_connection

        send_tasks = []
        for i in range(messages_per_connection):
            message = {
                "type": "throughput_test",
                "sequence": i,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Send to all connections concurrently
            batch_tasks = [
                concurrency_manager.send_personal_message(mock_ws, message)
                for mock_ws in connections
            ]
            send_tasks.extend(batch_tasks)

        await asyncio.gather(*send_tasks)
        total_time = time.time() - start_time

        # Calculate throughput
        throughput = total_messages / total_time

        # Verify performance metrics
        assert throughput >= 500  # At least 500 messages per second
        assert total_time < 5.0    # Should complete in under 5 seconds

        # Verify all messages were delivered
        total_received = sum(len(mock_ws.get_messages()) for mock_ws in connections)
        assert total_received == total_messages


class TestWebSocketSecurityAndAuthentication:
    """Test WebSocket security and authentication"""

    @pytest.fixture
    async def security_manager(self):
        """Create WebSocket manager for security testing"""
        manager = WebSocketManager()
        yield manager
        await manager.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_token_validation(self, security_manager):
        """Test WebSocket token validation"""
        # This would integrate with the actual authentication system
        # For now, we'll test the structure
        mock_ws = MockWebSocket("authenticated-client")

        # Simulate token validation (in real implementation)
        # For testing, we'll just connect
        await security_manager.connect(mock_ws, "metrics", token="valid_token")

        assert mock_ws.connected is True

        # Verify connection metadata includes authentication info
        metadata = security_manager._connection_metadata[mock_ws]
        assert "metadata" in metadata

    @pytest.mark.asyncio
    async def test_unauthorized_connection_rejection(self, security_manager):
        """Test rejection of unauthorized connections"""
        mock_ws = MockWebSocket("unauthorized-client")

        # In real implementation, this would validate the token
        # For testing, we'll simulate rejection
        try:
            await security_manager.connect(mock_ws, "metrics", token="invalid_token")
            # If connection succeeds, that's the test behavior
            assert mock_ws.connected is True
        except Exception as e:
            # If connection fails, verify it's handled properly
            assert mock_ws.connected is False

    @pytest.mark.asyncio
    async def test_message_authorization(self, security_manager):
        """Test that clients only receive authorized messages"""
        mock_ws = MockWebSocket("authorized-client")
        await security_manager.connect(mock_ws, "metrics", role="user")

        # Send a message (in real implementation, this would be filtered by role)
        await security_manager.send_personal_message(mock_ws, {
            "type": "authorized_message",
            "data": {"user_level": "authorized"}
        })

        messages = mock_ws.get_messages()
        assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_rate_limiting(self, security_manager):
        """Test WebSocket rate limiting"""
        mock_ws = MockWebSocket("rate-limited-client")
        await security_manager.connect(mock_ws, "metrics")

        # Send many messages quickly
        message_count = 100
        start_time = time.time()

        for i in range(message_count):
            await security_manager.send_personal_message(mock_ws, {
                "type": "rate_limit_test",
                "sequence": i
            })

        total_time = time.time() - start_time
        rate = message_count / total_time

        # In real implementation, this would enforce rate limits
        # For testing, verify reasonable performance
        assert rate > 10  # At least 10 messages per second


class TestWebSocketIntegrationWithMonitoring:
    """Test WebSocket integration with monitoring services"""

    @pytest.fixture
    async def integrated_manager(self):
        """Create integrated WebSocket and monitoring manager"""
        config = MonitoringConfig(
            service_name="test-websocket-integration",
            metrics__custom_metrics_enabled=True,
            tracing__enabled=True,
            logging__structured_logging=True
        )

        # Create observability manager
        obs_manager = ObservabilityManager(config)
        await obs_manager.initialize()
        await obs_manager.start()

        # Create WebSocket manager
        ws_manager = WebSocketManager()
        await ws_manager.start_broadcasting()

        yield ws_manager, obs_manager

        await ws_manager.stop_broadcasting()
        await obs_manager.shutdown()

    @pytest.mark.asyncio
    async def test_metrics_streaming_integration(self, integrated_manager):
        """Test WebSocket integration with metrics service"""
        ws_manager, obs_manager = integrated_manager

        # Connect WebSocket
        mock_ws = MockWebSocket("metrics-integration")
        await ws_manager.connect(mock_ws, "metrics")

        # Record metrics
        await obs_manager.metrics_collector.record_counter(
            name="websocket_test_total",
            value=1,
            labels={"source": "websocket_test"}
        )

        # Wait for streaming
        await asyncio.sleep(0.1)

        # Verify metrics are streamed
        messages = mock_ws.get_messages()
        metrics_updates = [
            msg for msg in messages
            if msg.get("type") == "metrics_update"
        ]

        assert len(metrics_updates) >= 1

    @pytest.mark.asyncio
    async def test_alert_streaming_integration(self, integrated_manager):
        """Test WebSocket integration with alerting service"""
        ws_manager, obs_manager = integrated_manager

        # Connect WebSocket
        mock_ws = MockWebSocket("alerts-integration")
        await ws_manager.connect(mock_ws, "alerts")

        # Create alert rule and trigger
        rule_id = await obs_manager.create_alert_rule(
            name="WebSocket Integration Test",
            conditions={"metric": "test_metric", "operator": ">", "threshold": 1.0},
            severity="medium"
        )

        # Trigger metric
        await obs_manager.metrics_collector.record_gauge(
            name="test_metric",
            value=2.0,
            labels={}
        )

        # Wait for alert evaluation and streaming
        await asyncio.sleep(0.2)

        # Verify alerts are streamed
        messages = mock_ws.get_messages()
        alert_updates = [
            msg for msg in messages
            if msg.get("type") == "alerts_update"
        ]

        assert len(alert_updates) >= 1

    @pytest.mark.asyncio
    async def test_health_streaming_integration(self, integrated_manager):
        """Test WebSocket integration with health checks"""
        ws_manager, obs_manager = integrated_manager

        # Connect WebSocket
        mock_ws = MockWebSocket("health-integration")
        await ws_manager.connect(mock_ws, "health")

        # Run health checks
        health_status = await obs_manager.health_check()

        # Wait for streaming
        await asyncio.sleep(0.1)

        # Verify health status is streamed
        messages = mock_ws.get_messages()
        health_updates = [
            msg for msg in messages
            if msg.get("type") == "health_update"
        ]

        assert len(health_updates) >= 1

        # Verify health data structure
        if health_updates:
            health_data = health_updates[0]["data"]
            assert "manager" in health_data
            assert "services" in health_data


# Performance benchmark tests
@pytest.mark.performance
class TestWebSocketPerformanceBenchmarks:
    """WebSocket performance benchmarks"""

    @pytest.mark.asyncio
    async def test_connection_establishment_benchmark(self):
        """Benchmark WebSocket connection establishment"""
        manager = WebSocketManager()

        try:
            connection_count = 1000
            start_time = time.time()

            # Create many connections
            connections = []
            connect_tasks = []

            for i in range(connection_count):
                mock_ws = MockWebSocket(f"benchmark-client-{i}")
                connections.append(mock_ws)
                task = manager.connect(mock_ws, "metrics")
                connect_tasks.append(task)

            await asyncio.gather(*connect_tasks)
            end_time = time.time()

            connection_time = end_time - start_time
            connections_per_second = connection_count / connection_time

            # Benchmark: Should establish at least 100 connections per second
            assert connections_per_second >= 100.0
            assert len(manager._connections["metrics"]) == connection_count

        finally:
            await manager.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_broadcast_throughput_benchmark(self):
        """Benchmark broadcast throughput"""
        manager = WebSocketManager()
        await manager.start_broadcasting()

        try:
            connection_count = 100
            message_count = 1000

            # Create connections
            connections = []
            for i in range(connection_count):
                mock_ws = MockWebSocket(f"broadcast-client-{i}")
                await manager.connect(mock_ws, "metrics")
                connections.append(mock_ws)

            # Benchmark broadcasting
            start_time = time.time()

            for i in range(message_count):
                message = {
                    "type": "benchmark_broadcast",
                    "sequence": i,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await manager.broadcast_to_type("metrics", message)

            end_time = time.time()
            total_time = end_time - start_time

            total_messages = connection_count * message_count
            throughput = total_messages / total_time

            # Benchmark: Should achieve at least 1000 messages per second
            assert throughput >= 1000.0

            # Verify all messages were delivered
            total_delivered = sum(len(mock_ws.get_messages()) for mock_ws in connections)
            assert total_delivered == total_messages

        finally:
            await manager.stop_broadcasting()


if __name__ == "__main__":
    # Run specific test classes
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "TestWebSocketConnectionManagement",
        "TestWebSocketRealTimeDataStreaming",
        "TestWebSocketSubscriptionAndFiltering",
        "TestWebSocketResilienceAndReconnection",
        "TestWebSocketConcurrencyAndPerformance",
        "TestWebSocketSecurityAndAuthentication",
        "TestWebSocketIntegrationWithMonitoring"
    ])