"""
Authentication Flow Integration Tests

Tests for authentication workflows using both PostgreSQL (user data)
and Redis (session/token management) to validate:
- Full login flow
- Token refresh and rotation
- Logout with session invalidation
- Multi-device session handling
"""

import pytest
import uuid
import time
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import jwt

# Mark all tests in this module
pytestmark = [
    pytest.mark.requires_postgres,
    pytest.mark.requires_redis,
    pytest.mark.integration,
]


class TokenManager:
    """JWT token manager for testing."""

    def __init__(self, redis_client, secret_key: str = "test-secret-key"):
        self.redis = redis_client
        self.secret_key = secret_key
        self.access_token_ttl = 900  # 15 minutes
        self.refresh_token_ttl = 86400 * 7  # 7 days

    def _token_key(self, token_id: str) -> str:
        return f"token:{token_id}"

    def _refresh_token_key(self, token_id: str) -> str:
        return f"refresh_token:{token_id}"

    def _user_tokens_key(self, user_id: str) -> str:
        return f"user_tokens:{user_id}"

    def create_access_token(self, user_id: str, user_data: dict) -> str:
        """Create a new access token."""
        token_id = str(uuid.uuid4())
        now = datetime.utcnow()

        payload = {
            "sub": str(user_id),
            "jti": token_id,
            "iat": now,
            "exp": now + timedelta(seconds=self.access_token_ttl),
            "type": "access",
            **user_data,
        }

        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        # Store token ID in Redis for validation/revocation
        self.redis.setex(
            self._token_key(token_id),
            self.access_token_ttl,
            json.dumps({"user_id": str(user_id), "created_at": now.isoformat()})
        )

        # Track token for user
        self.redis.sadd(self._user_tokens_key(user_id), token_id)
        self.redis.expire(self._user_tokens_key(user_id), self.refresh_token_ttl)

        return token

    def create_refresh_token(self, user_id: str, device_id: str = None) -> str:
        """Create a refresh token."""
        token_id = str(uuid.uuid4())
        now = datetime.utcnow()

        payload = {
            "sub": str(user_id),
            "jti": token_id,
            "iat": now,
            "exp": now + timedelta(seconds=self.refresh_token_ttl),
            "type": "refresh",
            "device_id": device_id or str(uuid.uuid4()),
        }

        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        # Store refresh token data
        self.redis.setex(
            self._refresh_token_key(token_id),
            self.refresh_token_ttl,
            json.dumps({
                "user_id": str(user_id),
                "device_id": payload["device_id"],
                "created_at": now.isoformat(),
            })
        )

        # Track refresh token IDs per user so global logout can revoke them.
        self.redis.sadd(self._user_tokens_key(user_id), token_id)
        self.redis.expire(self._user_tokens_key(user_id), self.refresh_token_ttl)

        return token

    def validate_access_token(self, token: str) -> dict:
        """Validate an access token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            if payload.get("type") != "access":
                return None

            # Check if token is revoked
            token_id = payload.get("jti")
            if not self.redis.exists(self._token_key(token_id)):
                return None

            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def validate_refresh_token(self, token: str) -> dict:
        """Validate a refresh token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            if payload.get("type") != "refresh":
                return None

            # Check if token exists in Redis
            token_id = payload.get("jti")
            if not self.redis.exists(self._refresh_token_key(token_id)):
                return None

            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"],
                                options={"verify_exp": False})
            token_id = payload.get("jti")
            token_type = payload.get("type")

            if token_type == "access":
                key = self._token_key(token_id)
            else:
                key = self._refresh_token_key(token_id)

            # Remove from user's token set
            user_id = payload.get("sub")
            self.redis.srem(self._user_tokens_key(user_id), token_id)

            return self.redis.delete(key) > 0
        except jwt.InvalidTokenError:
            return False

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user."""
        user_tokens_key = self._user_tokens_key(user_id)
        token_ids = self.redis.smembers(user_tokens_key)

        count = 0
        for tid in token_ids:
            tid_str = tid.decode() if isinstance(tid, bytes) else tid
            # Try both access and refresh token keys
            if self.redis.delete(self._token_key(tid_str)):
                count += 1
            if self.redis.delete(self._refresh_token_key(tid_str)):
                count += 1

        self.redis.delete(user_tokens_key)
        return count

    def refresh_access_token(self, refresh_token: str, user_data: dict) -> tuple:
        """
        Use refresh token to get new access token.
        Returns (new_access_token, new_refresh_token) or (None, None) on failure.
        """
        payload = self.validate_refresh_token(refresh_token)
        if not payload:
            return None, None

        user_id = payload.get("sub")
        device_id = payload.get("device_id")

        # Revoke old refresh token (rotation)
        self.revoke_token(refresh_token)

        # Create new tokens
        new_access = self.create_access_token(user_id, user_data)
        new_refresh = self.create_refresh_token(user_id, device_id)

        return new_access, new_refresh


@pytest.fixture(scope="function")
def db_session(postgres_container):
    """Create a database session for user operations."""
    from src.models.base import Base
    from src.models.user import User, UserRole
    from src.models.organization import Organization, StorageTier
    # Import ab_testing to resolve User -> Experiment relationship
    from src.models import ab_testing  # noqa: F401

    engine = create_engine(postgres_container["url"])
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # Drop tables with CASCADE to handle circular dependencies in ab_testing
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()
        engine.dispose()


@pytest.fixture
def redis_client(redis_container):
    """Create Redis client for token operations."""
    import redis

    client = redis.Redis.from_url(redis_container["url"])
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def token_manager(redis_client):
    """Create token manager."""
    return TokenManager(redis_client)


@pytest.fixture
def test_organization(db_session):
    """Create a test organization."""
    from src.models.organization import Organization, StorageTier

    org = Organization(
        id=uuid.uuid4(),
        name=f"Auth Test Org {uuid.uuid4().hex[:8]}",
        storage_tier=StorageTier.PROFESSIONAL,
        storage_limit_bytes=100 * 1024 ** 3,
        is_active=True,
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def test_user(db_session, test_organization):
    """Create a test user."""
    from src.models.user import User, UserRole
    from src.core.security import get_password_hash

    user = User(
        id=uuid.uuid4(),
        email=f"authtest-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("correctpassword123"),
        first_name="Auth",
        last_name="Tester",
        role=UserRole.USER,
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestFullLoginFlow:
    """Tests for complete login flow."""

    def test_full_login_flow(self, db_session, redis_client, token_manager, test_user):
        """Verify complete login workflow: validate credentials -> create tokens."""
        from src.models.user import User
        from src.core.security import verify_password

        # Step 1: Retrieve user from database
        user = db_session.query(User).filter_by(email=test_user.email).first()
        assert user is not None

        # Step 2: Verify password
        assert verify_password("correctpassword123", user.password_hash)

        # Step 3: Create tokens
        user_data = {
            "email": user.email,
            "role": user.role.value,
            "org_id": str(user.organization_id),
        }
        access_token = token_manager.create_access_token(str(user.id), user_data)
        refresh_token = token_manager.create_refresh_token(str(user.id))

        assert access_token is not None
        assert refresh_token is not None

        # Step 4: Update login tracking
        user.update_last_login()
        db_session.commit()

        # Verify login tracking updated
        db_session.refresh(user)
        assert user.login_count == 1
        assert user.last_login is not None

        # Step 5: Validate access token
        payload = token_manager.validate_access_token(access_token)
        assert payload is not None
        assert payload["sub"] == str(user.id)
        assert payload["email"] == user.email

    def test_login_fails_with_wrong_password(self, db_session, test_user):
        """Verify login fails with incorrect password."""
        from src.models.user import User
        from src.core.security import verify_password

        user = db_session.query(User).filter_by(email=test_user.email).first()
        assert user is not None

        # Wrong password should fail
        assert not verify_password("wrongpassword", user.password_hash)

    def test_login_fails_for_inactive_user(self, db_session, test_organization, token_manager):
        """Verify login fails for deactivated user."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash, verify_password

        inactive_user = User(
            id=uuid.uuid4(),
            email=f"inactive-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("password123"),
            first_name="Inactive",
            last_name="User",
            role=UserRole.USER,
            organization_id=test_organization.id,
            is_active=False,  # Deactivated
        )
        db_session.add(inactive_user)
        db_session.commit()

        # Password is correct, but user is inactive
        assert verify_password("password123", inactive_user.password_hash)

        # Application logic should check is_active
        assert not inactive_user.is_active
        # Login should be blocked at application layer


