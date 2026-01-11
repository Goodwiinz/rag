"""
Pytest configuration for AI integration tests.

Provides fixtures and markers for integration testing.
"""

import os
import pytest
from typing import Generator


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "ai: marks test as requiring AI provider access"
    )
    config.addinivalue_line(
        "markers",
        "openai: marks test as requiring OpenAI API"
    )
    config.addinivalue_line(
        "markers",
        "anthropic: marks test as requiring Anthropic API"
    )
    config.addinivalue_line(
        "markers",
        "azure: marks test as requiring Azure OpenAI API"
    )


@pytest.fixture(scope="session")
def ai_tests_enabled() -> bool:
    """Check if AI integration tests are enabled."""
    return os.getenv("AI_INTEGRATION_TESTS", "").lower() == "true"


@pytest.fixture(scope="session")
def openai_available() -> bool:
    """Check if OpenAI API is available."""
    return bool(os.getenv("OPENAI_API_KEY"))


@pytest.fixture(scope="session")
def anthropic_available() -> bool:
    """Check if Anthropic API is available."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


@pytest.fixture(scope="session")
def azure_available() -> bool:
    """Check if Azure OpenAI API is available."""
    return bool(
        os.getenv("AZURE_OPENAI_API_KEY") and
        os.getenv("AZURE_OPENAI_ENDPOINT")
    )


@pytest.fixture
def capture_api_calls() -> Generator[list, None, None]:
    """
    Fixture to capture API calls for debugging.

    Usage:
        def test_something(capture_api_calls):
            # ... make API calls ...
            print(capture_api_calls)  # List of call records
    """
    calls = []
    yield calls


@pytest.fixture
def rate_limit_retry_config() -> dict:
    """Configuration for rate limit retry behavior."""
    return {
        "max_retries": 3,
        "base_delay": 1.0,
        "max_delay": 60.0,
        "exponential_base": 2.0
    }
