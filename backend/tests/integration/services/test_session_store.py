"""
Session Store Integration Tests

Tests for session management with real Redis instance to validate:
- Session creation with expiry
- Session invalidation (single and bulk)
- Session TTL refresh on activity
- Concurrent session handling
"""

import pytest
import time
import uuid
import json
from concurrent.futures import ThreadPoolExecutor

# Mark all tests in this module
pytestmark = [
    pytest.mark.requires_redis,
    pytest.mark.integration,
]


@pytest.fixture
def sync_redis_client(redis_container):
    """Create a synchronous Redis client for testing."""
    import redis

    client = redis.Redis.from_url(redis_container["url"])
    yield client
    client.flushdb()
    client.close()


class SessionStore:
    """Simple session store implementation for testing."""

    def __init__(self, redis_client, default_ttl: int = 3600):
        self.redis = redis_client
        self.default_ttl = default_ttl

    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        return f"user_sessions:{user_id}"

    def create_session(self, user_id: str, data: dict, ttl: int = None) -> str:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        session_ttl = ttl or self.default_ttl

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": time.time(),
            "last_activity": time.time(),
            **data,
        }

        # Store session data
        session_key = self._session_key(session_id)
        self.redis.setex(session_key, session_ttl, json.dumps(session_data))

        # Track session for user (for bulk invalidation)
        user_sessions_key = self._user_sessions_key(user_id)
        self.redis.sadd(user_sessions_key, session_id)
        self.redis.expire(user_sessions_key, session_ttl * 2)

        return session_id

    def get_session(self, session_id: str) -> dict:
        """Get session data."""
        session_key = self._session_key(session_id)
        data = self.redis.get(session_key)
        if data:
            return json.loads(data)
        return None

    def update_session(self, session_id: str, updates: dict) -> bool:
        """Update session data."""
        session = self.get_session(session_id)
        if not session:
            return False

        session.update(updates)
        session["last_activity"] = time.time()

        session_key = self._session_key(session_id)
        ttl = self.redis.ttl(session_key)
        if ttl > 0:
            self.redis.setex(session_key, ttl, json.dumps(session))
            return True
        return False

    def refresh_session(self, session_id: str, ttl: int = None) -> bool:
        """Refresh session TTL."""
        session_ttl = ttl or self.default_ttl
        session_key = self._session_key(session_id)

        if self.redis.exists(session_key):
            session = self.get_session(session_id)
            session["last_activity"] = time.time()
            self.redis.setex(session_key, session_ttl, json.dumps(session))
            return True
        return False

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a single session."""
        session = self.get_session(session_id)
        if not session:
            return False

        # Remove from user's session set
        user_sessions_key = self._user_sessions_key(session["user_id"])
        self.redis.srem(user_sessions_key, session_id)

        # Delete session
        session_key = self._session_key(session_id)
        deleted = self.redis.delete(session_key)
        return deleted > 0

    def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user."""
        user_sessions_key = self._user_sessions_key(user_id)
        session_ids = self.redis.smembers(user_sessions_key)

        count = 0
        for sid in session_ids:
            session_key = self._session_key(sid.decode() if isinstance(sid, bytes) else sid)
            if self.redis.delete(session_key):
                count += 1

        self.redis.delete(user_sessions_key)
        return count

    def get_user_sessions(self, user_id: str) -> list:
        """Get all active sessions for a user."""
        user_sessions_key = self._user_sessions_key(user_id)
        session_ids = self.redis.smembers(user_sessions_key)

        sessions = []
        for sid in session_ids:
            sid_str = sid.decode() if isinstance(sid, bytes) else sid
            session = self.get_session(sid_str)
            if session:
                sessions.append(session)

        return sessions

    def get_session_ttl(self, session_id: str) -> int:
        """Get remaining TTL for session."""
        session_key = self._session_key(session_id)
        return self.redis.ttl(session_key)


@pytest.fixture
def session_store(sync_redis_client):
    """Create a session store instance."""
    return SessionStore(sync_redis_client, default_ttl=60)


