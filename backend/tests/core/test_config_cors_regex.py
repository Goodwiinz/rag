"""Regression coverage for credentialed CORS regex validation."""

import pytest
from pydantic import ValidationError

from src.core.config import Settings


STRONG_SECRET = "test-secret-with-at-least-thirty-two-characters"
REMOTE_DATABASE_URL = "postgresql://test:test@db.example.com:5432/rag"
VERCEL_PREVIEW_CORS_REGEX = r"^https://nous-platform-[a-z0-9-]+\.vercel\.app$"


def build_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    environment: str = "production",
    cors_origin_regex: str = VERCEL_PREVIEW_CORS_REGEX,
) -> Settings:
    """Create settings with enough secure values for deployed env validation."""
    monkeypatch.setenv("ENVIRONMENT", environment)
    return Settings(
        ENVIRONMENT=environment,
        DATABASE_URL=REMOTE_DATABASE_URL,
        SECRET_KEY=STRONG_SECRET,
        JWT_SECRET_KEY=STRONG_SECRET,
        NEO4J_PASSWORD=STRONG_SECRET,
        CORS_ORIGIN_REGEX=cors_origin_regex,
    )


@pytest.mark.unit
@pytest.mark.parametrize("environment", ["production", "staging"])
def test_cors_origin_regex_accepts_specific_vercel_preview_pattern(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    settings = build_settings(
        monkeypatch,
        environment=environment,
        cors_origin_regex=r"  ^https://nous-platform-[a-z0-9-]+\.vercel\.app$  ",
    )

    assert settings.CORS_ORIGIN_REGEX == VERCEL_PREVIEW_CORS_REGEX


@pytest.mark.unit
def test_cors_origin_regex_empty_value_disables_regex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = build_settings(monkeypatch, cors_origin_regex="  ")

    assert settings.CORS_ORIGIN_REGEX == ""


@pytest.mark.unit
@pytest.mark.parametrize(
    ("pattern", "message"),
    [
        (r"https://nous-platform-[a-z0-9-]+\.vercel\.app", "anchored"),
        (r"^https://.*$", "too permissive"),
        (r"^https://.+$", "too permissive"),
        (r"^https://nous-platform-([a-z0-9-]+\.vercel\.app$", "invalid"),
    ],
)
def test_cors_origin_regex_rejects_patterns_unsafe_for_credentials(
    monkeypatch: pytest.MonkeyPatch, pattern: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        build_settings(monkeypatch, cors_origin_regex=pattern)


@pytest.mark.unit
@pytest.mark.parametrize("environment", ["production", "staging"])
def test_cors_origin_regex_requires_https_in_deployed_environments(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    with pytest.raises(ValidationError, match=r"\^https://"):
        build_settings(
            monkeypatch,
            environment=environment,
            cors_origin_regex=r"^http://nous-platform-[a-z0-9-]+\.vercel\.app$",
        )


@pytest.mark.unit
def test_cors_origin_regex_allows_http_for_local_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = build_settings(
        monkeypatch,
        environment="development",
        cors_origin_regex=r"^http://nous-platform-[a-z0-9-]+\.localhost$",
    )

    assert (
        settings.CORS_ORIGIN_REGEX
        == r"^http://nous-platform-[a-z0-9-]+\.localhost$"
    )
