import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel
from unittest.mock import AsyncMock, Mock, patch
from src.core.security import auth_rate_limiter, get_client_ip
from src.core.rate_limit import InMemoryRateLimiter

# Create a minimal app with a stub /login endpoint to test rate limiting
# without importing the full auth router (which has no login route since
# Supabase handles authentication externally).
app = FastAPI()


class _LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/v1/auth/login")
async def _stub_login(body: _LoginRequest, request: Request):
    client_ip = get_client_ip(request)
    if not await auth_rate_limiter.is_allowed(client_ip, prefix="login"):
        raise HTTPException(status_code=429, detail="Too many requests")
    return {
        "access_token": "fake_token",
        "refresh_token": "fake_refresh",
        "token_type": "bearer",
        "expires_in": 3600,
        "refresh_expires_in": 86400,
        "remember_me": False,
        "user": {"id": "123", "email": body.email},
        "organization": None,
    }


client = TestClient(app)

@pytest.fixture
def mock_rate_limiter():
    # Force use of InMemoryRateLimiter to avoid Redis connection issues during tests
    # and ensure deterministic behavior.
    limiter = InMemoryRateLimiter(max_attempts=50, window_minutes=15)

    # Patch where the rate limiter is used by the stub login endpoint
    with patch("tests.security.test_auth_rate_limit.auth_rate_limiter", limiter):
        yield limiter

def test_login_rate_limit_enforces_ip_check(mock_rate_limiter):
    """
    Test that multiple login attempts from the same IP with DIFFERENT emails
    ARE blocked by the IP-based rate limiting.
    """
    # Use a specific IP for this test suite - simulated by TestClient default behavior
    # or by forcing a header if we had middleware.
    # Since we don't have X-Forwarded-For, it falls back to 'testclient' host.

    for i in range(60):
        email = f"user{i}@example.com"
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"}
        )

        if i < 50:
            assert response.status_code == 200, f"Request {i} failed with {response.status_code}"
        else:
            assert response.status_code == 429, f"Request {i} should have been blocked"

def test_get_client_ip():
    """Test IP extraction logic"""
    # Case 1: No proxy header
    req = Mock(spec=Request)
    req.headers = {}
    req.client.host = "1.2.3.4"
    assert get_client_ip(req) == "1.2.3.4"

    # Case 2: X-Forwarded-For present (single proxy)
    req.headers = {"X-Forwarded-For": "5.6.7.8"}
    assert get_client_ip(req) == "5.6.7.8"

    # Case 3: X-Forwarded-For present (multiple proxies)
    req.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
    assert get_client_ip(req) == "10.0.0.2"

    # Case 4: Spoofing attempt (taking last IP)
    req.headers = {"X-Forwarded-For": "spoofed_ip, real_ip"}
    assert get_client_ip(req) == "real_ip"

def test_login_rate_limit_respects_x_forwarded_for(mock_rate_limiter):
    """
    Test that requests with different X-Forwarded-For headers are treated as different IPs.
    """
    blocked_count = 0

    for i in range(60):
        email = f"user{i}@example.com"
        # Simulate different users behind a proxy
        headers = {"X-Forwarded-For": f"10.0.0.{i}"}

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"},
            headers=headers
        )

        if response.status_code == 429:
            blocked_count += 1

    assert blocked_count == 0, f"Expected 0 blocked requests, got {blocked_count}"
