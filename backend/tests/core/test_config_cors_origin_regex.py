from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from src.core.config import Settings


_SAFE_PROD_OVERRIDES: dict[str, Any] = {
    "DATABASE_URL": "postgresql://postgres:postgres@db.example.com:5432/app",
    "SECRET_KEY": "s" * 32,
    "JWT_SECRET_KEY": "j" * 32,
    "NEO4J_PASSWORD": "neo4j-password-for-prod-tests",
}


def _settings_for_regex(monkeypatch: pytest.MonkeyPatch, pattern: str) -> Settings:
    monkeypatch.setenv("ENVIRONMENT", "production")
    return Settings(
        ENVIRONMENT="production",
        CORS_ORIGIN_REGEX=pattern,
        **_SAFE_PROD_OVERRIDES,
    )


@pytest.mark.regression
def test_cors_origin_regex_accepts_project_specific_vercel_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_for_regex(
        monkeypatch,
        "  ^https://nous-platform-[a-z0-9-]+\\.vercel\\.app$  ",
    )

    assert (
        settings.CORS_ORIGIN_REGEX
        == "^https://nous-platform-[a-z0-9-]+\\.vercel\\.app$"
    )


@pytest.mark.regression
@pytest.mark.parametrize(
    ("pattern", "message"),
    [
        (
            "https://nous-platform-[a-z0-9-]+\\.vercel\\.app",
            "must be anchored",
        ),
        (
            "^http://nous-platform-[a-z0-9-]+\\.vercel\\.app$",
            "must use \\^https://",
        ),
        (
            "^https://.*$",
            "too permissive",
        ),
        (
            "^https://[a-z0-9-]+\\.vercel\\.app$",
            "project-specific literal",
        ),
        (
            "^https://nous-platform-[\\.vercel\\.app$",
            "is invalid",
        ),
    ],
)
def test_cors_origin_regex_rejects_unsafe_credentialed_patterns(
    monkeypatch: pytest.MonkeyPatch,
    pattern: str,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _settings_for_regex(monkeypatch, pattern)
