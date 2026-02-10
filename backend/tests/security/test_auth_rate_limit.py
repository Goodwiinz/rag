import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from src.services.security.auth_service import AuthService, get_auth_service
from src.core.security import auth_rate_limiter
from src.api.auth.auth import router as auth_router

# Create a minimal app for testing to avoid importing src.main and its heavy dependencies
app = FastAPI()
app.include_router(auth_router, prefix="/api/v1")

client = TestClient(app)

# Mock AuthService
async def mock_login_user(email, password, remember_me=False):
    return {
        "access_token": "fake_token",
        "refresh_token": "fake_refresh",
        "token_type": "bearer",
        "expires_in": 3600,
        "refresh_expires_in": 86400,
        "remember_me": remember_me,
        "user": {"id": "123", "email": email},
        "organization": None
    }

mock_auth_service = AsyncMock(spec=AuthService)
mock_auth_service.login_user = AsyncMock(side_effect=mock_login_user)

def get_mock_auth_service():
    return mock_auth_service

app.dependency_overrides[get_auth_service] = get_mock_auth_service

def setup_function():
    # Reset rate limiter before each test
    auth_rate_limiter.attempts = {}

def test_login_rate_limit_enforces_ip_check():
    """
    Test that multiple login attempts from the same IP with DIFFERENT emails
    ARE blocked by the IP-based rate limiting.
    """

    # Configure rate limiter for the test to have a small limit
    # We can't easily change the global instance's max_attempts, so we'll rely on
    # checking if it blocks.
    # The default is 50 attempts in 15 minutes.

    # We'll use a specific IP
    client_ip = "192.168.1.100"

    # Try 60 attempts (more than default 50)
    for i in range(60):
        email = f"user{i}@example.com"
        # Starlette TestClient does not allow setting client host per request easily in methods
        # It uses 'testclient' by default.
        # However, passing headers might not affect request.client.host unless behind proxy middleware.
        # But we are testing the API logic.
        # If the API uses request.client.host, it will see 'testclient'.
        # Since all requests come from 'testclient', if IP rate limiting WAS enabled,
        # it would block after 50 requests.

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"}
        )

        # If the rate limiter ONLY checks email, then 60 requests with 60 different emails
        # should all be ALLOWED (status 200 because we mocked success).

        # If the rate limiter checked IP, then after 50 requests, it should be BLOCKED (429).

        if i < 50:
            assert response.status_code == 200, f"Request {i} failed with {response.status_code}"
        else:
            assert response.status_code == 429, f"Request {i} should have been blocked"

    print("Vulnerability fixed: requests blocked after limit.")
