"""
Test constants and configuration
Centralized test secrets and configuration to avoid hardcoded values
"""

import os

# JWT secret for test token generation
TEST_JWT_SECRET = os.environ.get("TEST_JWT_SECRET", "test-jwt-secret-key-for-testing-only")

# JWT algorithm for tests
TEST_JWT_ALGORITHM = "HS256"

# Test API keys
TEST_API_KEY = os.environ.get("TEST_API_KEY", "test-api-key-12345")

# Test user passwords (for test fixtures only)
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "test-password-not-for-production")

# Test organization configuration
TEST_ORG_ID = "test-org-id"
TEST_USER_ID = "test-user-id"

# Test timeout configurations
TEST_TIMEOUT = 30.0
WS_TEST_TIMEOUT = 10.0
