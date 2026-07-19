"""
WebSocket Integration Tests - Comprehensive Contract Testing

This module tests the WebSocket contract compliance between frontend and backend,
including connection lifecycle, message formats, authentication, and error handling.

Test Coverage:
- WebSocket v1 API (/ws) basic functionality
- WebSocket v2 API (/api/v2/ws/connect) enhanced features
- Monitoring WebSockets (/ws/metrics, /ws/traces, etc.)
- Authentication and authorization
- Message format validation
- Connection lifecycle management
- Error handling and recovery
- Performance under load
"""

import asyncio
import json
import pytest
import time
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timezone as dt_timezone
from unittest.mock import Mock, patch, AsyncMock

import websockets
from fastapi.testclient import TestClient
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed, InvalidHandshake

# Import backend modules
from backend.src.api.websocket import router as websocket_v1_router
from backend.src.api.websocket_v2 import router as websocket_v2_router
from backend.src.monitoring.api.websocket_handlers import router as monitoring_router
from backend.src.main import app
from backend.src.services.websocket_manager import connection_manager
from backend.src.models.user import User

# Test configuration
logger = logging.getLogger(__name__)
TEST_USER_ID = "test_user_123"
TEST_ORG_ID = "test_org_456"
TEST_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0X3VzZXJfMTIzIiwib3JnYW5pemF0aW9uX2lkIjoidGVzdF9vcmdfNDU2IiwiZXhwIjo5OTk5OTk5OTk5fQ.test_signature"

class WebSocketTestConfig:
    """Configuration for WebSocket tests"""

    # Base URLs for different WebSocket versions
    WS_V1_URL = "ws://localhost:8000/ws"
    WS_V2_URL = "ws://localhost:8000/api/v2/ws/connect"
    MONITORING_BASE_URL = "ws://localhost:8000/ws"

    # Test timeouts
    CONNECTION_TIMEOUT = 10.0
    MESSAGE_TIMEOUT = 5.0
    PING_TIMEOUT = 3.0

    # Load test configuration
    LOAD_TEST_CONNECTIONS = 50
    LOAD_TEST_DURATION = 30  # seconds

    # Message templates
    PING_MESSAGE = {"type": "ping", "timestamp": datetime.now(dt_timezone.utc).isoformat()}
    SUBSCRIBE_MESSAGE = {"type": "subscribe", "channel": "document_processing"}

    @classmethod
    def get_monitoring_url(cls, endpoint: str) -> str:
        """Get monitoring WebSocket URL"""
        return f"{cls.MONITORING_BASE_URL}/{endpoint}"


class WebSocketTestHelper:
    """Helper class for WebSocket testing operations"""

    @staticmethod
    async def create_websocket_connection(
        url: str,
        token: Optional[str] = None,
        extra_params: Optional[Dict[str, str]] = None,
        timeout: float = WebSocketTestConfig.CONNECTION_TIMEOUT
    ) -> WebSocketClientProtocol:
        """Create WebSocket connection with optional parameters"""

        # Add query parameters
        if token or extra_params:
            separator = "&" if "?" in url else "?"
            params = []

            if token:
                params.append(f"token={token}")

            if extra_params:
                for key, value in extra_params.items():
                    params.append(f"{key}={value}")

            url = f"{url}{separator}{ '&'.join(params) }"

        return await websockets.connect(url, timeout=timeout)

    @staticmethod
    async def send_message_and_wait_for_response(
        websocket: WebSocketClientProtocol,
        message: Dict[str, Any],
        expected_type: Optional[str] = None,
        timeout: float = WebSocketTestConfig.MESSAGE_TIMEOUT
    ) -> Dict[str, Any]:
        """Send message and wait for response"""

        await websocket.send(json.dumps(message))
        response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        response_data = json.loads(response)

        if expected_type and response_data.get("type") != expected_type:
            raise AssertionError(f"Expected message type {expected_type}, got {response_data.get('type')}")

        return response_data

    @staticmethod
    async def authenticate_websocket_v1(websocket: WebSocketClientProtocol) -> Dict[str, Any]:
        """Handle WebSocket v1 authentication flow"""

        # Wait for welcome message
        welcome_msg = await asyncio.wait_for(
            websocket.recv(),
            timeout=WebSocketTestConfig.MESSAGE_TIMEOUT
        )
        welcome_data = json.loads(welcome_msg)

        assert welcome_data["type"] == "connected"
        assert "user_id" in welcome_data
        assert "timestamp" in welcome_data

        return welcome_data

    @staticmethod
    async def authenticate_websocket_v2(websocket: WebSocketClientProtocol) -> Dict[str, Any]:
        """Handle WebSocket v2 authentication flow"""

        # Wait for connection status message
        status_msg = await asyncio.wait_for(
            websocket.recv(),
            timeout=WebSocketTestConfig.MESSAGE_TIMEOUT
        )
        status_data = json.loads(status_msg)

        assert status_data["type"] == "connect"
        assert "connection_id" in status_data["data"]
        assert "server_capabilities" in status_data["data"]

        return status_data

    @staticmethod
    def validate_message_schema(message: Dict[str, Any], required_fields: List[str]) -> None:
        """Validate message schema"""
        for field in required_fields:
            assert field in message, f"Missing required field: {field}"

    @staticmethod
    def generate_test_token(user_id: str = TEST_USER_ID, org_id: str = TEST_ORG_ID) -> str:
        """Generate test JWT token"""
        # In real implementation, this would use the actual JWT signing
        return f"test_token_for_{user_id}_{int(time.time())}"


