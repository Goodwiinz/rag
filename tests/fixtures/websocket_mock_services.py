"""
Mock Services for WebSocket Testing

This module provides mock services and utilities for isolated WebSocket testing,
including mock WebSocket servers, connection managers, and test data generators.
"""

import asyncio
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import random
import logging

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from backend.src.services.websocket_manager import (
    WebSocketMessage,
    MessageType,
    Priority,
    ConnectionInfo
)
from backend.src.models.websocket_status import (
    ConnectionStatus,
    UpdateType,
    StatusUpdate,
    WebSocketConnection,
    ConnectionEvent
)


@dataclass
class MockConnection:
    """Mock WebSocket connection for testing"""
    connection_id: str
    user_id: str
    organization_id: str
    websocket: Optional[AsyncMock] = None
    connected_at: datetime = None
    last_heartbeat: datetime = None
    subscribed_channels: List[str] = None
    message_filter: Dict[str, Any] = None
    is_connected: bool = True
    sent_messages: List[Dict] = None
    received_messages: List[Dict] = None

    def __post_init__(self):
        if self.connected_at is None:
            self.connected_at = datetime.utcnow()
        if self.last_heartbeat is None:
            self.last_heartbeat = datetime.utcnow()
        if self.subscribed_channels is None:
            self.subscribed_channels = []
        if self.message_filter is None:
            self.message_filter = {}
        if self.sent_messages is None:
            self.sent_messages = []
        if self.received_messages is None:
            self.received_messages = []


