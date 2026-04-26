"""Unit tests for ``_build_llm`` model override (graph.py).

Verifies that ``_build_llm`` honors the per-request ``model_override`` so the
agent can route to any deployed Azure model (gpt-5, claude-sonnet-4-5, etc.)
instead of the configured default. Without an override it falls back to
``AZURE_OPENAI_CHAT_DEPLOYMENT_NAME``.
"""

from __future__ import annotations

from unittest.mock import patch


def _set_chat_settings(monkeypatch, **overrides):
    """Set the Azure chat-related settings on the shared settings instance."""
    from src.services.agent import graph as graph_module

    settings = graph_module.get_settings()
    defaults = {
        "AZURE_OPENAI_ENDPOINT": None,
        "AZURE_OPENAI_API_KEY": None,
        "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
        "AZURE_OPENAI_DEPLOYMENT_NAME": None,
        "AZURE_OPENAI_CHAT_ENDPOINT": "https://example.cognitiveservices.azure.com/openai/v1/",
        "AZURE_OPENAI_CHAT_API_KEY": "chat-key",
        "AZURE_OPENAI_CHAT_API_VERSION": "2024-12-01-preview",
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": "model-router",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(settings, key, value, raising=False)


@patch("langchain_openai.ChatOpenAI")
def test_build_llm_uses_configured_deployment_when_no_override(
    mock_chat_openai,
    monkeypatch,
):
    """No override → falls back to the configured deployment."""
    from src.services.agent.graph import _build_llm

    _set_chat_settings(monkeypatch)

    _build_llm()

    mock_chat_openai.assert_called_once()
    kwargs = mock_chat_openai.call_args.kwargs
    assert kwargs["model"] == "model-router"


@patch("langchain_openai.ChatOpenAI")
def test_build_llm_override_wins_over_settings(mock_chat_openai, monkeypatch):
    """A per-request override deployment is what reaches ChatOpenAI."""
    from src.services.agent.graph import _build_llm

    _set_chat_settings(monkeypatch)

    _build_llm(model_override="claude-sonnet-4-5")

    mock_chat_openai.assert_called_once()
    kwargs = mock_chat_openai.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-5"


@patch("langchain_openai.ChatOpenAI")
def test_build_llm_empty_override_falls_back_to_settings(
    mock_chat_openai,
    monkeypatch,
):
    """An empty-string override is treated as no override (server default wins)."""
    from src.services.agent.graph import _build_llm

    _set_chat_settings(monkeypatch)

    _build_llm(model_override="")

    mock_chat_openai.assert_called_once()
    kwargs = mock_chat_openai.call_args.kwargs
    assert kwargs["model"] == "model-router"


@patch("langchain_openai.AzureChatOpenAI")
def test_build_llm_override_threads_through_azure_client(
    mock_azure_chat,
    monkeypatch,
):
    """When the endpoint is plain Azure (not openai-compatible), override
    still wins — threaded through as ``azure_deployment``."""
    from src.services.agent.graph import _build_llm

    _set_chat_settings(
        monkeypatch,
        AZURE_OPENAI_CHAT_ENDPOINT="https://example.openai.azure.com",
    )

    _build_llm(model_override="gpt-5")

    mock_azure_chat.assert_called_once()
    kwargs = mock_azure_chat.call_args.kwargs
    assert kwargs["azure_deployment"] == "gpt-5"