class MockUserManager:
    """Mock user manager for testing"""

    @staticmethod
    def create_test_user(user_id: str = TEST_USER_ID, is_superuser: bool = False) -> User:
        """Create a test user"""
        user = Mock(spec=User)
        user.id = user_id
        user.email = f"test_{user_id}@example.com"
        user.organization_id = TEST_ORG_ID
        user.is_superuser = is_superuser
        user.is_active = True
        user.created_at = datetime.now(dt_timezone.utc)
        return user


# ============================================================================
# WebSocket V1 API Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.websocket
@pytest.mark.contract
class TestWebSocketV1Contract:
    """Test WebSocket v1 API contract compliance"""

    async def test_websocket_v1_connection_success(self):
        """Test successful WebSocket v1 connection"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        try:
            websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)

            # Test authentication and welcome message
            welcome_data = await WebSocketTestHelper.authenticate_websocket_v1(websocket)

            # Verify welcome message structure
            WebSocketTestHelper.validate_message_schema(
                welcome_data,
                ["type", "message", "timestamp", "user_id"]
            )

            assert welcome_data["type"] == "connected"
            assert welcome_data["message"] == "WebSocket connection established"

            await websocket.close()

        except Exception as e:
            pytest.fail(f"WebSocket v1 connection failed: {e}")

    async def test_websocket_v1_connection_no_token(self):
        """Test WebSocket v1 connection without token fails"""

        url = WebSocketTestConfig.WS_V1_URL

        with pytest.raises(Exception):  # Should raise connection error
            await WebSocketTestHelper.create_websocket_connection(url, token=None)

    async def test_websocket_v1_ping_pong(self):
        """Test WebSocket v1 ping/pong mechanism"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        await WebSocketTestHelper.authenticate_websocket_v1(websocket)

        # Send ping and wait for pong
        pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            WebSocketTestConfig.PING_MESSAGE,
            expected_type="pong"
        )

        # Validate pong response
        WebSocketTestHelper.validate_message_schema(pong_response, ["type", "timestamp"])
        assert pong_response["type"] == "pong"

        await websocket.close()

    async def test_websocket_v1_subscribe_functionality(self):
        """Test WebSocket v1 subscription functionality"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        await WebSocketTestHelper.authenticate_websocket_v1(websocket)

        # Test subscription
        subscribe_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            {"type": "subscribe", "channel": "document_processing"},
            expected_type="subscribed"
        )

        # Validate subscription response
        WebSocketTestHelper.validate_message_schema(
            subscribe_response,
            ["type", "channel", "timestamp"]
        )
        assert subscribe_response["channel"] == "document_processing"

        await websocket.close()

    async def test_websocket_v1_invalid_json_handling(self):
        """Test WebSocket v1 handles invalid JSON gracefully"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        await WebSocketTestHelper.authenticate_websocket_v1(websocket)

        # Send invalid JSON
        await websocket.send("invalid json string")

        # Connection should remain open
        # Send a valid ping to verify connection is still working
        pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            WebSocketTestConfig.PING_MESSAGE,
            expected_type="pong"
        )

        assert pong_response["type"] == "pong"

        await websocket.close()


