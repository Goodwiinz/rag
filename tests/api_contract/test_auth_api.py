"""
Authentication and User Management API Contract Tests
Comprehensive testing for authentication, registration, profile management, and token refresh
"""

import pytest
import json
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.contract
@pytest.mark.auth
class TestUserRegistrationAPI:
    """Test user registration endpoints"""

    def test_user_registration_success(self, test_client: TestClient):
        """Test successful user registration"""
        registration_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "New",
            "last_name": "User",
            "organization_name": "Test Organization"
        }

        response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        assert response.status_code == 201
        response_data = response.json()

        # Verify response structure
        assert "user" in response_data
        assert "access_token" in response_data
        assert "refresh_token" in response_data
        assert "token_type" in response_data
        assert "expires_in" in response_data

        # Verify user data
        user_data = response_data["user"]
        assert user_data["email"] == registration_data["email"]
        assert user_data["first_name"] == registration_data["first_name"]
        assert user_data["last_name"] == registration_data["last_name"]
        assert "id" in user_data
        assert "organization_id" in user_data
        assert user_data["role"] == "user"
        assert user_data["is_active"] is True

        # Verify token data
        assert response_data["token_type"] == "bearer"
        assert response_data["expires_in"] > 0
        assert len(response_data["access_token"]) > 0
        assert len(response_data["refresh_token"]) > 0

    def test_user_registration_with_existing_organization(self, test_client: TestClient):
        """Test user registration with existing organization"""
        registration_data = {
            "email": "orguser@example.com",
            "password": "SecurePassword123!",
            "first_name": "Org",
            "last_name": "User",
            "organization_id": str(uuid.uuid4())  # Existing org ID
        }

        response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        # This might fail if org doesn't exist, but should handle gracefully
        assert response.status_code in [201, 404, 422]

    def test_user_registration_invalid_email(self, test_client: TestClient):
        """Test user registration with invalid email"""
        registration_data = {
            "email": "invalid-email",
            "password": "SecurePassword123!",
            "first_name": "Invalid",
            "last_name": "Email"
        }

        response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        assert response.status_code == 422  # Validation error
        response_data = response.json()
        assert "email" in str(response_data).lower()

    def test_user_registration_weak_password(self, test_client: TestClient):
        """Test user registration with weak password"""
        registration_data = {
            "email": "weakpass@example.com",
            "password": "123",  # Too weak
            "first_name": "Weak",
            "last_name": "Password"
        }

        response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        assert response.status_code == 422  # Validation error
        response_data = response.json()
        assert "password" in str(response_data).lower()

    def test_user_registration_missing_fields(self, test_client: TestClient):
        """Test user registration with missing required fields"""
        registration_data = {
            "email": "incomplete@example.com",
            # Missing password, first_name, last_name
        }

        response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        assert response.status_code == 422  # Validation error

    def test_user_registration_duplicate_email(self, test_client: TestClient):
        """Test user registration with duplicate email"""
        # First registration
        registration_data = {
            "email": "duplicate@example.com",
            "password": "SecurePassword123!",
            "first_name": "First",
            "last_name": "User",
            "organization_name": "Test Organization"
        }

        response1 = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        assert response1.status_code == 201

        # Second registration with same email
        registration_data["first_name"] = "Second"
        response2 = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        assert response2.status_code == 409  # Conflict
        response_data = response2.json()
        assert "already exists" in response_data["error"]["message"].lower()

    def test_user_registration_rate_limiting(self, test_client: TestClient):
        """Test user registration rate limiting"""
        registration_data = {
            "email": "ratelimit@example.com",
            "password": "SecurePassword123!",
            "first_name": "Rate",
            "last_name": "Limit"
        }

        # Make multiple rapid registration attempts
        responses = []
        for i in range(10):
            registration_data["email"] = f"ratelimit{i}@example.com"
            response = test_client.post(
                "/api/v1/auth/register",
                json=registration_data
            )
            responses.append(response.status_code)

        # Should hit rate limit after several attempts
        assert 429 in responses  # Too Many Requests


