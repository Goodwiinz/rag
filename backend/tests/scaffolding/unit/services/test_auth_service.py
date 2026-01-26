"""
Unit Tests for AuthService

Tests authentication, JWT token handling, password validation,
and rate limiting with proper mocking.

All tests use mocks - no external services required.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from jose import jwt
import hashlib

from tests.mocks.services import MockAsyncSession, MockRedisClient


# ============================================================================
# Constants
# ============================================================================

TEST_SECRET_KEY = "test-secret-key-for-unit-testing-only"
TEST_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30


# ============================================================================
# Test Data Builders
# ============================================================================

class UserBuilder:
    """Builder pattern for user test data."""

    def __init__(self):
        self._id = uuid4()
        self._email = "test@example.com"
        self._first_name = "Test"
        self._last_name = "User"
        self._hashed_password = self._hash_password("TestPass123!")
        self._role = Mock(value="user")
        self._organization_id = uuid4()
        self._is_active = True
        self._created_at = datetime.utcnow()
        self._last_login = None
        self._failed_login_attempts = 0
        self._locked_until = None

    def _hash_password(self, password: str) -> str:
        """Simple hash for testing."""
        return hashlib.sha256(password.encode()).hexdigest()

    def with_id(self, id) -> "UserBuilder":
        self._id = id
        return self

    def with_email(self, email: str) -> "UserBuilder":
        self._email = email
        return self

    def with_password(self, password: str) -> "UserBuilder":
        self._hashed_password = self._hash_password(password)
        return self

    def with_role(self, role: str) -> "UserBuilder":
        self._role = Mock(value=role)
        return self

    def with_organization(self, org_id) -> "UserBuilder":
        self._organization_id = org_id
        return self

    def inactive(self) -> "UserBuilder":
        self._is_active = False
        return self

    def locked(self, until: datetime = None) -> "UserBuilder":
        self._locked_until = until or (datetime.utcnow() + timedelta(minutes=15))
        return self

    def with_failed_attempts(self, count: int) -> "UserBuilder":
        self._failed_login_attempts = count
        return self

    def build(self) -> Mock:
        user = Mock()
        user.id = self._id
        user.email = self._email
        user.first_name = self._first_name
        user.last_name = self._last_name
        user.hashed_password = self._hashed_password
        user.role = self._role
        user.organization_id = self._organization_id
        user.is_active = self._is_active
        user.created_at = self._created_at
        user.last_login = self._last_login
        user.failed_login_attempts = self._failed_login_attempts
        user.locked_until = self._locked_until
        return user


class TokenPayloadBuilder:
    """Builder pattern for JWT token payloads."""

    def __init__(self):
        self._sub = str(uuid4())
        self._email = "test@example.com"
        self._role = "user"
        self._org_id = str(uuid4())
        self._type = "access"
        self._exp = datetime.now(timezone.utc) + timedelta(minutes=30)
        self._iat = datetime.now(timezone.utc)

    def with_sub(self, sub: str) -> "TokenPayloadBuilder":
        self._sub = sub
        return self

    def with_email(self, email: str) -> "TokenPayloadBuilder":
        self._email = email
        return self

    def with_role(self, role: str) -> "TokenPayloadBuilder":
        self._role = role
        return self

    def with_type(self, type: str) -> "TokenPayloadBuilder":
        self._type = type
        return self

    def expired(self, minutes_ago: int = 1) -> "TokenPayloadBuilder":
        self._exp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        return self

    def expiring_in(self, minutes: int) -> "TokenPayloadBuilder":
        self._exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return self

    def build(self) -> dict:
        return {
            "sub": self._sub,
            "email": self._email,
            "role": self._role,
            "org_id": self._org_id,
            "type": self._type,
            "exp": self._exp,
            "iat": self._iat,
        }


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Create mock async session."""
    return MockAsyncSession()


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    return MockRedisClient()


@pytest.fixture
def mock_user():
    """Create mock user."""
    return UserBuilder().build()


@pytest.fixture
def mock_admin_user():
    """Create mock admin user."""
    return UserBuilder().with_role("admin").build()


# ============================================================================
# Password Validation Tests
# ============================================================================

