"""
Comprehensive test suite for WebSocket services
"""

import asyncio
import json
import pytest
import uuid
from datetime import datetime, timezone as dt_timezone
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from fastapi.testclient import TestClient
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.main import app
from src.services.websocket_manager import (
    EnhancedConnectionManager, WebSocketMessage, MessageType, Priority, ConnectionInfo
)
from src.services.status_update_service import (
    StatusUpdateService, Channel, UpdateFrequency, ProcessingProgress, SystemStatus
)
from src.services.processing_integration import (
    ProcessingIntegrationService, DocumentProcessingStages, ProcessingStep
)
from src.services.websocket_error_handler import (
    WebSocketErrorHandler, ErrorSeverity, RecoveryStrategy, ErrorContext
)
from src.services.websocket_service_initializer import WebSocketServiceInitializer
from src.models.document import Document, ProcessingStatus, DocumentType
from src.models.processing import ProcessingJob, JobStatus, JobType
from src.models.websocket_status import WebSocketConnection, ConnectionStatus
from src.core.config import settings

# Test fixtures
@pytest.fixture
async def test_client():
    """Create test client"""
    return TestClient(app)

@pytest.fixture
async def mock_websocket():
    """Create mock WebSocket"""
    websocket = Mock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.receive_text = AsyncMock()
    websocket.client = Mock(host="127.0.0.1")
    return websocket

@pytest.fixture
async def mock_user():
    """Create mock user"""
    return {
        "id": str(uuid.uuid4()),
        "email": "test@example.com",
        "is_superuser": False,
        "organization_id": str(uuid.uuid4())
    }

@pytest.fixture
async def mock_document():
    """Create mock document"""
    return Document(
        id=uuid.uuid4(),
        title="Test Document",
        filename="test.pdf",
        file_path="/uploads/test.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        document_type=DocumentType.PDF,
        processing_status=ProcessingStatus.PENDING,
        organization_id=uuid.uuid4(),
        uploaded_by_user_id=uuid.uuid4()
    )

@pytest.fixture
async def mock_job():
    """Create mock processing job"""
    return ProcessingJob(
        id=uuid.uuid4(),
        job_type=JobType.DOCUMENT_INGESTION,
        status=JobStatus.PENDING,
        organization_id=uuid.uuid4(),
        created_by_user_id=uuid.uuid4()
   )

