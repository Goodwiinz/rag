"""
Test Helper Utilities for Multimodal Enterprise RAG System
Provides common testing utilities and helper functions
"""

import json
import time
import uuid
import asyncio
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Callable, Union
from functools import wraps
from contextlib import contextmanager
from dataclasses import asdict
import requests
from fastapi.testclient import TestClient
from httpx import AsyncClient


class APITestHelper:
    """Helper class for API testing operations"""

    def __init__(self, client: Union[TestClient, AsyncClient], base_url: str = "http://localhost:8000"):
        self.client = client
        self.base_url = base_url
        self.api_prefix = "/api/v1"

    def get_headers(self, token: str) -> Dict[str, str]:
        """Create authenticated headers"""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def assert_successful_response(self, response, expected_status: int = 200):
        """Assert response is successful"""
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"
        return response

    def assert_error_response(self, response, expected_status: int = 400):
        """Assert response is an error"""
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"
        response_data = response.json()
        assert "error" in response_data, "Error response should contain 'error' field"
        return response_data

    def parse_response(self, response) -> Dict[str, Any]:
        """Parse JSON response safely"""
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"raw_response": response.text}

    def measure_response_time(self, func: Callable, *args, **kwargs) -> tuple:
        """Measure response time of a function call"""
        start_time = time.time()
        response = func(*args, **kwargs)
        end_time = time.time()
        response_time = end_time - start_time
        return response, response_time

    def retry_on_failure(self, func: Callable, max_retries: int = 3, delay: float = 1.0, *args, **kwargs):
        """Retry a function call on failure"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise last_exception

    async def async_retry_on_failure(self, func: Callable, max_retries: int = 3, delay: float = 1.0, *args, **kwargs):
        """Async version of retry_on_failure"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(delay * (2 ** attempt))
                else:
                    raise last_exception