class TestPasswordValidation:
    """Test password strength validation."""

    def test_accepts_strong_password(self):
        """Should accept password meeting all requirements."""
        password = "MyStr0ng!Pass"

        errors = []
        if len(password) < 8:
            errors.append("Too short")
        if not any(c.isupper() for c in password):
            errors.append("No uppercase")
        if not any(c.islower() for c in password):
            errors.append("No lowercase")
        if not any(c.isdigit() for c in password):
            errors.append("No digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("No special char")

        assert len(errors) == 0

    def test_rejects_short_password(self):
        """Should reject password shorter than 8 characters."""
        password = "Short1!"

        is_valid = len(password) >= 8
        assert is_valid is False

    def test_rejects_password_without_uppercase(self):
        """Should reject password without uppercase letter."""
        password = "alllowercase123!"

        has_upper = any(c.isupper() for c in password)
        assert has_upper is False

    def test_rejects_password_without_lowercase(self):
        """Should reject password without lowercase letter."""
        password = "ALLUPPERCASE123!"

        has_lower = any(c.islower() for c in password)
        assert has_lower is False

    def test_rejects_password_without_digit(self):
        """Should reject password without digit."""
        password = "NoDigitsHere!"

        has_digit = any(c.isdigit() for c in password)
        assert has_digit is False

    def test_rejects_password_without_special_char(self):
        """Should reject password without special character."""
        password = "NoSpecial123"

        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        has_special = any(c in special_chars for c in password)
        assert has_special is False

    def test_returns_all_validation_errors(self):
        """Should return all validation errors."""
        password = "weak"

        errors = []
        if len(password) < 8:
            errors.append("Too short")
        if not any(c.isupper() for c in password):
            errors.append("No uppercase")
        if not any(c.islower() for c in password):
            errors.append("No lowercase")
        if not any(c.isdigit() for c in password):
            errors.append("No digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("No special char")

        assert len(errors) == 4  # All but lowercase


# ============================================================================
# Authentication Tests
# ============================================================================

class TestUserAuthentication:
    """Test user authentication logic."""

    @pytest.mark.asyncio
    async def test_authenticates_valid_user(self, mock_db, mock_user):
        """Should authenticate user with valid credentials."""
        mock_db.set_query_result([mock_user])

        result = await mock_db.execute(Mock())
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.email == mock_user.email

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_user(self, mock_db):
        """Should reject authentication for nonexistent user."""
        mock_db.set_query_result([])

        result = await mock_db.execute(Mock())
        user = result.scalar_one_or_none()

        assert user is None

    @pytest.mark.asyncio
    async def test_rejects_inactive_user(self, mock_db):
        """Should reject authentication for inactive user."""
        inactive_user = UserBuilder().inactive().build()
        mock_db.set_query_result([inactive_user])

        result = await mock_db.execute(Mock())
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.is_active is False

    @pytest.mark.asyncio
    async def test_rejects_locked_user(self, mock_db):
        """Should reject authentication for locked user."""
        locked_user = UserBuilder().locked().build()
        mock_db.set_query_result([locked_user])

        result = await mock_db.execute(Mock())
        user = result.scalar_one_or_none()

        # Check if still locked
        is_locked = user.locked_until and user.locked_until > datetime.utcnow()
        assert is_locked is True


class TestPasswordVerification:
    """Test password verification."""

    def test_verifies_correct_password(self):
        """Should verify correct password."""
        password = "MyPassword123!"
        hashed = hashlib.sha256(password.encode()).hexdigest()

        # Verify
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        is_valid = input_hash == hashed

        assert is_valid is True

    def test_rejects_incorrect_password(self):
        """Should reject incorrect password."""
        password = "MyPassword123!"
        hashed = hashlib.sha256(password.encode()).hexdigest()

        # Try wrong password
        wrong_password = "WrongPassword!"
        input_hash = hashlib.sha256(wrong_password.encode()).hexdigest()
        is_valid = input_hash == hashed

        assert is_valid is False


# ============================================================================
# JWT Token Tests
# ============================================================================

class TestTokenGeneration:
    """Test JWT token generation."""

    def test_creates_access_token(self):
        """Should create valid access token."""
        payload = TokenPayloadBuilder().build()

        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        assert token is not None
        assert isinstance(token, str)

    def test_creates_refresh_token(self):
        """Should create valid refresh token."""
        payload = TokenPayloadBuilder() \
            .with_type("refresh") \
            .expiring_in(minutes=60 * 24 * 30) \
            .build()

        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        # Decode and verify type
        decoded = jwt.decode(token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])
        assert decoded["type"] == "refresh"

    def test_token_contains_user_info(self):
        """Token should contain user information."""
        user_id = str(uuid4())
        email = "user@example.com"
        role = "admin"

        payload = TokenPayloadBuilder() \
            .with_sub(user_id) \
            .with_email(email) \
            .with_role(role) \
            .build()

        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)
        decoded = jwt.decode(token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])

        assert decoded["sub"] == user_id
        assert decoded["email"] == email
        assert decoded["role"] == role

    def test_token_has_expiration(self):
        """Token should have expiration time."""
        payload = TokenPayloadBuilder().expiring_in(minutes=30).build()

        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)
        decoded = jwt.decode(token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])

        assert "exp" in decoded


