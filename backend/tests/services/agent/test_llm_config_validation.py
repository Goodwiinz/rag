"""Unit tests for validate_llm_config() in llm_factory.

Pure-unit: no infrastructure required. Settings fields are monkeypatched
directly on the Settings instance returned by get_settings().
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.agent.llm_factory import validate_llm_config


def _make_settings(**kwargs) -> MagicMock:
    """Return a MagicMock that behaves like Settings with all LLM fields falsy
    by default; override via kwargs."""
    defaults = {
        "AZURE_OPENAI_CHAT_ENDPOINT": "",
        "AZURE_OPENAI_ENDPOINT": "",
        "AZURE_OPENAI_CHAT_API_KEY": "",
        "AZURE_OPENAI_API_KEY": "",
    }
    defaults.update(kwargs)
    mock = MagicMock()
    for attr, val in defaults.items():
        setattr(mock, attr, val)
    return mock


@patch("src.services.agent.llm_factory.get_settings")
def test_returns_false_when_both_unset(mock_get_settings):
    mock_get_settings.return_value = _make_settings()
    assert validate_llm_config() is False


@patch("src.services.agent.llm_factory.get_settings")
def test_returns_false_when_endpoint_set_but_no_key(mock_get_settings):
    mock_get_settings.return_value = _make_settings(
        AZURE_OPENAI_CHAT_ENDPOINT="https://example.openai.azure.com/"
    )
    assert validate_llm_config() is False


@patch("src.services.agent.llm_factory.get_settings")
def test_returns_false_when_key_set_but_no_endpoint(mock_get_settings):
    mock_get_settings.return_value = _make_settings(
        AZURE_OPENAI_CHAT_API_KEY="sk-test-key"
    )
    assert validate_llm_config() is False


@patch("src.services.agent.llm_factory.get_settings")
def test_returns_true_when_chat_endpoint_and_chat_key_set(mock_get_settings):
    mock_get_settings.return_value = _make_settings(
        AZURE_OPENAI_CHAT_ENDPOINT="https://example.openai.azure.com/",
        AZURE_OPENAI_CHAT_API_KEY="sk-test-chat-key",
    )
    assert validate_llm_config() is True


@patch("src.services.agent.llm_factory.get_settings")
def test_returns_true_when_non_chat_fallback_fields_set(mock_get_settings):
    """AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY should also satisfy the check."""
    mock_get_settings.return_value = _make_settings(
        AZURE_OPENAI_ENDPOINT="https://example.openai.azure.com/",
        AZURE_OPENAI_API_KEY="sk-test-key",
    )
    assert validate_llm_config() is True


@patch("src.services.agent.llm_factory.get_settings")
def test_chat_fields_take_priority_over_non_chat(mock_get_settings):
    """When both CHAT and non-CHAT are set, the result is still True."""
    mock_get_settings.return_value = _make_settings(
        AZURE_OPENAI_CHAT_ENDPOINT="https://chat.openai.azure.com/",
        AZURE_OPENAI_CHAT_API_KEY="sk-chat-key",
        AZURE_OPENAI_ENDPOINT="https://base.openai.azure.com/",
        AZURE_OPENAI_API_KEY="sk-base-key",
    )
    assert validate_llm_config() is True