class AuthenticationHelper:
    """Helper class for authentication testing"""

    @staticmethod
    def register_user(client: TestClient, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new user and return tokens"""
        response = client.post("/api/v1/auth/register", json=user_data)
        if response.status_code == 201:
            return response.json()
        raise Exception(f"Registration failed: {response.status_code} - {response.text}")

    @staticmethod
    def login_user(client: TestClient, email: str, password: str) -> Dict[str, Any]:
        """Login user and return tokens"""
        login_data = {"email": email, "password": password}
        response = client.post("/api/v1/auth/login", json=login_data)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Login failed: {response.status_code} - {response.text}")

    @staticmethod
    def create_test_user_session(client: TestClient) -> tuple:
        """Create a complete test user session"""
        user_data = {
            "email": f"test_{uuid.uuid4()}@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
            "organization_name": "Test Organization"
        }

        # Register user
        register_response = AuthenticationHelper.register_user(client, user_data)
        token = register_response["access_token"]
        user_id = register_response["user"]["id"]

        headers = {"Authorization": f"Bearer {token}"}
        return user_data, token, user_id, headers

    @staticmethod
    def refresh_token(client: TestClient, refresh_token: str) -> Dict[str, Any]:
        """Refresh authentication token"""
        refresh_data = {"refresh_token": refresh_token}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")

    @staticmethod
    def create_expired_token() -> str:
        """Create an expired JWT token for testing"""
        # This would require access to JWT secret - simplified for now
        return "expired_mock_token"


class DocumentHelper:
    """Helper class for document testing operations"""

    @staticmethod
    def upload_document(client: TestClient, file_data: tuple, document_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Upload a document and return response"""
        filename, file_content, mime_type = file_data
        files = {"file": (filename, file_content, mime_type)}

        response = client.post(
            "/api/v1/documents/upload",
            files=files,
            data=document_data,
            headers=headers
        )

        if response.status_code == 201:
            return response.json()
        raise Exception(f"Document upload failed: {response.status_code} - {response.text}")

    @staticmethod
    def wait_for_processing(client: TestClient, document_id: str, headers: Dict[str, str], max_wait: int = 30, poll_interval: int = 2) -> Dict[str, Any]:
        """Wait for document processing to complete"""
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = client.get(f"/api/v1/documents/{document_id}/status", headers=headers)
            if response.status_code == 200:
                status_data = response.json()
                if status_data["status"] in ["completed", "failed"]:
                    return status_data

            time.sleep(poll_interval)

        raise TimeoutError(f"Document processing did not complete within {max_wait} seconds")

    @staticmethod
    def create_test_file_content(content_type: str = "text") -> tuple:
        """Create test file content for upload"""
        from tests.fixtures.test_data_fixtures import FileFixture

        if content_type == "text":
            return FileFixture.create_text_file()
        elif content_type == "pdf":
            return FileFixture.create_pdf_file()
        elif content_type == "image":
            return FileFixture.create_image_file()
        elif content_type == "audio":
            return FileFixture.create_audio_file()
        elif content_type == "video":
            return FileFixture.create_video_file()
        else:
            return FileFixture.create_text_file()

    @staticmethod
    def cleanup_documents(client: TestClient, document_ids: List[str], headers: Dict[str, str]):
        """Clean up test documents"""
        for doc_id in document_ids:
            try:
                client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
            except Exception:
                pass  # Ignore cleanup errors


class SearchHelper:
    """Helper class for search testing operations"""

    @staticmethod
    def perform_search(client: TestClient, search_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Perform a search query"""
        response = client.post("/api/v1/search/", json=search_data, headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Search failed: {response.status_code} - {response.text}")

    @staticmethod
    def perform_advanced_search(client: TestClient, search_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Perform an advanced search query"""
        response = client.post("/api/v1/search/advanced", json=search_data, headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Advanced search failed: {response.status_code} - {response.text}")

    @staticmethod
    def get_search_results(client: TestClient, query_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Get detailed search results"""
        response = client.get(f"/api/v1/search/{query_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Get search results failed: {response.status_code} - {response.text}")

    @staticmethod
    def get_search_history(client: TestClient, headers: Dict[str, str]) -> Dict[str, Any]:
        """Get search history"""
        response = client.get("/api/v1/search/history", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Get search history failed: {response.status_code} - {response.text}")

    @staticmethod
    def create_search_query(query: str = None, search_type: str = "hybrid", max_results: int = 10) -> Dict[str, Any]:
        """Create a search query data structure"""
        from tests.fixtures.test_data_fixtures import SearchQueryFixture

        if query is None:
            search_fixture = SearchQueryFixture.create(search_type=search_type, max_results=max_results)
            return {
                "query": search_fixture.query,
                "search_type": search_fixture.search_type,
                "max_results": search_fixture.max_results,
                "filters": search_fixture.filters
            }
        else:
            return {
                "query": query,
                "search_type": search_type,
                "max_results": max_results,
                "filters": {}
            }


class KnowledgeGraphHelper:
    """Helper class for knowledge graph testing operations"""

    @staticmethod
    def search_entities(client: TestClient, search_params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Search for entities in knowledge graph"""
        response = client.get("/api/v1/graph/entities", params=search_params, headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Entity search failed: {response.status_code} - {response.text}")

    @staticmethod
    def get_entity_details(client: TestClient, entity_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Get detailed entity information"""
        response = client.get(f"/api/v1/graph/entities/{entity_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Get entity details failed: {response.status_code} - {response.text}")

    @staticmethod
    def search_relationships(client: TestClient, search_params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Search for relationships in knowledge graph"""
        response = client.get("/api/v1/graph/relationships", params=search_params, headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Relationship search failed: {response.status_code} - {response.text}")

    @staticmethod
    def get_graph_visualization(client: TestClient, viz_params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Get graph visualization data"""
        response = client.get("/api/v1/graph/visualize", params=viz_params, headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Graph visualization failed: {response.status_code} - {response.text}")

    @staticmethod
    def get_graph_statistics(client: TestClient, headers: Dict[str, str]) -> Dict[str, Any]:
        """Get graph statistics"""
        response = client.get("/api/v1/graph/statistics", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Get graph statistics failed: {response.status_code} - {response.text}")


class PerformanceTestHelper:
    """Helper class for performance testing"""

    def __init__(self):
        self.metrics = {}
        self.start_times = {}

    def start_timer(self, operation_name: str):
        """Start timing an operation"""
        self.start_times[operation_name] = time.time()

    def end_timer(self, operation_name: str) -> float:
        """End timing an operation and return duration"""
        if operation_name in self.start_times:
            duration = time.time() - self.start_times[operation_name]
            if operation_name not in self.metrics:
                self.metrics[operation_name] = []
            self.metrics[operation_name].append(duration)
            return duration
        return 0.0

    def get_stats(self, operation_name: str) -> Dict[str, float]:
        """Get performance statistics for an operation"""
        if operation_name in self.metrics and self.metrics[operation_name]:
            times = self.metrics[operation_name]
            return {
                "count": len(times),
                "total": sum(times),
                "average": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
                "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
                "p99": sorted(times)[int(len(times) * 0.99)] if len(times) > 100 else max(times)
            }
        return {}

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for all operations"""
        return {op: self.get_stats(op) for op in self.metrics.keys()}

    def check_threshold(self, operation_name: str, threshold: float, percentile: str = "p95") -> bool:
        """Check if operation meets performance threshold"""
        stats = self.get_stats(operation_name)
        return stats.get(percentile, 0) <= threshold

    def reset_metrics(self):
        """Reset all performance metrics"""
        self.metrics.clear()
        self.start_times.clear()


class DatabaseTestHelper:
    """Helper class for database testing operations"""

    @staticmethod
    def create_test_database_url() -> str:
        """Create a test database URL"""
        return "sqlite:///:memory:"

    @staticmethod
    def cleanup_test_data(table_names: List[str], db_session):
        """Clean up test data from specified tables"""
        for table_name in table_names:
            try:
                db_session.execute(f"DELETE FROM {table_name}")
                db_session.commit()
            except Exception as e:
                print(f"Failed to clean up table {table_name}: {e}")
                db_session.rollback()

    @staticmethod
    def create_test_fixtures(db_session, fixture_classes: List[type], counts: List[int]):
        """Create test fixtures in database"""
        fixtures = []
        for fixture_class, count in zip(fixture_classes, counts):
            for _ in range(count):
                if hasattr(fixture_class, 'create'):
                    fixture = fixture_class.create()
                    db_session.add(fixture)
                    fixtures.append(fixture)
        db_session.commit()
        return fixtures


class WebSocketTestHelper:
    """Helper class for WebSocket testing"""

    @staticmethod
    async def connect_to_websocket(uri: str, token: str = None) -> Any:
        """Connect to WebSocket endpoint"""
        try:
            import websockets
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            return await websockets.connect(uri, extra_headers=headers)
        except Exception as e:
            raise Exception(f"WebSocket connection failed: {e}")

    @staticmethod
    async def send_message(websocket, message: Dict[str, Any]):
        """Send message through WebSocket"""
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            raise Exception(f"Failed to send WebSocket message: {e}")

    @staticmethod
    async def receive_message(websocket, timeout: float = 5.0) -> Dict[str, Any]:
        """Receive message from WebSocket"""
        try:
            import asyncio
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            return json.loads(message)
        except asyncio.TimeoutError:
            raise TimeoutError("WebSocket receive timeout")
        except Exception as e:
            raise Exception(f"Failed to receive WebSocket message: {e}")

    @staticmethod
    async def close_websocket(websocket):
        """Close WebSocket connection"""
        try:
            await websocket.close()
        except Exception:
            pass  # Ignore close errors


class TestDataManager:
    """Helper class for managing test data lifecycle"""

    def __init__(self):
        self.created_resources = {
            "users": [],
            "documents": [],
            "organizations": [],
            "searches": []
        }

    def track_resource(self, resource_type: str, resource_id: str):
        """Track a created resource for cleanup"""
        if resource_type in self.created_resources:
            self.created_resources[resource_type].append(resource_id)

    def cleanup_resources(self, client: TestClient, headers: Dict[str, str]):
        """Clean up all tracked resources"""
        # Clean up documents
        for doc_id in self.created_resources["documents"]:
            try:
                client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
            except Exception:
                pass

        # Users and organizations typically can't be deleted via API
        # In real implementation, you might have admin endpoints for cleanup

    def get_resource_count(self, resource_type: str) -> int:
        """Get count of tracked resources"""
        return len(self.created_resources.get(resource_type, []))

    def clear_tracking(self):
        """Clear all resource tracking"""
        for resource_type in self.created_resources:
            self.created_resources[resource_type].clear()


class AssertionHelper:
    """Helper class for common test assertions"""

    @staticmethod
    def assert_valid_uuid(uuid_string: str):
        """Assert that string is a valid UUID"""
        import uuid as uuid_lib
        try:
            uuid_lib.UUID(uuid_string)
        except ValueError:
            raise AssertionError(f"'{uuid_string}' is not a valid UUID")

    @staticmethod
    def assert_iso_datetime(datetime_string: str):
        """Assert that string is a valid ISO datetime"""
        try:
            datetime.fromisoformat(datetime_string.replace('Z', '+00:00'))
        except ValueError:
            raise AssertionError(f"'{datetime_string}' is not a valid ISO datetime")

    @staticmethod
    def assert_email_format(email: str):
        """Assert that string is a valid email format"""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise AssertionError(f"'{email}' is not a valid email format")

    @staticmethod
    def assert_response_structure(response_data: Dict[str, Any], required_fields: List[str]):
        """Assert that response contains all required fields"""
        missing_fields = [field for field in required_fields if field not in response_data]
        if missing_fields:
            raise AssertionError(f"Response missing required fields: {missing_fields}")

    @staticmethod
    def assert_pagination_structure(pagination_data: Dict[str, Any]):
        """Assert that pagination response has correct structure"""
        required_fields = ["page", "page_size", "total_count", "total_pages"]
        AssertionHelper.assert_response_structure(pagination_data, required_fields)

        # Assert logical constraints
        assert pagination_data["page"] >= 1, "Page number must be >= 1"
        assert pagination_data["page_size"] > 0, "Page size must be > 0"
        assert pagination_data["total_count"] >= 0, "Total count must be >= 0"
        assert pagination_data["total_pages"] >= 0, "Total pages must be >= 0"

    @staticmethod
    def assert_search_result_structure(result: Dict[str, Any]):
        """Assert that search result has correct structure"""
        required_fields = ["document_id", "title", "score", "content_preview"]
        AssertionHelper.assert_response_structure(result, required_fields)

        # Assert score is valid
        assert 0 <= result["score"] <= 1, f"Search score must be between 0 and 1, got {result['score']}"

    @staticmethod
    def assert_file_size_within_limits(file_size_mb: float, max_size_mb: float):
        """Assert that file size is within limits"""
        assert file_size_mb <= max_size_mb, f"File size {file_size_mb}MB exceeds limit {max_size_mb}MB"


def performance_threshold(threshold_seconds: float):
    """Decorator to enforce performance threshold on test functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time

            if execution_time > threshold_seconds:
                raise AssertionError(
                    f"Function '{func.__name__}' exceeded performance threshold: "
                    f"{execution_time:.3f}s > {threshold_seconds}s"
                )
            return result
        return wrapper
    return decorator


def retry_test(max_attempts: int = 3, delay: float = 1.0):
    """Decorator to retry flaky tests"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (2 ** attempt))
                    else:
                        raise last_exception
        return wrapper
    return decorator


@contextmanager
def temporary_environment(env_vars: Dict[str, str]):
    """Context manager for temporarily setting environment variables"""
    import os
    original_values = {}

    # Set new values
    for key, value in env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        yield
    finally:
        # Restore original values
        for key, original_value in original_values.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


def generate_test_checksum(data: Union[str, bytes]) -> str:
    """Generate checksum for test data verification"""
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def create_test_headers(user_id: str, org_id: str) -> Dict[str, str]:
    """Create test headers with user and organization context"""
    return {
        "X-User-ID": user_id,
        "X-Organization-ID": org_id,
        "X-Test-Mode": "true",
        "Content-Type": "application/json"
    }


class MockResponse:
    """Mock response class for testing"""

    def __init__(self, json_data: Dict[str, Any], status_code: int = 200):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)

    def json(self) -> Dict[str, Any]:
        return self.json_data


def create_mock_external_services():
    """Create mock objects for external services"""
    from unittest.mock import Mock

    # Mock Qdrant client
    mock_qdrant = Mock()
    mock_qdrant.upsert.return_value = None
    mock_qdrant.search.return_value = []
    mock_qdrant.create_collection.return_value = None

    # Mock Neo4j driver
    mock_neo4j = Mock()
    mock_session = Mock()
    mock_session.run.return_value = Mock()
    mock_neo4j.session.return_value = mock_session

    # Mock Redis client
    mock_redis = Mock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True

    return {
        "qdrant": mock_qdrant,
        "neo4j": mock_neo4j,
        "redis": mock_redis
    }