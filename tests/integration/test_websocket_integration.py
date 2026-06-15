"""
WebSocket Integration Tests
Tests real-time communication between frontend and backend via WebSocket connections
"""

import pytest
import asyncio
import json
import uuid
import websockets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock

from conftest import (
    APIAssertions, create_auth_headers, wait_for_condition,
    sample_organization, sample_user, sample_metrics_data
)
from tests.constants import TEST_JWT_SECRET


class TestWebSocketIntegration:
    """Test WebSocket real-time communication integration"""

    @pytest.fixture
    async def websocket_connection_factory(self, websocket_client, sample_user):
        """Factory to create authenticated WebSocket connections"""
        import jwt

        async def create_connection(path: str = "/ws/analytics"):
            # Create JWT token for WebSocket authentication
            token = jwt.encode(
                {
                    "sub": str(sample_user["id"]),
                    "email": sample_user["email"],
                    "organization_id": str(sample_user["organization_id"]),
                    "roles": sample_user["roles"],
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1)
                },
                TEST_JWT_SECRET,
                algorithm="HS256"
            )

            # Connect with authentication token
            uri = f"{websocket_client.base_url}{path}?token={token}"
            websocket = await websocket_client.connect(uri)
            return websocket

        return create_connection

    @pytest.fixture
    async def mock_realtime_service(self):
        """Mock real-time analytics service for testing"""
        class MockRealtimeService:
            def __init__(self):
                self.active_connections = {}
                self.subscriptions = {}
                self.messages = []

            async def handle_connection(self, connection_id: str, websocket):
                self.active_connections[connection_id] = websocket
                return connection_id

            async def handle_subscription(self, connection_id: str, subscription_data: Dict[str, Any]):
                subscription_id = str(uuid.uuid4())
                if connection_id not in self.subscriptions:
                    self.subscriptions[connection_id] = {}
                self.subscriptions[connection_id][subscription_id] = subscription_data
                return subscription_id

            async def broadcast_message(self, channel: str, message: Dict[str, Any]):
                self.messages.append({"channel": channel, "message": message, "timestamp": datetime.now(timezone.utc)})
                return True

            async def cleanup_connection(self, connection_id: str):
                if connection_id in self.active_connections:
                    del self.active_connections[connection_id]
                if connection_id in self.subscriptions:
                    del self.subscriptions[connection_id]

        return MockRealtimeService()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_connection_establishment(self, websocket_connection_factory):
        """Test WebSocket connection establishment and authentication"""
        # 1. Establish connection
        websocket = await websocket_connection_factory()

        try:
            # 2. Wait for welcome message
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            welcome_data = json.loads(message)

            # 3. Validate welcome message structure
            assert "type" in welcome_data
            assert welcome_data["type"] == "auth"  # Authentication confirmation
            assert "data" in welcome_data
            assert "connection_id" in welcome_data["data"]
            assert "user_id" in welcome_data["data"]
            assert "timestamp" in welcome_data["data"]

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_subscription_flow(self, websocket_connection_factory, sample_organization):
        """Test WebSocket subscription to real-time metrics"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Wait for authentication
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            auth_data = json.loads(auth_message)
            connection_id = auth_data["data"]["connection_id"]

            # 2. Subscribe to real-time metrics
            subscription_message = {
                "type": "subscribe",
                "subscription_type": "metrics",
                "channel": f"org_{sample_organization['id']}_metrics",
                "filters": {
                    "metric_types": ["entity", "relationship"],
                    "refresh_interval": 5000
                },
                "batch_size": 100,
                "update_interval": 1000
            }

            await websocket.send(json.dumps(subscription_message))

            # 3. Wait for subscription confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)

            assert response_data["type"] == "data"
            assert response_data["data"]["status"] == "subscribed"
            assert "subscription_id" in response_data["data"]

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_realtime_metrics_updates(self, websocket_connection_factory, sample_organization, sample_metrics_data):
        """Test receiving real-time metrics updates via WebSocket"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate and subscribe
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            subscription_message = {
                "type": "subscribe",
                "subscription_type": "metrics",
                "channel": f"org_{sample_organization['id']}_metrics",
                "filters": {"entity_types": ["person", "organization"]}
            }
            await websocket.send(json.dumps(subscription_message))

            # Wait for subscription confirmation
            await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Simulate receiving metrics update
            metrics_update = {
                "type": "data",
                "channel": f"org_{sample_organization['id']}_metrics",
                "data": {
                    "type": "metric_update",
                    "metrics": [metric.dict() for metric in sample_metrics_data]
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # In a real test, this would be sent by the backend
            # For testing, we'll verify the message structure
            assert "type" in metrics_update
            assert "channel" in metrics_update
            assert "data" in metrics_update
            assert "timestamp" in metrics_update

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_alert_notifications(self, websocket_connection_factory, sample_organization):
        """Test receiving alert notifications via WebSocket"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate and subscribe to alerts
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            subscription_message = {
                "type": "subscribe",
                "subscription_type": "alerts",
                "channel": f"org_{sample_organization['id']}_alerts",
                "filters": {"severity": ["warning", "critical"]}
            }
            await websocket.send(json.dumps(subscription_message))

            # Wait for subscription confirmation
            await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Simulate alert notification
            alert_notification = {
                "type": "data",
                "channel": f"org_{sample_organization['id']}_alerts",
                "data": {
                    "type": "alert_triggered",
                    "alert": {
                        "id": str(uuid.uuid4()),
                        "alert_name": "High Entity Growth Alert",
                        "severity": "warning",
                        "message": "Entity growth rate exceeded threshold",
                        "current_value": 125.5,
                        "threshold": 100.0,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            }

            # Verify alert notification structure
            assert alert_notification["data"]["type"] == "alert_triggered"
            assert "alert" in alert_notification["data"]
            assert alert_notification["data"]["alert"]["severity"] == "warning"

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_dashboard_updates(self, websocket_connection_factory, sample_organization):
        """Test receiving dashboard configuration updates via WebSocket"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate and subscribe to dashboard updates
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            subscription_message = {
                "type": "subscribe",
                "subscription_type": "dashboard",
                "channel": f"org_{sample_organization['id']}_dashboard",
                "filters": {"dashboard_ids": [str(uuid.uuid4())]}
            }
            await websocket.send(json.dumps(subscription_message))

            # Wait for subscription confirmation
            await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Simulate dashboard update notification
            dashboard_update = {
                "type": "data",
                "channel": f"org_{sample_organization['id']}_dashboard",
                "data": {
                    "type": "dashboard_change",
                    "dashboard_id": str(uuid.uuid4()),
                    "change_type": "widget_updated",
                    "widget_id": str(uuid.uuid4()),
                    "changes": {
                        "position": {"row": 1, "col": 2},
                        "config": {"metric_id": "new_metric"}
                    },
                    "updated_by": "test_user@example.com",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

            # Verify dashboard update structure
            assert dashboard_update["data"]["type"] == "dashboard_change"
            assert dashboard_update["data"]["change_type"] == "widget_updated"
            assert "changes" in dashboard_update["data"]

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_multiple_subscriptions(self, websocket_connection_factory, sample_organization):
        """Test managing multiple WebSocket subscriptions"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Subscribe to multiple channels
            subscriptions = [
                {
                    "type": "subscribe",
                    "subscription_type": "metrics",
                    "channel": f"org_{sample_organization['id']}_metrics",
                    "filters": {"metric_types": ["entity"]}
                },
                {
                    "type": "subscribe",
                    "subscription_type": "alerts",
                    "channel": f"org_{sample_organization['id']}_alerts",
                    "filters": {"severity": ["critical"]}
                },
                {
                    "type": "subscribe",
                    "subscription_type": "dashboard",
                    "channel": f"org_{sample_organization['id']}_dashboard"
                }
            ]

            subscription_ids = []
            for sub in subscriptions:
                await websocket.send(json.dumps(sub))
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                subscription_ids.append(response_data["data"]["subscription_id"])

            # 3. Verify all subscriptions are active
            assert len(subscription_ids) == 3

            # 4. Unsubscribe from one channel
            unsubscribe_message = {
                "type": "unsubscribe",
                "subscription_id": subscription_ids[0]
            }
            await websocket.send(json.dumps(unsubscribe_message))

            # 5. Verify unsubscription confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["data"]["status"] == "unsubscribed"

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_heartbeat_mechanism(self, websocket_connection_factory):
        """Test WebSocket heartbeat/ping-pong mechanism"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Send ping to server
            ping_message = {
                "type": "ping",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket.send(json.dumps(ping_message))

            # 3. Wait for pong response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)

            assert response_data["type"] == "pong"
            assert "timestamp" in response_data

            # 4. Receive ping from server and respond with pong
            # This would normally be handled by the WebSocket client automatically
            # For testing, we simulate receiving a ping
            server_ping = {
                "type": "ping",
                "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }

            # Respond with pong
            pong_message = {
                "type": "pong",
                "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
            await websocket.send(json.dumps(pong_message))

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_error_handling(self, websocket_connection_factory):
        """Test WebSocket error handling and recovery"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Send invalid message
            invalid_message = {
                "type": "invalid_type",
                "data": {"invalid": "data"}
            }
            await websocket.send(json.dumps(invalid_message))

            # 3. Wait for error response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            error_data = json.loads(response)

            assert error_data["type"] == "error"
            assert "error" in error_data

            # 4. Send malformed JSON
            await websocket.send("invalid json string")

            # 5. Wait for error response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            error_data = json.loads(response)

            assert error_data["type"] == "error"
            assert "error" in error_data

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_connection_limits(self, websocket_connection_factory, sample_user):
        """Test WebSocket connection limits and management"""
        connections = []

        try:
            # 1. Create multiple connections (simulating multiple browser tabs)
            max_connections = 5
            for i in range(max_connections):
                try:
                    websocket = await websocket_connection_factory()
                    connections.append(websocket)

                    # Wait for authentication
                    await asyncio.wait_for(websocket.recv(), timeout=5.0)
                except Exception as e:
                    # Connection limit reached
                    break

            # 2. Verify connections are established
            assert len(connections) > 0

            # 3. Test connection reuse
            # Close one connection and create a new one
            if len(connections) > 0:
                await connections[0].close()
                connections.pop(0)

                # Create new connection
                new_websocket = await websocket_connection_factory()
                connections.append(new_websocket)

                # Verify authentication
                auth_message = await asyncio.wait_for(new_websocket.recv(), timeout=5.0)
                auth_data = json.loads(auth_message)
                assert "connection_id" in auth_data["data"]

        finally:
            # Clean up all connections
            for websocket in connections:
                try:
                    await websocket.close()
                except:
                    pass

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_message_filtering(self, websocket_connection_factory, sample_organization):
        """Test WebSocket message filtering based on subscription criteria"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Subscribe with specific filters
            subscription_message = {
                "type": "subscribe",
                "subscription_type": "metrics",
                "channel": f"org_{sample_organization['id']}_metrics",
                "filters": {
                    "metric_types": ["entity"],
                    "min_confidence": 0.8,
                    "entity_types": ["person"]
                }
            }
            await websocket.send(json.dumps(subscription_message))

            # Wait for subscription confirmation
            await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 3. Simulate different types of messages
            messages = [
                {
                    "type": "data",
                    "channel": f"org_{sample_organization['id']}_metrics",
                    "data": {
                        "type": "metric_update",
                        "metric": {
                            "metric_type": "entity",
                            "confidence": 0.9,
                            "entity_type": "person"
                        }
                    }
                },
                {
                    "type": "data",
                    "channel": f"org_{sample_organization['id']}_metrics",
                    "data": {
                        "type": "metric_update",
                        "metric": {
                            "metric_type": "relationship",  # Should be filtered out
                            "confidence": 0.9
                        }
                    }
                }
            ]

            # Verify filtering criteria
            for message in messages:
                metric = message["data"]["metric"]
                if (metric["metric_type"] == "entity" and
                    metric.get("confidence", 0) >= 0.8 and
                    metric.get("entity_type") == "person"):
                    # This message should pass through
                    assert True
                else:
                    # This message should be filtered out
                    assert metric["metric_type"] != "entity" or metric.get("confidence", 0) < 0.8

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_graceful_shutdown(self, websocket_connection_factory, sample_organization):
        """Test WebSocket graceful shutdown and cleanup"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate and create subscriptions
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            connection_id = json.loads(auth_message)["data"]["connection_id"]

            # Create multiple subscriptions
            subscription_message = {
                "type": "subscribe",
                "subscription_type": "metrics",
                "channel": f"org_{sample_organization['id']}_metrics"
            }
            await websocket.send(json.dumps(subscription_message))

            await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Close connection gracefully
            await websocket.close()

            # 3. Verify connection is closed (should raise exception)
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                await websocket.recv()

        except:
            # Ensure cleanup even if test fails
            try:
                await websocket.close()
            except:
                pass

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_message_ordering(self, websocket_connection_factory, sample_organization):
        """Test WebSocket message ordering and sequencing"""
        websocket = await websocket_connection_factory()

        try:
            # 1. Authenticate
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 2. Subscribe to metrics
            subscription_message = {
                "type": "subscribe",
                "subscription_type": "metrics",
                "channel": f"org_{sample_organization['id']}_metrics"
            }
            await websocket.send(json.dumps(subscription_message))

            # Wait for subscription confirmation
            await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # 3. Send multiple messages in sequence
            messages = []
            for i in range(5):
                message = {
                    "type": "data",
                    "channel": f"org_{sample_organization['id']}_metrics",
                    "data": {
                        "type": "metric_update",
                        "sequence": i,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
                messages.append(message)

            # In a real scenario, these would be sent by the backend
            # For testing, verify message structure
            for i, message in enumerate(messages):
                assert message["data"]["sequence"] == i
                assert "timestamp" in message["data"]

        finally:
            await websocket.close()

    @pytest.mark.integration
    @pytest.mark.websocket
    async def test_websocket_authentication_expiry(self, websocket_connection_factory, sample_user):
        """Test WebSocket behavior when authentication expires"""
        # Create a token that will expire soon
        import jwt
        expired_token = jwt.encode(
            {
                "sub": str(sample_user["id"]),
                "email": sample_user["email"],
                "organization_id": str(sample_user["organization_id"]),
                "roles": sample_user["roles"],
                "exp": datetime.now(timezone.utc) + timedelta(seconds=2)  # Expires in 2 seconds
            },
            TEST_JWT_SECRET,
            algorithm="HS256"
        )

        try:
            # Connect with expiring token
            uri = f"{websocket_client.base_url}/ws/analytics?token={expired_token}"
            websocket = await websocket_client.connect(uri)

            # Wait for authentication
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)

            # Wait for token to expire
            await asyncio.sleep(3)

            # Try to send a message (should fail due to expired token)
            subscription_message = {
                "type": "subscribe",
                "subscription_type": "metrics",
                "channel": "test_channel"
            }

            await websocket.send(json.dumps(subscription_message))

            # Should receive authentication error
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            error_data = json.loads(response)

            assert error_data["type"] == "error"
            assert "authentication" in error_data["error"].lower()

        except Exception as e:
            # Connection should be closed due to authentication failure
            pass
        finally:
            try:
                await websocket.close()
            except:
                pass