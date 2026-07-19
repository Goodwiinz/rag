"""
Status Endpoints Integration Tests

Comprehensive contract testing for all status and monitoring REST API endpoints.
Tests API response formats, schema validation, performance, and error handling.

Test Coverage:
- WebSocket status endpoints
- Document processing status APIs
- System health checks
- Performance monitoring endpoints
- Error response validation
- API response time benchmarks
"""

import asyncio
import json
import time
import pytest
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone as dt_timezone
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi import status
import requests
import httpx

# Import backend modules
from backend.src.main import app
from backend.src.api.websocket import manager as v1_manager
from backend.src.api.websocket_v2 import connection_manager as v2_manager
from backend.src.monitoring.api.websocket_handlers import websocket_manager as monitoring_manager

# Test configuration
API_BASE_URL = "http://localhost:8000"
API_V1_PREFIX = "/api/v1"
API_V2_PREFIX = "/api/v2"

# Performance thresholds (in milliseconds)
RESPONSE_TIME_THRESHOLD = 1000  # 1 second
FAST_RESPONSE_THRESHOLD = 500   # 500ms

class StatusEndpointTester:
    """Helper class for status endpoint testing"""

    def __init__(self, client: TestClient):
        self.client = client
        self.response_times: List[Dict[str, Any]] = []

    def make_request_with_timing(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """Make HTTP request and measure response time"""

        start_time = time.time()
        response = self.client.request(method, endpoint, **kwargs)
        end_time = time.time()

        response_time_ms = (end_time - start_time) * 1000

        # Record timing information
        self.response_times.append({
            "endpoint": endpoint,
            "method": method,
            "response_time_ms": response_time_ms,
            "status_code": response.status_code,
            "timestamp": datetime.now(dt_timezone.utc).isoformat()
        })

        return response

    def validate_response_structure(
        self,
        response_data: Dict[str, Any],
        required_fields: List[str],
        optional_fields: Optional[List[str]] = None
    ) -> None:
        """Validate API response structure"""

        # Check required fields
        for field in required_fields:
            assert field in response_data, f"Missing required field: {field}"
            assert response_data[field] is not None, f"Required field '{field}' is null"

        # Check optional fields if present
        if optional_fields:
            for field in optional_fields:
                if field in response_data:
                    assert response_data[field] is not None, f"Optional field '{field}' is null"

    def validate_timestamp_format(self, timestamp_str: str) -> None:
        """Validate ISO8601 timestamp format"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            assert isinstance(timestamp, datetime)
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {timestamp_str}")

    def validate_pagination_structure(
        self,
        response_data: Dict[str, Any]
    ) -> None:
        """Validate paginated response structure"""

        required_fields = ["items", "total", "page", "per_page", "pages"]
        self.validate_response_structure(response_data, required_fields)

        # Validate pagination values
        assert isinstance(response_data["items"], list)
        assert isinstance(response_data["total"], int)
        assert isinstance(response_data["page"], int)
        assert isinstance(response_data["per_page"], int)
        assert isinstance(response_data["pages"], int)

        # Validate pagination logic
        assert response_data["total"] >= 0
        assert response_data["page"] >= 1
        assert response_data["per_page"] >= 1
        assert response_data["pages"] >= 1
        assert len(response_data["items"]) <= response_data["per_page"]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary"""

        if not self.response_times:
            return {"message": "No requests recorded"}

        response_times = [r["response_time_ms"] for r in self.response_times]

        return {
            "total_requests": len(self.response_times),
            "avg_response_time_ms": sum(response_times) / len(response_times),
            "min_response_time_ms": min(response_times),
            "max_response_time_ms": max(response_times),
            "requests_above_threshold": len([r for r in response_times if r > RESPONSE_TIME_THRESHOLD]),
            "fast_requests": len([r for r in response_times if r < FAST_RESPONSE_THRESHOLD]),
            "slowest_endpoint": max(self.response_times, key=lambda x: x["response_time_ms"])["endpoint"],
            "fastest_endpoint": min(self.response_times, key=lambda x: x["response_time_ms"])["endpoint"]
        }


# ============================================================================
# WebSocket Status Endpoints Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.contract
@pytest.mark.status
class TestWebSocketStatusEndpoints:
    """Test WebSocket status endpoints"""

    @pytest.fixture
    def status_tester(self):
        """Create status endpoint tester"""
        return StatusEndpointTester(TestClient(app))

    def test_websocket_v1_status_endpoint(self, status_tester):
        """Test WebSocket v1 status endpoint (/api/v1/ws/status)"""

        endpoint = f"{API_V1_PREFIX}/ws/status"

        # Make request with timing
        response = status_tester.make_request_with_timing("GET", endpoint)

        # Validate response
        assert response.status_code == 200

        response_data = response.json()

        # Validate required fields
        required_fields = ["status", "total_connections", "active_users", "timestamp"]
        status_tester.validate_response_structure(response_data, required_fields)

        # Validate field types and values
        assert response_data["status"] in ["available", "unavailable", "degraded"]
        assert isinstance(response_data["total_connections"], int)
        assert isinstance(response_data["active_users"], int)
        assert response_data["total_connections"] >= 0
        assert response_data["active_users"] >= 0

        # Validate timestamp format
        status_tester.validate_timestamp_format(response_data["timestamp"])

        # Performance validation
        response_time = status_tester.response_times[-1]["response_time_ms"]
        assert response_time < RESPONSE_TIME_THRESHOLD

    def test_websocket_v2_status_endpoint(self, status_tester):
        """Test WebSocket v2 comprehensive status endpoint (/api/v2/ws/status)"""

        endpoint = f"{API_V2_PREFIX}/ws/status"

        response = status_tester.make_request_with_timing("GET", endpoint)

        assert response.status_code == 200

        response_data = response.json()

        # Validate top-level structure
        required_sections = ["websocket_service", "connections", "channels", "performance", "system_status"]
        for section in required_sections:
            assert section in response_data, f"Missing section: {section}"

        # Validate websocket_service section
        service_section = response_data["websocket_service"]
        service_required_fields = ["status", "timestamp", "version", "features"]
        status_tester.validate_response_structure(service_section, service_required_fields)

        # Validate features
        features = service_section["features"]
        expected_features = [
            "jwt_authentication", "channel_subscription", "message_filtering",
            "heartbeat_monitoring", "automatic_reconnection", "message_batching"
        ]
        for feature in expected_features:
            assert feature in features, f"Missing feature: {feature}"
            assert isinstance(features[feature], bool)

        # Validate connections section
        connections = response_data["connections"]
        connection_fields = ["total_connections", "active_connections", "max_connections"]
        status_tester.validate_response_structure(connections, connection_fields)

        # Validate channels section
        channels = response_data["channels"]
        expected_channels = [
            "document_processing", "job_status", "system_status",
            "user_notifications", "quota_alerts", "quality_metrics", "admin_alerts"
        ]
        for channel in expected_channels:
            assert channel in channels, f"Missing channel: {channel}"
            channel_info = channels[channel]
            assert "description" in channel_info
            assert "subscribers" in channel_info
            assert "message_rate" in channel_info

        # Validate performance section
        performance = response_data["performance"]
        performance_fields = ["max_connections", "current_usage_percentage", "redis_enabled"]
        status_tester.validate_response_structure(performance, performance_fields)

        assert 0 <= performance["current_usage_percentage"] <= 100

        # Performance validation
        response_time = status_tester.response_times[-1]["response_time_ms"]
        assert response_time < RESPONSE_TIME_THRESHOLD

    def test_websocket_v2_channels_endpoint(self, status_tester):
        """Test WebSocket channels information endpoint (/api/v2/ws/channels)"""

        endpoint = f"{API_V2_PREFIX}/ws/channels"

        response = status_tester.make_request_with_timing("GET", endpoint)

        assert response.status_code == 200

        response_data = response.json()

        # Validate structure
        assert "channels" in response_data
        channels = response_data["channels"]
        assert isinstance(channels, list)
        assert len(channels) > 0

        # Validate channel structure
        for channel in channels:
            required_fields = ["name", "description", "message_types", "typical_update_frequency", "required_permissions"]
            status_tester.validate_response_structure(channel, required_fields)

            # Validate field values
            assert isinstance(channel["name"], str)
            assert isinstance(channel["description"], str)
            assert isinstance(channel["message_types"], list)
            assert isinstance(channel["typical_update_frequency"], str)
            assert isinstance(channel["required_permissions"], str)

            # Validate permission levels
            assert channel["required_permissions"] in ["user", "admin"]

    def test_websocket_v2_health_check_endpoint(self, status_tester):
        """Test WebSocket health check endpoint (/api/v2/ws/health)"""

        endpoint = f"{API_V2_PREFIX}/ws/health"

        response = status_tester.make_request_with_timing("GET", endpoint)

        assert response.status_code == 200

        response_data = response.json()

        # Validate health check structure
        required_fields = ["status", "timestamp", "checks", "metrics"]
        status_tester.validate_response_structure(response_data, required_fields)

        # Validate status values
        assert response_data["status"] in ["healthy", "degraded", "unhealthy"]

        # Validate individual health checks
        checks = response_data["checks"]
        expected_checks = ["connection_manager", "status_update_service", "redis_connection", "connection_load"]
        for check in expected_checks:
            assert check in checks
            assert checks[check] in ["healthy", "unhealthy", "high"]

        # Validate metrics
        metrics = response_data["metrics"]
        metric_fields = ["active_connections", "active_jobs", "failed_jobs_today", "average_processing_time"]
        for field in metric_fields:
            assert field in metrics

        # Performance validation
        response_time = status_tester.response_times[-1]["response_time_ms"]
        assert response_time < FAST_RESPONSE_THRESHOLD  # Health checks should be fast

    async def test_websocket_user_connections_endpoint(self, status_tester):
        """Test user connections endpoint (/api/v2/ws/connections/{user_id})"""

        # This test would require authentication
        # For now, test the endpoint structure

        endpoint = f"{API_V2_PREFIX}/ws/connections/test_user_123"

        # Test without authentication (should fail with 401 or 403)
        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should require authentication
        assert response.status_code in [401, 403]

        # If we get a response, validate its structure
        if response.status_code == 200:
            response_data = response.json()
            required_fields = ["user_id", "active_connections", "connections"]
            status_tester.validate_response_structure(response_data, required_fields)

            assert isinstance(response_data["connections"], list)


# ============================================================================
# Document Processing Status Endpoints Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.contract
@pytest.mark.documents
class TestDocumentProcessingStatusEndpoints:
    """Test document processing status endpoints"""

    @pytest.fixture
    def status_tester(self):
        """Create status endpoint tester"""
        return StatusEndpointTester(TestClient(app))

    def test_documents_status_endpoint(self, status_tester):
        """Test documents status endpoint (/api/v1/documents/status)"""

        endpoint = f"{API_V1_PREFIX}/documents/status"

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should return 200 (even if no documents)
        assert response.status_code == 200

        response_data = response.json()

        # Validate status structure
        if isinstance(response_data, dict):
            # May contain fields like: total_documents, processing_documents, completed_documents, etc.
            for key, value in response_data.items():
                assert isinstance(key, str)
                assert isinstance(value, (int, float, str, list, dict))

        # Performance validation
        response_time = status_tester.response_times[-1]["response_time_ms"]
        assert response_time < RESPONSE_TIME_THRESHOLD

    def test_documents_list_with_status_filter(self, status_tester):
        """Test documents list endpoint with status filter"""

        # Test with different status filters
        status_filters = ["processing", "completed", "failed", "queued"]

        for filter_status in status_filters:
            endpoint = f"{API_V1_PREFIX}/documents?status={filter_status}"

            response = status_tester.make_request_with_timing("GET", endpoint)

            assert response.status_code == 200

            response_data = response.json()

            # If paginated response
            if isinstance(response_data, dict) and "items" in response_data:
                status_tester.validate_pagination_structure(response_data)

                # Validate documents in response have the correct status
                for document in response_data["items"]:
                    assert "status" in document
                    # Status should match filter (case insensitive)
                    assert document["status"].lower() == filter_status.lower()

            # If simple list response
            elif isinstance(response_data, list):
                for document in response_data:
                    assert "status" in document
                    assert document["status"].lower() == filter_status.lower()

    def test_document_individual_status_endpoint(self, status_tester):
        """Test individual document status endpoint"""

        # Test with non-existent document ID
        document_id = "non_existent_doc_12345"
        endpoint = f"{API_V1_PREFIX}/documents/{document_id}/status"

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should return 404 for non-existent document
        assert response.status_code == 404

        response_data = response.json()

        # Validate error response structure
        assert "detail" in response_data or "error" in response_data

    async def test_processing_queue_status_endpoint(self, status_tester):
        """Test processing queue status endpoint"""

        endpoint = f"{API_V1_PREFIX}/processing/queue/status"

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should return queue status information
        assert response.status_code in [200, 404]  # 404 if endpoint not implemented

        if response.status_code == 200:
            response_data = response.json()

            # Validate queue status fields
            expected_fields = [
                "queue_size", "processing_jobs", "completed_jobs",
                "failed_jobs", "average_wait_time"
            ]

            for field in expected_fields:
                if field in response_data:
                    assert isinstance(response_data[field], (int, float))


# ============================================================================
# System Health and Monitoring Endpoints Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.contract
@pytest.mark.monitoring
class TestSystemHealthEndpoints:
    """Test system health and monitoring endpoints"""

    @pytest.fixture
    def status_tester(self):
        """Create status endpoint tester"""
        return StatusEndpointTester(TestClient(app))

    def test_system_health_check_endpoint(self, status_tester):
        """Test system health check endpoint"""

        endpoint = "/health"  # Standard health endpoint

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Health endpoint should always be available
        assert response.status_code in [200, 503]  # 503 if system unhealthy

        response_data = response.json()

        # Validate health check structure
        if response.status_code == 200:
            required_fields = ["status", "timestamp"]
            status_tester.validate_response_structure(response_data, required_fields)

            assert response_data["status"] in ["healthy", "unhealthy", "degraded"]
            status_tester.validate_timestamp_format(response_data["timestamp"])

    def test_system_metrics_endpoint(self, status_tester):
        """Test system metrics endpoint"""

        endpoint = f"{API_V1_PREFIX}/metrics"

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should return metrics or 404 if not implemented
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            response_data = response.json()

            # Validate metrics structure
            if isinstance(response_data, dict):
                # Should contain various system metrics
                expected_metric_categories = [
                    "system", "application", "database", "cache"
                ]

                for category in expected_metric_categories:
                    if category in response_data:
                        assert isinstance(response_data[category], dict)

    def test_database_health_check(self, status_tester):
        """Test database health check endpoint"""

        endpoint = f"{API_V1_PREFIX}/health/database"

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should return database health status
        assert response.status_code in [200, 503]  # 503 if database unavailable

        if response.status_code == 200:
            response_data = response.json()

            # Validate database health fields
            required_fields = ["status", "connection_time", "active_connections"]
            status_tester.validate_response_structure(response_data, required_fields)

            assert response_data["status"] in ["healthy", "unhealthy", "degraded"]
            assert isinstance(response_data["connection_time"], (int, float))
            assert isinstance(response_data["active_connections"], int)

    def test_external_services_health_check(self, status_tester):
        """Test external services health check endpoint"""

        endpoint = f"{API_V1_PREFIX}/health/external"

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should return status of external services
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            response_data = response.json()

            # Should contain status for various external services
            expected_services = [
                "neo4j", "qdrant", "redis", "openai", "anthropic"
            ]

            for service in expected_services:
                if service in response_data:
                    service_info = response_data[service]
                    assert "status" in service_info
                    assert service_info["status"] in ["healthy", "unhealthy", "degraded"]

                    if "response_time" in service_info:
                        assert isinstance(service_info["response_time"], (int, float))

    def test_performance_dashboard_endpoint(self, status_tester):
        """Test performance dashboard data endpoint"""

        endpoint = f"{API_V1_PREFIX}/dashboard/performance"

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should return performance data
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            response_data = response.json()

            # Validate performance dashboard structure
            if isinstance(response_data, dict):
                expected_sections = [
                    "system_metrics", "api_performance", "websocket_metrics",
                    "database_metrics", "processing_metrics"
                ]

                for section in expected_sections:
                    if section in response_data:
                        assert isinstance(response_data[section], (dict, list))


# ============================================================================
# Error Handling and Edge Cases Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.contract
@pytest.mark.error_handling
class TestStatusEndpointsErrorHandling:
    """Test status endpoints error handling and edge cases"""

    @pytest.fixture
    def status_tester(self):
        """Create status endpoint tester"""
        return StatusEndpointTester(TestClient(app))

    def test_invalid_endpoint_returns_404(self, status_tester):
        """Test that invalid endpoints return 404"""

        invalid_endpoints = [
            f"{API_V1_PREFIX}/ws/invalid_status",
            f"{API_V2_PREFIX}/ws/unknown_endpoint",
            f"{API_V1_PREFIX}/documents/invalid_status",
            "/api/invalid_endpoint"
        ]

        for endpoint in invalid_endpoints:
            response = status_tester.make_request_with_timing("GET", endpoint)

            assert response.status_code == 404

            # Validate error response structure
            response_data = response.json()
            assert "detail" in response_data

    def test_method_not_allowed_on_status_endpoints(self, status_tester):
        """Test that unsupported methods return 405"""

        endpoints_to_test = [
            f"{API_V1_PREFIX}/ws/status",
            f"{API_V2_PREFIX}/ws/status",
            f"{API_V1_PREFIX}/documents/status"
        ]

        unsupported_methods = ["POST", "PUT", "DELETE", "PATCH"]

        for endpoint in endpoints_to_test:
            for method in unsupported_methods:
                response = status_tester.make_request_with_timing(method, endpoint)

                assert response.status_code == 405

    def test_large_query_parameters_handling(self, status_tester):
        """Test handling of large query parameters"""

        # Test with very long status filter
        long_status = "x" * 1000
        endpoint = f"{API_V1_PREFIX}/documents?status={long_status}"

        response = status_tester.make_request_with_timing("GET", endpoint)

        # Should handle gracefully (either return empty result or error)
        assert response.status_code in [200, 400, 414]  # 414 for URI too long

    def test_malformed_json_in_post_requests(self, status_tester):
        """Test handling of malformed JSON in POST requests"""

        # Find endpoints that accept POST requests
        post_endpoints = [
            f"{API_V2_PREFIX}/ws/broadcast",
            f"{API_V1_PREFIX}/documents"
        ]

        malformed_json = '{"invalid": json structure}'

        for endpoint in post_endpoints:
            response = status_tester.client.post(
                endpoint,
                data=malformed_json,
                headers={"Content-Type": "application/json"}
            )

            # Should reject malformed JSON
            assert response.status_code == 422  # Unprocessable Entity

            response_data = response.json()
            assert "detail" in response_data

    def test_rate_limiting_on_status_endpoints(self, status_tester):
        """Test rate limiting on status endpoints"""

        endpoint = f"{API_V1_PREFIX}/ws/status"

        # Make multiple rapid requests
        responses = []
        for _ in range(20):  # Make 20 rapid requests
            response = status_tester.make_request_with_timing("GET", endpoint)
            responses.append(response)

            # If we get rate limited, break
            if response.status_code == 429:
                break

        # Check if any responses were rate limited
        rate_limited_responses = [r for r in responses if r.status_code == 429]

        if rate_limited_responses:
            # Validate rate limit response structure
            rate_limit_response = rate_limited_responses[0]
            response_data = rate_limit_response.json()

            # Should contain rate limit information
            assert "detail" in response_data
            # May also contain headers like Retry-After, X-RateLimit-Limit, etc.

    def test_concurrent_requests_to_status_endpoints(self, status_tester):
        """Test concurrent requests to status endpoints"""

        import concurrent.futures
        import threading

        endpoint = f"{API_V1_PREFIX}/ws/status"
        num_concurrent_requests = 10

        def make_request():
            """Make a single request"""
            response = status_tester.client.get(endpoint)
            return {
                "status_code": response.status_code,
                "response_time": time.time()
            }

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
            futures = [executor.submit(make_request) for _ in range(num_concurrent_requests)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        successful_requests = [r for r in results if r["status_code"] == 200]
        assert len(successful_requests) == num_concurrent_requests

        # Response times should be reasonable
        start_time = min(r["response_time"] for r in results)
        end_time = max(r["response_time"] for r in results)
        total_time = (end_time - start_time) * 1000  # Convert to milliseconds

        # Should complete concurrent requests in reasonable time
        assert total_time < RESPONSE_TIME_THRESHOLD * 2


# ============================================================================
# Performance Benchmarking Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.contract
@pytest.mark.performance
class TestStatusEndpointsPerformance:
    """Performance benchmarking for status endpoints"""

    @pytest.fixture
    def status_tester(self):
        """Create status endpoint tester"""
        return StatusEndpointTester(TestClient(app))

    def test_status_endpoints_performance_benchmark(self, status_tester):
        """Benchmark performance of all status endpoints"""

        # List of endpoints to benchmark
        endpoints_to_test = [
            (f"{API_V1_PREFIX}/ws/status", "WebSocket v1 Status"),
            (f"{API_V2_PREFIX}/ws/status", "WebSocket v2 Status"),
            (f"{API_V2_PREFIX}/ws/channels", "WebSocket Channels"),
            (f"{API_V2_PREFIX}/ws/health", "WebSocket Health"),
            (f"{API_V1_PREFIX}/documents/status", "Documents Status"),
            "/health", "System Health"
        ]

        # Make multiple requests to each endpoint
        requests_per_endpoint = 5

        for endpoint, description in endpoints_to_test:
            endpoint_response_times = []

            for _ in range(requests_per_endpoint):
                try:
                    response = status_tester.make_request_with_timing("GET", endpoint)
                    endpoint_response_times.append(status_tester.response_times[-1]["response_time_ms"])

                    # Verify request succeeded
                    assert response.status_code in [200, 404], f"{description} failed with {response.status_code}"

                except Exception as e:
                    pytest.fail(f"Performance test failed for {description}: {e}")

            # Calculate performance metrics for this endpoint
            if endpoint_response_times:
                avg_time = sum(endpoint_response_times) / len(endpoint_response_times)
                min_time = min(endpoint_response_times)
                max_time = max(endpoint_response_times)

                # Performance assertions
                assert avg_time < RESPONSE_TIME_THRESHOLD, f"{description} average time {avg_time:.2f}ms exceeds threshold"
                assert max_time < RESPONSE_TIME_THRESHOLD * 2, f"{description} max time {max_time:.2f}ms exceeds 2x threshold"

                print(f"\n{description} Performance:")
                print(f"  Average: {avg_time:.2f}ms")
                print(f"  Min: {min_time:.2f}ms")
                print(f"  Max: {max_time:.2f}ms")

    def test_overall_performance_summary(self, status_tester):
        """Generate overall performance summary"""

        # Make requests to various endpoints
        endpoints = [
            f"{API_V1_PREFIX}/ws/status",
            f"{API_V2_PREFIX}/ws/status",
            f"{API_V1_PREFIX}/documents/status",
            "/health"
        ]

        requests_per_endpoint = 3

        for endpoint in endpoints:
            for _ in range(requests_per_endpoint):
                try:
                    status_tester.make_request_with_timing("GET", endpoint)
                except Exception:
                    pass  # Ignore errors for performance summary

        # Generate performance summary
        summary = status_tester.get_performance_summary()

        # Validate summary metrics
        assert "total_requests" in summary
        assert "avg_response_time_ms" in summary
        assert "requests_above_threshold" in summary

        # Performance requirements
        assert summary["avg_response_time_ms"] < RESPONSE_TIME_THRESHOLD
        assert summary["fast_requests"] > 0  # Should have some fast requests

        # Print performance summary
        print(f"\nPerformance Summary:")
        print(f"  Total Requests: {summary['total_requests']}")
        print(f"  Average Response Time: {summary['avg_response_time_ms']:.2f}ms")
        print(f"  Requests Above Threshold: {summary['requests_above_threshold']}")
        print(f"  Fast Requests (<{FAST_RESPONSE_THRESHOLD}ms): {summary['fast_requests']}")
        print(f"  Slowest Endpoint: {summary.get('slowest_endpoint', 'N/A')}")
        print(f"  Fastest Endpoint: {summary.get('fastest_endpoint', 'N/A')}")


# ============================================================================
# Integration Test Runner
# ============================================================================

async def run_status_endpoints_integration_tests():
    """Run all status endpoints integration tests"""

    tester = StatusEndpointTester(TestClient(app))

    print("Running Status Endpoints Integration Tests...")

    # Test key endpoints
    test_cases = [
        (f"{API_V1_PREFIX}/ws/status", "WebSocket v1 Status"),
        (f"{API_V2_PREFIX}/ws/status", "WebSocket v2 Status"),
        (f"{API_V2_PREFIX}/ws/channels", "WebSocket Channels"),
        (f"{API_V2_PREFIX}/ws/health", "WebSocket Health"),
        (f"{API_V1_PREFIX}/documents/status", "Documents Status"),
        "/health", "System Health"
    ]

    results = []

    for endpoint, description in test_cases:
        print(f"\nTesting {description}: {endpoint}")

        try:
            response = tester.make_request_with_timing("GET", endpoint)
            response_time = tester.response_times[-1]["response_time_ms"]

            result = {
                "endpoint": endpoint,
                "description": description,
                "status_code": response.status_code,
                "response_time_ms": response_time,
                "success": response.status_code in [200, 404]  # 404 is acceptable for unimplemented endpoints
            }

            if response.status_code == 200:
                response_data = response.json()
                result["response_size_bytes"] = len(json.dumps(response_data))

            results.append(result)

            print(f"  ✅ Status: {response.status_code}, Time: {response_time:.2f}ms")

        except Exception as e:
            result = {
                "endpoint": endpoint,
                "description": description,
                "status_code": 0,
                "response_time_ms": 0,
                "success": False,
                "error": str(e)
            }
            results.append(result)

            print(f"  ❌ Failed: {e}")

    # Generate summary
    successful_tests = sum(1 for r in results if r["success"])
    total_tests = len(results)

    print(f"\n" + "="*50)
    print(f"STATUS ENDPOINTS TEST SUMMARY")
    print(f"="*50)
    print(f"Successful: {successful_tests}/{total_tests}")
    print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")

    if tester.response_times:
        avg_response_time = sum(r["response_time_ms"] for r in tester.response_times) / len(tester.response_times)
        print(f"Average Response Time: {avg_response_time:.2f}ms")

    # Save results
    timestamp = datetime.now(dt_timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_file = f"/tmp/status_endpoints_test_results_{timestamp}.json"

    with open(results_file, 'w') as f:
        json.dump({
            "test_run": timestamp,
            "summary": {
                "successful": successful_tests,
                "total": total_tests,
                "success_rate": (successful_tests/total_tests)*100
            },
            "results": results,
            "performance": tester.get_performance_summary()
        }, f, indent=2, default=str)

    print(f"\nDetailed results saved to: {results_file}")

    return results


if __name__ == "__main__":
    # Run integration tests when executed directly
    asyncio.run(run_status_endpoints_integration_tests())