class TestSessionCreation:
    """Tests for session creation."""

    def test_stores_session_with_expiry(self, session_store, sync_redis_client):
        """Verify session is stored with correct TTL."""
        user_id = f"user:{uuid.uuid4().hex}"
        session_data = {"ip": "192.168.1.1", "user_agent": "Test Browser"}

        session_id = session_store.create_session(user_id, session_data, ttl=30)

        # Session should exist
        session = session_store.get_session(session_id)
        assert session is not None
        assert session["user_id"] == user_id
        assert session["ip"] == "192.168.1.1"

        # TTL should be set
        ttl = session_store.get_session_ttl(session_id)
        assert 25 <= ttl <= 30

    def test_stores_multiple_sessions_per_user(self, session_store):
        """Verify user can have multiple sessions."""
        user_id = f"user:{uuid.uuid4().hex}"

        # Create 3 sessions (different devices)
        session_ids = []
        devices = ["mobile", "desktop", "tablet"]
        for device in devices:
            sid = session_store.create_session(
                user_id,
                {"device": device},
                ttl=120
            )
            session_ids.append(sid)

        # All sessions should be tracked
        user_sessions = session_store.get_user_sessions(user_id)
        assert len(user_sessions) == 3

        devices_found = [s["device"] for s in user_sessions]
        assert set(devices_found) == set(devices)


class TestSessionInvalidation:
    """Tests for session invalidation."""

    def test_invalidates_single_session(self, session_store):
        """Verify single session invalidation."""
        user_id = f"user:{uuid.uuid4().hex}"

        sid1 = session_store.create_session(user_id, {"device": "mobile"})
        sid2 = session_store.create_session(user_id, {"device": "desktop"})

        # Invalidate one session
        result = session_store.invalidate_session(sid1)
        assert result is True

        # Only that session should be gone
        assert session_store.get_session(sid1) is None
        assert session_store.get_session(sid2) is not None

    def test_invalidates_all_user_sessions(self, session_store):
        """Verify bulk session invalidation for user."""
        user_id = f"user:{uuid.uuid4().hex}"

        # Create multiple sessions
        for i in range(5):
            session_store.create_session(user_id, {"device": f"device_{i}"})

        # Verify sessions exist
        sessions = session_store.get_user_sessions(user_id)
        assert len(sessions) == 5

        # Invalidate all
        count = session_store.invalidate_all_user_sessions(user_id)
        assert count == 5

        # All sessions should be gone
        sessions = session_store.get_user_sessions(user_id)
        assert len(sessions) == 0

    def test_invalidate_nonexistent_session(self, session_store):
        """Verify graceful handling of invalid session ID."""
        fake_session_id = str(uuid.uuid4())
        result = session_store.invalidate_session(fake_session_id)
        assert result is False


class TestSessionRefresh:
    """Tests for session TTL refresh."""

    def test_refreshes_session_ttl_on_activity(self, session_store):
        """Verify session TTL is refreshed on activity."""
        user_id = f"user:{uuid.uuid4().hex}"

        # Create session with short TTL
        session_id = session_store.create_session(user_id, {}, ttl=10)

        # Wait a bit
        time.sleep(2)

        # Check TTL decreased
        ttl_before_refresh = session_store.get_session_ttl(session_id)
        assert ttl_before_refresh < 10

        # Refresh session
        result = session_store.refresh_session(session_id, ttl=30)
        assert result is True

        # TTL should be extended
        ttl_after_refresh = session_store.get_session_ttl(session_id)
        assert ttl_after_refresh > ttl_before_refresh
        assert 25 <= ttl_after_refresh <= 30

    def test_refresh_updates_last_activity(self, session_store):
        """Verify refresh updates last_activity timestamp."""
        user_id = f"user:{uuid.uuid4().hex}"

        session_id = session_store.create_session(user_id, {}, ttl=60)
        original_session = session_store.get_session(session_id)
        original_activity = original_session["last_activity"]

        # Wait and refresh
        time.sleep(1)
        session_store.refresh_session(session_id)

        # Check last_activity updated
        refreshed_session = session_store.get_session(session_id)
        assert refreshed_session["last_activity"] > original_activity

    def test_refresh_expired_session_fails(self, session_store):
        """Verify refresh fails for expired session."""
        user_id = f"user:{uuid.uuid4().hex}"

        # Create session with very short TTL
        session_id = session_store.create_session(user_id, {}, ttl=1)

        # Wait for expiration
        time.sleep(1.5)

        # Refresh should fail
        result = session_store.refresh_session(session_id)
        assert result is False


