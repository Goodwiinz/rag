"""Regression tests for credentialed CORS origin regex validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.config import Settings


def _settings(monkeypatch: pytest.MonkeyPatch, *, env: str, pattern: str) -> Settings:
    monkeypatch.setenv("ENVIRONMENT", env)
    return Settings(
        ENVIRONMENT=env,
        CORS_ORIGIN_REGEX=pattern,
        DATABASE_URL="postgresql://postgres:postgres@postgres:5432/multimodal_rag_dev",
        SECRET_KEY="s" * 40,
        JWT_SECRET_KEY="j" * 40,
        NEO4J_PASSWORD="secure-neo4j-password",
        SUPABASE_DB_URL="",
        DO_KB_ENABLED=False,
    )


@pytest.mark.unit
def test_cors_origin_regex_accepts_project_specific_vercel_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pattern = r"^https://nous-platform-[a-z0-9-]+\.vercel\.app$"

    settings = _settings(monkeypatch, env="production", pattern=pattern)

    assert settings.CORS_ORIGIN_REGEX == pattern


@pytest.mark.unit
def test_cors_origin_regex_allows_specific_http_origin_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pattern = r"^http://localhost:3000$"

    settings = _settings(monkeypatch, env="development", pattern=pattern)

    assert settings.CORS_ORIGIN_REGEX == pattern


@pytest.mark.unit
@pytest.mark.parametrize(
    ("pattern", "message"),
    [
        (
            r"https://nous-platform-[a-z0-9-]+\.vercel\.app",
            "anchored",
        ),
        (
            r"^http://nous-platform-[a-z0-9-]+\.vercel\.app$",
            r"\^https://",
        ),
        (
            r"^https://.*$",
            "too permissive",
        ),
        (
            r"^https://nous-platform-.*\.vercel\.app$",
            "too permissive",
        ),
        (
            r"^https://[a-z0-9-]+\.vercel\.app$",
            "project-specific literal",
        ),
        (
            r"^https://nous-platform-([a-z]+\.vercel\.app$",
            "invalid",
        ),
    ],
)
def test_cors_origin_regex_rejects_unsafe_production_patterns(
    monkeypatch: pytest.MonkeyPatch,
    pattern: str,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _settings(monkeypatch, env="production", pattern=pattern)


@pytest.mark.unit
def test_cors_origin_regex_blank_value_disables_regex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, env="production", pattern="  ")

    assert settings.CORS_ORIGIN_REGEX == ""
