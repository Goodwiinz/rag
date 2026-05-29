import pytest
from pydantic import ValidationError

from src.core.config import Settings


def _settings_with_cors(pattern: str) -> Settings:
    return Settings(
        CORS_ORIGIN_REGEX=pattern,
        DATABASE_URL="postgresql://postgres:postgres@db.example.com:5432/app",
        JWT_SECRET_KEY="jwt-value-with-enough-entropy-for-production-tests",
        NEO4J_PASSWORD="correct-horse-battery-staple",
        SECRET_KEY="app-value-with-enough-entropy-for-production-tests",
    )


@pytest.mark.unit
@pytest.mark.regression
def test_cors_origin_regex_accepts_anchored_project_specific_https_regex(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ENVIRONMENT", "production")

    settings = _settings_with_cors(
        r"^https://nous-platform-[a-z0-9-]+\.vercel\.app$"
    )

    assert (
        settings.CORS_ORIGIN_REGEX
        == r"^https://nous-platform-[a-z0-9-]+\.vercel\.app$"
    )


@pytest.mark.unit
@pytest.mark.regression
@pytest.mark.parametrize(
    ("pattern", "error_message"),
    [
        (
            r"https://nous-platform-[a-z0-9-]+\.vercel\.app",
            "must be anchored",
        ),
        (r"^https://.*$", "too permissive"),
        (r"^https://(.+)\.vercel\.app$", "too permissive"),
        (r"^https://[a-z0-9-]+\.io$", "project-specific literal"),
        (r"^https://nous-platform-[a-z0-9-]+\.vercel\.app($", "is invalid"),
    ],
)
def test_cors_origin_regex_rejects_unsafe_patterns(
    pattern: str,
    error_message: str,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(ValidationError, match=error_message):
        _settings_with_cors(pattern)


@pytest.mark.unit
@pytest.mark.regression
def test_cors_origin_regex_requires_https_in_staging_and_production(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ENVIRONMENT", "staging")

    with pytest.raises(ValidationError, match="must use \\^https://"):
        _settings_with_cors(r"^http://nous-platform-local\.test$")


@pytest.mark.unit
@pytest.mark.regression
def test_cors_origin_regex_allows_http_only_outside_staging_and_production(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ENVIRONMENT", "testing")

    settings = Settings(CORS_ORIGIN_REGEX=r"^http://nous-platform-local\.test$")

    assert settings.CORS_ORIGIN_REGEX == r"^http://nous-platform-local\.test$"
