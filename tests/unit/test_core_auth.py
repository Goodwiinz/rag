"""
Unit tests for Core Authentication Service
"""

import pytest
import jwt
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from src.services.core.auth import (
    User, decode_jwt_token, create_access_token,
    UserRateLimiter, rate_limiter
)


# Test configuration
TEST_JWT_SECRET = "test-jwt-secret-key-for-unit-testing"
TEST_JWT_ALGORITHM = "HS256"


class TestUserModel:
    """Test User model"""

    def test_user_creation(self):
        """Test creating a user"""
        user = User(
            id="user-123",
            email="test@example.com",
            tenant_id="tenant-123",
            role="analyst",
            permissions=["document_read", "document_create"]
        )
        
        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.tenant_id == "tenant-123"
        assert user.role == "analyst"
    
    def test_user_has_permission(self):
        """Test permission checking"""
        user = User(
            id="user-123",
            email="test@example.com",
            tenant_id="tenant-123",
            role="analyst",
            permissions=["document_read", "document_create"]
        )
        
        assert user.has_permission("document_read") == True
        assert user.has_permission("admin_access") == False
    
    def test_user_has_role(self):
        """Test role checking"""
        user = User(
            id="user-123",
            email="test@example.com",
            tenant_id="tenant-123",
            role="admin"
        )
        
        assert user.has_role("admin") == True
        assert user.has_role("viewer") == False


class TestJWTDecode:
    """Test JWT token decoding"""

    @pytest.mark.asyncio
    async def test_decode_valid_token(self):
        """Test decoding a valid token"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "tenant_id": "tenant-123",
            "role": "analyst",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)
        
        with patch('src.services.core.auth.config') as mock_config:
            mock_config.JWT_SECRET_KEY = TEST_JWT_SECRET
            mock_config.JWT_ALGORITHM = TEST_JWT_ALGORITHM
            
            result = await decode_jwt_token(token)
        
        assert result is not None
        assert result["sub"] == "user-123"
        assert result["tenant_id"] == "tenant-123"
    
    @pytest.mark.asyncio
    async def test_decode_expired_token(self):
        """Test decoding an expired token"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "tenant_id": "tenant-123",
            "exp": now - timedelta(hours=1),
            "iat": now - timedelta(hours=2),
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)
        
        with patch('src.services.core.auth.config') as mock_config:
            mock_config.JWT_SECRET_KEY = TEST_JWT_SECRET
            mock_config.JWT_ALGORITHM = TEST_JWT_ALGORITHM
            
            result = await decode_jwt_token(token)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_decode_invalid_token(self):
        """Test decoding an invalid token"""
        with patch('src.services.core.auth.config') as mock_config:
            mock_config.JWT_SECRET_KEY = TEST_JWT_SECRET
            mock_config.JWT_ALGORITHM = TEST_JWT_ALGORITHM
            
            result = await decode_jwt_token("invalid.token.here")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_decode_tampered_token(self):
        """Test decoding a tampered token"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "tenant_id": "tenant-123",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)
        tampered_token = token[:-10] + "tampered123"
        
        with patch('src.services.core.auth.config') as mock_config:
            mock_config.JWT_SECRET_KEY = TEST_JWT_SECRET
            mock_config.JWT_ALGORITHM = TEST_JWT_ALGORITHM
            
            result = await decode_jwt_token(tampered_token)
        
        assert result is None


class TestCreateAccessToken:
    """Test access token creation"""

    def test_create_token_with_default_expiry(self):
        """Test creating token with default expiry"""
        with patch('src.services.core.auth.config') as mock_config:
            mock_config.JWT_SECRET_KEY = TEST_JWT_SECRET
            mock_config.JWT_ALGORITHM = TEST_JWT_ALGORITHM
            mock_config.JWT_EXPIRE_MINUTES = 30
            
            data = {"sub": "user-123", "email": "test@example.com"}
            token = create_access_token(data)
        
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        assert decoded["sub"] == "user-123"
        assert "exp" in decoded
    
    def test_create_token_with_custom_expiry(self):
        """Test creating token with custom expiry"""
        with patch('src.services.core.auth.config') as mock_config:
            mock_config.JWT_SECRET_KEY = TEST_JWT_SECRET
            mock_config.JWT_ALGORITHM = TEST_JWT_ALGORITHM
            
            data = {"sub": "user-123"}
            expires = timedelta(hours=2)
            token = create_access_token(data, expires_delta=expires)
        
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        assert decoded["sub"] == "user-123"
        assert "exp" in decoded


class TestRateLimiter:
    """Test rate limiting"""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_limit(self):
        """Test requests under limit are allowed"""
        limiter = UserRateLimiter()
        
        # First 5 requests should be allowed
        for i in range(5):
            allowed = await limiter.is_allowed("user-123", limit=10, window=60)
            assert allowed == True
    
    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_limit(self):
        """Test requests over limit are blocked"""
        limiter = UserRateLimiter()
        
        # Make 5 requests with limit of 5
        for i in range(5):
            await limiter.is_allowed("user-123", limit=5, window=60)
        
        # 6th request should be blocked
        allowed = await limiter.is_allowed("user-123", limit=5, window=60)
        assert allowed == False
    
    @pytest.mark.asyncio
    async def test_rate_limit_per_user(self):
        """Test rate limit is per-user"""
        limiter = UserRateLimiter()
        
        # User 1 hits limit
        for i in range(5):
            await limiter.is_allowed("user-1", limit=5, window=60)
        
        # User 1 is blocked
        assert await limiter.is_allowed("user-1", limit=5, window=60) == False
        
        # User 2 is still allowed
        assert await limiter.is_allowed("user-2", limit=5, window=60) == True
    
    @pytest.mark.asyncio
    async def test_rate_limit_window_expires(self):
        """Test old requests are removed from window"""
        limiter = UserRateLimiter()
        
        # Make requests with very short window
        for i in range(5):
            await limiter.is_allowed("user-123", limit=5, window=1)
        
        # User should be blocked
        assert await limiter.is_allowed("user-123", limit=5, window=1) == False


class TestAuthEdgeCases:
    """Test authentication edge cases"""

    @pytest.mark.asyncio
    async def test_decode_token_with_wrong_secret(self):
        """Test decoding with wrong secret"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = jwt.encode(payload, "correct-secret", algorithm=TEST_JWT_ALGORITHM)
        
        with patch('src.services.core.auth.config') as mock_config:
            mock_config.JWT_SECRET_KEY = "wrong-secret"
            mock_config.JWT_ALGORITHM = TEST_JWT_ALGORITHM
            
            result = await decode_jwt_token(token)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_decode_token_with_missing_claims(self):
        """Test token with missing claims"""
        now = datetime.now(timezone.utc)
        payload = {
            "exp": now + timedelta(hours=1),
            "iat": now,
            # Missing sub
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)
        
        with patch('src.services.core.auth.config') as mock_config:
            mock_config.JWT_SECRET_KEY = TEST_JWT_SECRET
            mock_config.JWT_ALGORITHM = TEST_JWT_ALGORITHM
            
            result = await decode_jwt_token(token)
        
        assert result is not None
        assert "sub" not in result

    def test_user_no_permissions(self):
        """Test user with no permissions"""
        user = User(
            id="user-123",
            email="test@example.com",
            tenant_id="tenant-123",
            role="viewer"
        )
        
        assert user.permissions == []
        assert user.has_permission("anything") == False
    
    def test_user_default_role(self):
        """Test user default role"""
        user = User(
            id="user-123",
            email="test@example.com",
            tenant_id="tenant-123"
        )
        
        assert user.role == "user"