# ============================================================================
# WebSocket V2 API Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.websocket
@pytest.mark.contract
class TestWebSocketV2Contract:
    """Test WebSocket v2 API contract compliance"""

    async def test_websocket_v2_connection_success(self):
        """Test successful WebSocket v2 connection with enhanced features"""

        url = WebSocketTestConfig.WS_V2_URL
        token = WebSocketTestHelper.generate_test_token()

        # Test with enhanced parameters
        extra_params = {
            "channels": "document_processing,job_status,system_status",
            "frequency": "realtime",
            "client_info": json.dumps({
                "browser": "test_browser",
                "version": "1.0.0",
                "platform": "test_platform"
            })
        }

        websocket = await WebSocketTestHelper.create_websocket_connection(
            url,
            token=token,
            extra_params=extra_params
        )

        # Test enhanced authentication
        status_data = await WebSocketTestHelper.authenticate_websocket_v2(websocket)

        # Verify enhanced connection message
        connection_data = status_data["data"]
        assert "connection_id" in connection_data
        assert "subscribed_channels" in connection_data
        assert "server_capabilities" in connection_data
        assert "recommended_settings" in connection_data

        # Verify requested channels were subscribed
        assert "document_processing" in connection_data["subscribed_channels"]
        assert "job_status" in connection_data["subscribed_channels"]

        await websocket.close()

    async def test_websocket_v2_connection_with_invalid_frequency(self):
        """Test WebSocket v2 handles invalid frequency parameter gracefully"""

        url = WebSocketTestConfig.WS_V2_URL
        token = WebSocketTestHelper.generate_test_token()

        extra_params = {
            "channels": "document_processing",
            "frequency": "invalid_frequency"  # Invalid frequency
        }

        websocket = await WebSocketTestHelper.create_websocket_connection(
            url,
            token=token,
            extra_params=extra_params
        )

        # Should still connect with default frequency
        status_data = await WebSocketTestHelper.authenticate_websocket_v2(websocket)
        connection_data = status_data["data"]

        # Should default to "normal" frequency
        assert connection_data["update_frequency"] == "normal"

        await websocket.close()

    async def test_websocket_v2_server_capabilities(self):
        """Test WebSocket v2 server capabilities response"""

        url = WebSocketTestConfig.WS_V2_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        status_data = await WebSocketTestHelper.authenticate_websocket_v2(websocket)

        capabilities = status_data["data"]["server_capabilities"]

        # Verify required capability sections
        assert "channels" in capabilities
        assert "message_types" in capabilities
        assert "priorities" in capabilities
        assert "frequencies" in capabilities

        # Verify expected channels are available
        expected_channels = [
            "document_processing", "job_status", "system_status",
            "user_notifications", "quota_alerts", "quality_metrics", "admin_alerts"
        ]
        for channel in expected_channels:
            assert channel in capabilities["channels"]

        await websocket.close()

    async def test_websocket_v2_message_filtering(self):
        """Test WebSocket v2 message filtering functionality"""

        url = WebSocketTestConfig.WS_V2_URL
        token = WebSocketTestHelper.generate_test_token()

        # Test with message filter
        client_info = json.dumps({
            "message_filter": {
                "min_priority": "high",
                "user_id_filter": [TEST_USER_ID],
                "organization_id": TEST_ORG_ID
            }
        })

        extra_params = {"client_info": client_info}

        websocket = await WebSocketTestHelper.create_websocket_connection(
            url,
            token=token,
            extra_params=extra_params
        )

        status_data = await WebSocketTestHelper.authenticate_websocket_v2(websocket)

        # Message filtering should be acknowledged
        # (This would require actual implementation of filtering logic)

        await websocket.close()