class TestEnhancedConnectionManager:
    """Test suite for EnhancedConnectionManager"""

    @pytest.mark.asyncio
    async def test_connection_manager_initialization(self):
        """Test connection manager initialization"""
        manager = EnhancedConnectionManager()
        await manager.initialize()

        # Check initial state
        assert len(manager.active_connections) == 0
        assert len(manager.user_connections) == 0
        assert len(manager.organization_connections) == 0

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_websocket_authentication_success(self, mock_websocket, mock_user):
        """Test successful WebSocket authentication"""
        manager = EnhancedConnectionManager()

        # Mock JWT token
        with patch('jose.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": mock_user["id"],
                "organization_id": mock_user["organization_id"]
            }

            with patch('src.core.config.settings.JWT_SECRET_KEY', "test-secret"):
                auth_result = await manager.authenticate_websocket(
                    mock_websocket,
                    "valid-jwt-token"
                )

                assert auth_result is not None
                assert auth_result["user_id"] == mock_user["id"]
                assert auth_result["organization_id"] == mock_user["organization_id"]

    @pytest.mark.asyncio
    async def test_websocket_authentication_failure(self, mock_websocket):
        """Test WebSocket authentication failure"""
        manager = EnhancedConnectionManager()

        with patch('jose.jwt.decode', side_effect=Exception("Invalid token")):
            auth_result = await manager.authenticate_websocket(
                mock_websocket,
                "invalid-jwt-token"
            )

            assert auth_result is None
            mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, mock_websocket, mock_user):
        """Test WebSocket connection and disconnection"""
        manager = EnhancedConnectionManager()
        await manager.initialize()

        # Mock authentication
        with patch.object(manager, 'authenticate_websocket') as mock_auth:
            mock_auth.return_value = {
                "user_id": mock_user["id"],
                "organization_id": mock_user["organization_id"],
                "token_payload": {}
            }

            # Connect
            connection_id = await manager.connect(mock_websocket, "test-token")
            assert connection_id is not None
            assert connection_id in manager.active_connections

            # Check connection info
            conn_info = manager.active_connections[connection_id]
            assert conn_info.user_id == mock_user["id"]
            assert conn_info.organization_id == mock_user["organization_id"]

            # Disconnect
            await manager.disconnect(connection_id, "Test disconnect")
            assert connection_id not in manager.active_connections

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_channel_subscription(self, mock_websocket, mock_user):
        """Test channel subscription functionality"""
        manager = EnhancedConnectionManager()
        await manager.initialize()

        # Mock connection
        connection_id = str(uuid.uuid4())
        conn_info = ConnectionInfo(
            user_id=mock_user["id"],
            organization_id=mock_user["organization_id"],
            connection_id=connection_id,
            websocket=mock_websocket,
            connected_at=datetime.now(dt_timezone.utc),
            last_heartbeat=datetime.now(dt_timezone.utc),
            subscribed_channels=set()
        )
        manager.active_connections[connection_id] = conn_info

        # Subscribe to channel
        result = await manager.subscribe_to_channel(connection_id, "test_channel")
        assert result is True
        assert "test_channel" in conn_info.subscribed_channels

        # Unsubscribe from channel
        result = await manager.unsubscribe_from_channel(connection_id, "test_channel")
        assert result is True
        assert "test_channel" not in conn_info.subscribed_channels

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_message_broadcasting(self, mock_websocket, mock_user):
        """Test message broadcasting to channels"""
        manager = EnhancedConnectionManager()
        await manager.initialize()

        # Mock connection
        connection_id = str(uuid.uuid4())
        conn_info = ConnectionInfo(
            user_id=mock_user["id"],
            organization_id=mock_user["organization_id"],
            connection_id=connection_id,
            websocket=mock_websocket,
            connected_at=datetime.now(dt_timezone.utc),
            last_heartbeat=datetime.now(dt_timezone.utc),
            subscribed_channels={"test_channel"}
        )
        manager.active_connections[connection_id] = conn_info
        manager.channel_subscribers["test_channel"] = {connection_id}

        # Create test message
        message = WebSocketMessage(
            type=MessageType.SYSTEM_NOTIFICATION,
            data={"test": "message"},
            timestamp=datetime.now(dt_timezone.utc),
            target_channels=["test_channel"]
        )

        # Broadcast to channel
        await manager.broadcast_to_channel("test_channel", message)

        # Verify message was sent
        mock_websocket.send_json.assert_called_once()

        await manager.shutdown()

class TestStatusUpdateService:
    """Test suite for StatusUpdateService"""

    @pytest.mark.asyncio
    async def test_status_update_service_initialization(self):
        """Test status update service initialization"""
        service = StatusUpdateService()
        await service.initialize()

        assert service._update_queue is not None
        assert service._batch_updates is not None

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_document_update_broadcast(self, mock_document):
        """Test document status update broadcasting"""
        service = StatusUpdateService()
        await service.initialize()

        with patch('src.services.websocket_manager.connection_manager.broadcast_to_user') as mock_broadcast:
            await service.broadcast_document_update(
                document_id=str(mock_document.id),
                status=ProcessingStatus.PROCESSING,
                progress=ProcessingProgress(
                    document_id=str(mock_document.id),
                    current_step="text_extraction",
                    total_steps=5,
                    completed_steps=1,
                    progress_percentage=20.0,
                    estimated_remaining_seconds=80.0,
                    current_operation="Extracting text from PDF",
                    step_details={"pages_processed": 1},
                    warnings=[],
                    errors=[]
                )
            )

            mock_broadcast.assert_called_once()

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_job_update_broadcast(self, mock_job):
        """Test job status update broadcasting"""
        service = StatusUpdateService()
        await service.initialize()

        with patch('src.services.websocket_manager.connection_manager.broadcast_to_user') as mock_broadcast:
            await service.broadcast_job_update(
                job_id=str(mock_job.id),
                status=JobStatus.RUNNING,
                progress=50.0,
                current_step="embedding_generation"
            )

            mock_broadcast.assert_called_once()

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_system_notification_broadcast(self):
        """Test system notification broadcasting"""
        service = StatusUpdateService()
        await service.initialize()

        with patch('src.services.websocket_manager.connection_manager.broadcast_to_channel') as mock_broadcast:
            await service.broadcast_system_notification(
                title="Test Notification",
                message="This is a test notification",
                notification_type="info"
            )

            mock_broadcast.assert_called_once()

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_system_status_retrieval(self):
        """Test system status retrieval"""
        service = StatusUpdateService()
        await service.initialize()

        status = await service.get_system_status()
        assert isinstance(status, SystemStatus)
        assert status.active_jobs >= 0
        assert status.queued_jobs >= 0

        await service.shutdown()

