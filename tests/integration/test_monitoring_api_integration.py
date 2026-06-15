"""
Monitoring API Endpoint Integration Tests

This module provides comprehensive integration tests for monitoring API endpoints:
- OpenAPI specification compliance validation
- API endpoint contract testing
- Request/response validation
- Authentication and authorization testing
- Rate limiting and throttling validation
- API performance testing under load
- Error handling and status code validation
- API versioning and backward compatibility
"""

import pytest
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
import yaml
from pydantic import ValidationError

# Setup paths
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

from backend.src.main import app
from backend.src.monitoring.api.monitoring_endpoints import router
from backend.src.monitoring.api.websocket_handlers import websocket_manager
from backend.src.monitoring.services.observability_manager import ObservabilityManager, get_observability_manager
from backend.src.monitoring.config.monitoring_config import MonitoringConfig
from backend.src.monitoring.models.metrics import MetricPoint, MetricSeries
from backend.src.monitoring.models.tracing import TraceSpan
from backend.src.monitoring.models.alerting import Alert, AlertRule


class TestOpenAPICompliance:
    """Test OpenAPI specification compliance"""

    @pytest.fixture
    def openapi_spec(self):
        """Load OpenAPI specification"""
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        return response.json()

    def test_openapi_spec_structure(self, openapi_spec):
        """Test OpenAPI specification structure"""
        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            assert field in openapi_spec, f"Missing required field: {field}"

        # Verify API version
        assert openapi_spec["openapi"].startswith("3.0")

        # Verify info section
        info = openapi_spec["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info

        # Verify paths section
        paths = openapi_spec["paths"]
        assert isinstance(paths, dict)
        assert len(paths) > 0

    def test_monitoring_endpoints_documented(self, openapi_spec):
        """Test that all monitoring endpoints are documented"""
        paths = openapi_spec["paths"]

        monitoring_endpoints = [
            "/monitoring/health",
            "/monitoring/metrics",
            "/monitoring/prometheus",
            "/monitoring/traces",
            "/monitoring/logs",
            "/monitoring/alerts",
            "/monitoring/alert-rules",
            "/monitoring/service-health",
            "/monitoring/correlation-id",
            "/monitoring/config",
            "/monitoring/dashboard",
            "/monitoring/test-metric"
        ]

        for endpoint in monitoring_endpoints:
            assert endpoint in paths, f"Missing documentation for endpoint: {endpoint}"

    def test_endpoint_schema_compliance(self, openapi_spec):
        """Test endpoint schema compliance"""
        paths = openapi_spec["paths"]

        # Test health endpoint schema
        health_path = paths["/monitoring/health"]
        assert "get" in health_path

        health_get = health_path["get"]
        assert "responses" in health_get
        assert "200" in health_get["responses"]
        assert "schema" in health_get["responses"]["200"]

        response_schema = health_get["responses"]["200"]["schema"]
        assert response_schema.get("$ref") or response_schema.get("type")

    def test_security_schemes_defined(self, openapi_spec):
        """Test security schemes are defined"""
        if "components" in openapi_spec and "securitySchemes" in openapi_spec["components"]:
            security_schemes = openapi_spec["components"]["securitySchemes"]
            assert isinstance(security_schemes, dict)

            # Verify common security schemes
            for scheme_name, scheme in security_schemes.items():
                assert "type" in scheme
                assert scheme["type"] in ["apiKey", "http", "oauth2", "openIdConnect"]

    def test_parameter_validation_schemas(self, openapi_spec):
        """Test parameter validation schemas"""
        paths = openapi_spec["paths"]

        # Test metrics endpoint parameters
        metrics_path = paths.get("/monitoring/metrics", {})
        if "post" in metrics_path:
            metrics_post = metrics_path["post"]
            if "requestBody" in metrics_post:
                request_body = metrics_post["requestBody"]
                assert "content" in request_body
                assert "application/json" in request_body["content"]
                assert "schema" in request_body["content"]["application/json"]


class TestMonitoringAPIEndpoints:
    """Test monitoring API endpoints functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    async def observability_manager(self):
        """Create observability manager for testing"""
        config = MonitoringConfig(
            service_name="test-api-monitoring",
            environment="test",
            metrics__custom_metrics_enabled=True,
            tracing__enabled=True,
            logging__structured_logging=True,
            alerting__enabled=True,
            health_check__enabled=True
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        # Mock the global get_observability_manager function
        with patch('backend.src.monitoring.api.monitoring_endpoints.get_observability_manager') as mock_get:
            mock_get.return_value = manager
            yield manager

        await manager.shutdown()

    def test_health_endpoint(self, client, observability_manager):
        """Test health check endpoint"""
        response = client.get("/monitoring/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "manager" in data
        assert "services" in data
        assert "timestamp" in data

        # Verify response structure
        manager_data = data["manager"]
        assert "initialized" in manager_data
        assert "running" in manager_data
        assert "status" in manager_data

        services_data = data["services"]
        assert isinstance(services_data, dict)

    def test_metrics_endpoint(self, client, observability_manager):
        """Test metrics endpoint"""
        # Record test metrics
        import asyncio
        asyncio.run(observability_manager.metrics_collector.record_counter(
            name="test_api_metric",
            value=1,
            labels={"endpoint": "test"}
        ))

        # Query metrics
        request_data = {
            "service": "test-api-monitoring",
            "start_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat()
        }

        response = client.post("/monitoring/metrics", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "metrics" in data

    def test_prometheus_endpoint(self, client, observability_manager):
        """Test Prometheus metrics endpoint"""
        response = client.get("/monitoring/prometheus")
        assert response.status_code == 200

        # Verify response is text format for Prometheus
        assert response.headers["content-type"].startswith("text/plain")

        # Verify metrics format
        metrics_text = response.text
        assert len(metrics_text) > 0
        lines = metrics_text.strip().split('\n')
        assert len(lines) > 0

    def test_traces_endpoint(self, client, observability_manager):
        """Test traces endpoint"""
        request_data = {
            "service": "test-api-monitoring",
            "start_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "limit": 50
        }

        response = client.post("/monitoring/traces", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "traces" in data

    def test_logs_endpoint(self, client, observability_manager):
        """Test logs endpoint"""
        request_data = {
            "service": "test-api-monitoring",
            "level": "INFO",
            "start_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "limit": 100
        }

        response = client.post("/monitoring/logs", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "logs" in data

    def test_alerts_endpoint(self, client, observability_manager):
        """Test alerts endpoint"""
        request_data = {
            "status": "active",
            "start_time": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "limit": 100
        }

        response = client.post("/monitoring/alerts", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "alerts" in data

    def test_alert_rules_endpoint(self, client, observability_manager):
        """Test alert rules creation endpoint"""
        rule_data = {
            "name": "API Test Alert Rule",
            "conditions": {
                "metric": "test_metric",
                "operator": ">",
                "threshold": 1.0
            },
            "severity": "medium",
            "channels": ["email"],
            "description": "Test alert rule for API testing",
            "category": "test"
        }

        response = client.post("/monitoring/alert-rules", json=rule_data)
        assert response.status_code == 200

        data = response.json()
        assert "rule_id" in data
        assert "message" in data

    def test_service_health_endpoint(self, client, observability_manager):
        """Test service health endpoint"""
        response = client.get("/monitoring/service-health")
        assert response.status_code == 200

        data = response.json()
        assert "overall_status" in data
        assert "components" in data
        assert "timestamp" in data

    def test_correlation_id_endpoint(self, client, observability_manager):
        """Test correlation ID creation endpoint"""
        response = client.post("/monitoring/correlation-id")
        assert response.status_code == 200

        data = response.json()
        assert "correlation_id" in data
        assert isinstance(data["correlation_id"], str)
        assert len(data["correlation_id"]) > 0

    def test_config_endpoint(self, client, observability_manager):
        """Test configuration endpoint"""
        response = client.get("/monitoring/config")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        assert "service_name" in data
        assert "environment" in data

    def test_dashboard_endpoint(self, client, observability_manager):
        """Test dashboard data endpoint"""
        response = client.get("/monitoring/dashboard")
        assert response.status_code == 200

        data = response.json()
        assert "health" in data
        assert "metrics_summary" in data
        assert "recent_alerts" in data
        assert "service_health" in data
        assert "timestamp" in data

    def test_test_metric_endpoint(self, client, observability_manager):
        """Test test metric creation endpoint"""
        response = client.post("/monitoring/test-metric?metric_name=test_api_metric&value=42.5")
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert "test_api_metric" in data["message"]
        assert "42.5" in data["message"]


class TestAPIAuthenticationAndAuthorization:
    """Test API authentication and authorization"""

    @pytest.fixture
    def authenticated_client(self):
        """Create authenticated test client"""
        client = TestClient(app)
        # In a real implementation, this would set up authentication headers
        return client

    def test_public_endpoint_access(self, client):
        """Test access to public endpoints"""
        # Health check should be publicly accessible
        response = client.get("/monitoring/health")
        assert response.status_code == 200

        # Prometheus metrics should be publicly accessible
        response = client.get("/monitoring/prometheus")
        assert response.status_code == 200

    def test_protected_endpoint_without_auth(self, client):
        """Test access to protected endpoints without authentication"""
        # Metrics endpoint should require authentication
        response = client.post("/monitoring/metrics", json={})
        # Should return 401 or 403 depending on implementation
        assert response.status_code in [401, 403]

        # Alert rules creation should require authentication
        response = client.post("/monitoring/alert-rules", json={})
        assert response.status_code in [401, 403]

    def test_protected_endpoint_with_invalid_auth(self, client):
        """Test access with invalid authentication"""
        headers = {"Authorization": "Bearer invalid_token"}

        response = client.post("/monitoring/metrics", json={}, headers=headers)
        assert response.status_code in [401, 403]

    def test_role_based_access_control(self, authenticated_client):
        """Test role-based access control"""
        # Test admin-only endpoints
        admin_endpoints = [
            "/monitoring/config",
            "/monitoring/alert-rules"
        ]

        for endpoint in admin_endpoints:
            # This would test that admin role can access
            # and regular user role cannot access
            pass  # Implementation depends on auth system

    def test_api_key_authentication(self, client):
        """Test API key authentication"""
        headers = {"X-API-Key": "test_api_key"}

        response = client.get("/monitoring/metrics", headers=headers)
        # Should work if API key is valid
        assert response.status_code in [200, 401, 403]


class TestAPIRequestValidation:
    """Test API request validation"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_metrics_request_validation(self, client):
        """Test metrics endpoint request validation"""
        # Valid request
        valid_request = {
            "service": "test-service",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat()
        }

        response = client.post("/monitoring/metrics", json=valid_request)
        # Should succeed or fail with 401/403 due to auth, not validation error
        assert response.status_code in [200, 401, 403]

        # Invalid request - missing required fields
        invalid_request = {
            "service": "test-service"
            # Missing time range
        }

        response = client.post("/monitoring/metrics", json=invalid_request)
        # Should return validation error
        assert response.status_code == 422

    def test_alert_rules_request_validation(self, client):
        """Test alert rules creation request validation"""
        # Valid request
        valid_request = {
            "name": "Test Alert",
            "conditions": {"metric": "cpu", "operator": ">", "threshold": 80},
            "severity": "high"
        }

        response = client.post("/monitoring/alert-rules", json=valid_request)
        # Should succeed or fail with auth error
        assert response.status_code in [200, 401, 403]

        # Invalid request - missing required name
        invalid_request = {
            "conditions": {"metric": "cpu", "operator": ">", "threshold": 80},
            "severity": "high"
        }

        response = client.post("/monitoring/alert-rules", json=invalid_request)
        assert response.status_code == 422

        # Invalid request - invalid severity
        invalid_request = {
            "name": "Test Alert",
            "conditions": {"metric": "cpu", "operator": ">", "threshold": 80},
            "severity": "invalid_severity"
        }

        response = client.post("/monitoring/alert-rules", json=invalid_request)
        assert response.status_code == 422

    def test_traces_request_validation(self, client):
        """Test traces endpoint request validation"""
        # Valid request
        valid_request = {
            "limit": 100
        }

        response = client.post("/monitoring/traces", json=valid_request)
        assert response.status_code in [200, 401, 403]

        # Invalid request - limit too high
        invalid_request = {
            "limit": 2000  # Over the maximum of 1000
        }

        response = client.post("/monitoring/traces", json=invalid_request)
        assert response.status_code == 422

        # Invalid request - negative limit
        invalid_request = {
            "limit": -10
        }

        response = client.post("/monitoring/traces", json=invalid_request)
        assert response.status_code == 422

    def test_logs_request_validation(self, client):
        """Test logs endpoint request validation"""
        # Valid request
        valid_request = {
            "level": "INFO",
            "limit": 50
        }

        response = client.post("/monitoring/logs", json=valid_request)
        assert response.status_code in [200, 401, 403]

        # Invalid request - invalid log level
        invalid_request = {
            "level": "INVALID_LEVEL",
            "limit": 50
        }

        response = client.post("/monitoring/logs", json=invalid_request)
        assert response.status_code == 422

    def test_datetime_format_validation(self, client):
        """Test datetime format validation"""
        # Valid datetime format
        valid_request = {
            "start_time": "2023-01-01T00:00:00Z",
            "end_time": "2023-01-01T01:00:00Z"
        }

        response = client.post("/monitoring/metrics", json=valid_request)
        assert response.status_code in [200, 401, 403]

        # Invalid datetime format
        invalid_request = {
            "start_time": "invalid-datetime",
            "end_time": "2023-01-01T01:00:00Z"
        }

        response = client.post("/monitoring/metrics", json=invalid_request)
        assert response.status_code == 422


class TestAPIResponseValidation:
    """Test API response validation"""

    @pytest.fixture
    async def observability_manager(self):
        """Create observability manager with test data"""
        config = MonitoringConfig(
            service_name="test-response-validation",
            metrics__custom_metrics_enabled=True,
            tracing__enabled=True,
            logging__structured_logging=True,
            alerting__enabled=True
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        # Add test data
        await manager.metrics_collector.record_counter(
            name="response_test_metric",
            value=1,
            labels={"test": "response_validation"}
        )

        with patch('backend.src.monitoring.api.monitoring_endpoints.get_observability_manager') as mock_get:
            mock_get.return_value = manager
            yield manager

        await manager.shutdown()

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_response_structure(self, client, observability_manager):
        """Test health endpoint response structure"""
        response = client.get("/monitoring/health")
        assert response.status_code == 200

        data = response.json()

        # Verify required fields
        required_fields = ["status", "manager", "services", "timestamp"]
        for field in required_fields:
            assert field in data, f"Missing required field in response: {field}"

        # Verify data types
        assert isinstance(data["status"], str)
        assert isinstance(data["manager"], dict)
        assert isinstance(data["services"], dict)
        assert isinstance(data["timestamp"], str)

        # Verify timestamp format
        try:
            datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
        except ValueError:
            pytest.fail("Invalid timestamp format")

    def test_metrics_response_structure(self, client, observability_manager):
        """Test metrics endpoint response structure"""
        request_data = {"service": "test-response-validation"}
        response = client.post("/monitoring/metrics", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "metrics" in data
        assert isinstance(data["metrics"], dict)

    def test_alerts_response_structure(self, client, observability_manager):
        """Test alerts endpoint response structure"""
        request_data = {"status": "active"}
        response = client.post("/monitoring/alerts", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], dict)

        # If alerts exist, verify their structure
        if data["alerts"]:
            alert = list(data["alerts"].values())[0]
            alert_fields = ["id", "name", "severity", "status", "created_at"]
            for field in alert_fields:
                assert field in alert, f"Missing field in alert: {field}"

    def test_error_response_structure(self, client):
        """Test error response structure"""
        # Make a request that will fail validation
        response = client.post("/monitoring/metrics", json={"invalid": "data"})
        assert response.status_code == 422

        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)

        # Verify error detail structure
        if data["detail"]:
            error = data["detail"][0]
            assert "loc" in error  # Location of error
            assert "msg" in error  # Error message
            assert "type" in error  # Error type

    def test_pagination_response_structure(self, client, observability_manager):
        """Test pagination response structure"""
        request_data = {"limit": 10}
        response = client.post("/monitoring/traces", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "traces" in data
        assert isinstance(data["traces"], dict)

        # If pagination is implemented, verify pagination fields
        if "pagination" in data:
            pagination = data["pagination"]
            pagination_fields = ["page", "page_size", "total", "total_pages"]
            for field in pagination_fields:
                assert field in pagination


class TestAPIPerformance:
    """Test API performance under various conditions"""

    @pytest.fixture
    async def performance_manager(self):
        """Create observability manager for performance testing"""
        config = MonitoringConfig(
            service_name="test-api-performance",
            metrics__custom_metrics_enabled=True,
            tracing__enabled=True,
            logging__structured_logging=False  # Reduce overhead
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        # Generate test data
        for i in range(100):
            await manager.metrics_collector.record_counter(
                name="performance_test_metric",
                value=i,
                labels={"batch": str(i // 10)}
            )

        with patch('backend.src.monitoring.api.monitoring_endpoints.get_observability_manager') as mock_get:
            mock_get.return_value = manager
            yield manager

        await manager.shutdown()

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_endpoint_response_times(self, client, performance_manager):
        """Test endpoint response times"""
        endpoints = [
            ("/monitoring/health", "GET", None),
            ("/monitoring/prometheus", "GET", None),
            ("/monitoring/service-health", "GET", None),
            ("/monitoring/metrics", "POST", {"service": "test-api-performance"}),
            ("/monitoring/dashboard", "GET", None)
        ]

        for endpoint, method, data in endpoints:
            start_time = time.time()

            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json=data)

            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Response should be fast
            assert response_time < 1000, f"Endpoint {endpoint} took too long: {response_time}ms"

            # Response should be successful (or auth error, not server error)
            assert response.status_code in [200, 401, 403], f"Endpoint {endpoint} returned {response.status_code}"

    def test_concurrent_requests(self, client, performance_manager):
        """Test API performance under concurrent requests"""
        import threading
        import queue

        endpoint = "/monitoring/health"
        request_count = 50
        results = queue.Queue()

        def make_request():
            start_time = time.time()
            response = client.get(endpoint)
            response_time = (time.time() - start_time) * 1000
            results.put({
                "status_code": response.status_code,
                "response_time": response_time
            })

        # Make concurrent requests
        threads = []
        start_time = time.time()

        for _ in range(request_count):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all requests to complete
        for thread in threads:
            thread.join()

        total_time = (time.time() - start_time) * 1000

        # Analyze results
        successful_requests = 0
        response_times = []

        while not results.empty():
            result = results.get()
            if result["status_code"] == 200:
                successful_requests += 1
            response_times.append(result["response_time"])

        # Performance assertions
        success_rate = successful_requests / request_count
        assert success_rate >= 0.95, f"Low success rate: {success_rate}"

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)

            assert avg_response_time < 500, f"High average response time: {avg_response_time}ms"
            assert max_response_time < 2000, f"High max response time: {max_response_time}ms"

        # Should handle concurrent requests efficiently
        assert total_time < 10000, f"Concurrent requests took too long: {total_time}ms"

    def test_large_payload_handling(self, client, performance_manager):
        """Test handling of large payloads"""
        # Create a large metrics request
        large_request = {
            "service": "test-api-performance",
            "start_time": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "labels": {f"label_{i}": f"value_{i}" for i in range(100)}
        }

        start_time = time.time()
        response = client.post("/monitoring/metrics", json=large_request)
        response_time = (time.time() - start_time) * 1000

        # Should handle large payload without significant performance degradation
        assert response_time < 5000, f"Large payload handling too slow: {response_time}ms"
        assert response.status_code in [200, 401, 403], f"Large payload failed: {response.status_code}"

    def test_memory_usage_during_requests(self, client, performance_manager):
        """Test memory usage during API requests"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Make many requests
        for i in range(100):
            response = client.get("/monitoring/health")
            assert response.status_code in [200, 401, 403]

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024, f"High memory increase: {memory_increase / 1024 / 1024}MB"


class TestAPIErrorHandling:
    """Test API error handling and edge cases"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_404_not_found(self, client):
        """Test 404 Not Found handling"""
        response = client.get("/monitoring/nonexistent-endpoint")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data

    def test_405_method_not_allowed(self, client):
        """Test 405 Method Not Allowed handling"""
        response = client.put("/monitoring/health")
        assert response.status_code == 405

        data = response.json()
        assert "detail" in data

    def test_422_validation_error(self, client):
        """Test 422 Validation Error handling"""
        response = client.post("/monitoring/metrics", json={"invalid": "data"})
        assert response.status_code == 422

        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)

    def test_500_internal_server_error(self, client):
        """Test 500 Internal Server Error handling"""
        # This would require mocking a failure in the observability manager
        with patch('backend.src.monitoring.api.monitoring_endpoints.get_observability_manager') as mock_get:
            mock_manager = Mock()
            mock_manager.health_check.side_effect = Exception("Simulated failure")
            mock_get.return_value = mock_manager

            response = client.get("/monitoring/health")
            assert response.status_code == 500

            data = response.json()
            assert "detail" in data

    def test_request_timeout_handling(self, client):
        """Test request timeout handling"""
        # Mock a slow operation
        with patch('backend.src.monitoring.api.monitoring_endpoints.get_observability_manager') as mock_get:
            mock_manager = Mock()

            async def slow_health_check():
                await asyncio.sleep(10)  # Simulate slow operation
                return {"status": "healthy"}

            mock_manager.health_check = slow_health_check
            mock_get.return_value = mock_manager

            # This would test timeout handling (implementation dependent)
            pass

    def test_malformed_json_request(self, client):
        """Test handling of malformed JSON requests"""
        malformed_json = '{"invalid": json structure}'

        response = client.post(
            "/monitoring/metrics",
            data=malformed_json,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_empty_request_body(self, client):
        """Test handling of empty request body"""
        response = client.post("/monitoring/metrics", data="")
        assert response.status_code == 422

    def test_excessively_large_request(self, client):
        """Test handling of excessively large requests"""
        # Create a very large payload
        large_payload = {
            "data": ["x" * 10000] * 1000  # ~10MB of data
        }

        response = client.post("/monitoring/metrics", json=large_payload)
        # Should return 413 Payload Too Large or handle gracefully
        assert response.status_code in [413, 422, 500]


class TestAPIVersioning:
    """Test API versioning and backward compatibility"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_api_version_headers(self, client):
        """Test API version in response headers"""
        response = client.get("/monitoring/health")
        assert response.status_code == 200

        # Check for API version headers (if implemented)
        api_version = response.headers.get("API-Version")
        if api_version:
            assert isinstance(api_version, str)
            assert len(api_version) > 0

    def test_backward_compatibility(self, client):
        """Test backward compatibility with older API versions"""
        # This would test versioned endpoints if implemented
        # For example: /v1/monitoring/health

        # For now, test current endpoints are stable
        stable_endpoints = [
            "/monitoring/health",
            "/monitoring/prometheus",
            "/monitoring/service-health"
        ]

        for endpoint in stable_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [200, 401, 403]

            # Response structure should be stable
            data = response.json()
            assert isinstance(data, dict)

    def test_deprecated_endpoints(self, client):
        """Test handling of deprecated endpoints"""
        # This would test deprecated endpoints if any exist
        # Should return appropriate headers and warnings

        pass  # Implementation dependent

    def test_api_content_negotiation(self, client):
        """Test API content negotiation"""
        # Test JSON response
        response = client.get("/monitoring/health", headers={"Accept": "application/json"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Test Prometheus text format
        response = client.get("/monitoring/prometheus", headers={"Accept": "text/plain"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")


# Integration test runner
class TestMonitoringAPIIntegration:
    """Comprehensive monitoring API integration tests"""

    @pytest.fixture
    async def full_integration_manager(self):
        """Create fully integrated monitoring manager"""
        config = MonitoringConfig(
            service_name="test-full-api-integration",
            environment="test",
            metrics__custom_metrics_enabled=True,
            tracing__enabled=True,
            logging__structured_logging=True,
            alerting__enabled=True,
            health_check__enabled=True
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        # Generate comprehensive test data
        # Metrics
        for i in range(50):
            await manager.metrics_collector.record_counter(
                name="integration_test_metric",
                value=i,
                labels={"test": "full_integration", "batch": str(i // 10)}
            )

        # Traces
        for i in range(20):
            async with manager.trace_operation(
                operation_name=f"integration_operation_{i}",
                service="integration-test-service"
            ):
                await asyncio.sleep(0.001)

        # Logs
        for i in range(30):
            await manager.log_aggregator.add_log(
                level="INFO",
                message=f"Integration test log {i}",
                service="integration-test-service"
            )

        with patch('backend.src.monitoring.api.monitoring_endpoints.get_observability_manager') as mock_get:
            mock_get.return_value = manager
            yield manager

        await manager.shutdown()

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_full_api_workflow(self, client, full_integration_manager):
        """Test complete API workflow"""
        # 1. Check system health
        health_response = client.get("/monitoring/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert health_data["manager"]["status"] in ["healthy", "degraded"]

        # 2. Get service health
        service_health_response = client.get("/monitoring/service-health")
        assert service_health_response.status_code == 200
        service_health_data = service_health_response.json()
        assert "overall_status" in service_health_data

        # 3. Query metrics
        metrics_request = {
            "service": "integration-test-service",
            "start_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat()
        }
        metrics_response = client.post("/monitoring/metrics", json=metrics_request)
        assert metrics_response.status_code == 200
        metrics_data = metrics_response.json()
        assert "metrics" in metrics_data

        # 4. Query traces
        traces_request = {
            "service": "integration-test-service",
            "limit": 20
        }
        traces_response = client.post("/monitoring/traces", json=traces_request)
        assert traces_response.status_code == 200
        traces_data = traces_response.json()
        assert "traces" in traces_data

        # 5. Query logs
        logs_request = {
            "service": "integration-test-service",
            "level": "INFO",
            "limit": 30
        }
        logs_response = client.post("/monitoring/logs", json=logs_request)
        assert logs_response.status_code == 200
        logs_data = logs_response.json()
        assert "logs" in logs_data

        # 6. Get dashboard overview
        dashboard_response = client.get("/monitoring/dashboard")
        assert dashboard_response.status_code == 200
        dashboard_data = dashboard_response.json()
        assert "health" in dashboard_data
        assert "metrics_summary" in dashboard_data
        assert "service_health" in dashboard_data

    def test_api_error_recovery(self, client, full_integration_manager):
        """Test API error recovery mechanisms"""
        # Test malformed request recovery
        malformed_response = client.post("/monitoring/metrics", json={"invalid": "data"})
        assert malformed_response.status_code == 422

        # Subsequent valid request should work
        valid_response = client.get("/monitoring/health")
        assert valid_response.status_code == 200

        # Test timeout recovery (if implemented)
        # This would test that the API recovers from timeouts gracefully

    def test_api_consistency(self, client, full_integration_manager):
        """Test API response consistency across endpoints"""
        # Get data from multiple endpoints
        health_response = client.get("/monitoring/health")
        service_health_response = client.get("/monitoring/service-health")
        dashboard_response = client.get("/monitoring/dashboard")

        # All should succeed
        assert health_response.status_code == 200
        assert service_health_response.status_code == 200
        assert dashboard_response.status_code == 200

        # Timestamps should be consistent
        health_data = health_response.json()
        service_health_data = service_health_response.json()
        dashboard_data = dashboard_response.json()

        health_time = datetime.fromisoformat(health_data["timestamp"].replace('Z', '+00:00'))
        service_health_time = datetime.fromisoformat(service_health_data["timestamp"].replace('Z', '+00:00'))
        dashboard_time = datetime.fromisoformat(dashboard_data["timestamp"].replace('Z', '+00:00'))

        # Timestamps should be within a reasonable window (1 minute)
        time_diff = max(
            abs((health_time - service_health_time).total_seconds()),
            abs((health_time - dashboard_time).total_seconds()),
            abs((service_health_time - dashboard_time).total_seconds())
        )
        assert time_diff < 60, f"Inconsistent timestamps: {time_diff} seconds difference"


if __name__ == "__main__":
    # Run specific test classes
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "TestOpenAPICompliance",
        "TestMonitoringAPIEndpoints",
        "TestAPIAuthenticationAndAuthorization",
        "TestAPIRequestValidation",
        "TestAPIResponseValidation",
        "TestAPIPerformance",
        "TestAPIErrorHandling",
        "TestAPIVersioning",
        "TestMonitoringAPIIntegration"
    ])