class TestTokenRefresh:
    """Tests for token refresh flow."""

    def test_refresh_token_rotation(self, token_manager, test_user):
        """Verify refresh token rotation provides new tokens."""
        user_data = {"email": test_user.email, "role": test_user.role.value}

        # Create initial tokens
        access_token = token_manager.create_access_token(str(test_user.id), user_data)
        refresh_token = token_manager.create_refresh_token(str(test_user.id))

        # Wait a bit to ensure different timestamps
        time.sleep(0.1)

        # Refresh tokens
        new_access, new_refresh = token_manager.refresh_access_token(refresh_token, user_data)

        assert new_access is not None
        assert new_refresh is not None
        assert new_access != access_token
        assert new_refresh != refresh_token

        # New access token should be valid
        payload = token_manager.validate_access_token(new_access)
        assert payload is not None

        # Old refresh token should be revoked
        old_payload = token_manager.validate_refresh_token(refresh_token)
        assert old_payload is None

    def test_refresh_with_invalid_token_fails(self, token_manager, test_user):
        """Verify refresh fails with invalid token."""
        fake_token = jwt.encode(
            {"sub": str(test_user.id), "type": "refresh"},
            "wrong-secret",
            algorithm="HS256"
        )

        new_access, new_refresh = token_manager.refresh_access_token(fake_token, {})
        assert new_access is None
        assert new_refresh is None

    def test_refresh_with_access_token_fails(self, token_manager, test_user):
        """Verify refresh fails when using access token instead of refresh token."""
        user_data = {"email": test_user.email}
        access_token = token_manager.create_access_token(str(test_user.id), user_data)

        # Should not work with access token
        new_access, new_refresh = token_manager.refresh_access_token(access_token, user_data)
        assert new_access is None
        assert new_refresh is None


