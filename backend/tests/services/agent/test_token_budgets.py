"""Phase 1 regression tests — token budgets for lightweight LLMs.

Trace 019e1554/019e1555 showed gpt-5-mini structured-output calls failing
with ``LengthFinishReasonError`` because reasoning_tokens (~2752) burned
the entire 256/512-token budget before any output. These tests pin the
classifier and reflection caller-side max_tokens at 4096.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
def test_classifier_llm_uses_4096_token_budget():
    """Classifier must request 4096 max_tokens to leave room for gpt-5-mini
    internal reasoning before structured output is emitted."""
    import src.services.agent.classifier as classifier_mod

    classifier_mod._CLASSIFIER_LLM = None  # force rebuild

    with patch(
        "src.services.agent.llm_factory.build_lightweight_llm"
    ) as builder:
        builder.return_value = MagicMock()
        classifier_mod._build_classifier_llm()
        assert builder.call_count == 1
        kwargs = builder.call_args.kwargs
        assert kwargs["max_tokens"] == 4096, (
            "Classifier must pass max_tokens=4096 to build_lightweight_llm; "
            "256 caused LengthFinishReasonError in trace 019e1554."
        )

    classifier_mod._CLASSIFIER_LLM = None


@pytest.mark.unit
def test_reflection_llm_uses_4096_token_budget():
    """Reflection must request 4096 max_tokens for same reason as classifier."""
    import src.services.agent.reflection as reflection_mod

    reflection_mod._REFLECTION_LLM = None  # force rebuild

    with patch(
        "src.services.agent.reflection.build_lightweight_llm"
    ) as builder:
        builder.return_value = MagicMock()
        reflection_mod._build_reflection_llm()
        assert builder.call_count == 1
        kwargs = builder.call_args.kwargs
        assert kwargs["max_tokens"] == 4096, (
            "Reflection must pass max_tokens=4096; 512 caused LengthFinishReasonError"
        )

    reflection_mod._REFLECTION_LLM = None


@pytest.mark.unit
def test_planner_lightweight_llm_uses_2048_token_budget():
    """Planner complexity-check LLM uses 2048 max_tokens (raised from 1024)."""
    from src.services.agent import planner as planner_mod

    with patch(
        "src.services.agent.planner.build_lightweight_llm"
    ) as builder:
        builder.return_value = MagicMock()
        planner_mod._build_planner_llm()
        assert builder.call_count == 1
        kwargs = builder.call_args.kwargs
        assert kwargs["max_tokens"] == 2048


@pytest.mark.unit
def test_settings_default_parallel_tool_calls_disabled():
    """Default config disables parallel tool calls.

    Trace 019e18f0 showed gpt-5 firing 13+ parallel search_arxiv calls
    across 4 rounds when this defaulted to True. Forcing sequential lets
    the model see one result before issuing the next call.
    """
    from src.core.config import get_settings

    settings = get_settings()
    assert settings.AGENT_PARALLEL_TOOL_CALLS is False, (
        "AGENT_PARALLEL_TOOL_CALLS must default to False — flip via env "
        "only when paper-vs-paper parallel comparison is intentional."
    )