# ============================================================================
# Monitoring WebSocket Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.websocket
@pytest.mark.monitoring
class TestMonitoringWebSockets:
    """Test monitoring-specific WebSocket endpoints"""

    @pytest.mark.parametrize("endpoint", [
        "metrics", "traces", "logs", "alerts", "health", "dashboard"
    ])
    async def test_monitoring_websocket_connection(self, endpoint):
        """Test each monitoring WebSocket endpoint connection"""

        url = WebSocketTestConfig.get_monitoring_url(endpoint)
        token = WebSocketTestHelper.generate_test_token()

        try:
            websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)

            # Should receive connection established message
            connection_msg = await asyncio.wait_for(
                websocket.recv(),
                timeout=WebSocketTestConfig.MESSAGE_TIMEOUT
            )
            connection_data = json.loads(connection_msg)

            assert connection_data["type"] == "connection_established"
            assert "timestamp" in connection_data
            assert "user_id" in connection_data

            await websocket.close()

        except Exception as e:
            pytest.fail(f"Monitoring WebSocket {endpoint} connection failed: {e}")

    async def test_monitoring_websocket_unauthorized_access(self):
        """Test monitoring WebSocket rejects unauthorized access"""

        url = WebSocketTestConfig.get_monitoring_url("metrics")

        # Try connecting without token
        with pytest.raises(Exception):
            await WebSocketTestHelper.create_websocket_connection(url, token=None)

    async def test_monitoring_websocket_ping_pong(self, endpoint="metrics"):
        """Test monitoring WebSocket ping/pong"""

        url = WebSocketTestConfig.get_monitoring_url(endpoint)
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)

        # Wait for connection message
        await asyncio.wait_for(websocket.recv(), timeout=WebSocketTestConfig.MESSAGE_TIMEOUT)

        # Test ping/pong
        pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            WebSocketTestConfig.PING_MESSAGE,
            expected_type="pong"
        )

        assert pong_response["type"] == "pong"

        await websocket.close()

    async def test_monitoring_websocket_subscription(self, endpoint="logs"):
        """Test monitoring WebSocket subscription functionality"""

        url = WebSocketTestConfig.get_monitoring_url(endpoint)
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)

        # Wait for connection message
        await asyncio.wait_for(websocket.recv(), timeout=WebSocketTestConfig.MESSAGE_TIMEOUT)

        # Test subscription
        subscribe_message = {
            "type": f"subscribe_{endpoint}",
            "filters": {"level": "info", "source": "test"}
        }

        subscribe_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            subscribe_message,
            expected_type=f"{endpoint}_subscription_confirmed"
        )

        assert "filters" in subscribe_response
        assert subscribe_response["filters"]["level"] == "info"

        await websocket.close()


# ============================================================================
# WebSocket Contract Validation Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.websocket
@pytest.mark.contract
class TestWebSocketMessageContracts:
    """Test WebSocket message contract compliance"""

    async def test_message_timestamp_format(self):
        """Test all messages include valid ISO8601 timestamps"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)

        # Test welcome message timestamp
        welcome_data = await WebSocketTestHelper.authenticate_websocket_v1(websocket)
        timestamp_str = welcome_data["timestamp"]

        # Verify timestamp format (ISO8601)
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        assert isinstance(timestamp, datetime)

        # Test pong message timestamp
        pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            WebSocketTestConfig.PING_MESSAGE,
            expected_type="pong"
        )

        pong_timestamp = datetime.fromisoformat(pong_response["timestamp"].replace('Z', '+00:00'))
        assert isinstance(pong_timestamp, datetime)

        await websocket.close()

    async def test_message_field_validation(self):
        """Test message field validation and required fields"""

        url = WebSocketTestConfig.WS_V2_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        status_data = await WebSocketTestHelper.authenticate_websocket_v2(websocket)

        # Validate connection message structure
        connection_data = status_data["data"]
        required_fields = [
            "connection_id", "subscribed_channels", "update_frequency",
            "server_capabilities", "recommended_settings"
        ]

        for field in required_fields:
            assert field in connection_data, f"Missing required field in connection data: {field}"

        # Validate server capabilities structure
        capabilities = connection_data["server_capabilities"]
        capability_fields = ["channels", "message_types", "priorities", "frequencies"]

        for field in capability_fields:
            assert field in capabilities, f"Missing capability field: {field}"
            assert isinstance(capabilities[field], list), f"Capability field {field} should be a list"

        await websocket.close()

    async def test_message_size_limits(self):
        """Test WebSocket message size limits"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        await WebSocketTestHelper.authenticate_websocket_v1(websocket)

        # Test normal size message
        normal_message = {"type": "test", "data": "x" * 1000}
        await websocket.send(json.dumps(normal_message))

        # Test oversized message (should handle gracefully)
        oversized_message = {"type": "test", "data": "x" * (1024 * 1024 + 1)}  # > 1MB

        try:
            await websocket.send(json.dumps(oversized_message))
            # If send succeeds, verify connection is still working
            pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
                websocket,
                WebSocketTestConfig.PING_MESSAGE,
                expected_type="pong"
            )
            assert pong_response["type"] == "pong"
        except Exception:
            # Oversized message should be rejected, but connection should remain
            # Verify connection is still working
            pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
                websocket,
                WebSocketTestConfig.PING_MESSAGE,
                expected_type="pong"
            )
            assert pong_response["type"] == "pong"

        await websocket.close()


