"""Unit tests for ``llm_factory`` lightweight deployment resolution.

Verifies that ``_resolve_lightweight_deployment`` correctly reads
``AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`` and falls back to ``model-router``
when the env var is unset or empty.
"""

from __future__ import annotations

import pytest


def _set_lightweight_settings(monkeypatch, value):
    """Set AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT on the shared settings instance."""
    from src.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT", value, raising=False)


@pytest.mark.unit
class TestResolveLightweightDeployment:
    def test_default_when_unset(self, monkeypatch):
        """When env var is None (unset), should return model-router."""
        _set_lightweight_settings(monkeypatch, None)

        from src.services.agent.llm_factory import _resolve_lightweight_deployment

        assert _resolve_lightweight_deployment() == "model-router"

    def test_custom_value(self, monkeypatch):
        """When env var is set to a custom deployment, should return that value."""
        _set_lightweight_settings(monkeypatch, "gpt-5-mini")

        from src.services.agent.llm_factory import _resolve_lightweight_deployment

        assert _resolve_lightweight_deployment() == "gpt-5-mini"

    def test_empty_string_falls_back(self, monkeypatch):
        """When env var is empty string (falsy), should fall back to model-router."""
        _set_lightweight_settings(monkeypatch, "")

        from src.services.agent.llm_factory import _resolve_lightweight_deployment

        assert _resolve_lightweight_deployment() == "model-router"


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