class TestProcessingIntegration:
    """Test suite for ProcessingIntegrationService"""

    @pytest.mark.asyncio
    async def test_processing_context_manager(self, mock_document):
        """Test processing context manager"""
        service = ProcessingIntegrationService()
        await service.initialize()

        with patch.object(service, '_update_document_status') as mock_update, \
             patch.object(service, '_broadcast_processing_start') as mock_start:

            async with service.processing_context(
                document_id=str(mock_document.id),
                processing_type="document_processing"
            ) as context:

                assert context["document_id"] == str(mock_document.id)
                assert context["document_type"] == mock_document.document_type
                assert len(context["processing_steps"]) > 0

            mock_update.assert_called()
            mock_start.assert_called()

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_step_progress_update(self, mock_document):
        """Test step progress update"""
        service = ProcessingIntegrationService()
        await service.initialize()

        job_id = str(uuid.uuid4())
        service._active_jobs[job_id] = {
            "document_id": str(mock_document.id),
            "processing_steps": DocumentProcessingStages.get_all_steps(mock_document.document_type),
            "total_weight": 100.0,
            "completed_weight": 0.0,
            "current_step_index": 0,
            "start_time": datetime.now(dt_timezone.utc),
            "step_times": {},
            "errors": [],
            "warnings": []
        }

        with patch.object(service, '_broadcast_processing_progress') as mock_broadcast:
            await service.update_step_progress(
                job_id=job_id,
                step_name="file_validation",
                progress_percentage=100.0,
                details={"validation_result": "passed"}
            )

            mock_broadcast.assert_called_once()

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_processing_completion(self, mock_document):
        """Test processing completion"""
        service = ProcessingIntegrationService()
        await service.initialize()

        with patch.object(service, '_update_document_status') as mock_update, \
             patch.object(service, '_broadcast_processing_completion') as mock_broadcast:

            await service.complete_processing(
                document_id=str(mock_document.id),
                result={"processed_pages": 10, "entities_extracted": 25}
            )

            mock_update.assert_called_once_with(str(mock_document.id), ProcessingStatus.COMPLETED)
            mock_broadcast.assert_called_once()

        await service.shutdown()

class TestWebSocketErrorHandler:
    """Test suite for WebSocketErrorHandler"""

    @pytest.mark.asyncio
    async def test_error_handler_initialization(self):
        """Test error handler initialization"""
        handler = WebSocketErrorHandler()
        await handler.initialize()

        assert len(handler._error_handlers) > 0
        assert handler._circuit_breakers is not None

        await handler.shutdown()

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, mock_websocket):
        """Test WebSocket error handling"""
        handler = WebSocketErrorHandler()
        await handler.initialize()

        test_error = Exception("Test error")
        connection_id = str(uuid.uuid4())

        with patch.object(handler, '_send_error_to_client') as mock_send, \
             patch.object(handler, '_log_error') as mock_log:

            await handler.handle_websocket_error(
                websocket=mock_websocket,
                error=test_error,
                connection_id=connection_id
            )

            mock_log.assert_called_once()
            assert len(handler._error_history) == 1

        await handler.shutdown()

    @pytest.mark.asyncio
    async def test_reconnection_scheduling(self):
        """Test reconnection scheduling"""
        handler = WebSocketErrorHandler()
        await handler.initialize()

        connection_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        organization_id = str(uuid.uuid4())

        with patch.object(handler._reconnection_queue, 'put') as mock_put:
            await handler.schedule_reconnection(
                connection_id=connection_id,
                user_id=user_id,
                organization_id=organization_id,
                delay_seconds=5.0
            )

            mock_put.assert_called_once()

        await handler.shutdown()

    def test_error_severity_determination(self):
        """Test error severity determination"""
        handler = WebSocketErrorHandler()

        # Test critical error
        critical_error = Exception("Authentication failed")
        severity = handler._determine_error_severity(critical_error)
        assert severity == ErrorSeverity.CRITICAL

        # Test connection error
        conn_error = Exception("Connection lost")
        severity = handler._determine_error_severity(conn_error)
        assert severity == ErrorSeverity.HIGH

        # Test validation error
        validation_error = Exception("Invalid data format")
        severity = handler._determine_error_severity(validation_error)
        assert severity == ErrorSeverity.MEDIUM

    def test_recovery_strategy_determination(self):
        """Test recovery strategy determination"""
        handler = WebSocketErrorHandler()

        # Test connection error
        conn_error = Exception("WebSocket connection failed")
        strategy = handler._determine_recovery_strategy(conn_error)
        assert strategy == RecoveryStrategy.RECONNECT

        # Test timeout error
        timeout_error = Exception("Request timeout")
        strategy = handler._determine_recovery_strategy(timeout_error)
        assert strategy == RecoveryStrategy.RETRY

        # Test authentication error
        auth_error = Exception("Invalid credentials")
        strategy = handler._determine_recovery_strategy(auth_error)
        assert strategy == RecoveryStrategy.FAILFAST