class TestSessionExpiration:
    """Tests for session expiration behavior."""

    def test_session_auto_expires(self, session_store):
        """Verify sessions automatically expire after TTL."""
        user_id = f"user:{uuid.uuid4().hex}"

        session_id = session_store.create_session(user_id, {"data": "test"}, ttl=1)

        # Session should exist
        assert session_store.get_session(session_id) is not None

        # Wait for expiration
        time.sleep(1.5)

        # Session should be gone
        assert session_store.get_session(session_id) is None

    def test_expired_session_removed_from_user_set(self, session_store, sync_redis_client):
        """Verify expired sessions are cleaned from user tracking set."""
        user_id = f"user:{uuid.uuid4().hex}"

        # Create sessions with different TTLs
        short_session = session_store.create_session(user_id, {"type": "short"}, ttl=1)
        long_session = session_store.create_session(user_id, {"type": "long"}, ttl=60)

        # Both should be in user sessions
        sessions = session_store.get_user_sessions(user_id)
        assert len(sessions) == 2

        # Wait for short session to expire
        time.sleep(1.5)

        # get_user_sessions should filter out expired
        sessions = session_store.get_user_sessions(user_id)
        assert len(sessions) == 1
        assert sessions[0]["type"] == "long"


class TestConcurrentSessions:
    """Tests for concurrent session operations."""

    def test_concurrent_session_creation(self, session_store):
        """Verify concurrent session creation is safe."""
        user_id = f"user:{uuid.uuid4().hex}"
        session_ids = []

        def create_session():
            sid = session_store.create_session(user_id, {"thread": uuid.uuid4().hex})
            return sid

        # Create sessions concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_session) for _ in range(10)]
            session_ids = [f.result() for f in futures]

        # All sessions should be unique
        assert len(set(session_ids)) == 10

        # All should be tracked for user
        user_sessions = session_store.get_user_sessions(user_id)
        assert len(user_sessions) == 10

    def test_concurrent_session_invalidation(self, session_store):
        """Verify concurrent invalidation is safe."""
        user_id = f"user:{uuid.uuid4().hex}"

        # Create sessions
        session_ids = []
        for i in range(10):
            sid = session_store.create_session(user_id, {"index": i})
            session_ids.append(sid)

        def invalidate_session(sid):
            return session_store.invalidate_session(sid)

        # Invalidate concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(invalidate_session, sid) for sid in session_ids]
            results = [f.result() for f in futures]

        # All should succeed
        assert all(results)

        # No sessions should remain
        user_sessions = session_store.get_user_sessions(user_id)
        assert len(user_sessions) == 0


class TestSessionDataUpdate:
    """Tests for session data updates."""

    def test_updates_session_data(self, session_store):
        """Verify session data can be updated."""
        user_id = f"user:{uuid.uuid4().hex}"

        session_id = session_store.create_session(
            user_id,
            {"theme": "light", "language": "en"},
            ttl=60
        )

        # Update session data
        result = session_store.update_session(session_id, {"theme": "dark"})
        assert result is True

        # Verify update
        session = session_store.get_session(session_id)
        assert session["theme"] == "dark"
        assert session["language"] == "en"  # Unchanged

    def test_update_preserves_ttl(self, session_store):
        """Verify update doesn't reset TTL."""
        user_id = f"user:{uuid.uuid4().hex}"

        session_id = session_store.create_session(user_id, {}, ttl=30)

        # Wait a bit
        time.sleep(2)
        ttl_before = session_store.get_session_ttl(session_id)

        # Update
        session_store.update_session(session_id, {"updated": True})

        # TTL should be roughly the same
        ttl_after = session_store.get_session_ttl(session_id)
        assert abs(ttl_before - ttl_after) <= 1  # Allow 1 second variance

    def test_update_nonexistent_session(self, session_store):
        """Verify update fails for nonexistent session."""
        fake_session_id = str(uuid.uuid4())
        result = session_store.update_session(fake_session_id, {"data": "test"})
        assert result is False