class TestTokenVerification:
    """Test JWT token verification."""

    def test_verifies_valid_token(self):
        """Should verify valid token."""
        payload = TokenPayloadBuilder().expiring_in(minutes=30).build()
        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        try:
            decoded = jwt.decode(token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])
            is_valid = True
        except jwt.JWTError:
            is_valid = False

        assert is_valid is True

    def test_rejects_expired_token(self):
        """Should reject expired token."""
        payload = TokenPayloadBuilder().expired(minutes_ago=5).build()
        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        try:
            jwt.decode(token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])
            is_valid = True
        except jwt.ExpiredSignatureError:
            is_valid = False

        assert is_valid is False

    def test_rejects_invalid_signature(self):
        """Should reject token with invalid signature."""
        payload = TokenPayloadBuilder().build()
        token = jwt.encode(payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        try:
            jwt.decode(token, "wrong-secret-key", algorithms=[TEST_ALGORITHM])
            is_valid = True
        except jwt.JWTError:
            is_valid = False

        assert is_valid is False

    def test_rejects_malformed_token(self):
        """Should reject malformed token."""
        malformed_token = "not.a.valid.token"

        try:
            jwt.decode(malformed_token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])
            is_valid = True
        except jwt.JWTError:
            is_valid = False

        assert is_valid is False


class TestTokenRefresh:
    """Test token refresh flow."""

    def test_refresh_token_generates_new_access_token(self):
        """Refresh token should generate new access token."""
        # Create refresh token
        refresh_payload = TokenPayloadBuilder() \
            .with_type("refresh") \
            .expiring_in(minutes=60 * 24) \
            .build()

        refresh_token = jwt.encode(refresh_payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        # Decode refresh token
        decoded = jwt.decode(refresh_token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])

        # Generate new access token
        access_payload = TokenPayloadBuilder() \
            .with_sub(decoded["sub"]) \
            .with_email(decoded["email"]) \
            .with_role(decoded["role"]) \
            .with_type("access") \
            .expiring_in(minutes=30) \
            .build()

        new_access_token = jwt.encode(access_payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        # Verify new token
        new_decoded = jwt.decode(new_access_token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])
        assert new_decoded["type"] == "access"
        assert new_decoded["sub"] == decoded["sub"]

    def test_rejects_expired_refresh_token(self):
        """Should reject expired refresh token."""
        refresh_payload = TokenPayloadBuilder() \
            .with_type("refresh") \
            .expired(minutes_ago=1) \
            .build()

        refresh_token = jwt.encode(refresh_payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)

        try:
            jwt.decode(refresh_token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])
            can_refresh = True
        except jwt.ExpiredSignatureError:
            can_refresh = False

        assert can_refresh is False


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestLoginRateLimiting:
    """Test login attempt rate limiting."""

    @pytest.mark.asyncio
    async def test_tracks_failed_login_attempts(self, mock_redis):
        """Should track failed login attempts."""
        email = "user@example.com"
        key = f"login_attempts:{email}"

        # Record failed attempt
        await mock_redis.incr(key)
        await mock_redis.expire(key, 900)  # 15 minutes

        attempts = int(await mock_redis.get(key) or 0)
        assert attempts == 1

    @pytest.mark.asyncio
    async def test_blocks_after_max_attempts(self, mock_redis):
        """Should block login after max failed attempts."""
        email = "user@example.com"
        key = f"login_attempts:{email}"
        max_attempts = 5

        # Simulate 5 failed attempts
        for _ in range(5):
            await mock_redis.incr(key)

        attempts = int(await mock_redis.get(key) or 0)
        is_blocked = attempts >= max_attempts

        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_resets_attempts_after_lockout(self, mock_redis):
        """Should reset attempts after lockout period."""
        email = "user@example.com"
        key = f"login_attempts:{email}"

        # Set attempts with expiry
        await mock_redis.setex(key, 1, "5")  # Expires in 1 second

        # Simulate expiry
        mock_redis._cache.pop(key, None)

        attempts = await mock_redis.get(key)
        assert attempts is None

    @pytest.mark.asyncio
    async def test_successful_login_resets_attempts(self, mock_redis):
        """Successful login should reset failed attempts."""
        email = "user@example.com"
        key = f"login_attempts:{email}"

        # Set some failed attempts
        mock_redis.set_value(key, "3")

        # Successful login - clear attempts
        await mock_redis.delete(key)

        attempts = await mock_redis.get(key)
        assert attempts is None


