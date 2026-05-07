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