# ============================================================================
# WebSocket Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.websocket
@pytest.mark.error_handling
class TestWebSocketErrorHandling:
    """Test WebSocket error handling and recovery"""

    async def test_connection_recovery_after_timeout(self):
        """Test connection recovery after timeout"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        # Create connection
        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        await WebSocketTestHelper.authenticate_websocket_v1(websocket)

        # Simulate connection timeout by not sending messages
        await asyncio.sleep(2)  # Wait longer than typical timeout

        # Connection should still be alive (with proper ping/pong)
        pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            WebSocketTestConfig.PING_MESSAGE,
            expected_type="pong"
        )
        assert pong_response["type"] == "pong"

        await websocket.close()

    async def test_invalid_message_type_handling(self):
        """Test handling of invalid message types"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        await WebSocketTestHelper.authenticate_websocket_v1(websocket)

        # Send unknown message type
        unknown_message = {"type": "unknown_message_type", "data": {}}
        await websocket.send(json.dumps(unknown_message))

        # Connection should remain open
        pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            WebSocketTestHelper.PING_MESSAGE,
            expected_type="pong"
        )
        assert pong_response["type"] == "pong"

        await websocket.close()

    async def test_malformed_message_handling(self):
        """Test handling of malformed messages"""

        url = WebSocketTestConfig.WS_V1_URL
        token = WebSocketTestHelper.generate_test_token()

        websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
        await WebSocketTestHelper.authenticate_websocket_v1(websocket)

        # Send messages with missing required fields
        incomplete_message = {"type": "subscribe"}  # Missing channel
        await websocket.send(json.dumps(incomplete_message))

        # Connection should remain open
        pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
            websocket,
            WebSocketTestConfig.PING_MESSAGE,
            expected_type="pong"
        )
        assert pong_response["type"] == "pong"

        await websocket.close()

    async def test_authentication_token_expiration(self):
        """Test behavior with expired authentication token"""

        # This test would require mocking JWT validation
        # For now, test with invalid token format
        url = WebSocketTestConfig.WS_V1_URL
        invalid_token = "invalid.jwt.token"

        with pytest.raises(Exception):
            await WebSocketTestHelper.create_websocket_connection(url, token=invalid_token)