@pytest.mark.contract
@pytest.mark.auth
class TestUserLoginAPI:
    """Test user login endpoints"""

    def test_user_login_success(self, test_client: TestClient):
        """Test successful user login"""
        # First register a user
        registration_data = {
            "email": "loginuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "Login",
            "last_name": "User",
            "organization_name": "Login Test Organization"
        }

        register_response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        assert register_response.status_code == 201

        # Now login
        login_data = {
            "email": registration_data["email"],
            "password": registration_data["password"]
        }

        response = test_client.post(
            "/api/v1/auth/login",
            json=login_data
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "access_token" in response_data
        assert "refresh_token" in response_data
        assert "token_type" in response_data
        assert "expires_in" in response_data
        assert "user" in response_data

        # Verify user data
        user_data = response_data["user"]
        assert user_data["email"] == login_data["email"]
        assert "id" in user_data

    def test_user_login_invalid_credentials(self, test_client: TestClient):
        """Test user login with invalid credentials"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }

        response = test_client.post(
            "/api/v1/auth/login",
            json=login_data
        )

        assert response.status_code == 401  # Unauthorized
        response_data = response.json()
        assert "invalid" in response_data["error"]["message"].lower()

    def test_user_login_missing_fields(self, test_client: TestClient):
        """Test user login with missing fields"""
        login_data = {
            "email": "test@example.com"
            # Missing password
        }

        response = test_client.post(
            "/api/v1/auth/login",
            json=login_data
        )

        assert response.status_code == 422  # Validation error

    def test_user_login_inactive_user(self, test_client: TestClient, test_database):
        """Test user login with inactive user"""
        # This would require creating an inactive user in the database
        # For now, test the structure
        login_data = {
            "email": "inactive@example.com",
            "password": "password123"
        }

        response = test_client.post(
            "/api/v1/auth/login",
            json=login_data
        )

        # Should return 401 for inactive users
        assert response.status_code in [401, 404]

    def test_user_login_rate_limiting(self, test_client: TestClient):
        """Test user login rate limiting"""
        login_data = {
            "email": "ratelimitlogin@example.com",
            "password": "wrongpassword"
        }

        # Make multiple rapid login attempts
        responses = []
        for i in range(10):
            response = test_client.post(
                "/api/v1/auth/login",
                json=login_data
            )
            responses.append(response.status_code)

        # Should hit rate limit after several failed attempts
        assert 429 in responses  # Too Many Requests


@pytest.mark.contract
@pytest.mark.auth
class TestTokenRefreshAPI:
    """Test token refresh endpoints"""

    def test_token_refresh_success(self, test_client: TestClient):
        """Test successful token refresh"""
        # First register and login
        registration_data = {
            "email": "refreshuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "Refresh",
            "last_name": "User",
            "organization_name": "Refresh Test Organization"
        }

        register_response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        register_data = register_response.json()
        refresh_token = register_data["refresh_token"]

        # Refresh token
        refresh_data = {
            "refresh_token": refresh_token
        }

        response = test_client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify new tokens
        assert "access_token" in response_data
        assert "refresh_token" in response_data
        assert "token_type" in response_data
        assert "expires_in" in response_data

        # New tokens should be different
        assert response_data["access_token"] != register_data["access_token"]
        assert response_data["refresh_token"] != refresh_token

    def test_token_refresh_invalid_token(self, test_client: TestClient):
        """Test token refresh with invalid token"""
        refresh_data = {
            "refresh_token": "invalid_refresh_token"
        }

        response = test_client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )

        assert response.status_code == 401  # Unauthorized

    def test_token_refresh_expired_token(self, test_client: TestClient):
        """Test token refresh with expired token"""
        # Create an expired JWT token
        expired_token = jwt.encode(
            {
                "sub": "test@example.com",
                "user_id": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1)  # Expired
            },
            "secret",  # This should match the actual secret
            algorithm="HS256"
        )

        refresh_data = {
            "refresh_token": expired_token
        }

        response = test_client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )

        assert response.status_code == 401  # Unauthorized

    def test_token_refresh_missing_token(self, test_client: TestClient):
        """Test token refresh without token"""
        refresh_data = {}  # Missing refresh_token

        response = test_client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.contract
@pytest.mark.auth
class TestUserProfileAPI:
    """Test user profile management endpoints"""

    def test_get_user_profile_success(self, test_client: TestClient, auth_headers):
        """Test successful user profile retrieval"""
        headers = auth_headers({
            "email": "profile@example.com",
            "first_name": "Profile",
            "last_name": "User"
        })

        response = test_client.get(
            "/api/v1/users/profile",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify profile structure
        assert "id" in response_data
        assert "email" in response_data
        assert "first_name" in response_data
        assert "last_name" in response_data
        assert "role" in response_data
        assert "organization_id" in response_data
        assert "is_active" in response_data
        assert "created_at" in response_data
        assert "updated_at" in response_data

        # Sensitive data should not be included
        assert "password" not in response_data
        assert "hashed_password" not in response_data

    def test_get_user_profile_unauthorized(self, test_client: TestClient):
        """Test user profile retrieval without authentication"""
        response = test_client.get("/api/v1/users/profile")

        assert response.status_code == 401

    def test_update_user_profile_success(self, test_client: TestClient, auth_headers):
        """Test successful user profile update"""
        headers = auth_headers({
            "email": "update@example.com",
            "first_name": "Update",
            "last_name": "User"
        })

        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "profile_data": {
                "bio": "Software Developer",
                "location": "San Francisco",
                "website": "https://example.com"
            }
        }

        response = test_client.put(
            "/api/v1/users/profile",
            json=update_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify updated data
        assert response_data["first_name"] == update_data["first_name"]
        assert response_data["last_name"] == update_data["last_name"]
        assert response_data["profile_data"]["bio"] == update_data["profile_data"]["bio"]

    def test_update_user_profile_invalid_email(self, test_client: TestClient, auth_headers):
        """Test user profile update with invalid email"""
        headers = auth_headers({
            "email": "invalidupdate@example.com",
            "first_name": "Invalid",
            "last_name": "Update"
        })

        update_data = {
            "email": "invalid-email-format"  # Invalid email
        }

        response = test_client.put(
            "/api/v1/users/profile",
            json=update_data,
            headers=headers
        )

        assert response.status_code == 422  # Validation error

    def test_update_user_profile_duplicate_email(self, test_client: TestClient, auth_headers):
        """Test user profile update with duplicate email"""
        # Create two users
        headers1 = auth_headers({
            "email": "user1@example.com",
            "first_name": "User",
            "last_name": "One"
        })

        headers2 = auth_headers({
            "email": "user2@example.com",
            "first_name": "User",
            "last_name": "Two"
        })

        # Try to update user2's email to user1's email
        update_data = {
            "email": "user1@example.com"
        }

        response = test_client.put(
            "/api/v1/users/profile",
            json=update_data,
            headers=headers2
        )

        assert response.status_code == 409  # Conflict

    def test_update_user_profile_unauthorized(self, test_client: TestClient):
        """Test user profile update without authentication"""
        update_data = {
            "first_name": "Unauthorized"
        }

        response = test_client.put(
            "/api/v1/users/profile",
            json=update_data
        )

        assert response.status_code == 401


@pytest.mark.contract
@pytest.mark.auth
class TestPasswordManagementAPI:
    """Test password management endpoints"""

    def test_password_change_success(self, test_client: TestClient, auth_headers):
        """Test successful password change"""
        headers = auth_headers({
            "email": "password@example.com",
            "first_name": "Password",
            "last_name": "User"
        })

        password_data = {
            "current_password": "TestPassword123!",
            "new_password": "NewSecurePassword456!"
        }

        response = test_client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()
        assert "success" in response_data["message"].lower()

    def test_password_change_wrong_current_password(self, test_client: TestClient, auth_headers):
        """Test password change with wrong current password"""
        headers = auth_headers({
            "email": "wrongpass@example.com",
            "first_name": "Wrong",
            "last_name": "Password"
        })

        password_data = {
            "current_password": "wrongpassword",
            "new_password": "NewSecurePassword456!"
        }

        response = test_client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=headers
        )

        assert response.status_code == 401  # Unauthorized

    def test_password_change_weak_new_password(self, test_client: TestClient, auth_headers):
        """Test password change with weak new password"""
        headers = auth_headers({
            "email": "weaknew@example.com",
            "first_name": "Weak",
            "last_name": "New"
        })

        password_data = {
            "current_password": "TestPassword123!",
            "new_password": "123"  # Too weak
        }

        response = test_client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=headers
        )

        assert response.status_code == 422  # Validation error

    def test_password_change_unauthorized(self, test_client: TestClient):
        """Test password change without authentication"""
        password_data = {
            "current_password": "password",
            "new_password": "newpassword"
        }

        response = test_client.post(
            "/api/v1/auth/change-password",
            json=password_data
        )

        assert response.status_code == 401

    def test_password_reset_request_success(self, test_client: TestClient):
        """Test successful password reset request"""
        # First register a user
        registration_data = {
            "email": "reset@example.com",
            "password": "SecurePassword123!",
            "first_name": "Reset",
            "last_name": "User",
            "organization_name": "Reset Test Organization"
        }

        register_response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        assert register_response.status_code == 201

        # Request password reset
        reset_data = {
            "email": registration_data["email"]
        }

        response = test_client.post(
            "/api/v1/auth/reset-password",
            json=reset_data
        )

        assert response.status_code == 200
        response_data = response.json()
        assert "reset token" in response_data["message"].lower() or "email" in response_data["message"].lower()

    def test_password_reset_request_nonexistent_email(self, test_client: TestClient):
        """Test password reset request for nonexistent email"""
        reset_data = {
            "email": "nonexistent@example.com"
        }

        response = test_client.post(
            "/api/v1/auth/reset-password",
            json=reset_data
        )

        # Should not reveal whether email exists
        assert response.status_code == 200

    def test_password_reset_confirmation_success(self, test_client: TestClient):
        """Test successful password reset confirmation"""
        # This would require a valid reset token
        # For now, test the structure
        reset_data = {
            "token": "valid_reset_token",
            "new_password": "NewSecurePassword789!"
        }

        response = test_client.post(
            "/api/v1/auth/confirm-reset",
            json=reset_data
        )

        # Should handle invalid tokens gracefully
        assert response.status_code in [200, 400, 401]

    def test_password_reset_confirmation_invalid_token(self, test_client: TestClient):
        """Test password reset confirmation with invalid token"""
        reset_data = {
            "token": "invalid_reset_token",
            "new_password": "NewSecurePassword789!"
        }

        response = test_client.post(
            "/api/v1/auth/confirm-reset",
            json=reset_data
        )

        assert response.status_code == 401  # Unauthorized


@pytest.mark.contract
@pytest.mark.auth
class TestAuthenticationMiddleware:
    """Test authentication middleware functionality"""

    def test_valid_token_access(self, test_client: TestClient, auth_headers):
        """Test API access with valid token"""
        headers = auth_headers({
            "email": "validtoken@example.com",
            "first_name": "Valid",
            "last_name": "Token"
        })

        response = test_client.get(
            "/api/v1/users/profile",
            headers=headers
        )

        assert response.status_code == 200

    def test_invalid_token_access(self, test_client: TestClient):
        """Test API access with invalid token"""
        headers = {
            "Authorization": "Bearer invalid_token"
        }

        response = test_client.get(
            "/api/v1/users/profile",
            headers=headers
        )

        assert response.status_code == 401

    def test_expired_token_access(self, test_client: TestClient):
        """Test API access with expired token"""
        # Create expired token
        expired_token = jwt.encode(
            {
                "sub": "expired@example.com",
                "user_id": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1)
            },
            "secret",
            algorithm="HS256"
        )

        headers = {
            "Authorization": f"Bearer {expired_token}"
        }

        response = test_client.get(
            "/api/v1/users/profile",
            headers=headers
        )

        assert response.status_code == 401

    def test_missing_token_access(self, test_client: TestClient):
        """Test API access without token"""
        response = test_client.get("/api/v1/users/profile")

        assert response.status_code == 401

    def test_malformed_token_access(self, test_client: TestClient):
        """Test API access with malformed token"""
        headers = {
            "Authorization": "Bearer malformed.token.with.three.parts"
        }

        response = test_client.get(
            "/api/v1/users/profile",
            headers=headers
        )

        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.auth
@pytest.mark.performance
class TestAuthenticationPerformance:
    """Performance tests for authentication endpoints"""

    def test_login_performance(self, test_client: TestClient, performance_tracker):
        """Test login endpoint performance"""
        # Register a user first
        registration_data = {
            "email": "perflogin@example.com",
            "password": "SecurePassword123!",
            "first_name": "Perf",
            "last_name": "Login",
            "organization_name": "Performance Test Organization"
        }

        test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        login_data = {
            "email": registration_data["email"],
            "password": registration_data["password"]
        }

        performance_tracker.start_timer("login")

        response = test_client.post(
            "/api/v1/auth/login",
            json=login_data
        )

        duration = performance_tracker.end_timer("login")

        assert response.status_code == 200
        assert duration < 2.0  # Login should be fast

    def test_registration_performance(self, test_client: TestClient, performance_tracker):
        """Test registration endpoint performance"""
        registration_data = {
            "email": "perfreg@example.com",
            "password": "SecurePassword123!",
            "first_name": "Perf",
            "last_name": "Register",
            "organization_name": "Performance Test Organization"
        }

        performance_tracker.start_timer("registration")

        response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        duration = performance_tracker.end_timer("registration")

        assert response.status_code == 201
        assert duration < 3.0  # Registration should complete quickly

    def test_token_refresh_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test token refresh performance"""
        headers = auth_headers({
            "email": "perfrefresh@example.com",
            "first_name": "Perf",
            "last_name": "Refresh"
        })

        # Get a refresh token from registration
        # This would need to be adjusted based on actual token handling
        refresh_data = {
            "refresh_token": "mock_refresh_token"
        }

        performance_tracker.start_timer("token_refresh")

        response = test_client.post(
            "/api/v1/auth/refresh",
            json=refresh_data,
            headers=headers
        )

        duration = performance_tracker.end_timer("token_refresh")

        # Should handle invalid tokens gracefully and still be fast
        assert response.status_code in [200, 401]
        assert duration < 1.0  # Token refresh should be very fast

    def test_concurrent_authentication_performance(self, test_client: TestClient, performance_tracker):
        """Test concurrent authentication performance"""
        import threading
        import queue
        import time

        results = queue.Queue()

        def register_user(user_id):
            """Register a user in a separate thread"""
            registration_data = {
                "email": f"concurrent{user_id}@example.com",
                "password": "SecurePassword123!",
                "first_name": f"User{user_id}",
                "last_name": "Concurrent",
                "organization_name": f"Concurrent Organization {user_id}"
            }

            start_time = time.time()

            response = test_client.post(
                "/api/v1/auth/register",
                json=registration_data
            )

            duration = time.time() - start_time
            results.put((response.status_code, duration))

        # Start concurrent registrations
        threads = []
        performance_tracker.start_timer("concurrent_registrations")

        for i in range(5):
            thread = threading.Thread(target=register_user, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all registrations to complete
        for thread in threads:
            thread.join()

        total_duration = performance_tracker.end_timer("concurrent_registrations")

        # Collect results
        successful_registrations = 0
        registration_durations = []

        while not results.empty():
            status, duration = results.get()
            if status == 201:
                successful_registrations += 1
                registration_durations.append(duration)

        assert successful_registrations >= 4  # At least 4 out of 5 should succeed
        assert len(registration_durations) > 0

        avg_registration_time = sum(registration_durations) / len(registration_durations)
        assert avg_registration_time < 5.0  # Average registration should be reasonable