class MockWebSocketServer:
    """Mock WebSocket server for testing"""

    def __init__(self):
        self.connections: Dict[str, MockConnection] = {}
        self.message_history: List[Dict] = []
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.auth_tokens: Dict[str, Dict[str, Any]] = {}
        self.channel_subscribers: Dict[str, List[str]] = defaultdict(list)
        self.is_running = False
        self.logger = logging.getLogger(__name__)

    async def start(self, host: str = "localhost", port: int = 8765):
        """Start the mock WebSocket server"""
        self.is_running = True
        self.logger.info(f"Mock WebSocket server started on {host}:{port}")

    async def stop(self):
        """Stop the mock WebSocket server"""
        self.is_running = False
        for connection in self.connections.values():
            await self.disconnect(connection.connection_id, "Server shutdown")
        self.logger.info("Mock WebSocket server stopped")

    def generate_auth_token(self, user_id: str, organization_id: str,
                          expires_in: int = 3600, **kwargs) -> str:
        """Generate mock authentication token"""
        token_id = str(uuid.uuid4())
        token_data = {
            "user_id": user_id,
            "organization_id": organization_id,
            "token_id": token_id,
            "issued_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat(),
            **kwargs
        }

        # Simple mock token encoding
        token = f"mock_token_{token_id}"
        self.auth_tokens[token] = token_data

        return token

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate mock authentication token"""
        if token not in self.auth_tokens:
            return None

        token_data = self.auth_tokens[token]
        expires_at = datetime.fromisoformat(token_data["expires_at"])

        if datetime.utcnow() > expires_at:
            del self.auth_tokens[token]
            return None

        return token_data

    async def connect(self, websocket: AsyncMock, token: str,
                     client_info: Dict[str, Any] = None) -> Optional[str]:
        """Handle new WebSocket connection"""
        # Validate authentication token
        token_data = self.validate_token(token)
        if not token_data:
            await self._send_error(websocket, "Invalid or expired token")
            return None

        # Check connection limits
        user_connections = [c for c in self.connections.values()
                          if c.user_id == token_data["user_id"] and c.is_connected]

        if len(user_connections) >= 5:  # Mock limit
            await self._send_error(websocket, "Connection limit exceeded")
            return None

        # Create connection
        connection_id = str(uuid.uuid4())
        connection = MockConnection(
            connection_id=connection_id,
            user_id=token_data["user_id"],
            organization_id=token_data["organization_id"],
            websocket=websocket,
            client_info=client_info or {}
        )

        self.connections[connection_id] = connection

        # Send welcome message
        welcome_message = {
            "type": MessageType.CONNECT.value,
            "data": {
                "connection_id": connection_id,
                "user_id": connection.user_id,
                "organization_id": connection.organization_id,
                "server_time": datetime.utcnow().isoformat(),
                "heartbeat_interval": 30
            },
            "timestamp": datetime.utcnow().isoformat(),
            "id": str(uuid.uuid4()),
            "priority": Priority.NORMAL.value
        }

        await self._send_message(connection_id, welcome_message)

        # Trigger connection event
        await self._trigger_event("connection_established", connection)

        self.logger.info(f"Mock connection established: {connection_id}")
        return connection_id

    async def disconnect(self, connection_id: str, reason: str = None):
        """Handle WebSocket disconnection"""
        if connection_id not in self.connections:
            return

        connection = self.connections[connection_id]
        connection.is_connected = False

        # Remove from channel subscriptions
        for channel in connection.subscribed_channels:
            if connection_id in self.channel_subscribers[channel]:
                self.channel_subscribers[channel].remove(connection_id)

        # Trigger disconnection event
        await self._trigger_event("connection_closed", connection, {"reason": reason})

        self.logger.info(f"Mock connection closed: {connection_id} - {reason}")

    async def send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific connection"""
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]
        if not connection.is_connected:
            return False

        # Add metadata to message
        message_with_metadata = {
            **message,
            "timestamp": datetime.utcnow().isoformat(),
            "id": str(uuid.uuid4()),
            "priority": message.get("priority", Priority.NORMAL.value)
        }

        connection.sent_messages.append(message_with_metadata)
        self.message_history.append({
            "connection_id": connection_id,
            "direction": "sent",
            "message": message_with_metadata,
            "timestamp": datetime.utcnow()
        })

        # Simulate WebSocket send
        if connection.websocket:
            connection.websocket.send.assert_called_with(json.dumps(message_with_metadata))

        return True

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast message to all channel subscribers"""
        if channel not in self.channel_subscribers:
            return

        for connection_id in self.channel_subscribers[channel]:
            await self.send_message(connection_id, message)

    async def handle_message(self, connection_id: str, raw_message: str):
        """Handle incoming message from client"""
        if connection_id not in self.connections:
            return

        connection = self.connections[connection_id]
        connection.last_heartbeat = datetime.utcnow()

        try:
            message = json.loads(raw_message)
            connection.received_messages.append(message)

            self.message_history.append({
                "connection_id": connection_id,
                "direction": "received",
                "message": message,
                "timestamp": datetime.utcnow()
            })

            # Handle message types
            await self._handle_message_type(connection_id, message)

        except json.JSONDecodeError:
            await self._send_error(connection_id, "Invalid JSON format")

    async def _handle_message_type(self, connection_id: str, message: Dict[str, Any]):
        """Handle specific message types"""
        message_type = message.get("type")
        message_data = message.get("data", {})

        if message_type == MessageType.PING.value:
            pong_message = {
                "type": MessageType.PONG.value,
                "data": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "sequence": message_data.get("sequence", 0)
                }
            }
            await self.send_message(connection_id, pong_message)

        elif message_type == MessageType.SUBSCRIBE.value:
            channel = message_data.get("channel")
            if channel:
                await self.subscribe_to_channel(connection_id, channel)

        elif message_type == MessageType.UNSUBSCRIBE.value:
            channel = message_data.get("channel")
            if channel:
                await self.unsubscribe_from_channel(connection_id, channel)

        elif message_type == MessageType.STATUS_UPDATE.value:
            connection.last_heartbeat = datetime.utcnow()
            if "message_filter" in message_data:
                connection.message_filter = message_data["message_filter"]

    async def subscribe_to_channel(self, connection_id: str, channel: str):
        """Subscribe connection to channel"""
        if connection_id not in self.connections:
            return

        connection = self.connections[connection_id]
        if channel not in connection.subscribed_channels:
            connection.subscribed_channels.append(channel)

        if connection_id not in self.channel_subscribers[channel]:
            self.channel_subscribers[channel].append(connection_id)

        # Send confirmation
        confirmation_message = {
            "type": MessageType.SUBSCRIBE.value,
            "data": {
                "channel": channel,
                "subscribed": True
            }
        }
        await self.send_message(connection_id, confirmation_message)

    async def unsubscribe_from_channel(self, connection_id: str, channel: str):
        """Unsubscribe connection from channel"""
        if connection_id not in self.connections:
            return

        connection = self.connections[connection_id]
        if channel in connection.subscribed_channels:
            connection.subscribed_channels.remove(channel)

        if connection_id in self.channel_subscribers[channel]:
            self.channel_subscribers[channel].remove(connection_id)

        # Send confirmation
        confirmation_message = {
            "type": MessageType.UNSUBSCRIBE.value,
            "data": {
                "channel": channel,
                "subscribed": False
            }
        }
        await self.send_message(connection_id, confirmation_message)

    async def _send_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to connection"""
        await self.send_message(connection_id, message)

    async def _send_error(self, connection_or_websocket, error_message: str):
        """Send error message"""
        error_response = {
            "type": MessageType.ERROR.value,
            "data": {
                "error": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        if isinstance(connection_or_websocket, str):
            # Connection ID
            await self.send_message(connection_or_websocket, error_response)
        else:
            # WebSocket mock
            connection_or_websocket.send.assert_called_with(json.dumps(error_response))

    async def _trigger_event(self, event_type: str, connection: MockConnection,
                           event_data: Dict[str, Any] = None):
        """Trigger server event"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(connection, event_data or {})
                except Exception as e:
                    self.logger.error(f"Event handler error: {e}")

    def add_event_handler(self, event_type: str, handler: Callable):
        """Add event handler"""
        self.event_handlers[event_type].append(handler)

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        connected = [c for c in self.connections.values() if c.is_connected]

        return {
            "total_connections": len(connected),
            "unique_users": len(set(c.user_id for c in connected)),
            "unique_organizations": len(set(c.organization_id for c in connected)),
            "channel_subscriptions": {
                channel: len(subscribers)
                for channel, subscribers in self.channel_subscribers.items()
            },
            "messages_sent": sum(len(c.sent_messages) for c in connected),
            "messages_received": sum(len(c.received_messages) for c in connected),
            "message_history_size": len(self.message_history)
        }

    def simulate_message_delay(self, min_delay: float = 0.01, max_delay: float = 0.1):
        """Simulate message processing delay"""
        delay = random.uniform(min_delay, max_delay)
        return asyncio.sleep(delay)


class MockStatusUpdateService:
    """Mock service for generating status updates"""

    def __init__(self, websocket_server: MockWebSocketServer):
        self.websocket_server = websocket_server
        self.update_generators: Dict[str, asyncio.Task] = {}
        self.status_templates = self._load_status_templates()

    def _load_status_templates(self) -> Dict[str, List[Dict]]:
        """Load templates for different status update types"""
        return {
            "document_processing": [
                {
                    "type": UpdateType.DOCUMENT_PROCESSING.value,
                    "data": {
                        "status": "pending",
                        "progress": 0,
                        "message": "Document queued for processing"
                    }
                },
                {
                    "type": UpdateType.DOCUMENT_PROCESSING.value,
                    "data": {
                        "status": "processing",
                        "progress": 25,
                        "message": "Extracting text content"
                    }
                },
                {
                    "type": UpdateType.DOCUMENT_PROCESSING.value,
                    "data": {
                        "status": "processing",
                        "progress": 50,
                        "message": "Analyzing document structure"
                    }
                },
                {
                    "type": UpdateType.DOCUMENT_PROCESSING.value,
                    "data": {
                        "status": "processing",
                        "progress": 75,
                        "message": "Generating embeddings"
                    }
                },
                {
                    "type": UpdateType.DOCUMENT_PROCESSING.value,
                    "data": {
                        "status": "completed",
                        "progress": 100,
                        "message": "Document processed successfully"
                    }
                },
                {
                    "type": UpdateType.DOCUMENT_PROCESSING.value,
                    "data": {
                        "status": "failed",
                        "progress": 30,
                        "error": "File format not supported",
                        "error_code": "UNSUPPORTED_FORMAT"
                    }
                }
            ],
            "job_status": [
                {
                    "type": UpdateType.JOB_STATUS.value,
                    "data": {
                        "status": "queued",
                        "total_items": 100,
                        "processed_items": 0,
                        "progress_percentage": 0
                    }
                },
                {
                    "type": UpdateType.JOB_STATUS.value,
                    "data": {
                        "status": "running",
                        "total_items": 100,
                        "processed_items": 45,
                        "progress_percentage": 45,
                        "current_step": "vector_indexing"
                    }
                },
                {
                    "type": UpdateType.JOB_STATUS.value,
                    "data": {
                        "status": "completed",
                        "total_items": 100,
                        "processed_items": 100,
                        "progress_percentage": 100
                    }
                }
            ],
            "system_health": [
                {
                    "type": UpdateType.SYSTEM_STATUS.value,
                    "data": {
                        "service": "vector_store",
                        "status": "healthy",
                        "response_time_ms": random.randint(10, 100),
                        "uptime_percentage": random.uniform(99.0, 100.0)
                    }
                },
                {
                    "type": UpdateType.SYSTEM_STATUS.value,
                    "data": {
                        "service": "processing_queue",
                        "status": "warning",
                        "queue_depth": random.randint(500, 2000),
                        "threshold": 1000
                    }
                }
            ]
        }

    async def start_status_updates(self, update_type: str, interval: float = 5.0):
        """Start generating status updates of specified type"""
        if update_type in self.update_generators:
            return  # Already running

        self.update_generators[update_type] = asyncio.create_task(
            self._generate_status_updates(update_type, interval)
        )

    async def stop_status_updates(self, update_type: str):
        """Stop generating status updates"""
        if update_type in self.update_generators:
            self.update_generators[update_type].cancel()
            del self.update_generators[update_type]

    async def _generate_status_updates(self, update_type: str, interval: float):
        """Generate status updates continuously"""
        templates = self.status_templates.get(update_type, [])

        while True:
            try:
                # Select random template
                template = random.choice(templates)
                update = dict(template)  # Deep copy

                # Add unique identifiers
                if update_type == "document_processing":
                    update["data"]["document_id"] = str(uuid.uuid4())
                    update["data"]["timestamp"] = datetime.utcnow().isoformat()
                elif update_type == "job_status":
                    update["data"]["job_id"] = str(uuid.uuid4())
                    update["data"]["timestamp"] = datetime.utcnow().isoformat()
                elif update_type == "system_health":
                    update["data"]["timestamp"] = datetime.utcnow().isoformat()
                    update["data"]["last_check"] = datetime.utcnow().isoformat()

                # Add WebSocket message metadata
                message = {
                    "type": update["type"],
                    "data": update["data"],
                    "priority": Priority.NORMAL.value
                }

                # Broadcast to appropriate channel
                channel = f"{update_type}_updates"
                await self.websocket_server.broadcast_to_channel(channel, message)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error generating status update: {e}")
                await asyncio.sleep(1)

    async def send_single_update(self, connection_id: str, update_type: str,
                               custom_data: Dict[str, Any] = None):
        """Send a single status update to specific connection"""
        templates = self.status_templates.get(update_type, [])
        if not templates:
            return

        template = random.choice(templates)
        update = dict(template)

        # Apply custom data
        if custom_data:
            update["data"].update(custom_data)

        message = {
            "type": update["type"],
            "data": update["data"],
            "priority": Priority.NORMAL.value
        }

        await self.websocket_server.send_message(connection_id, message)


class MockTestClient:
    """Mock test client for WebSocket testing"""

    def __init__(self, mock_server: MockWebSocketServer):
        self.mock_server = mock_server
        self.connections: List[MockConnection] = []

    async def connect(self, user_id: str = None, organization_id: str = None,
                     token: str = None, client_info: Dict[str, Any] = None) -> Optional[str]:
        """Connect to mock WebSocket server"""
        if not token:
            user_id = user_id or f"test_user_{uuid.uuid4().hex[:8]}"
            organization_id = organization_id or f"test_org_{uuid.uuid4().hex[:8]}"
            token = self.mock_server.generate_auth_token(user_id, organization_id)

        # Create mock WebSocket
        mock_websocket = AsyncMock()

        connection_id = await self.mock_server.connect(
            mock_websocket, token, client_info
        )

        if connection_id:
            connection = self.mock_server.connections[connection_id]
            self.connections.append(connection)

        return connection_id

    async def send_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message through mock connection"""
        raw_message = json.dumps(message)
        await self.mock_server.handle_message(connection_id, raw_message)

    async def receive_message(self, connection_id: str, timeout: float = 5.0) -> Optional[Dict]:
        """Receive message from mock connection"""
        if connection_id not in self.mock_server.connections:
            return None

        connection = self.mock_server.connections[connection_id]
        if connection.sent_messages:
            return connection.sent_messages[-1]  # Return last message

        return None

    async def disconnect(self, connection_id: str, reason: str = None):
        """Disconnect from mock server"""
        await self.mock_server.disconnect(connection_id, reason)

        # Remove from client's connection list
        self.connections = [
            c for c in self.connections
            if c.connection_id != connection_id
        ]

    async def subscribe(self, connection_id: str, channel: str):
        """Subscribe to channel"""
        await self.mock_server.subscribe_to_channel(connection_id, channel)

    async def unsubscribe(self, connection_id: str, channel: str):
        """Unsubscribe from channel"""
        await self.mock_server.unsubscribe_from_channel(connection_id, channel)

    def get_connection_info(self, connection_id: str) -> Optional[MockConnection]:
        """Get connection information"""
        return self.mock_server.connections.get(connection_id)

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return self.mock_server.get_connection_stats()


@pytest.fixture
async def mock_websocket_server():
    """Fixture providing mock WebSocket server"""
    server = MockWebSocketServer()
    await server.start()

    try:
        yield server
    finally:
        await server.stop()


@pytest.fixture
async def mock_status_service(mock_websocket_server):
    """Fixture providing mock status update service"""
    service = MockStatusUpdateService(mock_websocket_server)

    try:
        yield service
    finally:
        # Stop all update generators
        for update_type in list(service.update_generators.keys()):
            await service.stop_status_updates(update_type)


@pytest.fixture
async def mock_websocket_client(mock_websocket_server):
    """Fixture providing mock WebSocket test client"""
    client = MockTestClient(mock_websocket_server)

    try:
        yield client
    finally:
        # Clean up all connections
        for connection in client.connections:
            await client.disconnect(connection.connection_id)


class WebSocketTestDataGenerator:
    """Generator for WebSocket test data"""

    @staticmethod
    def generate_test_users(count: int = 10) -> List[Dict[str, Any]]:
        """Generate test user data"""
        users = []
        for i in range(count):
            users.append({
                "user_id": str(uuid.uuid4()),
                "email": f"testuser{i}@example.com",
                "first_name": f"Test{i}",
                "last_name": f"User{i}",
                "organization_id": str(uuid.uuid4())
            })
        return users

    @staticmethod
    def generate_test_documents(count: int = 20) -> List[Dict[str, Any]]:
        """Generate test document data"""
        titles = [
            "Machine Learning Fundamentals",
            "Deep Learning Architecture",
            "Natural Language Processing",
            "Computer Vision Applications",
            "Reinforcement Learning",
            "Data Science Best Practices",
            "Algorithm Design Patterns",
            "Database Optimization",
            "Cloud Computing Principles",
            "DevOps Strategies"
        ]

        documents = []
        for i in range(count):
            title = titles[i % len(titles)]
            documents.append({
                "document_id": str(uuid.uuid4()),
                "title": f"{title} - Part {i//len(titles) + 1}",
                "file_type": random.choice(["pdf", "txt", "docx"]),
                "size_bytes": random.randint(1024, 10 * 1024 * 1024),
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat(),
                "processing_status": random.choice(["pending", "processing", "completed", "failed"])
            })
        return documents

    @staticmethod
    def generate_test_jobs(count: int = 15) -> List[Dict[str, Any]]:
        """Generate test job data"""
        job_types = ["batch_processing", "index_rebuild", "data_export", "cleanup"]

        jobs = []
        for i in range(count):
            job_type = job_types[i % len(job_types)]
            jobs.append({
                "job_id": str(uuid.uuid4()),
                "job_type": job_type,
                "status": random.choice(["queued", "running", "completed", "failed"]),
                "total_items": random.randint(10, 1000),
                "processed_items": random.randint(0, 1000),
                "created_at": (datetime.utcnow() - timedelta(minutes=random.randint(0, 120))).isoformat(),
                "estimated_completion": (datetime.utcnow() + timedelta(minutes=random.randint(5, 60))).isoformat()
            })
        return jobs

    @staticmethod
    def generate_test_search_queries(count: int = 25) -> List[Dict[str, Any]]:
        """Generate test search query data"""
        query_templates = [
            "machine learning algorithms",
            "neural network architecture",
            "data processing pipeline",
            "cloud computing best practices",
            "software design patterns",
            "database optimization techniques",
            "artificial intelligence applications",
            "big data analytics",
            "cybersecurity principles",
            "web development frameworks"
        ]

        queries = []
        for i in range(count):
            query = query_templates[i % len(query_templates)]
            queries.append({
                "query_id": str(uuid.uuid4()),
                "query": f"{query} advanced techniques",
                "search_type": random.choice(["vector", "graph", "hybrid", "fulltext"]),
                "max_results": random.randint(10, 100),
                "response_time_ms": random.randint(50, 2000),
                "results_count": random.randint(0, 50),
                "timestamp": (datetime.utcnow() - timedelta(seconds=random.randint(0, 3600))).isoformat()
            })
        return queries

    @staticmethod
    def generate_error_scenarios() -> List[Dict[str, Any]]:
        """Generate test error scenarios"""
        return [
            {
                "error_type": "authentication_error",
                "description": "Invalid or expired JWT token",
                "http_status": 401,
                "websocket_code": 1008,
                "test_trigger": "invalid_token"
            },
            {
                "error_type": "connection_limit_error",
                "description": "Too many connections from user",
                "http_status": 429,
                "websocket_code": 1013,
                "test_trigger": "exceed_connection_limit"
            },
            {
                "error_type": "message_format_error",
                "description": "Invalid message format",
                "http_status": 400,
                "test_trigger": "invalid_message_format"
            },
            {
                "error_type": "rate_limit_error",
                "description": "Too many messages",
                "http_status": 429,
                "test_trigger": "message_rate_limit"
            },
            {
                "error_type": "subscription_error",
                "description": "Invalid channel subscription",
                "http_status": 400,
                "test_trigger": "invalid_channel"
            }
        ]


# Utility functions for testing
async def create_mock_connections(client: MockTestClient, count: int) -> List[str]:
    """Create multiple mock WebSocket connections"""
    connection_ids = []

    for i in range(count):
        connection_id = await client.connect(
            user_id=f"test_user_{i}",
            organization_id=f"test_org_{i}",
            client_info={"test_index": i}
        )

        if connection_id:
            connection_ids.append(connection_id)

    return connection_ids


async def wait_for_message(client: MockTestClient, connection_id: str,
                         message_type: str = None, timeout: float = 5.0) -> Optional[Dict]:
    """Wait for specific type of message"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        message = await client.receive_message(connection_id)

        if message:
            if message_type is None or message.get("type") == message_type:
                return message

        await asyncio.sleep(0.1)

    return None


def assert_message_structure(message: Dict[str, Any], expected_type: str = None):
    """Assert message has required structure"""
    assert isinstance(message, dict)
    assert "type" in message
    assert "timestamp" in message
    assert "id" in message
    assert "priority" in message
    assert "data" in message
    assert isinstance(message["data"], dict)

    if expected_type:
        assert message["type"] == expected_type