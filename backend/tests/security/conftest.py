"""
Pytest configuration and fixtures for security tests.
"""

import pytest
import jwt
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass
import httpx
from httpx import AsyncClient


@dataclass
class TestConfig:
    """Security testing configuration"""
    base_url: str = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
    api_prefix: str = "/api/v1"
    search_endpoint: str = "/search"
    auth_endpoint: str = "/auth"
    timeout: int = 30
    max_retries: int = 3
    jwt_secret: str = os.environ.get("JWT_SECRET", "test_secret_for_testing_only")
    jwt_algorithm: str = "HS256"


@dataclass
class TestUser:
    """Test user credentials and tokens"""
    id: str
    email: str
    password: str
    role: str
    organization_id: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    api_key: Optional[str] = None


def generate_test_token(
    user_id: str,
    role: str = "user",
    organization_id: str = "test-org",
    expired: bool = False,
    secret: str = "test_secret_for_testing_only",
    algorithm: str = "HS256"
) -> str:
    """Generate a test JWT token"""
    now = datetime.utcnow()
    
    if expired:
        exp = now - timedelta(hours=1)
    else:
        exp = now + timedelta(hours=1)
    
    payload = {
        "sub": user_id,
        "role": role,
        "org_id": organization_id,
        "iat": now,
        "exp": exp,
        "type": "access"
    }
    
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
def test_config():
    """Pytest fixture for test configuration"""
    return TestConfig()


@pytest.fixture
async def async_client(test_config):
    """Pytest fixture for async HTTP client"""
    async with AsyncClient(base_url=test_config.base_url, timeout=test_config.timeout) as client:
        yield client


@pytest.fixture
def sync_client(test_config):
    """Pytest fixture for sync HTTP client"""
    with httpx.Client(base_url=test_config.base_url, timeout=test_config.timeout) as client:
        yield client


@pytest.fixture
def test_users(test_config):
    """Pytest fixture for test users with tokens"""
    users = {
        "user": TestUser(
            id="test-user-1",
            email="user@test.com",
            password="UserPassword123!",
            role="user",
            organization_id="org-1"
        ),
        "admin": TestUser(
            id="test-admin-1",
            email="admin@test.com",
            password="AdminPassword123!",
            role="admin",
            organization_id="org-1"
        ),
        "analyst": TestUser(
            id="test-analyst-1",
            email="analyst@test.com",
            password="AnalystPassword123!",
            role="analyst",
            organization_id="org-1"
        ),
        "other_org_user": TestUser(
            id="test-user-2",
            email="other@test.com",
            password="OtherPassword123!",
            role="user",
            organization_id="org-2"
        )
    }
    
    # Generate tokens for each user
    for name, user in users.items():
        user.access_token = generate_test_token(
            user_id=user.id,
            role=user.role,
            organization_id=user.organization_id,
            secret=test_config.jwt_secret,
            algorithm=test_config.jwt_algorithm
        )
    
    return users


@pytest.fixture
def expired_token(test_config):
    """Pytest fixture for expired token"""
    return generate_test_token(
        user_id="test-user-expired",
        role="user",
        organization_id="org-1",
        expired=True,
        secret=test_config.jwt_secret,
        algorithm=test_config.jwt_algorithm
    )


@pytest.fixture
def invalid_tokens():
    """Pytest fixture for various invalid tokens"""
    return [
        "",  # Empty token
        "invalid_token",  # Random string
        "Bearer invalid_token",  # With Bearer prefix
        "JWT_REDACTED",
        "a" * 1000,  # Very long token
        "null",
        "undefined",
        "\x00\x00\x00",  # Null bytes
    ]


@pytest.fixture
def sql_injection_payloads():
    """Pytest fixture for SQL injection payloads"""
    return [
        "'; DROP TABLE documents; --",
        "' OR '1'='1",
        "1' OR '1'='1' --",
        "1; SELECT * FROM users; --",
        "' UNION SELECT username, password FROM users --",
        "'; WAITFOR DELAY '0:0:5' --",
        "1' AND SLEEP(5) --",
        "'; pg_sleep(5); --",
    ]


@pytest.fixture
def xss_payloads():
    """Pytest fixture for XSS payloads"""
    return [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "%3Cscript%3Ealert('XSS')%3C/script%3E",
    ]


@pytest.fixture
def command_injection_payloads():
    """Pytest fixture for command injection payloads"""
    return [
        "; ls -la",
        "| cat /etc/passwd",
        "& whoami",
        "`id`",
        "$(cat /etc/passwd)",
    ]


# Markers for categorizing tests
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "security: security-related tests")
    config.addinivalue_line("markers", "input_validation: input validation tests")
    config.addinivalue_line("markers", "authentication: authentication tests")
    config.addinivalue_line("markers", "authorization: authorization tests")
    config.addinivalue_line("markers", "rate_limiting: rate limiting tests")
    config.addinivalue_line("markers", "error_handling: error handling tests")
    config.addinivalue_line("markers", "logging: logging and auditing tests")
    config.addinivalue_line("markers", "slow: tests that are slow to run")
    config.addinivalue_line("markers", "integration: tests requiring live server")
