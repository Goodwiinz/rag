"""Unit tests for ``_runtime_model_line`` (graph.py).

The helper renders a 'Runtime model' line into the system prompt so the
agent can answer 'which model are you?' truthfully instead of guessing.
"""

from __future__ import annotations


def _set_chat_settings(monkeypatch, **overrides):
    from src.services.agent import graph as graph_module

    settings = graph_module.get_settings()
    defaults = {
        "AZURE_OPENAI_DEPLOYMENT_NAME": None,
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": "model-router",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(settings, key, value, raising=False)


def test_runtime_model_line_for_model_router_explains_per_request_routing(monkeypatch):
    from src.services.agent.graph import _runtime_model_line

    _set_chat_settings(monkeypatch, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="model-router")
    line = _runtime_model_line(None)

    assert line.startswith("Runtime model:")
    assert "model-router" in line
    assert "selected per request" in line


def test_runtime_model_line_for_specific_deployment_names_it(monkeypatch):
    from src.services.agent.graph import _runtime_model_line

    _set_chat_settings(monkeypatch, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="gpt-5-chat")
    line = _runtime_model_line(None)

    assert line == "Runtime model: routed via Azure deployment `gpt-5-chat`."


def test_runtime_model_line_honors_request_override(monkeypatch):
    from src.services.agent.graph import _runtime_model_line

    _set_chat_settings(monkeypatch, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="some-default")
    line = _runtime_model_line("model-router")

    assert "model-router" in line
    assert "some-default" not in line


def test_runtime_model_line_returns_empty_when_nothing_configured(monkeypatch):
    from src.services.agent.graph import _runtime_model_line

    _set_chat_settings(
        monkeypatch,
        AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=None,
        AZURE_OPENAI_DEPLOYMENT_NAME=None,
    )

    assert _runtime_model_line(None) == ""