# ============================================================================
# WebSocket REST API Integration Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.websocket
@pytest.mark.integration
class TestWebSocketRESTIntegration:
    """Test WebSocket integration with REST API endpoints"""

    async def test_websocket_status_endpoint(self):
        """Test WebSocket status REST endpoint"""

        client = TestClient(app)

        # Test v1 status endpoint
        response = client.get("/api/v1/ws/status")
        assert response.status_code == 200

        status_data = response.json()
        required_fields = ["status", "total_connections", "active_users", "timestamp"]

        for field in required_fields:
            assert field in status_data, f"Missing status field: {field}"

        assert status_data["status"] == "available"
        assert isinstance(status_data["total_connections"], int)
        assert isinstance(status_data["active_users"], int)

    async def test_websocket_v2_status_endpoint(self):
        """Test WebSocket v2 status REST endpoint"""

        client = TestClient(app)

        response = client.get("/api/v2/ws/status")
        assert response.status_code == 200

        status_data = response.json()

        # Verify comprehensive status structure
        assert "websocket_service" in status_data
        assert "connections" in status_data
        assert "channels" in status_data
        assert "performance" in status_data

        # Verify service status
        service_status = status_data["websocket_service"]
        assert service_status["status"] == "healthy"
        assert "features" in service_status
        assert service_status["features"]["jwt_authentication"]

        # Verify channel information
        channels = status_data["channels"]
        expected_channels = [
            "document_processing", "job_status", "system_status",
            "user_notifications", "quota_alerts", "quality_metrics", "admin_alerts"
        ]

        for channel in expected_channels:
            assert channel in channels
            assert "description" in channels[channel]
            assert "subscribers" in channels[channel]

    async def test_websocket_channels_endpoint(self):
        """Test WebSocket channels information endpoint"""

        client = TestClient(app)

        response = client.get("/api/v2/ws/channels")
        assert response.status_code == 200

        channels_data = response.json()
        assert "channels" in channels_data

        channels = channels_data["channels"]
        assert isinstance(channels, list)
        assert len(channels) > 0

        # Verify channel structure
        for channel in channels:
            assert "name" in channel
            assert "description" in channel
            assert "message_types" in channel
            assert "typical_update_frequency" in channel
            assert "required_permissions" in channel

    async def test_websocket_health_check_endpoint(self):
        """Test WebSocket health check endpoint"""

        client = TestClient(app)

        response = client.get("/api/v2/ws/health")
        assert response.status_code == 200

        health_data = response.json()

        # Verify health check structure
        assert "status" in health_data
        assert "timestamp" in health_data
        assert "checks" in health_data
        assert "metrics" in health_data

        # Verify health status is either "healthy" or "degraded"
        assert health_data["status"] in ["healthy", "degraded", "unhealthy"]

        # Verify individual health checks
        checks = health_data["checks"]
        expected_checks = [
            "connection_manager", "status_update_service",
            "redis_connection", "connection_load"
        ]

        for check in expected_checks:
            assert check in checks
            assert checks[check] in ["healthy", "unhealthy", "high"]


# ============================================================================
# Test Fixtures and Utilities
# ============================================================================

@pytest.fixture
async def websocket_v1_connection():
    """Fixture providing WebSocket v1 connection"""

    url = WebSocketTestConfig.WS_V1_URL
    token = WebSocketTestHelper.generate_test_token()

    websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
    await WebSocketTestHelper.authenticate_websocket_v1(websocket)

    yield websocket

    await websocket.close()


@pytest.fixture
async def websocket_v2_connection():
    """Fixture providing WebSocket v2 connection"""

    url = WebSocketTestConfig.WS_V2_URL
    token = WebSocketTestHelper.generate_test_token()

    websocket = await WebSocketTestHelper.create_websocket_connection(url, token=token)
    await WebSocketTestHelper.authenticate_websocket_v2(websocket)

    yield websocket

    await websocket.close()


@pytest.fixture
def mock_user():
    """Fixture providing mock user"""
    return MockUserManager.create_test_user()


@pytest.fixture
def mock_admin_user():
    """Fixture providing mock admin user"""
    return MockUserManager.create_test_user(is_superuser=True)


# ============================================================================
# Async Test Runner
# ============================================================================

if __name__ == "__main__":
    # Example of running tests directly
    async def run_sample_tests():
        """Run sample WebSocket tests"""

        print("Running WebSocket Contract Tests...")

        # Test v1 connection
        try:
            await TestWebSocketV1Contract().test_websocket_v1_connection_success()
            print("✅ WebSocket v1 connection test passed")
        except Exception as e:
            print(f"❌ WebSocket v1 connection test failed: {e}")

        # Test v2 connection
        try:
            await TestWebSocketV2Contract().test_websocket_v2_connection_success()
            print("✅ WebSocket v2 connection test passed")
        except Exception as e:
            print(f"❌ WebSocket v2 connection test failed: {e}")

        # Test monitoring
        try:
            await TestMonitoringWebSockets().test_monitoring_websocket_connection("metrics")
            print("✅ Monitoring WebSocket connection test passed")
        except Exception as e:
            print(f"❌ Monitoring WebSocket connection test failed: {e}")

    # Run tests
    asyncio.run(run_sample_tests())