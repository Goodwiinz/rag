"""Unit tests for ``llm_factory`` deployment resolution.

``_resolve_lightweight_deployment`` reads
``AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`` and falls back to the **main chat
deployment** when unset or empty. It used to fall back to ``model-router``,
which meant a blank secret silently put the router back inside the agent
loop — the configuration behind the 30s timeout cap on research_llm_node
(trace 019e1da5). Leaving the per-role overrides unset is now the supported
way to run one deployment everywhere.
"""

from __future__ import annotations

import pytest


def _set_lightweight_settings(monkeypatch, value):
    """Set AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT on the shared settings instance."""
    from src.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(
        settings, "AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT", value, raising=False
    )


def _set_main_deployment(monkeypatch, value):
    from src.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(
        settings, "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", value, raising=False
    )


@pytest.mark.unit
class TestResolveLightweightDeployment:
    def test_falls_back_to_main_deployment_when_unset(self, monkeypatch):
        """Unset override == run the main deployment, never the router."""
        _set_lightweight_settings(monkeypatch, None)
        _set_main_deployment(monkeypatch, "gpt-5.6-luna")

        from src.services.agent.llm_factory import _resolve_lightweight_deployment

        assert _resolve_lightweight_deployment() == "gpt-5.6-luna"

    def test_custom_value(self, monkeypatch):
        """When env var is set to a custom deployment, should return that value."""
        _set_lightweight_settings(monkeypatch, "gpt-5-mini")

        from src.services.agent.llm_factory import _resolve_lightweight_deployment

        assert _resolve_lightweight_deployment() == "gpt-5-mini"

    def test_empty_string_falls_back_to_main_deployment(self, monkeypatch):
        """A blank secret is the realistic misconfiguration, not an unset one."""
        _set_lightweight_settings(monkeypatch, "")
        _set_main_deployment(monkeypatch, "gpt-5.6-luna")

        from src.services.agent.llm_factory import _resolve_lightweight_deployment

        assert _resolve_lightweight_deployment() == "gpt-5.6-luna"

    def test_never_resolves_to_model_router_implicitly(self, monkeypatch):
        """The router must not re-enter the agent loop through a blank value."""
        _set_lightweight_settings(monkeypatch, "")
        _set_main_deployment(monkeypatch, "gpt-5.6-luna")

        from src.services.agent.llm_factory import (
            _resolve_lightweight_deployment,
            _resolve_synthesis_deployment,
        )

        monkeypatch.setattr(
            __import__("src.core.config", fromlist=["get_settings"]).get_settings(),
            "AZURE_OPENAI_SYNTHESIS_DEPLOYMENT",
            "",
            raising=False,
        )
        assert _resolve_lightweight_deployment() != "model-router"
        assert _resolve_synthesis_deployment() != "model-router"


def test_fast_path_deployment_defaults_to_luna(monkeypatch):
    from src.core.config import get_settings
    from src.services.agent.llm_factory import _resolve_fast_path_deployment

    settings = get_settings()
    monkeypatch.setattr(
        settings, "AGENT_FAST_PATH_DEPLOYMENT", "gpt-5.6-luna", raising=False
    )

    assert _resolve_fast_path_deployment() == "gpt-5.6-luna"


@pytest.mark.unit
class TestBuilderCaching:
    """build_synthesis_llm / build_lightweight_llm cache one instance per args."""

    @pytest.fixture(autouse=True)
    def _clear_factory_caches(self):
        from src.services.agent.llm_factory import reset_llm_caches

        reset_llm_caches()
        yield
        reset_llm_caches()

    def test_synthesis_same_args_returns_same_object(self, monkeypatch):
        from src.services.agent import llm_factory

        monkeypatch.setattr(llm_factory, "_build_chat_llm", lambda *a, **k: object())
        a = llm_factory.build_synthesis_llm(max_tokens=4096)
        b = llm_factory.build_synthesis_llm(max_tokens=4096)
        assert a is b  # cache hit — built once

    def test_synthesis_different_args_returns_different_object(self, monkeypatch):
        from src.services.agent import llm_factory

        monkeypatch.setattr(llm_factory, "_build_chat_llm", lambda *a, **k: object())
        a = llm_factory.build_synthesis_llm(max_tokens=4096)
        b = llm_factory.build_synthesis_llm(max_tokens=512)
        assert a is not b

    def test_lightweight_caches_per_args(self, monkeypatch):
        from src.services.agent import llm_factory

        calls = {"n": 0}

        def _fake(*a, **k):
            calls["n"] += 1
            return object()

        monkeypatch.setattr(llm_factory, "_build_chat_llm", _fake)

        x = llm_factory.build_lightweight_llm(max_tokens=512)
        y = llm_factory.build_lightweight_llm(max_tokens=512)
        z = llm_factory.build_lightweight_llm(max_tokens=2048)
        assert x is y and x is not z
        assert calls["n"] == 2  # built once per distinct key

    def test_only_user_facing_synthesis_enables_streaming(self, monkeypatch):
        """Auxiliary JSON must stay buffered; final prose should emit chunks."""
        from src.services.agent import llm_factory

        calls = []

        def _fake(*args, **kwargs):
            calls.append(kwargs)
            return object()

        monkeypatch.setattr(llm_factory, "_build_chat_llm", _fake)

        llm_factory.build_lightweight_llm()
        llm_factory.build_synthesis_llm()

        assert calls[0]["streaming"] is False
        assert calls[1]["streaming"] is True
