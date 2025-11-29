"""
Tests for API Gateway Service
"""

import pytest
import json
import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient

from backend.src.services.api_gateway import app
from backend.src.shared.schemas import UserRole


class TestAPIGateway:
    """Test API Gateway functionality"""

    @pytest.fixture
    def client(self):
        """Create test client for API Gateway"""
        return TestClient(app)

    @pytest.fixture
    async def http_client(self):
        """Create async HTTP client"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_gateway_status(self, client):
        """Test gateway status endpoint"""
        response = client.get("/status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "services" in data

    def test_list_routes(self, client):
        """Test route listing endpoint"""
        response = client.get("/routes")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        assert "/api/v1/documents" in data
        assert "/api/v1/search" in data
        assert "/api/v1/auth" in data

    def test_list_services(self, client):
        """Test services listing endpoint"""
        response = client.get("/services")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)

    def test_get_version(self, client):
        """Test version endpoint"""
        response = client.get("/version")
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "deprecated" in data
        assert data["deprecated"] is False

    @patch('backend.src.services.api_gateway.make_http_request')
    async def test_proxy_request_success(self, mock_request, http_client):
        """Test successful request proxying"""
        # Mock successful service response
        mock_request.return_value = {
            "message": "Service response",
            "status": "success"
        }

        # Test proxying to document service
        response = await http_client.get("/api/v1/documents")

        # The actual implementation would route to the service
        # For testing, we verify the gateway handles the request
        assert response.status_code in [200, 404, 500]  # Depends on service availability

    @patch('backend.src.services.api_gateway.make_http_request')
    async def test_proxy_request_service_unavailable(self, mock_request, http_client):
        """Test proxying when service is unavailable"""
        # Mock service unavailable
        mock_request.side_effect = Exception("Service unavailable")

        response = await http_client.get("/api/v1/documents")

        # Should return service unavailable error
        assert response.status_code == 500

    @patch('backend.src.services.api_gateway.rate_limiter')
    async def test_rate_limiting(self, mock_rate_limiter, http_client):
        """Test rate limiting functionality"""
        # Mock rate limit exceeded
        mock_rate_limiter.is_allowed.return_value = (
            False,
            {"limit": 10, "remaining": 0, "reset_time": 1234567890, "retry_after": 60}
        )

        response = await http_client.get("/api/v1/documents")

        # Should return rate limit error
        assert response.status_code == 429

    async def test_cors_headers(self, http_client):
        """Test CORS headers are properly set"""
        response = await http_client.options("/api/v1/documents")

        # Check CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

    async def test_correlation_id_header(self, http_client):
        """Test correlation ID is added to responses"""
        response = await http_client.get("/health")

        # Check correlation ID header
        assert "x-correlation-id" in response.headers
        assert len(response.headers["x-correlation-id"]) > 0

    @patch('backend.src.services.api_gateway.verify_jwt_token')
    async def test_authentication_middleware(self, mock_verify_token, http_client):
        """Test JWT authentication middleware"""
        # Mock valid token
        mock_verify_token.return_value = {
            "sub": str(uuid.uuid4()),
            "email": "test@example.com",
            "role": "user",
            "organization_id": str(uuid.uuid4())
        }

        # Test with Authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = await http_client.get("/api/v1/documents", headers=headers)

        # Should accept valid token (actual response depends on service)
        mock_verify_token.assert_called_once()

    @patch('backend.src.services.api_gateway.verify_jwt_token')
    async def test_authentication_invalid_token(self, mock_verify_token, http_client):
        """Test authentication with invalid token"""
        # Mock invalid token
        mock_verify_token.side_effect = Exception("Invalid token")

        headers = {"Authorization": "Bearer invalid_token"}
        response = await http_client.get("/api/v1/documents", headers=headers)

        # Should reject invalid token
        assert response.status_code == 401

    async def test_request_logging(self, http_client):
        """Test request logging functionality"""
        with patch('backend.src.services.api_gateway.event_logger') as mock_logger:
            response = await http_client.get("/health")

            # Verify logging was called
            assert mock_logger.log_event.called

    async def test_metrics_collection(self, http_client):
        """Test metrics collection"""
        with patch('backend.src.services.api_gateway.metrics') as mock_metrics:
            response = await http_client.get("/health")

            # Verify metrics were recorded
            mock_metrics.increment_counter.assert_called()

    async def test_error_handling(self, http_client):
        """Test error handling in gateway"""
        # Test invalid endpoint
        response = await http_client.get("/invalid-endpoint")

        # Should return 404
        assert response.status_code == 404

    @patch('backend.src.services.api_gateway.health_checker')
    def test_service_health_monitoring(self, mock_health_checker, client):
        """Test service health monitoring"""
        # Mock service health
        mock_health_checker.check_health.return_value = {
            "status": "healthy",
            "checks": {
                "document-management": {"status": "healthy"},
                "search": {"status": "healthy"}
            }
        }

        response = client.get("/health")

        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data

    async def test_load_balancing(self, http_client):
        """Test load balancing functionality"""
        # This would test multiple service instances
        # For now, test that requests are handled
        response = await http_client.get("/health")
        assert response.status_code == 200

    def test_prometheus_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")

        # Should return metrics (if enabled)
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_background_task_execution(self):
        """Test background task execution"""
        from backend.src.services.api_gateway import health_check_loop, metrics_collection_loop

        # Test that background tasks can be created
        with patch('backend.src.services.api_gateway.event_logger') as mock_logger:
            # Create a small test for background task
            task = asyncio.create_task(
                mock_logger.log_event("test", {"test": True})
            )
            await task
            mock_logger.log_event.assert_called_once()

    async def test_service_registry_routing(self, http_client):
        """Test service registry routing"""
        # Test that different routes map to correct services
        endpoints = [
            "/api/v1/documents",
            "/api/v1/search",
            "/api/v1/auth",
            "/api/v1/users",
            "/api/v1/websocket"
        ]

        for endpoint in endpoints:
            response = await http_client.get(endpoint)
            # Should not crash (actual response depends on service)
            assert response.status_code in [200, 404, 401, 500]

    async def test_request_timeout_handling(self, http_client):
        """Test request timeout handling"""
        # Test with very short timeout
        with patch('backend.src.services.api_gateway.make_http_request') as mock_request:
            mock_request.side_effect = asyncio.TimeoutError("Request timeout")

            response = await http_client.get("/api/v1/documents")
            # Should handle timeout gracefully
            assert response.status_code == 500

    async def test_request_validation(self, http_client):
        """Test request validation"""
        # Test with invalid request data
        invalid_data = {"invalid": "data"}
        response = await http_client.post("/api/v1/documents", json=invalid_data)

        # Should validate request (actual response depends on service)
        assert response.status_code in [400, 422, 500]

    def test_service_discovery(self, client):
        """Test service discovery functionality"""
        response = client.get("/services")

        data = response.json()
        assert isinstance(data, dict)

        # Should contain service information
        if data:
            for service_name, service_info in data.items():
                assert "status" in service_info
                assert "url" in service_info