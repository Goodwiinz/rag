from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
import json
import secrets
import string
from typing import Any, Literal

import redis as redis_lib


CLIAuthSessionStatus = Literal["pending", "approved", "denied", "expired"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _generate_verification_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


@dataclass(frozen=True)
class CLIAuthSession:
    session_id: str
    poll_token: str
    verification_code: str
    created_at: datetime
    expires_at: datetime
    status: CLIAuthSessionStatus = "pending"
    user_id: str | None = None
    credential_payload: dict[str, Any] = field(default_factory=dict)
    approved_at: datetime | None = None
    denied_at: datetime | None = None
    expired_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        current_time = now or _utc_now()
        return self.status == "expired" or current_time >= self.expires_at


class InMemoryCLIAuthSessionStore:
    _MAX_SESSIONS = 1000
    _MAX_APPROVE_ATTEMPTS = 5

    def __init__(self, *, ttl_minutes: int = 5) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._sessions: dict[str, CLIAuthSession] = {}
        self._approve_attempts: dict[str, int] = {}

    def _evict_expired(self) -> None:
        now = _utc_now()
        expired_ids = [
            sid for sid, s in self._sessions.items() if now >= s.expires_at
        ]
        for sid in expired_ids:
            del self._sessions[sid]
            self._approve_attempts.pop(sid, None)

    def create_session(self) -> CLIAuthSession:
        self._evict_expired()
        if len(self._sessions) >= self._MAX_SESSIONS:
            raise RuntimeError("Too many pending CLI auth sessions")
        now = _utc_now()
        session = CLIAuthSession(
            session_id=secrets.token_urlsafe(16),
            poll_token=secrets.token_urlsafe(24),
            verification_code=_generate_verification_code(),
            created_at=now,
            expires_at=now + self._ttl,
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str, poll_token: str) -> CLIAuthSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.poll_token != poll_token:
            return None

        if session.is_expired():
            expired_session = self._mark_expired(session)
            self._sessions[session_id] = expired_session
            return expired_session

        return session

    def approve_session(
        self,
        session_id: str,
        *,
        verification_code: str,
        user_id: str,
        credential_payload: dict[str, Any],
    ) -> CLIAuthSession | None:
        session = self._sessions.get(session_id)
        if session is None or session.status != "pending" or session.is_expired():
            return None

        attempts = self._approve_attempts.get(session_id, 0)
        if attempts >= self._MAX_APPROVE_ATTEMPTS:
            self.deny_session(session_id)
            return None

        if session.verification_code != verification_code:
            self._approve_attempts[session_id] = attempts + 1
            return None

        approved = replace(
            session,
            status="approved",
            user_id=user_id,
            credential_payload=dict(credential_payload),
            approved_at=_utc_now(),
        )
        self._sessions[session_id] = approved
        self._approve_attempts.pop(session_id, None)
        return approved

    def deny_session(self, session_id: str) -> CLIAuthSession | None:
        session = self._sessions.get(session_id)
        if session is None or session.status != "pending" or session.is_expired():
            return None

        denied = replace(
            session,
            status="denied",
            denied_at=_utc_now(),
        )
        self._sessions[session_id] = denied
        return denied

    def expire_session(self, session_id: str) -> CLIAuthSession | None:
        session = self._sessions.get(session_id)
        if session is None or session.status != "pending":
            return None

        expired = self._mark_expired(session)
        self._sessions[session_id] = expired
        return expired

    def _mark_expired(self, session: CLIAuthSession) -> CLIAuthSession:
        return replace(
            session,
            status="expired",
            expired_at=_utc_now(),
        )


class RedisCLIAuthSessionStore:
    """Session store backed by Redis — safe across multiple Gunicorn workers."""

    _KEY_PREFIX = "cli_auth:session:"
    _ATTEMPTS_PREFIX = "cli_auth:attempts:"
    _MAX_APPROVE_ATTEMPTS = 5

    def __init__(self, redis_client: redis_lib.Redis, *, ttl_minutes: int = 5) -> None:  # type: ignore[type-arg]
        self._r = redis_client
        self._ttl_minutes = ttl_minutes

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _key(self, session_id: str) -> str:
        return f"{self._KEY_PREFIX}{session_id}"

    def _attempts_key(self, session_id: str) -> str:
        return f"{self._ATTEMPTS_PREFIX}{session_id}"

    def _dump(self, session: CLIAuthSession) -> str:
        def _iso(v: datetime | None) -> str | None:
            return v.isoformat() if v else None

        return json.dumps({
            "session_id": session.session_id,
            "poll_token": session.poll_token,
            "verification_code": session.verification_code,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "status": session.status,
            "user_id": session.user_id,
            "credential_payload": session.credential_payload,
            "approved_at": _iso(session.approved_at),
            "denied_at": _iso(session.denied_at),
            "expired_at": _iso(session.expired_at),
        })

    def _load(self, raw: bytes | str) -> CLIAuthSession:
        d = json.loads(raw)

        def _dt(v: str | None) -> datetime | None:
            return datetime.fromisoformat(v) if v else None

        return CLIAuthSession(
            session_id=d["session_id"],
            poll_token=d["poll_token"],
            verification_code=d["verification_code"],
            created_at=datetime.fromisoformat(d["created_at"]),
            expires_at=datetime.fromisoformat(d["expires_at"]),
            status=d["status"],
            user_id=d.get("user_id"),
            credential_payload=d.get("credential_payload") or {},
            approved_at=_dt(d.get("approved_at")),
            denied_at=_dt(d.get("denied_at")),
            expired_at=_dt(d.get("expired_at")),
        )

    def _save(self, session: CLIAuthSession) -> None:
        remaining = max(int((session.expires_at - _utc_now()).total_seconds()), 0)
        # Keep for at least 2 minutes after session expiry so the CLI can poll for the result.
        self._r.setex(self._key(session.session_id), remaining + 120, self._dump(session))

    # ------------------------------------------------------------------
    # Public interface (mirrors InMemoryCLIAuthSessionStore)
    # ------------------------------------------------------------------

    def create_session(self) -> CLIAuthSession:
        now = _utc_now()
        session = CLIAuthSession(
            session_id=secrets.token_urlsafe(16),
            poll_token=secrets.token_urlsafe(24),
            verification_code=_generate_verification_code(),
            created_at=now,
            expires_at=now + timedelta(minutes=self._ttl_minutes),
        )
        self._save(session)
        return session

    def get_session(self, session_id: str, poll_token: str) -> CLIAuthSession | None:
        raw = self._r.get(self._key(session_id))
        if raw is None:
            return None
        session = self._load(raw)
        if session.poll_token != poll_token:
            return None
        if session.is_expired() and session.status == "pending":
            expired = self._mark_expired(session)
            self._save(expired)
            return expired
        return session

    def approve_session(
        self,
        session_id: str,
        *,
        verification_code: str,
        user_id: str,
        credential_payload: dict[str, Any],
    ) -> CLIAuthSession | None:
        raw = self._r.get(self._key(session_id))
        if raw is None:
            return None
        session = self._load(raw)
        if session.status != "pending" or session.is_expired():
            return None

        attempts_raw = self._r.get(self._attempts_key(session_id))
        attempts = int(attempts_raw) if attempts_raw else 0
        if attempts >= self._MAX_APPROVE_ATTEMPTS:
            self.deny_session(session_id)
            return None

        if session.verification_code != verification_code:
            self._r.incr(self._attempts_key(session_id))
            self._r.expire(self._attempts_key(session_id), self._ttl_minutes * 60)
            return None

        approved = replace(
            session,
            status="approved",
            user_id=user_id,
            credential_payload=dict(credential_payload),
            approved_at=_utc_now(),
        )
        self._save(approved)
        self._r.delete(self._attempts_key(session_id))
        return approved

    def deny_session(self, session_id: str) -> CLIAuthSession | None:
        raw = self._r.get(self._key(session_id))
        if raw is None:
            return None
        session = self._load(raw)
        if session.status != "pending" or session.is_expired():
            return None
        denied = replace(session, status="denied", denied_at=_utc_now())
        self._save(denied)
        return denied

    def expire_session(self, session_id: str) -> CLIAuthSession | None:
        raw = self._r.get(self._key(session_id))
        if raw is None:
            return None
        session = self._load(raw)
        if session.status != "pending":
            return None
        expired = self._mark_expired(session)
        self._save(expired)
        return expired

    def _mark_expired(self, session: CLIAuthSession) -> CLIAuthSession:
        return replace(session, status="expired", expired_at=_utc_now())
