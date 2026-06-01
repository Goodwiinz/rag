"""Regression coverage for credentialed CORS origin-regex validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.config import Settings


_STRONG_SECRET = "test-secret-value-with-more-than-32-characters"
_JWT_SECRET = "test-jwt-secret-value-with-more-than-32-characters"
_DATABASE_URL = "postgresql://postgres:postgres@postgres:5432/multimodal_rag"


def _make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "SECRET_KEY": _STRONG_SECRET,
        "JWT_SECRET_KEY": _JWT_SECRET,
        "NEO4J_PASSWORD": "test-neo4j-password",
        "DATABASE_URL": _DATABASE_URL,
        "SUPABASE_DB_URL": "",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.mark.unit
def test_cors_origin_regex_accepts_specific_preview_host(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")

    settings = _make_settings(
        ENVIRONMENT="staging",
        CORS_ORIGIN_REGEX=r"^https://nous-platform-[a-z0-9-]+\.vercel\.app$",
    )

    assert (
        settings.CORS_ORIGIN_REGEX
        == r"^https://nous-platform-[a-z0-9-]+\.vercel\.app$"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("pattern", "message"),
    [
        ("https://nous-platform-[a-z0-9-]+\\.vercel\\.app", "anchored"),
        (r"^https://.*$", "too permissive"),
        (r"^https://.+$", "too permissive"),
        (r"^https://nous-[a-z0-9-]+\.vercel\.app$", "project-specific literal"),
        (r"^https://nous-platform-[a-z0-9+\.vercel\.app$", "invalid"),
    ],
)
def test_cors_origin_regex_rejects_unsafe_patterns(
    monkeypatch, pattern: str, message: str
):
    monkeypatch.setenv("ENVIRONMENT", "staging")

    with pytest.raises(ValidationError, match=message):
        _make_settings(ENVIRONMENT="staging", CORS_ORIGIN_REGEX=pattern)


@pytest.mark.unit
def test_cors_origin_regex_requires_https_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(ValidationError, match=r"\^https://"):
        _make_settings(
            ENVIRONMENT="production",
            CORS_ORIGIN_REGEX=r"^http://nous-platform-[a-z0-9-]+\.vercel\.app$",
        )