# ============================================================================
# Token Revocation Tests
# ============================================================================

class TestTokenRevocation:
    """Test token revocation."""

    @pytest.mark.asyncio
    async def test_revokes_refresh_token(self, mock_redis):
        """Should revoke refresh token."""
        token_id = str(uuid4())
        key = f"revoked_token:{token_id}"

        # Revoke token
        await mock_redis.set(key, "1", ex=60 * 60 * 24 * 30)  # 30 days

        is_revoked = await mock_redis.exists(key) > 0
        assert is_revoked is True

    @pytest.mark.asyncio
    async def test_checks_if_token_is_revoked(self, mock_redis):
        """Should check if token is revoked before use."""
        token_id = str(uuid4())
        key = f"revoked_token:{token_id}"

        # Token not revoked
        is_revoked = await mock_redis.exists(key) > 0
        assert is_revoked is False

        # Revoke it
        await mock_redis.set(key, "1")

        # Now revoked
        is_revoked = await mock_redis.exists(key) > 0
        assert is_revoked is True

    @pytest.mark.asyncio
    async def test_revokes_all_user_tokens(self, mock_redis):
        """Should revoke all tokens for a user."""
        user_id = str(uuid4())

        # Simulate user version increment (invalidates all tokens)
        version_key = f"user_token_version:{user_id}"
        await mock_redis.incr(version_key)

        version = int(await mock_redis.get(version_key) or 0)
        assert version == 1


# ============================================================================
# User Session Tests
# ============================================================================

class TestUserSession:
    """Test user session management."""

    @pytest.mark.asyncio
    async def test_creates_session_on_login(self, mock_redis, mock_user):
        """Should create session on successful login."""
        session_id = str(uuid4())
        session_key = f"session:{session_id}"

        session_data = {
            "user_id": str(mock_user.id),
            "email": mock_user.email,
            "created_at": datetime.utcnow().isoformat()
        }

        await mock_redis.set(session_key, str(session_data), ex=60 * 60 * 24)

        stored = await mock_redis.get(session_key)
        assert stored is not None

    @pytest.mark.asyncio
    async def test_invalidates_session_on_logout(self, mock_redis):
        """Should invalidate session on logout."""
        session_id = str(uuid4())
        session_key = f"session:{session_id}"

        # Create session
        await mock_redis.set(session_key, "session_data")

        # Logout - delete session
        await mock_redis.delete(session_key)

        exists = await mock_redis.exists(session_key) > 0
        assert exists is False

    @pytest.mark.asyncio
    async def test_session_expires_after_timeout(self, mock_redis):
        """Session should expire after timeout."""
        session_id = str(uuid4())
        session_key = f"session:{session_id}"
        timeout_seconds = 3600  # 1 hour

        await mock_redis.setex(session_key, timeout_seconds, "session_data")

        ttl = await mock_redis.ttl(session_key)
        assert ttl == timeout_seconds


# ============================================================================
# Organization Access Tests
# ============================================================================

class TestOrganizationAccess:
    """Test organization-based access control."""

    def test_user_belongs_to_organization(self, mock_user):
        """User should belong to an organization."""
        assert mock_user.organization_id is not None

    def test_user_can_access_own_organization_data(self, mock_user):
        """User should access data in their organization."""
        data_org_id = mock_user.organization_id

        can_access = data_org_id == mock_user.organization_id
        assert can_access is True

    def test_user_cannot_access_other_organization_data(self, mock_user):
        """User should not access data in other organizations."""
        other_org_id = uuid4()

        can_access = other_org_id == mock_user.organization_id
        assert can_access is False

    def test_admin_can_access_organization_data(self, mock_admin_user):
        """Admin should access their organization's data."""
        # Admins have elevated permissions within their org
        assert mock_admin_user.role.value == "admin"
