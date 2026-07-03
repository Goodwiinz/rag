"""Unit tests for ``verify_token`` dispatch + ``get_current_user_token``.

Coverage gap (daily audit #923, finding #3): ``test_cli_token.py`` already
covers the CLI-token (HS256/``JWT_SECRET_KEY``) branch, but the other two
``verify_token`` fallbacks — Supabase HS256 (shared secret) and Supabase
ES256 via JWKS — plus the ``get_current_user_token`` chokepoint had no direct
coverage. A regression there (audience or algorithm confusion) would let a
forged or mis-scoped token authenticate. These tests exercise every branch,
including the failure modes (bad signature, wrong audience, expired, alg
confusion).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

import src.core.security as security
from src.core.config import settings
from src.core.security import (
    TokenData,
    get_current_user_token,
    verify_token,
)

_SUPABASE_SECRET = "supabase-test-shared-secret-32chars!!"


def _exp(minutes: int) -> int:
    return int((datetime.now(timezone.utc) + timedelta(minutes=minutes)).timestamp())


def _supabase_hs256(secret: str, *, aud: str = "authenticated", **claims) -> str:
    payload = {
        "sub": "sb-user",
        "email": "sb@example.com",
        "app_metadata": {"role": "ADMIN"},
        "aud": aud,
        "exp": _exp(60),
    }
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def es256_keypair():
    """Return (private_pem, jwks_dict, kid) for an ES256 signing key."""
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub_pem = (
        priv.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    from jose import jwk

    kid = "test-kid"
    pub_jwk = jwk.construct(pub_pem, algorithm="ES256").to_dict()
    pub_jwk["kid"] = kid
    pub_jwk.setdefault("alg", "ES256")
    return priv_pem, {"keys": [pub_jwk]}, kid


# ---------------------------------------------------------------------------
# Supabase HS256 branch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_supabase_hs256_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    token = _supabase_hs256(_SUPABASE_SECRET)

    data = verify_token(token)

    assert data is not None
    assert data.user_id == "sb-user"
    assert data.email == "sb@example.com"
    assert data.role == "ADMIN"  # pulled from app_metadata
    assert data.is_cli is False


@pytest.mark.unit
def test_supabase_hs256_defaults_role_to_user(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    token = _supabase_hs256(_SUPABASE_SECRET, app_metadata={})

    data = verify_token(token)

    assert data is not None
    assert data.role == "USER"


@pytest.mark.unit
def test_supabase_hs256_wrong_audience_rejected(monkeypatch):
    """Audience confusion: a validly-signed token addressed to a different
    audience must not authenticate."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    token = _supabase_hs256(_SUPABASE_SECRET, aud="some-other-service")

    assert verify_token(token) is None


@pytest.mark.unit
def test_supabase_hs256_bad_signature_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    token = _supabase_hs256("attacker-signed-with-wrong-secret-key")

    assert verify_token(token) is None


@pytest.mark.unit
def test_supabase_hs256_expired_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    token = _supabase_hs256(_SUPABASE_SECRET, exp=_exp(-5))

    assert verify_token(token) is None


# ---------------------------------------------------------------------------
# Supabase ES256 / JWKS branch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_supabase_es256_valid_token(monkeypatch, es256_keypair):
    priv_pem, jwks, kid = es256_keypair
    monkeypatch.setattr(security, "_supabase_jwks_cache", None, raising=False)
    monkeypatch.setattr(security, "_get_supabase_jwks", lambda: jwks)
    # Ensure the HS256 paths can't accidentally match.
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "unrelated-secret")

    token = jwt.encode(
        {
            "sub": "es-user",
            "email": "es@example.com",
            "app_metadata": {"role": "CONTENT_MANAGER"},
            "aud": "authenticated",
            "exp": _exp(60),
        },
        priv_pem,
        algorithm="ES256",
        headers={"kid": kid},
    )

    data = verify_token(token)

    assert data is not None
    assert data.user_id == "es-user"
    assert data.role == "CONTENT_MANAGER"
    assert data.is_cli is False


@pytest.mark.unit
def test_es256_algorithm_confusion_rejected(monkeypatch, es256_keypair):
    """Classic alg-confusion attack: forge an HS256 token using the ES256
    PUBLIC key material as the HMAC secret. ``jose.jwt.encode`` refuses to sign
    HS256 with an asymmetric key, so — exactly as a real attacker would — we
    hand-roll the JWT bytes. Because the JWKS path pins ``algorithms=["ES256"]``
    and the header alg is HS256, no branch accepts it."""
    priv_pem, jwks, kid = es256_keypair
    # Recover the public PEM the server publishes — the attacker's HMAC secret.
    pub_pem = (
        serialization.load_pem_private_key(priv_pem.encode(), password=None)
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    monkeypatch.setattr(security, "_supabase_jwks_cache", None, raising=False)
    monkeypatch.setattr(security, "_get_supabase_jwks", lambda: jwks)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "unrelated-secret")

    def _b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": kid}).encode())
    payload = _b64(
        json.dumps({"sub": "attacker", "aud": "authenticated", "exp": _exp(60)}).encode()
    )
    signing_input = header + b"." + payload
    sig = _b64(hmac.new(pub_pem.encode(), signing_input, hashlib.sha256).digest())
    forged = (signing_input + b"." + sig).decode()

    assert verify_token(forged) is None


@pytest.mark.unit
def test_es256_returns_none_when_jwks_unavailable(monkeypatch, es256_keypair):
    priv_pem, _jwks, kid = es256_keypair
    monkeypatch.setattr(security, "_supabase_jwks_cache", None, raising=False)
    monkeypatch.setattr(security, "_get_supabase_jwks", lambda: None)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "unrelated-secret")

    token = jwt.encode(
        {"sub": "es-user", "aud": "authenticated", "exp": _exp(60)},
        priv_pem,
        algorithm="ES256",
        headers={"kid": kid},
    )

    assert verify_token(token) is None


# ---------------------------------------------------------------------------
# No path matches
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_garbage_token_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    assert verify_token("not-a-jwt-at-all") is None


# ---------------------------------------------------------------------------
# get_current_user_token chokepoint
# ---------------------------------------------------------------------------


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.unit
def test_get_current_user_token_valid(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    token = _supabase_hs256(_SUPABASE_SECRET)

    data = get_current_user_token(_creds(token))

    assert isinstance(data, TokenData)
    assert data.user_id == "sb-user"


@pytest.mark.unit
def test_get_current_user_token_invalid_raises_401(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)

    with pytest.raises(HTTPException) as exc:
        get_current_user_token(_creds("garbage-token"))

    assert exc.value.status_code == 401
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.unit
def test_get_current_user_token_rejects_expired_tokendata(monkeypatch):
    """Even if verify_token were to return a TokenData with a past ``exp``,
    the chokepoint's own expiry guard must reject it with a 401."""
    stale = TokenData(user_id="u", exp=datetime.utcnow() - timedelta(minutes=1))
    monkeypatch.setattr(security, "verify_token", lambda _token: stale)

    with pytest.raises(HTTPException) as exc:
        get_current_user_token(_creds("any"))

    assert exc.value.status_code == 401