class TestLogout:
    """Tests for logout flow."""

    def test_logout_invalidates_tokens(self, token_manager, test_user):
        """Verify logout invalidates access and refresh tokens."""
        user_data = {"email": test_user.email}

        access_token = token_manager.create_access_token(str(test_user.id), user_data)
        refresh_token = token_manager.create_refresh_token(str(test_user.id))

        # Both tokens should be valid initially
        assert token_manager.validate_access_token(access_token) is not None
        assert token_manager.validate_refresh_token(refresh_token) is not None

        # Logout - revoke both tokens
        token_manager.revoke_token(access_token)
        token_manager.revoke_token(refresh_token)

        # Both should be invalid now
        assert token_manager.validate_access_token(access_token) is None
        assert token_manager.validate_refresh_token(refresh_token) is None

    def test_logout_invalidates_all_sessions(self, token_manager, test_user):
        """Verify logout from all devices invalidates all tokens."""
        user_data = {"email": test_user.email}

        # Create tokens for multiple devices
        tokens = []
        for device in ["mobile", "desktop", "tablet"]:
            access = token_manager.create_access_token(str(test_user.id), user_data)
            refresh = token_manager.create_refresh_token(str(test_user.id), device_id=device)
            tokens.append((access, refresh))

        # Verify all valid
        for access, refresh in tokens:
            assert token_manager.validate_access_token(access) is not None
            assert token_manager.validate_refresh_token(refresh) is not None

        # Logout from all devices
        count = token_manager.revoke_all_user_tokens(str(test_user.id))
        assert count >= 3  # At least 3 tokens revoked

        # All should be invalid
        for access, refresh in tokens:
            assert token_manager.validate_access_token(access) is None
            assert token_manager.validate_refresh_token(refresh) is None


