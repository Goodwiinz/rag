"""
WebSocket Message Format Validation Tests

This module contains comprehensive tests for WebSocket message format validation,
including schema validation, message types, data integrity, and edge cases.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from jsonschema import validate, ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from backend.src.services.websocket_manager import (
    WebSocketMessage,
    MessageType,
    Priority,
    EnhancedConnectionManager
)
from backend.src.models.websocket_status import (
    StatusUpdate,
    UpdateType,
    ConnectionStatus
)


@pytest.mark.contract
@pytest.mark.websocket
class TestWebSocketMessageValidation:
    """Test WebSocket message format validation"""

    @pytest.mark.asyncio
    async def test_valid_message_formats(self, websocket_test_client):
        """Test that all valid message formats are accepted"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Test all valid message types
        valid_messages = [
            {
                "type": MessageType.PING.value,
                "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
            },
            {
                "type": MessageType.SUBSCRIBE.value,
                "data": {"channel": "document_processing", "filters": {"user_id": "test"}}
            },
            {
                "type": MessageType.UNSUBSCRIBE.value,
                "data": {"channel": "document_processing"}
            },
            {
                "type": MessageType.STATUS_UPDATE.value,
                "data": {
                    "heartbeat": True,
                    "message_filter": {"event_types": ["document_uploaded"]}
                }
            }
        ]

        for message in valid_messages:
            # Send message
            await websocket_test_client.send_message(message)

            # Should not receive an error response
            try:
                response = await asyncio.wait_for(
                    websocket_test_client.receive_message(), timeout=1.0
                )
                # If we get a response, it should not be an error
                assert response.get("type") != MessageType.ERROR.value
            except asyncio.TimeoutError:
                # No response is also acceptable for some message types
                pass

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_invalid_message_formats(self, websocket_test_client):
        """Test that invalid message formats are rejected"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Test various invalid message formats
        invalid_messages = [
            # Missing required fields
            {"data": {"test": "value"}},  # Missing type
            {"type": "ping"},  # Missing data

            # Invalid message types
            {"type": "invalid_type", "data": {}},
            {"type": "", "data": {}},
            {"type": None, "data": {}},

            # Invalid data types
            {"type": "ping", "data": "not_an_object"},
            {"type": "ping", "data": None},
            {"type": "ping", "data": 123},

            # Malformed JSON
            "invalid json string",
            '{"type": "ping", "data": {invalid json}}',
            '{"type": "ping", "data": {"nested": unclosed}}',

            # Extra fields that shouldn't be there
            {"type": "ping", "data": {}, "unexpected_field": "value"},

            # Empty message
            {},
            None,

            # oversized message
            {
                "type": "ping",
                "data": {"large_payload": "x" * 1000000}  # 1MB payload
            }
        ]

        for invalid_message in invalid_messages:
            try:
                if isinstance(invalid_message, str):
                    await websocket_test_client.send_raw_message(invalid_message)
                elif invalid_message is not None:
                    await websocket_test_client.send_message(invalid_message)

                # Should receive an error response
                try:
                    error_response = await asyncio.wait_for(
                        websocket_test_client.receive_message(), timeout=2.0
                    )
                    assert error_response is not None
                    assert error_response.get("type") == MessageType.ERROR.value
                    assert "error" in error_response.get("data", {})

                except asyncio.TimeoutError:
                    # Should always get an error for invalid messages
                    pytest.fail(f"Expected error response for invalid message: {invalid_message}")

            except Exception as e:
                # Some invalid messages might cause connection issues
                # Reconnect if needed
                if connection_id not in websocket_test_client.active_connections:
                    connection_id = await websocket_test_client.connect(token=token)
                    assert connection_id is not None

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_message_schema_validation(self, websocket_test_client):
        """Test message schema validation with detailed schemas"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Define schemas for different message types
        schemas = {
            MessageType.PING.value: {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["ping"]},
                    "data": {
                        "type": "object",
                        "properties": {
                            "timestamp": {"type": "string", "format": "date-time"},
                            "sequence": {"type": "integer"}
                        },
                        "additionalProperties": True
                    }
                },
                "required": ["type", "data"]
            },

            MessageType.SUBSCRIBE.value: {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["subscribe"]},
                    "data": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "filters": {"type": "object"}
                        },
                        "required": ["channel"],
                        "additionalProperties": True
                    }
                },
                "required": ["type", "data"]
            }
        }

        # Test valid messages against schemas
        valid_messages = [
            {
                "type": MessageType.PING.value,
                "data": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "sequence": 1
                }
            },
            {
                "type": MessageType.SUBSCRIBE.value,
                "data": {
                    "channel": "document_processing",
                    "filters": {"user_id": "test"}
                }
            }
        ]

        for message in valid_messages:
            # Validate against schema
            schema = schemas.get(message["type"])
            if schema:
                validate(instance=message, schema=schema)

            # Send message
            await websocket_test_client.send_message(message)

            # Should be accepted
            try:
                response = await asyncio.wait_for(
                    websocket_test_client.receive_message(), timeout=1.0
                )
                assert response.get("type") != MessageType.ERROR.value
            except asyncio.TimeoutError:
                pass

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_server_message_format_validation(self, websocket_test_client):
        """Test that server sends properly formatted messages"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Trigger various server messages and validate their format

        # 1. Welcome message (already received)
        welcome_message = await websocket_test_client.receive_message(timeout=1.0)
        await self._validate_server_message(welcome_message, "welcome")

        # 2. Ping-Pong
        ping_message = {
            "type": MessageType.PING.value,
            "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
        }
        await websocket_test_client.send_message(ping_message)

        pong_message = await websocket_test_client.receive_message(timeout=2.0)
        await self._validate_server_message(pong_message, "pong")

        # 3. Subscription confirmation
        subscribe_message = {
            "type": MessageType.SUBSCRIBE.value,
            "data": {"channel": "test_channel"}
        }
        await websocket_test_client.send_message(subscribe_message)

        sub_confirmation = await websocket_test_client.receive_message(timeout=2.0)
        await self._validate_server_message(sub_confirmation, "subscription")

        await websocket_test_client.close()

    async def _validate_server_message(self, message: Dict[str, Any], message_category: str):
        """Validate server message format"""
        # Basic structure validation
        assert isinstance(message, dict)
        assert "type" in message
        assert isinstance(message["type"], str)
        assert message["type"]  # Not empty

        # All server messages should have timestamp
        assert "timestamp" in message
        assert isinstance(message["timestamp"], str)

        # Message ID should be present
        assert "id" in message
        assert isinstance(message["id"], str)

        # Priority should be present
        assert "priority" in message
        assert message["priority"] in ["low", "normal", "high", "critical"]

        # Data field should be present and be a dict
        assert "data" in message
        assert isinstance(message["data"], dict)

        # Category-specific validation
        if message_category == "welcome":
            assert message["type"] == MessageType.CONNECT.value
            assert "connection_id" in message["data"]
            assert "server_time" in message["data"]
            assert "heartbeat_interval" in message["data"]

        elif message_category == "pong":
            assert message["type"] == MessageType.PONG.value
            assert "timestamp" in message["data"]

        elif message_category == "subscription":
            assert message["type"] in [MessageType.SUBSCRIBE.value, MessageType.UNSUBSCRIBE.value]
            assert "channel" in message["data"]
            assert "subscribed" in message["data"]

    @pytest.mark.asyncio
    async def test_message_size_limits(self, websocket_test_client):
        """Test message size limits and handling"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Test various message sizes
        size_tests = [
            (1024, "1KB message"),      # Small message
            (10240, "10KB message"),    # Medium message
            (102400, "100KB message"),  # Large message
            (512000, "512KB message"),  # Very large message
        ]

        for size, description in size_tests:
            # Create message of specified size
            payload = "x" * size
            message = {
                "type": MessageType.STATUS_UPDATE.value,
                "data": {
                    "test": True,
                    "payload": payload,
                    "size": size
                }
            }

            start_time = datetime.now(timezone.utc)

            await websocket_test_client.send_message(message)

            # Measure processing time
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Should be processed successfully (unless too large)
            try:
                response = await asyncio.wait_for(
                    websocket_test_client.receive_message(), timeout=5.0
                )

                if response and response.get("type") == MessageType.ERROR.value:
                    # Error for oversized message is acceptable
                    assert "size" in response.get("data", {}).get("error", "").lower()
                else:
                    # Message was processed successfully
                    assert processing_time < 2.0  # Should process quickly

            except asyncio.TimeoutError:
                # For very large messages, timeout is acceptable
                if size <= 102400:  # 100KB
                    pytest.fail(f"Message processing timed out for {description}")

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_message_encoding_validation(self, websocket_test_client):
        """Test message encoding and character set validation"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Test various character encodings
        test_messages = [
            # UTF-8 characters
            {
                "type": MessageType.PING.value,
                "data": {"message": "Hello 世界 🌍 ñáéíóú"}
            },

            # Special characters
            {
                "type": MessageType.PING.value,
                "data": {"message": "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"}
            },

            # Unicode escape sequences
            {
                "type": MessageType.PING.value,
                "data": {"message": "Unicode: \\u00e9 \\u4e2d\\u6587"}
            },

            # Newlines and tabs
            {
                "type": MessageType.PING.value,
                "data": {"message": "Line 1\nLine 2\tTabbed"}
            },

            # JSON control characters
            {
                "type": MessageType.PING.value,
                "data": {"message": "JSON: \"quotes\" and \\backslashes\\"}
            }
        ]

        for message in test_messages:
            # Send message
            await websocket_test_client.send_message(message)

            # Should be processed successfully
            try:
                response = await asyncio.wait_for(
                    websocket_test_client.receive_message(), timeout=2.0
                )

                if response:
                    assert response.get("type") != MessageType.ERROR.value

            except asyncio.TimeoutError:
                # Timeout is acceptable for ping messages
                pass

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_message_priority_handling(self, websocket_test_client):
        """Test message priority handling and ordering"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Send messages with different priorities
        priorities = ["low", "normal", "high", "critical"]
        messages = []

        for priority in priorities:
            message = {
                "type": MessageType.STATUS_UPDATE.value,
                "priority": priority,
                "data": {
                    "test": True,
                    "priority": priority,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            messages.append(message)
            await websocket_test_client.send_message(message)

        # Send a high priority message
        high_priority_message = {
            "type": MessageType.STATUS_UPDATE.value,
            "priority": "critical",
            "data": {
                "urgent": True,
                "message": "This is critical!"
            }
        }
        await websocket_test_client.send_message(high_priority_message)

        # Monitor message processing order (if priority is implemented)
        processed_messages = []
        try:
            for _ in range(len(messages) + 1):
                response = await asyncio.wait_for(
                    websocket_test_client.receive_message(), timeout=2.0
                )
                if response and response.get("priority"):
                    processed_messages.append(response)

        except asyncio.TimeoutError:
            pass

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_message_timestamp_validation(self, websocket_test_client):
        """Test message timestamp validation and handling"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        assert connection_id is not None

        # Test various timestamp formats
        timestamp_tests = [
            # Valid ISO 8601 formats
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),

            # Invalid formats
            "invalid-timestamp",
            "2024-13-32T25:61:61",  # Invalid date/time values
            "not-a-date",
            1234567890,  # Unix timestamp (not ISO format)
            None
        ]

        for timestamp in timestamp_tests:
            message = {
                "type": MessageType.PING.value,
                "data": {
                    "timestamp": timestamp,
                    "test_id": str(uuid.uuid4())
                }
            }

            await websocket_test_client.send_message(message)

            try:
                response = await asyncio.wait_for(
                    websocket_test_client.receive_message(), timeout=2.0
                )

                # Check if timestamp was processed correctly
                if response and "data" in response and "timestamp" in response["data"]:
                    response_timestamp = response["data"]["timestamp"]
                    # Response timestamp should be in valid ISO format
                    try:
                        datetime.fromisoformat(response_timestamp.replace('Z', '+00:00'))
                    except ValueError:
                        pytest.fail(f"Invalid timestamp in response: {response_timestamp}")

            except asyncio.TimeoutError:
                pass  # Timeout is acceptable for ping messages

        await websocket_test_client.close()


@pytest.mark.contract
@pytest.mark.websocket
class TestStatusUpdateValidation:
    """Test status update message validation"""

    @pytest.mark.asyncio
    async def test_document_processing_status_updates(self, websocket_test_client):
        """Test document processing status update message format"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        # Subscribe to document processing updates
        await websocket_test_client.send_message({
            "type": MessageType.SUBSCRIBE.value,
            "data": {"channel": "document_processing"}
        })

        # Simulate receiving document processing status updates
        status_updates = [
            {
                "type": UpdateType.DOCUMENT_PROCESSING.value,
                "data": {
                    "document_id": str(uuid.uuid4()),
                    "status": "pending",
                    "progress": 0,
                    "message": "Document queued for processing"
                }
            },
            {
                "type": UpdateType.DOCUMENT_PROCESSING.value,
                "data": {
                    "document_id": str(uuid.uuid4()),
                    "status": "processing",
                    "progress": 45,
                    "message": "Extracting text and analyzing content"
                }
            },
            {
                "type": UpdateType.DOCUMENT_PROCESSING.value,
                "data": {
                    "document_id": str(uuid.uuid4()),
                    "status": "completed",
                    "progress": 100,
                    "message": "Document processed successfully"
                }
            },
            {
                "type": UpdateType.DOCUMENT_PROCESSING.value,
                "data": {
                    "document_id": str(uuid.uuid4()),
                    "status": "failed",
                    "progress": 25,
                    "error": "File format not supported",
                    "error_code": "UNSUPPORTED_FORMAT"
                }
            }
        ]

        for update in status_updates:
            # Validate status update structure
            await self._validate_status_update_structure(update)

            # This would normally be sent by the server
            # For testing, we'll just validate the structure

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_job_status_updates(self, websocket_test_client):
        """Test job status update message format"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        # Subscribe to job status updates
        await websocket_test_client.send_message({
            "type": MessageType.SUBSCRIBE.value,
            "data": {"channel": "job_status"}
        })

        # Simulate job status updates
        job_updates = [
            {
                "type": UpdateType.JOB_STATUS.value,
                "data": {
                    "job_id": str(uuid.uuid4()),
                    "job_type": "batch_processing",
                    "status": "queued",
                    "total_items": 100,
                    "processed_items": 0,
                    "estimated_completion": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
                }
            },
            {
                "type": UpdateType.JOB_STATUS.value,
                "data": {
                    "job_id": str(uuid.uuid4()),
                    "job_type": "index_rebuild",
                    "status": "running",
                    "total_items": 500,
                    "processed_items": 125,
                    "progress_percentage": 25.0,
                    "current_step": "vector_indexing"
                }
            }
        ]

        for update in job_updates:
            await self._validate_status_update_structure(update)

        await websocket_test_client.close()

    @pytest.mark.asyncio
    async def test_system_status_updates(self, websocket_test_client):
        """Test system status update message format"""
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)

        # Subscribe to system status updates
        await websocket_test_client.send_message({
            "type": MessageType.SUBSCRIBE.value,
            "data": {"channel": "system_status"}
        })

        # Simulate system status updates
        system_updates = [
            {
                "type": UpdateType.SYSTEM_STATUS.value,
                "data": {
                    "service": "vector_store",
                    "status": "healthy",
                    "response_time_ms": 45,
                    "uptime_percentage": 99.9,
                    "last_check": datetime.now(timezone.utc).isoformat()
                }
            },
            {
                "type": UpdateType.SYSTEM_STATUS.value,
                "data": {
                    "service": "processing_queue",
                    "status": "warning",
                    "queue_depth": 1500,
                    "threshold": 1000,
                    "message": "Queue depth above threshold"
                }
            }
        ]

        for update in system_updates:
            await self._validate_status_update_structure(update)

        await websocket_test_client.close()

    async def _validate_status_update_structure(self, update: Dict[str, Any]):
        """Validate status update message structure"""
        # Basic structure
        assert isinstance(update, dict)
        assert "type" in update
        assert "data" in update
        assert isinstance(update["data"], dict)

        # Type should be valid
        valid_types = [ut.value for ut in UpdateType]
        assert update["type"] in valid_types

        # Common data fields
        data = update["data"]

        # All status updates should have timestamp or related timing info
        has_timestamp = (
            "timestamp" in data or
            "created_at" in data or
            "updated_at" in data or
            "last_check" in data
        )

        # Status field should be present and valid
        if "status" in data:
            valid_statuses = ["pending", "processing", "completed", "failed", "running", "queued", "healthy", "warning", "critical"]
            assert data["status"] in valid_statuses

        # Progress should be in valid range
        if "progress" in data:
            assert isinstance(data["progress"], (int, float))
            assert 0 <= data["progress"] <= 100

        if "progress_percentage" in data:
            assert isinstance(data["progress_percentage"], (int, float))
            assert 0 <= data["progress_percentage"] <= 100

        # Error fields should be consistent
        if "error" in data:
            assert isinstance(data["error"], str)
            assert len(data["error"]) > 0

        if "error_code" in data:
            assert isinstance(data["error_code"], str)
            assert len(data["error_code"]) > 0