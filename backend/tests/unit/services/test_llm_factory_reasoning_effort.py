"""Unit tests for reasoning_effort suppression on tool-calling turns.

Azure rejects function tools sent alongside ``reasoning_effort`` on Chat
Completions (400 "Function tools with reasoning_effort are not supported for
this model in /v1/chat/completions"). #1334 dropped the kwarg in ``_build_llm``;
these cover the auxiliary builders in ``llm_factory``, whose results also reach
``bind_tools`` and ``with_structured_output(method="function_calling")``.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def azure_mock(monkeypatch):
    """Patch AzureChatOpenAI and point the factory at a gpt-5 deployment."""
    from src.services.agent import llm_factory

    llm_factory.reset_llm_caches()

    settings = llm_factory.get_settings()
    for key, value in {
        "AZURE_OPENAI_CHAT_ENDPOINT": "https://example.cognitiveservices.azure.com/",
        "AZURE_OPENAI_CHAT_API_KEY": "chat-key",
        "AZURE_OPENAI_CHAT_API_VERSION": "2024-12-01-preview",
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": "gpt-5",
        # Unset per-role overrides: the documented "one deployment everywhere"
        # setup, where synthesis/lightweight fall back to the main deployment.
        "AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT": None,
        "AZURE_OPENAI_SYNTHESIS_DEPLOYMENT": None,
        "AGENT_LIGHTWEIGHT_REASONING_EFFORT": "minimal",
    }.items():
        monkeypatch.setattr(settings, key, value, raising=False)

    azure_cls = MagicMock()
    module = types.ModuleType("langchain_openai")
    setattr(module, "AzureChatOpenAI", azure_cls)
    setattr(module, "ChatOpenAI", MagicMock())
    with patch.dict("sys.modules", {"langchain_openai": module}):
        yield azure_cls

    llm_factory.reset_llm_caches()


def _effort(azure_cls):
    return azure_cls.call_args.kwargs.get("reasoning_effort", "<absent>")


@pytest.mark.parametrize(
    "builder_name", ["build_synthesis_llm", "build_lightweight_llm"]
)
def test_effort_dropped_when_tools_are_bound(azure_mock, builder_name):
    from src.services.agent import llm_factory

    getattr(llm_factory, builder_name)(tool_calling=True)

    assert _effort(azure_mock) == "<absent>", (
        "reasoning_effort must not be sent on a turn that binds function "
        "tools — Azure returns 400 for the combination"
    )


@pytest.mark.parametrize(
    "builder_name", ["build_synthesis_llm", "build_lightweight_llm"]
)
def test_effort_kept_for_prose_and_classification(azure_mock, builder_name):
    from src.services.agent import llm_factory

    getattr(llm_factory, builder_name)()

    assert _effort(azure_mock) == "minimal"


def test_tool_calling_variants_are_cached_separately(azure_mock):
    """The flag is part of the cache key, else the first caller wins."""
    from src.services.agent import llm_factory

    llm_factory.build_synthesis_llm(max_tokens=4096)
    llm_factory.build_synthesis_llm(max_tokens=4096, tool_calling=True)

    assert azure_mock.call_count == 2
    assert _effort(azure_mock) == "<absent>"