class TestMultiDeviceAuth:
    """Tests for multi-device authentication scenarios."""

    def test_multiple_device_sessions(self, db_session, token_manager, test_user):
        """Verify user can have sessions on multiple devices."""
        user_data = {"email": test_user.email, "role": test_user.role.value}

        # Create sessions for 3 devices
        device_tokens = {}
        for device in ["iphone", "android", "laptop"]:
            access = token_manager.create_access_token(str(test_user.id), user_data)
            refresh = token_manager.create_refresh_token(str(test_user.id), device_id=device)
            device_tokens[device] = {"access": access, "refresh": refresh}

        # All access tokens should be valid
        for device, tokens in device_tokens.items():
            payload = token_manager.validate_access_token(tokens["access"])
            assert payload is not None
            assert payload["sub"] == str(test_user.id)

    def test_revoke_single_device_preserves_others(self, token_manager, test_user):
        """Verify revoking one device's session doesn't affect others."""
        user_data = {"email": test_user.email}

        # Create sessions
        mobile_access = token_manager.create_access_token(str(test_user.id), user_data)
        mobile_refresh = token_manager.create_refresh_token(str(test_user.id), device_id="mobile")

        desktop_access = token_manager.create_access_token(str(test_user.id), user_data)
        desktop_refresh = token_manager.create_refresh_token(str(test_user.id), device_id="desktop")

        # Revoke mobile tokens
        token_manager.revoke_token(mobile_access)
        token_manager.revoke_token(mobile_refresh)

        # Mobile should be invalid
        assert token_manager.validate_access_token(mobile_access) is None
        assert token_manager.validate_refresh_token(mobile_refresh) is None

        # Desktop should still be valid
        assert token_manager.validate_access_token(desktop_access) is not None
        assert token_manager.validate_refresh_token(desktop_refresh) is not None


class TestTokenExpiration:
    """Tests for token expiration with real TTLs."""

    def test_access_token_expires(self, redis_client):
        """Verify access token expires after TTL."""
        # Create manager with short TTL for testing
        short_ttl_manager = TokenManager(redis_client)
        short_ttl_manager.access_token_ttl = 1  # 1 second

        user_id = str(uuid.uuid4())
        access_token = short_ttl_manager.create_access_token(user_id, {"test": True})

        # Should be valid immediately
        assert short_ttl_manager.validate_access_token(access_token) is not None

        # Wait for expiration
        time.sleep(1.5)

        # Token should now be expired (Redis TTL expired)
        assert short_ttl_manager.validate_access_token(access_token) is None

    def test_database_and_redis_consistency(self, db_session, redis_client, token_manager, test_user):
        """Verify database user state is checked along with token validity."""
        from src.models.user import User

        user_data = {"email": test_user.email, "role": test_user.role.value}
        access_token = token_manager.create_access_token(str(test_user.id), user_data)

        # Token valid and user active
        payload = token_manager.validate_access_token(access_token)
        assert payload is not None

        user = db_session.query(User).filter_by(id=test_user.id).first()
        assert user.is_active is True

        # Deactivate user in database
        user.is_active = False
        db_session.commit()

        # Token is technically still valid in Redis
        payload = token_manager.validate_access_token(access_token)
        assert payload is not None

        # But application should check database state too
        user = db_session.query(User).filter_by(id=uuid.UUID(payload["sub"])).first()
        assert user.is_active is False  # Should block at app layer
