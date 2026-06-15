"""
WebSocket Connection Lifecycle Contract Tests

This module contains comprehensive tests for WebSocket connection lifecycle,
including authentication, connection management, heartbeat, and graceful shutdown.
"""

import pytest
import asyncio
import json
import uuid
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import websockets
from fastapi.testclient import TestClient
from httpx import AsyncClient
from websockets.exceptions import ConnectionClosed, InvalidURI

from backend.src.services.websocket_manager import (
    EnhancedConnectionManager,
    WebSocketMessage,
    MessageType,
    ConnectionInfo,
    Priority
)
from backend.src.models.websocket_status import ConnectionStatus, UpdateType


@pytest.mark.contract
@pytest.mark.websocket
class TestWebSocketConnectionLifecycle:
    """Test WebSocket connection lifecycle management"""

    @pytest.mark.asyncio
    async def test_successful_connection_flow(self, websocket_test_client):
        """Test complete successful connection flow"""
        # Step 1: Connect with valid token
        token = websocket_test_client.generate_test_token()

        connection_id = await websocket_test_client.connect(
            token=token,
            client_info={
                "user_agent": "pytest-client",
                "client_type": "test",
                "version": "1.0.0"
            }
        )

        assert connection_id is not None
        assert len(connection_id) == 36  # UUID format

        # Step 2: Verify welcome message
        welcome_message = await websocket_test_client.receive_message(timeout=5.0)
        assert welcome_message is not None
        assert welcome_message["type"] == MessageType.CONNECT.value
        assert welcome_message["data"]["connection_id"] == connection_id
        assert "server_time" in welcome_message["data"]
        assert "heartbeat_interval" in welcome_message["data"]

        # Step 3: Verify connection is tracked
        connection_stats = await websocket_test_client.get_connection_stats()
        assert connection_stats["total_connections"] >= 1
        assert connection_id in websocket_test_client.active_connections

        # Step 4: Graceful disconnect
        await websocket_test_client.close()

        # Step 5: Verify connection cleanup
        connection_stats = await websocket_test_client.get_connection_stats()
        assert connection_id not in websocket_test_client.active_connections

    @pytest.mark.asyncio
    async def test_authentication_required(self, websocket_test_client):
        """Test that WebSocket connections require authentication"""
        # Test 1: No token provided
        connection_id = await websocket_test_client.connect(token=None)
        assert connection_id is None

        # Test 2: Empty token
        connection_id = await websocket_test_client.connect(token="")
        assert connection_id is None

        # Test 3: Invalid token format
        connection_id = await websocket_test_client.connect(token="invalid-token")
        assert connection_id is None

        # Test 4: Expired token
        expired_token = websocket_test_client.generate_test_token(expired=True)
        connection_id = await websocket_test_client.connect(token=expired_token)
        assert connection_id is None

    @pytest.mark.asyncio
    async def test_connection_limits(self, websocket_test_client):
        """Test connection limits and capacity management"""
        token = websocket_test_client.generate_test_token()

        # Create connections up to the limit
        connections = []
        max_connections = websocket_test_client.max_connections_per_user

        for i in range(max_connections + 5):  # Try to exceed limit
            try:
                connection_id = await websocket_test_client.connect(
                    token=token,
                    client_info={"connection_index": i}
                )
                if connection_id:
                    connections.append(connection_id)
                else:
                    # Should fail when limit is reached
                    break
            except Exception as e:
                # Connection should be rejected
                break

        # Verify we didn't exceed the limit
        assert len(connections) <= max_connections

        # Clean up connections
        for conn_id in connections:
            await websocket_test_client.close_connection(conn_id)

    @pytest.mark.asyncio
    async def test_heartbeat_mechanism(self, websocket_test_client):
        """Test heartbeat/ping-pong mechanism"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Send ping message
        ping_message = {
            "type": MessageType.PING.value,
            "data": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sequence": 1
            }
        }

        await websocket_test_client.send_message(ping_message)

        # Wait for pong response
        pong_response = await websocket_test_client.receive_message(timeout=5.0)
        assert pong_response is not None
        assert pong_response["type"] == MessageType.PONG.value
        assert "timestamp" in pong_response["data"]

        # Test server-initiated ping
        # This would require mocking the heartbeat monitor
        with patch.object(websocket_test_client.manager, '_heartbeat_monitor') as mock_heartbeat:
            mock_heartbeat.return_value = None

            # Trigger heartbeat check
            await websocket_test_client.trigger_heartbeat_check()

            # Should receive ping from server
            server_ping = await websocket_test_client.receive_message(timeout=2.0)
            if server_ping:
                assert server_ping["type"] == MessageType.PING.value

                # Respond with pong
                pong_message = {
                    "type": MessageType.PONG.value,
                    "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
                }
                await websocket_test_client.send_message(pong_message)

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_connection_timeout(self, websocket_test_client):
        """Test connection timeout handling"""
        token = websocket_test_client.generate_test_token()

        # Set short timeout for testing
        original_timeout = websocket_test_client.connection_timeout
        websocket_test_client.connection_timeout = 2  # 2 seconds

        connection_id = await websocket_test_client.connect(token=token)
        assert connection_id is not None

        # Wait for timeout to occur
        await asyncio.sleep(3)

        # Connection should be automatically closed
        assert connection_id not in websocket_test_client.active_connections

        # Restore original timeout
        websocket_test_client.connection_timeout = original_timeout

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, websocket_test_client):
        """Test graceful shutdown of WebSocket connections"""
        token = websocket_test_client.generate_test_token()

        # Create multiple connections
        connections = []
        for i in range(3):
            conn_id = await websocket_test_client.connect(
                token=token,
                client_info={"shutdown_test": i}
            )
            if conn_id:
                connections.append(conn_id)

        # Trigger graceful shutdown
        await websocket_test_client.shutdown_gracefully()

        # All connections should be closed
        for conn_id in connections:
            assert conn_id not in websocket_test_client.active_connections

    @pytest.mark.asyncio
    async def test_connection_info_tracking(self, websocket_test_client):
        """Test that connection information is properly tracked"""
        token = websocket_test_client.generate_test_token()
        client_info = {
            "user_agent": "pytest-test/1.0.0",
            "client_type": "test",
            "version": "1.0.0",
            "features": ["websocket_testing"]
        }

        connection_id = await websocket_test_client.connect(
            token=token,
            client_info=client_info
        )

        assert connection_id is not None

        # Verify connection info is tracked
        connection_info = await websocket_test_client.get_connection_info(connection_id)
        assert connection_info is not None
        assert connection_info.client_info == client_info
        assert connection_info.user_id is not None
        assert connection_info.organization_id is not None
        assert connection_info.connected_at is not None
        assert connection_info.last_heartbeat is not None

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, websocket_test_client):
        """Test connection error handling and recovery"""
        token = websocket_test_client.generate_test_token()

        # Test connection with invalid URI
        with pytest.raises((ConnectionClosed, InvalidURI)):
            await websocket_test_client.connect_with_uri("ws://invalid-uri", token)

        # Test connection handling of malformed messages
        connection_id = await websocket_test_client.connect(token=token)
        assert connection_id is not None

        # Send malformed JSON
        await websocket_test_client.send_raw_message("invalid json{")

        # Should receive error message
        error_response = await websocket_test_client.receive_message(timeout=2.0)
        assert error_response is not None
        assert error_response["type"] == MessageType.ERROR.value

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_concurrent_connections_same_user(self, websocket_test_client):
        """Test multiple concurrent connections from the same user"""
        token = websocket_test_client.generate_test_token()

        # Create multiple connections simultaneously
        connection_tasks = []
        for i in range(5):
            task = asyncio.create_task(
                websocket_test_client.connect(
                    token=token,
                    client_info={"concurrent_test": i}
                )
            )
            connection_tasks.append(task)

        # Wait for all connections to establish
        connection_ids = await asyncio.gather(*connection_tasks)

        # Filter out None values (failed connections)
        valid_connections = [conn_id for conn_id in connection_ids if conn_id is not None]

        assert len(valid_connections) >= 3  # At least 3 should succeed

        # Verify all connections are tracked
        for conn_id in valid_connections:
            assert conn_id in websocket_test_client.active_connections

            # Send a test message to each connection
            await websocket_test_client.send_message_to_connection(
                conn_id,
                {"type": "test", "connection_id": conn_id}
            )

        # Close all connections
        for conn_id in valid_connections:
            await websocket_test_client.close_connection(conn_id)

    @pytest.mark.asyncio
    async def test_connection_reconnection(self, websocket_test_client):
        """Test connection reconnection scenarios"""
        token = websocket_test_client.generate_test_token()

        # First connection
        connection_id_1 = await websocket_test_client.connect(token=token)
        assert connection_id_1 is not None

        # Simulate sudden disconnection
        await websocket_test_client.force_disconnect(connection_id_1)

        # Reconnect with same token
        connection_id_2 = await websocket_test_client.connect(token=token)
        assert connection_id_2 is not None
        assert connection_id_2 != connection_id_1  # Should get new connection ID

        # Verify reconnection worked
        await websocket_test_client.send_message({"type": "reconnected", "test": True})
        response = await websocket_test_client.receive_message(timeout=2.0)
        assert response is not None

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_websocket_protocol_negotiation(self, websocket_test_client):
        """Test WebSocket protocol negotiation"""
        token = websocket_test_client.generate_test_token()

        # Test with different protocols
        protocols = ["websocket", "ws-protocol-v1", "custom-protocol"]

        for protocol in protocols:
            connection_id = await websocket_test_client.connect(
                token=token,
                protocols=[protocol],
                client_info={"test_protocol": protocol}
            )

            if connection_id:
                # Verify protocol was negotiated
                connection_info = await websocket_test_client.get_connection_info(connection_id)
                assert connection_info is not None

                await websocket_test_client.close_connection(connection_id)


@pytest.mark.contract
@pytest.mark.websocket
@pytest.mark.performance
class TestWebSocketConnectionPerformance:
    """Performance tests for WebSocket connections"""

    @pytest.mark.asyncio
    async def test_connection_establishment_latency(self, websocket_test_client, performance_tracker):
        """Test WebSocket connection establishment latency"""
        token = websocket_test_client.generate_test_token()

        # Measure connection time over multiple attempts
        connection_times = []

        for i in range(10):
            performance_tracker.start_timer(f"connection_{i}")

            connection_id = await websocket_test_client.connect(
                token=token,
                client_info={"latency_test": i}
            )

            connection_time = performance_tracker.end_timer(f"connection_{i}")

            if connection_id:
                connection_times.append(connection_time)
                await websocket_test_client.close_connection(connection_id)

        # Analyze performance
        avg_connection_time = sum(connection_times) / len(connection_times)
        max_connection_time = max(connection_times)

        # Performance assertions
        assert avg_connection_time < 0.5  # Average under 500ms
        assert max_connection_time < 1.0  # Max under 1 second

        print(f"Connection latency - Avg: {avg_connection_time:.3f}s, Max: {max_connection_time:.3f}s")

    @pytest.mark.asyncio
    async def test_memory_usage_with_connections(self, websocket_test_client, performance_tracker):
        """Test memory usage with multiple connections"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        token = websocket_test_client.generate_test_token()
        connections = []

        # Create 100 connections
        for i in range(100):
            connection_id = await websocket_test_client.connect(
                token=token,
                client_info={"memory_test": i}
            )
            if connection_id:
                connections.append(connection_id)

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory
        memory_per_connection = memory_increase / len(connections)

        # Clean up connections
        for conn_id in connections:
            await websocket_test_client.close_connection(conn_id)

        # Memory usage should be reasonable
        assert memory_per_connection < 1024 * 1024  # Less than 1MB per connection

        print(f"Memory usage: {memory_per_connection / 1024:.2f}KB per connection")

    @pytest.mark.asyncio
    async def test_connection_scalability(self, websocket_test_client, performance_tracker):
        """Test connection scalability under load"""
        token = websocket_test_client.generate_test_token()

        # Test with increasing connection counts
        connection_counts = [10, 50, 100, 200]
        performance_data = []

        for count in connection_counts:
            performance_tracker.start_timer(f"scale_test_{count}")

            connections = []
            connection_start = time.time()

            # Create connections
            for i in range(count):
                connection_id = await websocket_test_client.connect(
                    token=token,
                    client_info={"scale_test": i}
                )
                if connection_id:
                    connections.append(connection_id)

            connection_time = time.time() - connection_start
            performance_tracker.end_timer(f"scale_test_{count}")

            # Measure response time for each connection
            response_times = []
            for conn_id in connections:
                start_time = time.time()
                await websocket_test_client.send_message_to_connection(
                    conn_id,
                    {"type": "ping", "test": True}
                )

                try:
                    response = await websocket_test_client.receive_message_from_connection(
                        conn_id, timeout=1.0
                    )
                    if response:
                        response_times.append(time.time() - start_time)
                except asyncio.TimeoutError:
                    pass

            # Clean up
            for conn_id in connections:
                await websocket_test_client.close_connection(conn_id)

            # Record performance data
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0

            performance_data.append({
                "connections": len(connections),
                "connection_time": connection_time,
                "avg_response_time": avg_response_time,
                "success_rate": len(connections) / count
            })

        # Analyze scalability
        for data in performance_data:
            assert data["success_rate"] > 0.8  # At least 80% success rate
            assert data["avg_response_time"] < 0.1  # Response under 100ms

        # Performance should not degrade significantly
        response_times = [data["avg_response_time"] for data in performance_data]
        assert max(response_times) / min(response_times) < 3  # Less than 3x degradation

        print("Scalability Test Results:")
        for data in performance_data:
            print(f"  {data['connections']} connections: "
                  f"{data['connection_time']:.2f}s setup, "
                  f"{data['avg_response_time']*1000:.1f}ms avg response")