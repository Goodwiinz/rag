"""Unit tests for long-lived CLI tokens (HS256, scope=cli).

CLI tokens are minted at /cli-auth/approve so the device-flow CLI doesn't
have to re-authenticate every Supabase access-token refresh (~1h). These
tests cover:

  * create_cli_token() round-trips through verify_token()
  * the right TokenData fields are extracted (user_id, email, org, role, exp)
  * a token signed with a different secret is rejected
  * a token without scope=cli is not accepted via the CLI path
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from src.core.config import settings
from src.core.security import (
    _CLI_TOKEN_ISSUER,
    _CLI_TOKEN_SCOPE,
    create_cli_token,
    get_current_user_token,
    verify_token,
)


def _raw_cli_token(iat: datetime, exp: datetime) -> str:
    """Mint a CLI JWT with explicit iat/exp (to simulate a token issued under a
    previously larger CLI_TOKEN_EXPIRE_DAYS)."""
    return jwt.encode(
        {
            "sub": "u",
            "email": "u@example.com",
            "app_metadata": {"organization_id": "o", "role": "USER"},
            "scope": _CLI_TOKEN_SCOPE,
            "iss": _CLI_TOKEN_ISSUER,
            "iat": int(iat.timestamp()),
            "exp": int(exp.timestamp()),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def test_create_cli_token_roundtrips_through_verify_token() -> None:
    token, _expires_at = create_cli_token(
        user_id="user-1",
        email="admin@multimodal-rag.com",
        organization_id="org-1",
        role="ADMIN",
    )

    data = verify_token(token)
    assert data is not None
    assert data.user_id == "user-1"
    assert data.email == "admin@multimodal-rag.com"
    assert data.organization_id == "org-1"
    assert data.role == "ADMIN"


def test_create_cli_token_uses_configured_lifetime() -> None:
    before = datetime.now(timezone.utc)
    _, expires_at = create_cli_token(
        user_id="u",
        email="u@example.com",
        organization_id="o",
    )

    expected = before + timedelta(days=settings.CLI_TOKEN_EXPIRE_DAYS)
    # Allow 5s slack between the snapshot and the call inside create_cli_token.
    assert abs((expires_at - expected).total_seconds()) < 5


def test_create_cli_token_refuses_without_jwt_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        create_cli_token(user_id="u", email="u@example.com", organization_id="o")


def test_verify_token_rejects_cli_token_signed_with_wrong_secret() -> None:
    bogus = jwt.encode(
        {
            "sub": "attacker",
            "email": "attacker@example.com",
            "app_metadata": {"organization_id": "o", "role": "ADMIN"},
            "scope": _CLI_TOKEN_SCOPE,
            "iss": _CLI_TOKEN_ISSUER,
            "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        },
        "not-the-real-secret",
        algorithm=settings.JWT_ALGORITHM,
    )

    assert verify_token(bogus) is None


def test_verify_token_ignores_cli_path_when_scope_missing() -> None:
    """A token signed with JWT_SECRET_KEY but without scope=cli must not be
    accepted by the CLI verification path. (It may still be accepted as a
    Supabase HS256 token if SUPABASE_JWT_SECRET happens to equal
    JWT_SECRET_KEY, but that's a separate path with its own audience check.)
    """
    no_scope = jwt.encode(
        {
            "sub": "u",
            "email": "u@example.com",
            "app_metadata": {"organization_id": "o", "role": "USER"},
            "iss": _CLI_TOKEN_ISSUER,
            "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    # If SUPABASE_JWT_SECRET differs (the normal case), no path matches.
    if settings.SUPABASE_JWT_SECRET != settings.JWT_SECRET_KEY:
        assert verify_token(no_scope) is None


def test_cli_token_within_max_age_is_accepted() -> None:
    now = datetime.now(timezone.utc)
    token = _raw_cli_token(iat=now - timedelta(days=1), exp=now + timedelta(days=1))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    data = get_current_user_token(creds)
    assert data.user_id == "u"
    assert data.is_cli is True


def test_cli_token_older_than_max_age_is_rejected() -> None:
    """A CLI token whose iat predates CLI_TOKEN_EXPIRE_DAYS is rejected even if
    its own exp is still in the future (minted under a larger past config).
    Bounds the Redis-loss exposure window. (audit D7)"""
    now = datetime.now(timezone.utc)
    over_cap = settings.CLI_TOKEN_EXPIRE_DAYS + 5
    token = _raw_cli_token(
        iat=now - timedelta(days=over_cap),
        exp=now + timedelta(days=10),  # still valid by its own exp claim
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc:
        get_current_user_token(creds)
    assert exc.value.status_code == 401
