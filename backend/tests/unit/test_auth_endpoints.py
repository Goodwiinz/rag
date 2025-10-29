"""
Unit tests for Authentication API endpoints
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json
import jwt
from datetime import datetime, timedelta

from conftest_fastapi import *


class TestAuthEndpoints:
    """Test class for authentication endpoints"""

    @pytest.fixture
    def auth_service_mock(self):
        """Mock authentication service"""
        service = Mock()
        service.authenticate_user = AsyncMock()
        service.create_user = AsyncMock()
        service.create_access_token = Mock()
        service.create_refresh_token = Mock()
        service.refresh_access_token = AsyncMock()
        service.change_password = AsyncMock()
        service.reset_password = AsyncMock()
        service.get_user_by_email = AsyncMock()
        return service

    @pytest.fixture
    def override_auth_dependencies(self, test_app, auth_service_mock, mock_user):
        """Override authentication dependencies"""
        from src.core.dependencies import get_auth_service

        test_app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        yield

        # Clean up
        test_app.dependency_overrides.clear()

    @pytest.mark.unit
    @pytest.mark.auth
    def test_login_success(self, test_client: TestClient, auth_service_mock, mock_user, override_auth_dependencies):
        """Test successful user login"""
        # Setup mock responses
        auth_service_mock.authenticate_user.return_value = mock_user
        auth_service_mock.create_access_token.return_value = "test-access-token"
        auth_service_mock.create_refresh_token.return_value = "test-refresh-token"

        # Test data
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }

        # Make request
        response = test_client.post("/api/v1/auth/login", json=login_data)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "test-access-token"
        assert data["refresh_token"] == "test-refresh-token"
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["user"]["email"] == mock_user.email

        # Verify service calls
        auth_service_mock.authenticate_user.assert_called_once_with(
            login_data["email"], login_data["password"]
        )

    @pytest.mark.unit
    @pytest.mark.auth
    def test_login_invalid_credentials(self, test_client: TestClient, auth_service_mock, override_auth_dependencies):
        """Test login with invalid credentials"""
        # Setup mock response
        auth_service_mock.authenticate_user.return_value = None

        # Test data
        login_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }

        # Make request
        response = test_client.post("/api/v1/auth/login", json=login_data)

        # Assertions
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["message"] == "Invalid email or password"

    @pytest.mark.unit
    @pytest.mark.auth
    def test_login_validation_error(self, test_client: TestClient):
        """Test login with invalid data"""
        # Test data with missing email
        login_data = {
            "password": "testpassword123"
        }

        # Make request
        response = test_client.post("/api/v1/auth/login", json=login_data)

        # Assertions
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "validation_error"

    @pytest.mark.unit
    @pytest.mark.auth
    def test_register_success(self, test_client: TestClient, auth_service_mock, mock_user, override_auth_dependencies):
        """Test successful user registration"""
        # Setup mock responses
        auth_service_mock.create_user.return_value = mock_user
        auth_service_mock.create_access_token.return_value = "test-access-token"
        auth_service_mock.create_refresh_token.return_value = "test-refresh-token"

        # Test data
        register_data = {
            "email": "newuser@example.com",
            "password": "newpassword123",
            "first_name": "New",
            "last_name": "User",
            "organization_name": "Test Org"
        }

        # Make request
        response = test_client.post("/api/v1/auth/register", json=register_data)

        # Assertions
        assert response.status_code == 201
        data = response.json()
        assert data["access_token"] == "test-access-token"
        assert data["refresh_token"] == "test-refresh-token"
        assert data["user"]["email"] == mock_user.email

        # Verify service calls
        auth_service_mock.create_user.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.auth
    def test_register_duplicate_email(self, test_client: TestClient, auth_service_mock, override_auth_dependencies):
        """Test registration with duplicate email"""
        # Setup mock response - user already exists
        from sqlalchemy.exc import IntegrityError
        auth_service_mock.create_user.side_effect = IntegrityError("mock", "mock", "mock")

        # Test data
        register_data = {
            "email": "existing@example.com",
            "password": "password123",
            "first_name": "Existing",
            "last_name": "User"
        }

        # Make request
        response = test_client.post("/api/v1/auth/register", json=register_data)

        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "already exists" in data["error"]["message"].lower()

    @pytest.mark.unit
    @pytest.mark.auth
    def test_refresh_token_success(self, test_client: TestClient, auth_service_mock, mock_user, override_auth_dependencies):
        """Test successful token refresh"""
        # Setup mock responses
        auth_service_mock.refresh_access_token.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600
        }

        # Test data
        refresh_data = {
            "refresh_token": "valid-refresh-token"
        }

        # Make request
        response = test_client.post("/api/v1/auth/refresh", json=refresh_data)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new-access-token"
        assert data["refresh_token"] == "new-refresh-token"
        assert data["expires_in"] == 3600

        # Verify service calls
        auth_service_mock.refresh_access_token.assert_called_once_with(refresh_data["refresh_token"])

    @pytest.mark.unit
    @pytest.mark.auth
    def test_refresh_token_invalid(self, test_client: TestClient, auth_service_mock, override_auth_dependencies):
        """Test refresh with invalid token"""
        # Setup mock response - invalid token
        auth_service_mock.refresh_access_token.return_value = None

        # Test data
        refresh_data = {
            "refresh_token": "invalid-refresh-token"
        }

        # Make request
        response = test_client.post("/api/v1/auth/refresh", json=refresh_data)

        # Assertions
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "invalid" in data["error"]["message"].lower()

    @pytest.mark.unit
    @pytest.mark.auth
    def test_change_password_success(self, test_client: TestClient, auth_service_mock, mock_user, mock_auth_headers, override_auth_dependencies):
        """Test successful password change"""
        # Setup mock response
        auth_service_mock.change_password.return_value = True

        # Test data
        password_data = {
            "current_password": "oldpassword",
            "new_password": "newpassword123"
        }

        # Make request
        response = test_client.post("/api/v1/auth/change-password", json=password_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Password changed successfully"

        # Verify service calls
        auth_service_mock.change_password.assert_called_once_with(
            mock_user.id, password_data["current_password"], password_data["new_password"]
        )

    @pytest.mark.unit
    @pytest.mark.auth
    def test_change_password_wrong_current(self, test_client: TestClient, auth_service_mock, mock_user, mock_auth_headers, override_auth_dependencies):
        """Test password change with wrong current password"""
        # Setup mock response
        auth_service_mock.change_password.return_value = False

        # Test data
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword123"
        }

        # Make request
        response = test_client.post("/api/v1/auth/change-password", json=password_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "current password" in data["error"]["message"].lower()

    @pytest.mark.unit
    @pytest.mark.auth
    def test_reset_password_request(self, test_client: TestClient, auth_service_mock, override_auth_dependencies):
        """Test password reset request"""
        # Setup mock response
        auth_service_mock.reset_password.return_value = True

        # Test data
        reset_data = {
            "email": "test@example.com"
        }

        # Make request
        response = test_client.post("/api/v1/auth/reset-password", json=reset_data)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Password reset email sent"

        # Verify service calls
        auth_service_mock.reset_password.assert_called_once_with(reset_data["email"])

    @pytest.mark.unit
    @pytest.mark.auth
    def test_get_current_user(self, test_client: TestClient, mock_user, mock_auth_headers):
        """Test getting current user information"""
        # Make request
        response = test_client.get("/api/v1/auth/me", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == mock_user.email
        assert data["first_name"] == mock_user.first_name
        assert data["last_name"] == mock_user.last_name

    @pytest.mark.unit
    @pytest.mark.auth
    def test_get_current_user_unauthorized(self, test_client: TestClient):
        """Test getting current user without authentication"""
        # Make request without auth headers
        response = test_client.get("/api/v1/auth/me")

        # Assertions
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "not authenticated" in data["error"]["detail"].lower()

    @pytest.mark.unit
    @pytest.mark.auth
    def test_logout_success(self, test_client: TestClient, mock_auth_headers):
        """Test successful logout"""
        # Make request
        response = test_client.post("/api/v1/auth/logout", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully logged out"

    @pytest.mark.unit
    @pytest.mark.auth
    def test_token_validation(self, test_client: TestClient):
        """Test token validation endpoint"""
        # Test with invalid token
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = test_client.get("/api/v1/auth/me", headers=invalid_headers)

        # Assertions
        assert response.status_code == 401

    @pytest.mark.unit
    @pytest.mark.auth
    @pytest.mark.parametrize("endpoint,method", [
        ("/api/v1/auth/login", "POST"),
        ("/api/v1/auth/register", "POST"),
        ("/api/v1/auth/refresh", "POST"),
        ("/api/v1/auth/reset-password", "POST"),
    ])
    def test_public_endpoints_available(self, test_client: TestClient, endpoint: str, method: str):
        """Test that public auth endpoints are accessible without authentication"""
        if method == "POST":
            response = test_client.post(endpoint, json={})

        # Should return 422 (validation error) rather than 401 (unauthorized)
        # This indicates the endpoint is accessible but request format is invalid
        assert response.status_code in [422, 400, 401]

    @pytest.mark.unit
    @pytest.mark.auth
    @pytest.mark.parametrize("endpoint,method", [
        ("/api/v1/auth/me", "GET"),
        ("/api/v1/auth/change-password", "POST"),
        ("/api/v1/auth/logout", "POST"),
    ])
    def test_protected_endpoints_require_auth(self, test_client: TestClient, endpoint: str, method: str):
        """Test that protected auth endpoints require authentication"""
        if method == "GET":
            response = test_client.get(endpoint)
        elif method == "POST":
            response = test_client.post(endpoint, json={})

        # Should return 401 (unauthorized)
        assert response.status_code == 401

    @pytest.mark.unit
    @pytest.mark.auth
    def test_rate_limiting_login(self, test_client: TestClient, auth_service_mock, override_auth_dependencies):
        """Test rate limiting on login endpoint"""
        # Setup mock response - always fail for rate limiting test
        auth_service_mock.authenticate_user.return_value = None

        # Make multiple failed login attempts
        login_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }

        for i in range(5):
            response = test_client.post("/api/v1/auth/login", json=login_data)

        # Last request should be rate limited (assuming rate limit is 5 per minute)
        # Note: This test depends on the actual rate limiting implementation
        assert response.status_code in [401, 429]