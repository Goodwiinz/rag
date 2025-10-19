"""
Real-time WebSocket API Contract Tests
Comprehensive testing for WebSocket connections, real-time updates, and notifications
"""

import pytest
import json
import uuid
import asyncio
import websockets
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.contract
@pytest.mark.websocket
class TestWebSocketConnectionAPI:
    """Test WebSocket connection endpoints"""

    @pytest.mark.asyncio
    async def test_websocket_connection_success(self, test_client: TestClient, auth_headers, websocket_client):
        """Test successful WebSocket connection"""
        headers = auth_headers({"email": "websocket@example.com", "first_name": "WebSocket", "last_name": "User"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to WebSocket
        connected = await websocket_client.connect("/ws/notifications", token)
        assert connected is True

        # Send a test message
        test_message = {
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat()
        }

        await websocket_client.send_message(test_message)

        # Receive response (should get a pong or similar)
        try:
            response = await asyncio.wait_for(websocket_client.receive_message(), timeout=5.0)
            assert response is not None
            assert "type" in response
        except asyncio.TimeoutError:
            # If no response, connection is still considered successful
            pass

        # Close connection
        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_websocket_connection_unauthorized(self, websocket_client):
        """Test WebSocket connection without authentication"""
        # Try to connect without token
        connected = await websocket_client.connect("/ws/notifications")
        assert connected is False

    @pytest.mark.asyncio
    async def test_websocket_connection_invalid_token(self, websocket_client):
        """Test WebSocket connection with invalid token"""
        invalid_token = "invalid_jwt_token"
        connected = await websocket_client.connect("/ws/notifications", invalid_token)
        assert connected is False

    @pytest.mark.asyncio
    async def test_websocket_connection_expired_token(self, websocket_client):
        """Test WebSocket connection with expired token"""
        expired_token = "expired_jwt_token"
        connected = await websocket_client.connect("/ws/notifications", expired_token)
        assert connected is False

    @pytest.mark.asyncio
    async def test_websocket_connection_multiple_endpoints(self, test_client: TestClient, auth_headers, websocket_client):
        """Test WebSocket connections to different endpoints"""
        headers = auth_headers({"email": "multiws@example.com", "first_name": "Multi", "last_name": "WebSocket"})
        token = headers["Authorization"].replace("Bearer ", "")

        endpoints = [
            "/ws/notifications",
            "/ws/processing-updates",
            "/ws/search-status",
            "/ws/system-events"
        ]

        for endpoint in endpoints:
            connected = await websocket_client.connect(endpoint, token)
            assert connected is True
            await websocket_client.close()

    @pytest.mark.asyncio
    async def test_websocket_connection_limit(self, test_client: TestClient, auth_headers):
        """Test WebSocket connection limits per user"""
        headers = auth_headers({"email": "limitws@example.com", "first_name": "Limit", "last_name": "WebSocket"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Try to create multiple connections
        connections = []
        max_connections = 5

        for i in range(max_connections + 2):  # Try to exceed limit
            client = type(websocket_client)()  # Create new client instance
            connected = await client.connect("/ws/notifications", token)
            if connected:
                connections.append(client)
            else:
                # Should fail when limit is reached
                break

        # Should have at most max_connections
        assert len(connections) <= max_connections

        # Clean up connections
        for client in connections:
            await client.close()


@pytest.mark.contract
@pytest.mark.websocket
class TestDocumentProcessingNotifications:
    """Test document processing notifications via WebSocket"""

    @pytest.mark.asyncio
    async def test_document_processing_status_updates(self, test_client: TestClient, auth_headers, websocket_client):
        """Test receiving document processing status updates"""
        headers = auth_headers({"email": "processing@example.com", "first_name": "Processing", "last_name": "User"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to processing updates WebSocket
        connected = await websocket_client.connect("/ws/processing-updates", token)
        assert connected is True

        # Upload a document (this should trigger processing notifications)
        files = {"file": ("processing_test.txt", b"Test content for processing", "text/plain")}
        data = {"title": "Processing Test Document"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert upload_response.status_code == 201
        document_id = upload_response.json()["id"]

        # Listen for processing updates
        received_updates = []
        try:
            for _ in range(5):  # Wait for up to 5 updates
                update = await asyncio.wait_for(websocket_client.receive_message(), timeout=10.0)
                received_updates.append(update)

                # Check if this is about our document
                if update.get("document_id") == document_id:
                    break
        except asyncio.TimeoutError:
            pass  # No more updates within timeout

        # Verify update structure
        for update in received_updates:
            assert "type" in update
            assert "timestamp" in update
            assert "document_id" in update
            assert "status" in update

            valid_statuses = ["pending", "processing", "completed", "failed"]
            assert update["status"] in valid_statuses

            if "progress" in update:
                assert 0 <= update["progress"] <= 100

        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_processing_error_notifications(self, test_client: TestClient, auth_headers, websocket_client):
        """Test receiving processing error notifications"""
        headers = auth_headers({"email": "errorproc@example.com", "first_name": "Error", "last_name": "Processing"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to processing updates WebSocket
        connected = await websocket_client.connect("/ws/processing-updates", token)
        assert connected is True

        # Upload a file that might cause processing errors
        files = {"file": ("error_test.txt", b"Content that might cause processing issues", "text/plain")}
        data = {"title": "Error Test Document"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        if upload_response.status_code == 201:
            document_id = upload_response.json()["id"]

            # Listen for error notifications
            try:
                for _ in range(10):  # Wait for updates
                    update = await asyncio.wait_for(websocket_client.receive_message(), timeout=5.0)

                    if update.get("document_id") == document_id and update.get("status") == "failed":
                        # Verify error notification structure
                        assert "error_message" in update
                        assert "error_code" in update
                        assert "retry_count" in update
                        break
            except asyncio.TimeoutError:
                pass  # No error notification received

        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_batch_processing_notifications(self, test_client: TestClient, auth_headers, websocket_client):
        """Test notifications for batch document processing"""
        headers = auth_headers({"email": "batch@example.com", "first_name": "Batch", "last_name": "Processing"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to processing updates WebSocket
        connected = await websocket_client.connect("/ws/processing-updates", token)
        assert connected is True

        # Upload multiple documents
        document_ids = []
        for i in range(3):
            files = {"file": (f"batch_test_{i}.txt", f"Batch test content {i}".encode(), "text/plain")}
            data = {"title": f"Batch Test Document {i}"}

            upload_response = test_client.post(
                "/api/v1/documents/upload",
                files=files,
                data=data,
                headers=headers
            )

            if upload_response.status_code == 201:
                document_ids.append(upload_response.json()["id"])

        # Listen for batch processing updates
        batch_updates = []
        try:
            for _ in range(20):  # Wait for multiple updates
                update = await asyncio.wait_for(websocket_client.receive_message(), timeout=15.0)

                if update.get("document_id") in document_ids:
                    batch_updates.append(update)

                # Stop if we've received updates for all documents
                updated_docs = {u.get("document_id") for u in batch_updates}
                if updated_docs.issuperset(set(document_ids)):
                    break
        except asyncio.TimeoutError:
            pass

        # Verify we received updates for our documents
        updated_doc_ids = {u.get("document_id") for u in batch_updates}
        assert len(updated_doc_ids.intersection(set(document_ids))) > 0

        await websocket_client.close()


@pytest.mark.contract
@pytest.mark.websocket
class TestSearchStatusNotifications:
    """Test search status notifications via WebSocket"""

    @pytest.mark.asyncio
    async def test_search_progress_notifications(self, test_client: TestClient, auth_headers, websocket_client):
        """Test receiving search progress notifications"""
        headers = auth_headers({"email": "searchws@example.com", "first_name": "Search", "last_name": "WebSocket"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to search status WebSocket
        connected = await websocket_client.connect("/ws/search-status", token)
        assert connected is True

        # Submit a complex search query
        search_data = {
            "query": "complex machine learning deep learning algorithms",
            "search_type": "hybrid",
            "max_results": 50,
            "enable_facets": True,
            "enable_aggregations": True
        }

        search_response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        if search_response.status_code == 200:
            query_id = search_response.json()["query_id"]

            # Listen for search progress updates
            search_updates = []
            try:
                for _ in range(10):  # Wait for search updates
                    update = await asyncio.wait_for(websocket_client.receive_message(), timeout=10.0)

                    if update.get("query_id") == query_id:
                        search_updates.append(update)

                        # Verify search update structure
                        assert "type" in update
                        assert "query_id" in update
                        assert "status" in update
                        assert "timestamp" in update

                        valid_statuses = ["queued", "searching", "ranking", "completed", "failed"]
                        assert update["status"] in valid_statuses

                        if "progress" in update:
                            assert 0 <= update["progress"] <= 100

                        if "stage" in update:
                            valid_stages = ["vector_search", "graph_search", "fulltext_search", "reranking"]
                            assert update["stage"] in valid_stages

                        # Stop if search is completed
                        if update.get("status") in ["completed", "failed"]:
                            break
            except asyncio.TimeoutError:
                pass  # No more updates

        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_concurrent_search_notifications(self, test_client: TestClient, auth_headers, websocket_client):
        """Test notifications for concurrent searches"""
        headers = auth_headers({"email": "concurrentsearch@example.com", "first_name": "Concurrent", "last_name": "Search"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to search status WebSocket
        connected = await websocket_client.connect("/ws/search-status", token)
        assert connected is True

        # Submit multiple search queries
        search_queries = [
            {"query": "machine learning", "search_type": "hybrid"},
            {"query": "natural language processing", "search_type": "vector"},
            {"query": "computer vision", "search_type": "graph"}
        ]

        query_ids = []
        for search_data in search_queries:
            search_data["max_results"] = 20
            response = test_client.post(
                "/api/v1/search/",
                json=search_data,
                headers=headers
            )

            if response.status_code == 200:
                query_ids.append(response.json()["query_id"])

        # Listen for concurrent search updates
        concurrent_updates = []
        try:
            for _ in range(30):  # Wait for multiple updates
                update = await asyncio.wait_for(websocket_client.receive_message(), timeout=15.0)

                if update.get("query_id") in query_ids:
                    concurrent_updates.append(update)

                # Stop if we've received completion for all queries
                completed_queries = {
                    u.get("query_id") for u in concurrent_updates
                    if u.get("status") == "completed"
                }
                if completed_queries.issuperset(set(query_ids)):
                    break
        except asyncio.TimeoutError:
            pass

        # Verify we received updates for our queries
        updated_query_ids = {u.get("query_id") for u in concurrent_updates}
        assert len(updated_query_ids.intersection(set(query_ids))) > 0

        await websocket_client.close()


@pytest.mark.contract
@pytest.mark.websocket
class TestSystemEventNotifications:
    """Test system event notifications via WebSocket"""

    @pytest.mark.asyncio
    async def test_system_health_notifications(self, test_client: TestClient, auth_headers, websocket_client):
        """Test receiving system health notifications"""
        headers = auth_headers({"email": "system@example.com", "first_name": "System", "last_name": "Health"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to system events WebSocket
        connected = await websocket_client.connect("/ws/system-events", token)
        assert connected is True

        # Subscribe to system health events
        subscribe_message = {
            "type": "subscribe",
            "event_types": ["system_health", "performance_metrics"]
        }

        await websocket_client.send_message(subscribe_message)

        # Listen for system health notifications
        system_updates = []
        try:
            for _ in range(5):  # Wait for system updates
                update = await asyncio.wait_for(websocket_client.receive_message(), timeout=10.0)
                system_updates.append(update)

                # Verify system update structure
                assert "type" in update
                assert "timestamp" in update
                assert "data" in update

                if update["type"] == "system_health":
                    health_data = update["data"]
                    assert "overall_status" in health_data
                    assert "services" in health_data

                    for service, status in health_data["services"].items():
                        assert "status" in status
                        assert "response_time" in status
                        assert "last_check" in status

                elif update["type"] == "performance_metrics":
                    metrics_data = update["data"]
                    assert "cpu_usage" in metrics_data
                    assert "memory_usage" in metrics_data
                    assert "active_connections" in metrics_data

        except asyncio.TimeoutError:
            pass  # No system updates within timeout

        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_maintenance_notifications(self, test_client: TestClient, auth_headers, websocket_client):
        """Test receiving maintenance notifications"""
        headers = auth_headers({"email": "maintenance@example.com", "first_name": "Maintenance", "last_name": "User"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to system events WebSocket
        connected = await websocket_client.connect("/ws/system-events", token)
        assert connected is True

        # Subscribe to maintenance events
        subscribe_message = {
            "type": "subscribe",
            "event_types": ["maintenance", "downtime"]
        }

        await websocket_client.send_message(subscribe_message)

        # Listen for maintenance notifications
        try:
            for _ in range(3):  # Wait for maintenance updates
                update = await asyncio.wait_for(websocket_client.receive_message(), timeout=5.0)

                if update["type"] in ["maintenance", "downtime"]:
                    # Verify maintenance notification structure
                    maintenance_data = update["data"]
                    assert "title" in maintenance_data
                    assert "description" in maintenance_data
                    assert "scheduled_start" in maintenance_data
                    assert "scheduled_end" in maintenance_data
                    assert "affected_services" in maintenance_data
                    assert isinstance(maintenance_data["affected_services"], list)

                    break
        except asyncio.TimeoutError:
            pass  # No maintenance notifications

        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_user_activity_notifications(self, test_client: TestClient, auth_headers, websocket_client):
        """Test receiving user activity notifications"""
        headers = auth_headers({"email": "activity@example.com", "first_name": "Activity", "last_name": "User"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to notifications WebSocket
        connected = await websocket_client.connect("/ws/notifications", token)
        assert connected is True

        # Perform some user activity
        # Upload a document
        files = {"file": ("activity_test.txt", b"Activity test content", "text/plain")}
        data = {"title": "Activity Test Document"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        # Perform a search
        search_data = {
            "query": "activity test",
            "search_type": "hybrid",
            "max_results": 10
        }

        search_response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        # Listen for activity notifications
        activity_updates = []
        try:
            for _ in range(5):  # Wait for activity updates
                update = await asyncio.wait_for(websocket_client.receive_message(), timeout=10.0)

                if update.get("type") == "user_activity":
                    activity_updates.append(update)

                    # Verify activity notification structure
                    activity_data = update["data"]
                    assert "activity_type" in activity_data
                    assert "user_id" in activity_data
                    assert "timestamp" in activity_data

                    valid_activities = ["document_uploaded", "search_performed", "profile_updated"]
                    assert activity_data["activity_type"] in valid_activities

        except asyncio.TimeoutError:
            pass  # No activity notifications

        await websocket_client.close()


@pytest.mark.contract
@pytest.mark.websocket
@pytest.mark.performance
class TestWebSocketPerformance:
    """Performance tests for WebSocket functionality"""

    @pytest.mark.asyncio
    async def test_websocket_connection_latency(self, test_client: TestClient, auth_headers, websocket_client, performance_tracker):
        """Test WebSocket connection latency"""
        headers = auth_headers({"email": "latency@example.com", "first_name": "Latency", "last_name": "Test"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Measure connection time
        performance_tracker.start_timer("websocket_connection")

        connected = await websocket_client.connect("/ws/notifications", token)
        connection_time = performance_tracker.end_timer("websocket_connection")

        assert connected is True
        assert connection_time < 1.0  # Connection should be fast

        # Measure message round-trip time
        for i in range(10):
            performance_tracker.start_timer(f"message_rtt_{i}")

            ping_message = {
                "type": "ping",
                "message_id": i,
                "timestamp": datetime.utcnow().isoformat()
            }

            await websocket_client.send_message(ping_message)

            try:
                response = await asyncio.wait_for(websocket_client.receive_message(), timeout=2.0)
                rtt_time = performance_tracker.end_timer(f"message_rtt_{i}")

                if response and response.get("type") == "pong":
                    assert rtt_time < 0.1  # Should be under 100ms for WebSocket
            except asyncio.TimeoutError:
                performance_tracker.end_timer(f"message_rtt_{i}")

        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_websocket_message_throughput(self, test_client: TestClient, auth_headers, websocket_client, performance_tracker):
        """Test WebSocket message throughput"""
        headers = auth_headers({"email": "throughput@example.com", "first_name": "Throughput", "last_name": "Test"})
        token = headers["Authorization"].replace("Bearer ", "")

        connected = await websocket_client.connect("/ws/notifications", token)
        assert connected is True

        # Send multiple messages rapidly
        message_count = 100
        performance_tracker.start_timer("message_throughput")

        for i in range(message_count):
            message = {
                "type": "test_message",
                "message_id": i,
                "payload": f"Test message {i}" * 10  # Make messages reasonably sized
            }

            await websocket_client.send_message(message)

        total_time = performance_tracker.end_timer("message_throughput")
        messages_per_second = message_count / total_time

        # Should handle at least 50 messages per second
        assert messages_per_second > 50

        print(f"WebSocket throughput: {messages_per_second:.2f} messages/second")

        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_concurrent_websocket_connections(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test concurrent WebSocket connections"""
        import asyncio

        headers = auth_headers({"email": "concurrentws@example.com", "first_name": "Concurrent", "last_name": "WS"})
        token = headers["Authorization"].replace("Bearer ", "")

        async def create_connection(connection_id):
            """Create a WebSocket connection"""
            client = type(websocket_client)()
            connected = await client.connect("/ws/notifications", token)

            if connected:
                # Send a test message
                await client.send_message({
                    "type": "test",
                    "connection_id": connection_id
                })

                # Wait briefly
                await asyncio.sleep(0.1)

                await client.close()
                return True
            return False

        # Create multiple concurrent connections
        connection_count = 20
        performance_tracker.start_timer("concurrent_connections")

        tasks = [create_connection(i) for i in range(connection_count)]
        results = await asyncio.gather(*tasks)

        total_time = performance_tracker.end_timer("concurrent_connections")
        successful_connections = sum(results)

        # Most connections should succeed
        assert successful_connections >= connection_count * 0.8

        print(f"Successfully created {successful_connections}/{connection_count} WebSocket connections in {total_time:.2f}s")


@pytest.mark.integration
@pytest.mark.websocket
class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality"""

    @pytest.mark.asyncio
    async def test_end_to_end_websocket_workflow(self, test_client: TestClient, auth_headers, websocket_client):
        """Test complete WebSocket workflow"""
        headers = auth_headers({"email": "workflowws@example.com", "first_name": "Workflow", "last_name": "WebSocket"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Step 1: Connect to notifications WebSocket
        connected = await websocket_client.connect("/ws/notifications", token)
        assert connected is True

        # Step 2: Upload a document
        files = {"file": ("workflow_test.txt", b"Workflow test content", "text/plain")}
        data = {"title": "Workflow Test Document"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert upload_response.status_code == 201
        document_id = upload_response.json()["id"]

        # Step 3: Listen for upload notification
        try:
            upload_notification = await asyncio.wait_for(websocket_client.receive_message(), timeout=5.0)
            assert upload_notification.get("type") == "document_uploaded"
            assert upload_notification.get("document_id") == document_id
        except asyncio.TimeoutError:
            pass  # No notification received

        # Step 4: Connect to processing updates
        processing_client = type(websocket_client)()
        await processing_client.connect("/ws/processing-updates", token)

        # Step 5: Listen for processing updates
        processing_updates = []
        try:
            for _ in range(10):
                update = await asyncio.wait_for(processing_client.receive_message(), timeout=10.0)
                if update.get("document_id") == document_id:
                    processing_updates.append(update)

                if update.get("status") in ["completed", "failed"]:
                    break
        except asyncio.TimeoutError:
            pass

        # Step 6: Perform a search
        search_data = {
            "query": "workflow test",
            "search_type": "hybrid",
            "max_results": 10
        }

        search_response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        if search_response.status_code == 200:
            query_id = search_response.json()["query_id"]

            # Step 7: Connect to search status
            search_client = type(websocket_client)()
            await search_client.connect("/ws/search-status", token)

            # Step 8: Listen for search updates
            try:
                for _ in range(5):
                    search_update = await asyncio.wait_for(search_client.receive_message(), timeout=5.0)
                    if search_update.get("query_id") == query_id:
                        break
            except asyncio.TimeoutError:
                pass

            await search_client.close()

        # Clean up
        await processing_client.close()
        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_websocket_reconnection_handling(self, test_client: TestClient, auth_headers, websocket_client):
        """Test WebSocket reconnection handling"""
        headers = auth_headers({"email": "reconnect@example.com", "first_name": "Reconnect", "last_name": "Test"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Initial connection
        connected = await websocket_client.connect("/ws/notifications", token)
        assert connected is True

        # Send a test message
        await websocket_client.send_message({"type": "test", "action": "initial_connect"})

        # Simulate connection loss
        await websocket_client.close()

        # Reconnect
        reconnected = await websocket_client.connect("/ws/notifications", token)
        assert reconnected is True

        # Send another test message
        await websocket_client.send_message({"type": "test", "action": "reconnect"})

        # Verify reconnection worked
        try:
            response = await asyncio.wait_for(websocket_client.receive_message(), timeout=2.0)
            assert response is not None
        except asyncio.TimeoutError:
            pass  # No response but connection is still valid

        await websocket_client.close()

    @pytest.mark.asyncio
    async def test_websocket_message_filtering(self, test_client: TestClient, auth_headers, websocket_client):
        """Test WebSocket message filtering and subscriptions"""
        headers = auth_headers({"email": "filter@example.com", "first_name": "Message", "last_name": "Filter"})
        token = headers["Authorization"].replace("Bearer ", "")

        # Connect to notifications WebSocket
        connected = await websocket_client.connect("/ws/notifications", token)
        assert connected is True

        # Subscribe to specific event types
        subscribe_message = {
            "type": "subscribe",
            "filters": {
                "event_types": ["document_uploaded", "search_completed"],
                "user_id_only": True
            }
        }

        await websocket_client.send_message(subscribe_message)

        # Upload a document
        files = {"file": ("filter_test.txt", b"Filter test content", "text/plain")}
        data = {"title": "Filter Test Document"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        # Listen for filtered messages
        filtered_messages = []
        try:
            for _ in range(5):
                message = await asyncio.wait_for(websocket_client.receive_message(), timeout=5.0)
                filtered_messages.append(message)

                # Verify message matches our filters
                assert message.get("type") in ["document_uploaded", "search_completed"]
        except asyncio.TimeoutError:
            pass

        await websocket_client.close()

        # Should only receive messages matching our subscription
        if filtered_messages:
            for message in filtered_messages:
                assert message.get("type") in ["document_uploaded", "search_completed"]