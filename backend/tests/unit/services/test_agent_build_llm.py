"""Unit tests for ``_build_llm`` model override (graph.py).

Verifies that ``_build_llm`` honors the per-request ``model_override`` so the
agent can route to any deployed Azure model (gpt-5, claude-sonnet-4-5, etc.)
instead of the configured default. Without an override it falls back to
``AZURE_OPENAI_CHAT_DEPLOYMENT_NAME``.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch


def _make_langchain_openai_mock():
    mock_module = types.ModuleType("langchain_openai")
    setattr(mock_module, "ChatOpenAI", MagicMock())
    setattr(mock_module, "AzureChatOpenAI", MagicMock())
    return mock_module


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


def _clear_llm_cache():
    """Clear the module-level LLM cache so each test builds a fresh client."""
    from src.services.agent import graph as graph_module
    graph_module._LLM_CACHE.clear()


def test_build_llm_uses_configured_deployment_when_no_override(monkeypatch):
    """No override → falls back to the configured deployment."""
    from src.services.agent.graph import _build_llm

    _clear_llm_cache()
    _set_chat_settings(monkeypatch)
    mock_lc = _make_langchain_openai_mock()
    with patch.dict(sys.modules, {"langchain_openai": mock_lc}):
        _build_llm()

    mock_lc.ChatOpenAI.assert_called_once()
    kwargs = mock_lc.ChatOpenAI.call_args.kwargs
    assert kwargs["model"] == "model-router"


def test_build_llm_override_wins_over_settings(monkeypatch):
    """A per-request override deployment is what reaches ChatOpenAI."""
    from src.services.agent.graph import _build_llm

    _clear_llm_cache()
    _set_chat_settings(monkeypatch)
    mock_lc = _make_langchain_openai_mock()
    with patch.dict(sys.modules, {"langchain_openai": mock_lc}):
        _build_llm(model_override="claude-sonnet-4-5")

    mock_lc.ChatOpenAI.assert_called_once()
    kwargs = mock_lc.ChatOpenAI.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-5"


def test_build_llm_empty_override_falls_back_to_settings(monkeypatch):
    """An empty-string override is treated as no override (server default wins)."""
    from src.services.agent.graph import _build_llm

    _clear_llm_cache()
    _set_chat_settings(monkeypatch)
    mock_lc = _make_langchain_openai_mock()
    with patch.dict(sys.modules, {"langchain_openai": mock_lc}):
        _build_llm(model_override="")

    mock_lc.ChatOpenAI.assert_called_once()
    kwargs = mock_lc.ChatOpenAI.call_args.kwargs
    assert kwargs["model"] == "model-router"


def test_build_llm_override_threads_through_azure_client(monkeypatch):
    """When the endpoint is plain Azure (not openai-compatible), override
    still wins — threaded through as ``azure_deployment``."""
    from src.services.agent.graph import _build_llm

    _clear_llm_cache()
    _set_chat_settings(
        monkeypatch,
        AZURE_OPENAI_CHAT_ENDPOINT="https://example.openai.azure.com",
    )
    mock_lc = _make_langchain_openai_mock()
    with patch.dict(sys.modules, {"langchain_openai": mock_lc}):
        _build_llm(model_override="gpt-5")

    mock_lc.AzureChatOpenAI.assert_called_once()
    kwargs = mock_lc.AzureChatOpenAI.call_args.kwargs
    assert kwargs["azure_deployment"] == "gpt-5"
