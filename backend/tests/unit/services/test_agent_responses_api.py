"""Unit tests for the Azure Responses API opt-in (AGENT_USE_RESPONSES_API).

Chat Completions rejects function tools sent with ``reasoning_effort``; the
Responses API accepts them (api-version >= 2025-04-01-preview). The flag lets
_build_llm switch, and ``normalize_ai_content`` hides the resulting typed
content blocks from everything downstream.
"""

from __future__ import annotations

import types
from collections.abc import Iterator
from typing import Any, Callable
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


def _azure_module() -> types.ModuleType:
    module = types.ModuleType("langchain_openai")
    setattr(module, "AzureChatOpenAI", MagicMock())
    setattr(module, "ChatOpenAI", MagicMock())
    return module


@pytest.fixture
def build(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[[bool], dict[str, Any]]]:
    """Return (call_build_llm, azure_cls) with settings pinned to a gpt-5 deployment."""
    from src.services.agent import graph as graph_module

    settings = graph_module.get_settings()
    for key, value in {
        "AZURE_OPENAI_CHAT_ENDPOINT": "https://example.cognitiveservices.azure.com/",
        "AZURE_OPENAI_CHAT_API_KEY": "chat-key",
        "AZURE_OPENAI_CHAT_API_VERSION": "2025-04-01-preview",
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": "gpt-5.6-luna",
        "AGENT_MAIN_REASONING_EFFORT": "medium",
    }.items():
        monkeypatch.setattr(settings, key, value, raising=False)

    module = _azure_module()

    def _run(use_responses: bool) -> dict[str, Any]:
        monkeypatch.setattr(
            settings, "AGENT_USE_RESPONSES_API", use_responses, raising=False
        )
        graph_module._LLM_CACHE.clear()
        with patch.dict("sys.modules", {"langchain_openai": module}):
            graph_module._build_llm()
        return module.AzureChatOpenAI.call_args.kwargs

    yield _run
    graph_module._LLM_CACHE.clear()


def test_chat_completions_is_the_default_and_sends_no_effort(
    build: Callable[[bool], dict[str, Any]],
) -> None:
    kwargs = build(False)

    assert kwargs["use_responses_api"] is False
    assert "reasoning_effort" not in kwargs, (
        "Chat Completions 400s when function tools and reasoning_effort are "
        "sent together, and every _build_llm consumer binds tools"
    )


def test_responses_api_opt_in_restores_reasoning_effort(
    build: Callable[[bool], dict[str, Any]],
) -> None:
    kwargs = build(True)

    assert kwargs["use_responses_api"] is True
    assert kwargs["reasoning_effort"] == "medium"


class TestNormalizeAiContent:
    """The Responses API returns typed blocks where downstream expects str."""

    def test_string_content_passes_through_untouched(self) -> None:
        from src.services.agent._nodes_llm import normalize_ai_content

        msg = AIMessage(content="plain text")
        assert normalize_ai_content(msg) is msg

    def test_text_blocks_are_joined(self) -> None:
        from src.services.agent._nodes_llm import normalize_ai_content

        msg = AIMessage(
            content=[
                {"type": "text", "text": "Here are "},
                {"type": "text", "text": "two papers."},
            ]
        )
        assert normalize_ai_content(msg).content == "Here are two papers."

    def test_reasoning_blocks_are_dropped(self) -> None:
        """rs_ items are not user-facing and must never reach the SSE wire."""
        from src.services.agent._nodes_llm import normalize_ai_content

        msg = AIMessage(
            content=[
                {"type": "reasoning", "id": "rs_abc", "summary": []},
                {"type": "text", "text": "The answer."},
            ]
        )
        assert normalize_ai_content(msg).content == "The answer."

    def test_tool_calls_survive_normalisation(self) -> None:
        """The tool loop breaks if tool_calls are lost while rewriting content."""
        from src.services.agent._nodes_llm import normalize_ai_content

        msg = AIMessage(
            content=[{"type": "reasoning", "id": "rs_1", "summary": []}],
            tool_calls=[
                {
                    "name": "search_arxiv",
                    "args": {"query": "rag"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        )
        out = normalize_ai_content(msg)

        assert out.content == ""
        assert len(out.tool_calls) == 1
        assert out.tool_calls[0]["id"] == "call_1"
