import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.auth.auth import router as auth_router, get_auth_service

@pytest.fixture
def test_client():
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    return TestClient(app)

def test_password_reset_rate_limit_check(test_client):
    """
    Test that the password reset endpoint checks for rate limits.
    """
    # Create the test client from the fixture
    # Note: test_client is an instance of TestClient, not a callable,
    # but the fixture returns it. We need access to the underlying app to set overrides.
    app = test_client.app

    # Mock the auth service (async)
    mock_service = AsyncMock()
    mock_service.initiate_password_reset.return_value = "reset-token"

    # Override the dependency
    app.dependency_overrides[get_auth_service] = lambda: mock_service

    try:
        # We patch the auth_rate_limiter imported in src.api.auth.auth
        with patch("src.api.auth.auth.auth_rate_limiter") as mock_limiter:
            # Mock is_allowed to return True so the request proceeds (async)
            mock_limiter.is_allowed = AsyncMock(return_value=True)

            # Make the request
            response = test_client.post(
                "/api/v1/auth/reset-password",
                json={"email": "victim@example.com"}
            )

            # Ensure the request succeeded
            assert response.status_code == 200

            # Verify that rate limiter was checked
            mock_limiter.is_allowed.assert_called()
    finally:
        # Clean up overrides
        app.dependency_overrides = {}
