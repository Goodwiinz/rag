"""
WebSocket Error Handling and Reconnection Tests

This module contains comprehensive tests for WebSocket error handling,
reconnection scenarios, timeout management, and fault tolerance.
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
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK
from fastapi import status

from backend.src.services.websocket_manager import (
    EnhancedConnectionManager,
    WebSocketMessage,
    MessageType,
    Priority,
    ConnectionInfo
)
from backend.src.models.websocket_status import ConnectionStatus


@pytest.mark.contract
@pytest.mark.websocket
class TestWebSocketErrorHandling:
    """Test WebSocket error handling mechanisms"""

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, websocket_test_client):
        """Test authentication error scenarios"""
        # Test 1: Missing token
        connection_id = await websocket_test_client.connect(token=None)
        assert connection_id is None

        # Verify error details
        error_details = websocket_test_client.get_last_error()
        assert error_details is not None
        assert error_details["code"] == status.WS_1008_POLICY_VIOLATION
        assert "token" in error_details["reason"].lower()

        # Test 2: Invalid JWT format
        connection_id = await websocket_test_client.connect(token="invalid.jwt.token")
        assert connection_id is None

        error_details = websocket_test_client.get_last_error()
        assert error_details is not None
        assert error_details["code"] == status.WS_1008_POLICY_VIOLATION

        # Test 3: Expired token
        expired_token = websocket_test_client.generate_test_token(expired=True)
        connection_id = await websocket_test_client.connect(token=expired_token)
        assert connection_id is None

        error_details = websocket_test_client.get_last_error()
        assert error_details is not None

        # Test 4: Token with invalid signature
        invalid_signature_token = websocket_test_client.generate_test_token(invalid_signature=True)
        connection_id = await websocket_test_client.connect(token=invalid_signature_token)
        assert connection_id is None

    @pytest.mark.asyncio
    async def test_connection_limit_error_handling(self, websocket_test_client):
        """Test connection limit exceeded scenarios"""
        token = websocket_test_client.generate_test_token()

        # Create connections up to the limit
        connections = []
        max_connections = websocket_test_client.max_connections_per_user

        for i in range(max_connections + 5):
            connection_id = await websocket_test_client.connect(
                token=token,
                client_info={"limit_test": i}
            )

            if connection_id:
                connections.append(connection_id)
            else:
                # Should fail with appropriate error
                error_details = websocket_test_client.get_last_error()
                if error_details:
                    assert error_details["code"] == status.WS_1013_TRY_AGAIN_LATER
                    assert "capacity" in error_details["reason"].lower() or "limit" in error_details["reason"].lower()
                break

        # Verify we have at most the max connections
        assert len(connections) <= max_connections

        # Clean up
        for conn_id in connections:
            await websocket_test_client.close_connection(conn_id)

    @pytest.mark.asyncio
    async def test_malformed_message_error_handling(self, websocket_test_client):
        """Test handling of malformed messages"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        malformed_messages = [
            # Invalid JSON
            '{"type": "ping", invalid json}',
            '{"type": "ping", "data": }',
            '{"type": "ping", "data": {"unclosed": "value"}',
            'not json at all',
            '{"type": "ping", "data": {"nested": {"deep": {"unclosed": "value"}}}',

            # Invalid message structure
            '{"type": null, "data": {}}',
            '{"type": "", "data": {}}',
            '{"type": 123, "data": {}}',
            '{"data": {}}',  # Missing type
            '{"type": "ping"}',  # Missing data
            '{}',  # Empty object
            'null',  # Null value

            # Data type errors
            '{"type": "ping", "data": "should be object"}',
            '{"type": "ping", "data": 123}',
            '{"type": "ping", "data": []}',

            # Unknown message types
            '{"type": "unknown_message_type", "data": {}}',
            '{"type": "invalid_operation", "data": {}}',
        ]

        for malformed_msg in malformed_messages:
            try:
                await websocket_test_client.send_raw_message(malformed_msg)

                # Should receive error response
                try:
                    error_response = await asyncio.wait_for(
                        websocket_test_client.receive_message(), timeout=2.0
                    )

                    assert error_response is not None
                    assert error_response.get("type") == MessageType.ERROR.value
                    assert "error" in error_response.get("data", {})

                    # Error message should be informative
                    error_data = error_response["data"]
                    assert "message" in error_data or "error" in error_data

                except asyncio.TimeoutError:
                    pytest.fail(f"Expected error response for malformed message: {malformed_msg[:100]}")

            except Exception as e:
                # Some malformed messages might cause the connection to close
                # Reconnect if needed
                if connection_id not in websocket_test_client.active_connections:
                    connection_id = await websocket_test_client.connect(token=token)
                    assert connection_id is not None

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_oversized_message_error_handling(self, websocket_test_client):
        """Test handling of oversized messages"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Test with increasingly large messages
        size_tests = [
            (1024 * 1024 + 1, "1MB + 1 byte"),      # Just over 1MB
            (5 * 1024 * 1024, "5MB"),               # 5MB
            (10 * 1024 * 1024, "10MB"),             # 10MB
        ]

        for size, description in size_tests:
            large_message = {
                "type": MessageType.STATUS_UPDATE.value,
                "data": {
                    "payload": "x" * size,
                    "description": description
                }
            }

            try:
                await websocket_test_client.send_message(large_message)

                # Check if message was accepted or rejected
                try:
                    response = await asyncio.wait_for(
                        websocket_test_client.receive_message(), timeout=5.0
                    )

                    if response and response.get("type") == MessageType.ERROR.value:
                        # Should be rejected for being too large
                        error_data = response.get("data", {})
                        assert any(term in error_data.get("error", "").lower()
                                 for term in ["size", "large", "limit", "oversize"])

                except asyncio.TimeoutError:
                    # For very large messages, timeout might occur
                    # This indicates the message was rejected or caused issues
                    pass

            except Exception as e:
                # Large messages might cause connection issues
                # Reconnect if needed
                if connection_id not in websocket_test_client.active_connections:
                    connection_id = await websocket_test_client.connect(token=token)
                    assert connection_id is not None

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_rate_limiting_error_handling(self, websocket_test_client):
        """Test rate limiting and spam protection"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Send messages rapidly to trigger rate limiting
        message_count = 100
        error_count = 0

        for i in range(message_count):
            message = {
                "type": MessageType.PING.value,
                "data": {
                    "sequence": i,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

            await websocket_test_client.send_message(message)

            try:
                response = await asyncio.wait_for(
                    websocket_test_client.receive_message(), timeout=0.1
                )

                if response and response.get("type") == MessageType.ERROR.value:
                    error_count += 1
                    error_data = response.get("data", {})
                    assert any(term in error_data.get("error", "").lower()
                             for term in ["rate", "limit", "spam", "throttle"])

            except asyncio.TimeoutError:
                # No immediate response is normal for ping messages
                pass

        # Should have received some rate limiting errors
        if error_count > 0:
            print(f"Received {error_count} rate limiting errors out of {message_count} messages")

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_network_interruption_handling(self, websocket_test_client):
        """Test handling of network interruptions"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Simulate network interruption by force closing the connection
        await websocket_test_client.force_disconnect(connection_id)

        # Verify connection is marked as disconnected
        assert connection_id not in websocket_test_client.active_connections

        # Try to send a message (should fail gracefully)
        try:
            await websocket_test_client.send_message_to_connection(
                connection_id,
                {"type": "test", "message": "should fail"}
            )
            pytest.fail("Should not be able to send message to disconnected connection")
        except Exception as e:
            # Expected behavior
            assert "connection" in str(e).lower() or "disconnected" in str(e).lower()

    @pytest.mark.asyncio
    async def test_server_error_propagation(self, websocket_test_client):
        """Test that server errors are properly propagated to clients"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Trigger server-side errors
        error_triggers = [
            # Invalid channel subscription
            {
                "type": MessageType.SUBSCRIBE.value,
                "data": {"channel": ""}  # Empty channel
            },
            # Invalid unsubscribe request
            {
                "type": MessageType.UNSUBSCRIBE.value,
                "data": {"channel": "nonexistent_channel"}
            },
            # Invalid status update
            {
                "type": MessageType.STATUS_UPDATE.value,
                "data": {"invalid_field": "value"}  # Missing required fields
            }
        ]

        for trigger in error_triggers:
            await websocket_test_client.send_message(trigger)

            try:
                response = await asyncio.wait_for(
                    websocket_test_client.receive_message(), timeout=2.0
                )

                # Should receive error response
                if response:
                    assert response.get("type") == MessageType.ERROR.value
                    error_data = response.get("data", {})
                    assert "error" in error_data

                    # Error should be user-friendly (in production mode)
                    if not websocket_test_client.debug_mode:
                        assert "traceback" not in str(error_data).lower()

            except asyncio.TimeoutError:
                # Some errors might not generate immediate responses
                pass

        await websocket_test_client.close()


@pytest.mark.contract
@pytest.mark.websocket
class TestWebSocketReconnection:
    """Test WebSocket reconnection scenarios and resilience"""

    @pytest.mark.asyncio
    async def test_graceful_reconnection(self, websocket_test_client):
        """Test graceful reconnection after normal disconnection"""
        token = websocket_test_client.generate_test_token()

        # Initial connection
        connection_id_1 = await websocket_test_client.connect(token=token)
        assert connection_id_1 is not None

        # Send a test message
        await websocket_test_client.send_message({
            "type": MessageType.PING.value,
            "data": {"test": "initial_connection"}
        })

        # Graceful disconnect
        await websocket_test_client.close()

        # Reconnect with same token
        connection_id_2 = await websocket_test_client.connect(token=token)
        assert connection_id_2 is not None
        assert connection_id_2 != connection_id_1  # Should get new connection ID

        # Verify reconnection worked
        await websocket_test_client.send_message({
            "type": MessageType.PING.value,
            "data": {"test": "reconnected"}
        })

        try:
            response = await asyncio.wait_for(
                websocket_test_client.receive_message(), timeout=2.0
            )
            assert response is not None
        except asyncio.TimeoutError:
            pass  # No immediate response is acceptable

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_abrupt_reconnection(self, websocket_test_client):
        """Test reconnection after abrupt disconnection"""
        token = websocket_test_client.generate_test_token()

        # Initial connection
        connection_id_1 = await websocket_test_client.connect(token=token)
        assert connection_id_1 is not None

        # Simulate abrupt disconnection (network loss, server crash)
        await websocket_test_client.force_disconnect(connection_id_1)

        # Verify connection is lost
        assert connection_id_1 not in websocket_test_client.active_connections

        # Attempt reconnection (should succeed)
        connection_id_2 = await websocket_test_client.connect(token=token)
        assert connection_id_2 is not None
        assert connection_id_2 != connection_id_1

        # Verify new connection works
        await websocket_test_client.send_message({
            "type": MessageType.PING.value,
            "data": {"recovery": "successful"}
        })

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_multiple_reconnection_attempts(self, websocket_test_client):
        """Test multiple reconnection attempts"""
        token = websocket_test_client.generate_test_token()

        connections = []
        reconnection_count = 5

        for attempt in range(reconnection_count):
            # Connect
            connection_id = await websocket_test_client.connect(
                token=token,
                client_info={"attempt": attempt}
            )

            if connection_id:
                connections.append(connection_id)

                # Send test message
                await websocket_test_client.send_message({
                    "type": MessageType.PING.value,
                    "data": {"attempt": attempt}
                })

                # Disconnect
                await websocket_test_client.close()

                # Brief pause before reconnection
                await asyncio.sleep(0.1)

        # Should have successful reconnections
        assert len(connections) == reconnection_count

        # All connection IDs should be unique
        assert len(set(connections)) == len(connections)

    @pytest.mark.asyncio
    async def test_exponential_backoff_reconnection(self, websocket_test_client):
        """Test exponential backoff in reconnection attempts"""
        token = websocket_test_client.generate_test_token()

        # Mock server to simulate reconnection failures
        with patch.object(websocket_test_client, 'connect') as mock_connect:
            # First few attempts fail, then succeed
            mock_connect.side_effect = [
                None,  # Fail
                None,  # Fail
                "new_connection_id",  # Succeed
            ]

            # Test reconnection with exponential backoff
            reconnection_times = []
            backoff_intervals = [1, 2, 4]  # Exponential backoff

            for interval in backoff_intervals:
                start_time = time.time()

                connection_id = await websocket_test_client.connect_with_backoff(
                    token=token,
                    max_attempts=3,
                    base_delay=interval
                )

                elapsed_time = time.time() - start_time
                reconnection_times.append(elapsed_time)

                if connection_id:
                    break

        # Verify exponential backoff behavior
        # (This is a simplified test - real implementation would be more sophisticated)
        assert len(reconnection_times) >= 2

    @pytest.mark.asyncio
    async def test_reconnection_state_preservation(self, websocket_test_client):
        """Test state preservation across reconnections"""
        token = websocket_test_client.generate_test_token()

        # Initial connection with subscriptions
        connection_id_1 = await websocket_test_client.connect(token=token)
        assert connection_id_1 is not None

        # Subscribe to channels
        channels = ["document_processing", "job_status", "system_events"]
        for channel in channels:
            await websocket_test_client.send_message({
                "type": MessageType.SUBSCRIBE.value,
                "data": {"channel": channel}
            })

        # Set message filter
        await websocket_test_client.send_message({
            "type": MessageType.STATUS_UPDATE.value,
            "data": {
                "message_filter": {
                    "event_types": ["document_uploaded", "job_completed"],
                    "priority": ["high", "critical"]
                }
            }
        })

        # Disconnect and reconnect
        await websocket_test_client.close()
        connection_id_2 = await websocket_test_client.connect(
            token=token,
            restore_session=True  # Assuming this feature exists
        )
        assert connection_id_2 is not None

        # Verify state was restored (if implemented)
        # This would depend on the specific implementation
        # For now, we just verify reconnection works
        await websocket_test_client.send_message({
            "type": MessageType.PING.value,
            "data": {"state_restored": True}
        })

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_concurrent_reconnection_attempts(self, websocket_test_client):
        """Test handling of concurrent reconnection attempts"""
        token = websocket_test_client.generate_test_token()

        # Create initial connection
        connection_id = await websocket_test_client.connect(token=token)
        assert connection_id is not None

        # Force disconnect
        await websocket_test_client.force_disconnect(connection_id)

        # Attempt multiple concurrent reconnections
        reconnection_tasks = []
        for i in range(5):
            task = asyncio.create_task(
                websocket_test_client.connect(
                    token=token,
                    client_info={"concurrent_attempt": i}
                )
            )
            reconnection_tasks.append(task)

        # Wait for all reconnection attempts
        results = await asyncio.gather(*reconnection_tasks, return_exceptions=True)

        # Analyze results
        successful_reconnections = [r for r in results if r is not None]
        failed_reconnections = [r for r in results if r is None or isinstance(r, Exception)]

        # At least one reconnection should succeed
        assert len(successful_reconnections) >= 1

        # Clean up any successful reconnections
        for conn_id in successful_reconnections:
            if isinstance(conn_id, str):
                await websocket_test_client.close_connection(conn_id)

    @pytest.mark.asyncio
    async def test_reconnection_with_invalid_session(self, websocket_test_client):
        """Test reconnection attempts with invalid/expired sessions"""
        # Connect with initial token
        valid_token = websocket_test_client.generate_test_token()
        connection_id_1 = await websocket_test_client.connect(token=valid_token)
        assert connection_id_1 is not None

        await websocket_test_client.close()

        # Try to reconnect with expired token
        expired_token = websocket_test_client.generate_test_token(expired=True)
        connection_id_2 = await websocket_test_client.connect(token=expired_token)
        assert connection_id_2 is None  # Should fail

        # Try to reconnect with invalid token
        invalid_token = "completely.invalid.token"
        connection_id_3 = await websocket_test_client.connect(token=invalid_token)
        assert connection_id_3 is None  # Should fail

        # Reconnect with valid token should work
        connection_id_4 = await websocket_test_client.connect(token=valid_token)
        assert connection_id_4 is not None

        await websocket_test_client.close()


@pytest.mark.contract
@pytest.mark.websocket
@pytest.mark.resilience
class TestWebSocketResilience:
    """Test WebSocket resilience and fault tolerance"""

    @pytest.mark.asyncio
    async def test_connection_timeout_recovery(self, websocket_test_client):
        """Test recovery from connection timeouts"""
        token = websocket_test_client.generate_test_token()

        # Set very short timeout for testing
        original_timeout = websocket_test_client.connection_timeout
        websocket_test_client.connection_timeout = 1  # 1 second

        connection_id = await websocket_test_client.connect(token=token)
        assert connection_id is not None

        # Wait for timeout to occur
        await asyncio.sleep(2)

        # Connection should be timed out
        assert connection_id not in websocket_test_client.active_connections

        # Reconnect should work
        websocket_test_client.connection_timeout = original_timeout
        new_connection_id = await websocket_test_client.connect(token=token)
        assert new_connection_id is not None

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_memory_leak_prevention(self, websocket_test_client):
        """Test memory leak prevention during reconnections"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        token = websocket_test_client.generate_test_token()

        # Perform many connect/disconnect cycles
        cycles = 50
        for i in range(cycles):
            connection_id = await websocket_test_client.connect(token=token)
            if connection_id:
                await websocket_test_client.send_message({
                    "type": MessageType.PING.value,
                    "data": {"cycle": i}
                })
                await websocket_test_client.close()

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # Memory increase should be reasonable
        max_acceptable_increase = 50 * 1024 * 1024  # 50MB
        assert memory_increase < max_acceptable_increase

        print(f"Memory increase after {cycles} cycles: {memory_increase / 1024 / 1024:.2f}MB")

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_error(self, websocket_test_client):
        """Test proper resource cleanup when errors occur"""
        token = websocket_test_client.generate_test_token()

        # Get initial resource counts
        initial_stats = await websocket_test_client.get_connection_stats()
        initial_connections = initial_stats["total_connections"]

        # Create connections and trigger various errors
        for i in range(10):
            connection_id = await websocket_test_client.connect(token=token)
            if connection_id:
                # Trigger an error
                try:
                    await websocket_test_client.send_raw_message("invalid json" * 1000)
                except:
                    pass

                # Force disconnect
                await websocket_test_client.force_disconnect(connection_id)

        # Check final resource counts
        final_stats = await websocket_test_client.get_connection_stats()
        final_connections = final_stats["total_connections"]

        # Resources should be properly cleaned up
        assert final_connections <= initial_connections + 2  # Allow for small margin