class TestWebSocketAPI:
    """Test suite for WebSocket API endpoints"""

    def test_websocket_status_endpoint(self, test_client):
        """Test WebSocket status endpoint"""
        response = test_client.get("/api/v2/ws/status")
        assert response.status_code == 200

        data = response.json()
        assert "websocket_service" in data
        assert "connections" in data
        assert "channels" in data
        assert "performance" in data

    def test_websocket_health_endpoint(self, test_client):
        """Test WebSocket health endpoint"""
        response = test_client.get("/api/v2/ws/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "checks" in data

    def test_websocket_channels_endpoint(self, test_client):
        """Test WebSocket channels endpoint"""
        response = test_client.get("/api/v2/ws/channels")
        assert response.status_code == 200

        data = response.json()
        assert "channels" in data
        assert isinstance(data["channels"], list)

        # Check expected channels are present
        channel_names = [ch["name"] for ch in data["channels"]]
        expected_channels = [c.value for c in Channel]
        for expected_channel in expected_channels:
            assert expected_channel in channel_names

# Performance tests
@pytest.mark.asyncio
async def test_concurrent_connections():
    """Test handling of concurrent WebSocket connections"""
    manager = EnhancedConnectionManager()
    await manager.initialize()

    connection_ids = []
    mock_websockets = []

    # Create multiple mock connections
    for i in range(10):
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_websockets.append(mock_ws)

        connection_id = str(uuid.uuid4())
        conn_info = ConnectionInfo(
            user_id=str(uuid.uuid4()),
            organization_id=str(uuid.uuid4()),
            connection_id=connection_id,
            websocket=mock_ws,
            connected_at=datetime.now(dt_timezone.utc),
            last_heartbeat=datetime.now(dt_timezone.utc),
            subscribed_channels=set()
        )
        manager.active_connections[connection_id] = conn_info
        connection_ids.append(connection_id)

    # Test concurrent message broadcasting
    message = WebSocketMessage(
        type=MessageType.SYSTEM_NOTIFICATION,
        data={"test": "concurrent"},
        timestamp=datetime.now(dt_timezone.utc),
        target_channels=["test_channel"]
    )

    # Broadcast to all connections
    tasks = []
    for connection_id in connection_ids:
        task = asyncio.create_task(
            manager.send_message_to_connection(connection_id, message)
        )
        tasks.append(task)

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify all messages were sent
    assert all(result is True for result in results if not isinstance(result, Exception))

    await manager.shutdown()

# Load testing
@pytest.mark.asyncio
async def test_message_queue_performance():
    """Test message queue performance under load"""
    service = StatusUpdateService()
    await service.initialize()

    # Simulate high message volume
    message_count = 100
    tasks = []

    for i in range(message_count):
        task = asyncio.create_task(
            service.broadcast_system_notification(
                title=f"Test Message {i}",
                message=f"This is test message {i}",
                notification_type="info"
            )
        )
        tasks.append(task)

    # Measure performance
    start_time = datetime.now(dt_timezone.utc)
    await asyncio.gather(*tasks, return_exceptions=True)
    end_time = datetime.now(dt_timezone.utc)

    duration = (end_time - start_time).total_seconds()
    messages_per_second = message_count / duration

    # Assert performance meets expectations
    assert messages_per_second > 10  # Should handle at least 10 messages/second

    await service.shutdown()

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])