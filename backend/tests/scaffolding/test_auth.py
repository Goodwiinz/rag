"""
Tests for authentication API endpoints.

Tests cover registration, login (with dual-layer rate limiting),
token refresh, and remember-me extended sessions.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.core.dependencies import get_current_user
from src.core.database import get_db
from src.services.security.auth_service import (
    AuthService,
    AuthenticationError,
    RegistrationError,
    get_auth_service,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user(**overrides):
    """Return a Mock that behaves like a User ORM instance."""
    user = Mock()
    user.id = overrides.get("id", "user-id-1234")
    user.email = overrides.get("email", "new@example.com")
    user.first_name = overrides.get("first_name", "New")
    user.last_name = overrides.get("last_name", "User")
    user.role = Mock(value=overrides.get("role", "admin"))
    user.organization_id = overrides.get("organization_id", "org-id-1")
    user.is_active = True
    user.is_deleted = False
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    user.to_dict = Mock(return_value={
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role.value,
        "organization_id": str(user.organization_id),
        "is_active": user.is_active,
    })
    return user


def _make_login_token_data(remember_me=False):
    """Return a dict matching AuthService.login_user output."""
    return {
        "access_token": "access.jwt.token",
        "refresh_token": "refresh.jwt.token",
        "token_type": "bearer",
        "expires_in": 1800,
        "refresh_expires_in": 2592000 if remember_me else 604800,
        "remember_me": remember_me,
        "user": {
            "id": "user-id-1234",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "role": "user",
        },
        "organization": None,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_auth_service():
    """Create a mock AuthService with async methods."""
    svc = AsyncMock(spec=AuthService)
    return svc


@pytest.fixture()
def client(mock_auth_service):
    """
    Create a TestClient with dependency overrides so that:
      - get_auth_service  -> mock_auth_service
      - get_db            -> a no-op async generator
      - get_current_user  -> not overridden here (only needed for protected routes)
    The lifespan is replaced with a no-op to avoid DB/Redis startup.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _no_lifespan(_app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _no_lifespan

    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
    app.dependency_overrides[get_db] = _fake_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# Registration Tests
# ---------------------------------------------------------------------------

class TestRegister:
    """Tests for POST /api/v1/auth/register"""

    @patch("src.api.auth.auth.auth_rate_limiter")
    def test_register_success(self, mock_limiter, client, mock_auth_service):
        """Successful registration returns 200 with user data."""
        mock_limiter.is_allowed.return_value = True

        mock_user = _make_mock_user()
        mock_auth_service.register_user.return_value = mock_user

        response = client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "StrongPassword123!",
            "first_name": "New",
            "last_name": "User",
            "organization_name": "New Org",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "User registered successfully"
        assert "user" in data
        assert data["user"]["email"] == "new@example.com"

        mock_auth_service.register_user.assert_awaited_once()

    @patch("src.api.auth.auth.auth_rate_limiter")
    def test_register_rate_limited(self, mock_limiter, client, mock_auth_service):
        """Rate limiter rejection returns 429."""
        mock_limiter.is_allowed.return_value = False

        response = client.post("/api/v1/auth/register", json={
            "email": "spam@example.com",
            "password": "StrongPassword123!",
            "first_name": "Spam",
            "last_name": "Bot",
            "organization_name": "Spam Org",
        })

        assert response.status_code == 429
        # Custom exception handler wraps errors as {"error": {"message": ...}}
        assert "Too many registration attempts" in response.json()["error"]["message"]
        mock_auth_service.register_user.assert_not_awaited()


# ---------------------------------------------------------------------------
# Login Tests
# ---------------------------------------------------------------------------

class TestLogin:
    """Tests for POST /api/v1/auth/login"""

    @patch("src.api.auth.auth.auth_rate_limiter")
    def test_login_success(self, mock_limiter, client, mock_auth_service):
        """Valid credentials return tokens and user info."""
        mock_limiter.is_allowed.return_value = True

        token_data = _make_login_token_data(remember_me=False)
        mock_auth_service.login_user.return_value = token_data

        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "CorrectPassword1!",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access.jwt.token"
        assert data["refresh_token"] == "refresh.jwt.token"
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["remember_me"] is False

        mock_auth_service.login_user.assert_awaited_once_with(
            email="test@example.com",
            password="CorrectPassword1!",
            remember_me=False,
        )

    @patch("src.api.auth.auth.auth_rate_limiter")
    def test_login_invalid_credentials(self, mock_limiter, client, mock_auth_service):
        """AuthService raising exception returns 401."""
        mock_limiter.is_allowed.return_value = True

        mock_auth_service.login_user.side_effect = AuthenticationError(
            "Invalid email or password"
        )

        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPassword",
        })

        assert response.status_code == 401
        # Custom exception handler wraps errors as {"error": {"message": ...}}
        assert "Invalid email or password" in response.json()["error"]["message"]

    @patch("src.api.auth.auth.auth_rate_limiter")
    def test_login_ip_rate_limited(self, mock_limiter, client, mock_auth_service):
        """IP-level rate limit rejection returns 429."""
        # First call (ip prefix) returns False -> blocked
        mock_limiter.is_allowed.return_value = False

        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "SomePassword1!",
        })

        assert response.status_code == 429
        # Custom exception handler wraps errors as {"error": {"message": ...}}
        assert "Too many login attempts from this IP" in response.json()["error"]["message"]
        mock_auth_service.login_user.assert_not_awaited()

    @patch("src.api.auth.auth.auth_rate_limiter")
    def test_login_email_rate_limited(self, mock_limiter, client, mock_auth_service):
        """IP passes but email-level rate limit fails -> 429."""
        # is_allowed is called twice: first with prefix="ip", then prefix="email"
        mock_limiter.is_allowed.side_effect = lambda identifier, prefix="": (
            True if prefix == "ip" else False
        )

        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "SomePassword1!",
        })

        assert response.status_code == 429
        # Custom exception handler wraps errors as {"error": {"message": ...}}
        assert "Too many login attempts for this account" in response.json()["error"]["message"]
        mock_auth_service.login_user.assert_not_awaited()

    @patch("src.api.auth.auth.auth_rate_limiter")
    def test_login_with_remember_me(self, mock_limiter, client, mock_auth_service):
        """remember_me=True returns extended refresh expiry."""
        mock_limiter.is_allowed.return_value = True

        token_data = _make_login_token_data(remember_me=True)
        mock_auth_service.login_user.return_value = token_data

        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "CorrectPassword1!",
            "remember_me": True,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["remember_me"] is True
        # 30-day refresh: 30 * 24 * 3600 = 2_592_000
        assert data["refresh_expires_in"] == 2592000

        mock_auth_service.login_user.assert_awaited_once_with(
            email="test@example.com",
            password="CorrectPassword1!",
            remember_me=True,
        )


# ---------------------------------------------------------------------------
# Token Refresh Tests
# ---------------------------------------------------------------------------

class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh"""

    def test_refresh_token(self, client, mock_auth_service):
        """Valid refresh token returns new access token."""
        mock_auth_service.refresh_access_token.return_value = {
            "access_token": "new.access.token",
            "token_type": "bearer",
            "expires_in": 1800,
            "remember_me": False,
            "refresh_token": "new.refresh.token",
            "refresh_expires_in": 604800,
        }

        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "old.refresh.token",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new.access.token"
        assert data["token_type"] == "bearer"

        mock_auth_service.refresh_access_token.assert_awaited_once_with(
            refresh_token="old.refresh.token"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
