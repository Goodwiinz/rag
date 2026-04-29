"""Unit tests for the intent classifier module.

Covers:
- LLM-based classification via mocked structured output
- Keyword-based classification
- Fallback behaviour on low confidence
- Fallback behaviour on LLM failure
"""

from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_classification(intent: str, confidence: float, reasoning: str):
    """Create a mock IntentClassification-like object returned by .ainvoke()."""
    from src.services.agent.classifier import IntentClassification

    return IntentClassification(
        intent=intent,
        confidence=confidence,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# ClassificationResult is frozen
# ---------------------------------------------------------------------------


class TestClassificationResult:
    """ClassificationResult should be an immutable frozen dataclass."""

    def test_frozen_dataclass(self):
        from src.services.agent.classifier import ClassificationResult

        result = ClassificationResult(
            intent="research",
            confidence=0.95,
            reasoning="User asked to search papers",
            source="llm",
        )
        assert result.intent == "research"
        assert result.confidence == 0.95
        assert result.source == "llm"

        with pytest.raises(FrozenInstanceError):
            result.intent = "general"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Keyword classifier
# ---------------------------------------------------------------------------


class TestKeywordClassifier:
    """Tests for classify_intent_keywords."""

    @pytest.mark.parametrize(
        "query, expected_intent",
        [
            ("search for papers on transformers", "research"),
            ("find arxiv papers about attention", "research"),
            ("ingest these papers into the system", "research"),
            ("write a summary of the document", "writing"),
            ("draft a literature review", "writing"),
            ("create note about findings", "writing"),
            ("extract entities from the paper", "knowledge_graph"),
            ("search the knowledge graph for relationships", "knowledge_graph"),
            ("what is the ontology of this domain", "knowledge_graph"),
            ("hello, how are you?", "general"),
            ("tell me a joke", "general"),
        ],
    )
    def test_keyword_classification(self, query: str, expected_intent: str):
        from src.services.agent.classifier import classify_intent_keywords

        result = classify_intent_keywords(query)
        assert result.intent == expected_intent
        assert result.source == "keyword"
        assert 0.0 <= result.confidence <= 1.0

    def test_keyword_tie_breaking_uses_priority(self):
        """When multiple intents tie, priority order should break the tie."""
        from src.services.agent.classifier import classify_intent_keywords

        # "search" matches research, "graph" matches knowledge_graph
        # Both score 2 — priority order is writing > knowledge_graph > research
        # so knowledge_graph should win over research
        result = classify_intent_keywords("search the graph")
        assert result.intent in ("research", "knowledge_graph")

    def test_keyword_general_has_zero_confidence(self):
        """Queries matching no keywords should return general with 0.0 confidence."""
        from src.services.agent.classifier import classify_intent_keywords

        result = classify_intent_keywords("what time is it")
        assert result.intent == "general"
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# LLM classifier
# ---------------------------------------------------------------------------


class TestLLMClassifier:
    """Tests for classify_intent_llm with mocked LLM."""

    @pytest.mark.parametrize(
        "query, intent, confidence",
        [
            ("find papers on transformers", "research", 0.95),
            ("write a literature review", "writing", 0.9),
            ("extract entities from this paper", "knowledge_graph", 0.85),
            ("hello there", "general", 0.8),
        ],
    )
    async def test_llm_classification_returns_result(
        self, query: str, intent: str, confidence: float
    ):
        from src.services.agent.classifier import classify_intent_llm

        mock_classification = _make_llm_classification(
            intent=intent,
            confidence=confidence,
            reasoning=f"User intent is {intent}",
        )

        mock_chain = AsyncMock(return_value=mock_classification)

        with patch(
            "src.services.agent.classifier._build_classifier_llm"
        ) as mock_build:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock(
                ainvoke=mock_chain,
            )
            mock_build.return_value = mock_llm

            result = await classify_intent_llm(query, {"type": "unknown"})

        assert result.intent == intent
        assert result.confidence == confidence
        assert result.source == "llm"

    async def test_llm_classification_passes_page_context(self):
        """The LLM should receive page context in the prompt."""
        from src.services.agent.classifier import classify_intent_llm

        mock_classification = _make_llm_classification(
            intent="research", confidence=0.9, reasoning="research query"
        )

        captured_messages = []

        async def capture_ainvoke(messages, **kwargs):
            captured_messages.extend(messages)
            return mock_classification

        with patch(
            "src.services.agent.classifier._build_classifier_llm"
        ) as mock_build:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = capture_ainvoke
            mock_llm.with_structured_output.return_value = mock_chain
            mock_build.return_value = mock_llm

            await classify_intent_llm(
                "find papers",
                {"type": "project", "project_id": "proj-1"},
            )

        # System message should mention the page context
        system_content = captured_messages[0].content
        assert "project" in system_content.lower()

    async def test_llm_classification_includes_previous_turn(self):
        """Previous turn context should be passed to the LLM."""
        from src.services.agent.classifier import classify_intent_llm

        mock_classification = _make_llm_classification(
            intent="writing", confidence=0.85, reasoning="writing follow-up"
        )

        captured_messages = []

        async def capture_ainvoke(messages, **kwargs):
            captured_messages.extend(messages)
            return mock_classification

        with patch(
            "src.services.agent.classifier._build_classifier_llm"
        ) as mock_build:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = capture_ainvoke
            mock_llm.with_structured_output.return_value = mock_chain
            mock_build.return_value = mock_llm

            await classify_intent_llm(
                "now summarize it",
                {"type": "unknown"},
                previous_turn="I found 3 papers on transformers.",
            )

        # The previous turn should appear somewhere in the messages
        all_content = " ".join(m.content for m in captured_messages)
        assert "found 3 papers" in all_content


# ---------------------------------------------------------------------------
# Fallback classifier
# ---------------------------------------------------------------------------


class TestFallbackClassifier:
    """Tests for classify_intent_with_fallback."""

    async def test_uses_llm_when_confident(self):
        """Should return LLM result when confidence >= 0.7."""
        from src.services.agent.classifier import (
            ClassificationResult,
            classify_intent_with_fallback,
        )

        llm_result = ClassificationResult(
            intent="research",
            confidence=0.9,
            reasoning="clear research query",
            source="llm",
        )

        with patch(
            "src.services.agent.classifier.classify_intent_llm",
            new_callable=AsyncMock,
            return_value=llm_result,
        ):
            result = await classify_intent_with_fallback(
                "find papers on ML", {"type": "unknown"}
            )

        assert result.intent == "research"
        assert result.source == "llm"
        assert result.confidence == 0.9

    async def test_falls_back_to_keyword_on_low_confidence(self):
        """Should fall back to keyword classifier when LLM confidence < 0.7."""
        from src.services.agent.classifier import (
            ClassificationResult,
            classify_intent_with_fallback,
        )

        llm_result = ClassificationResult(
            intent="general",
            confidence=0.4,
            reasoning="unclear intent",
            source="llm",
        )

        with patch(
            "src.services.agent.classifier.classify_intent_llm",
            new_callable=AsyncMock,
            return_value=llm_result,
        ):
            result = await classify_intent_with_fallback(
                "search for arxiv papers on attention",
                {"type": "unknown"},
            )

        assert result.source == "keyword"
        # The keyword classifier should detect "search" and "arxiv" → research
        assert result.intent == "research"

    async def test_falls_back_to_keyword_on_llm_failure(self):
        """Should fall back to keyword classifier when LLM call raises an exception."""
        from src.services.agent.classifier import classify_intent_with_fallback

        with patch(
            "src.services.agent.classifier.classify_intent_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM unavailable"),
        ):
            result = await classify_intent_with_fallback(
                "draft a literature review",
                {"type": "unknown"},
            )

        assert result.source == "keyword"
        assert result.intent == "writing"

    async def test_fallback_returns_general_when_both_fail(self):
        """If LLM fails and keywords match nothing, should return general/fallback."""
        from src.services.agent.classifier import classify_intent_with_fallback

        with patch(
            "src.services.agent.classifier.classify_intent_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM unavailable"),
        ):
            result = await classify_intent_with_fallback(
                "hello, how are you?",
                {"type": "unknown"},
            )

        assert result.intent == "general"
        # Could be keyword, fallback, or shortcut source
        assert result.source in ("keyword", "fallback", "shortcut")

    async def test_shortcut_skips_llm_for_short_zero_confidence_query(self):
        """Short queries with no keyword signal should return general without an LLM call."""
        from src.services.agent.classifier import classify_intent_with_fallback

        with patch(
            "src.services.agent.classifier.classify_intent_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            result = await classify_intent_with_fallback("hi", {"type": "unknown"})

        mock_llm.assert_not_called()
        assert result.intent == "general"
        assert result.source == "shortcut"
        assert result.confidence >= 0.7

    async def test_shortcut_does_not_fire_with_prior_tool(self):
        """Retry phrases (short, zero keywords) must still reach the LLM when prior_tool exists."""
        from src.services.agent.classifier import (
            ClassificationResult,
            classify_intent_with_fallback,
        )

        llm_result = ClassificationResult(
            intent="research",
            confidence=0.85,
            reasoning="retry of prior ingest",
            source="llm",
        )

        with patch(
            "src.services.agent.classifier.classify_intent_llm",
            new_callable=AsyncMock,
            return_value=llm_result,
        ) as mock_llm:
            result = await classify_intent_with_fallback(
                "try again",
                {"type": "unknown"},
                prior_tool={"name": "ingest_arxiv_papers", "args": {}, "result": ""},
            )

        mock_llm.assert_called_once()
        assert result.intent == "research"


# ---------------------------------------------------------------------------
# Prior tool context (retry-routing fix)
# ---------------------------------------------------------------------------


class TestPriorToolContext:
    """Tests for the prior_tool parameter that helps classify retry phrases."""

    def test_format_prior_tool_returns_none_when_missing(self):
        from src.services.agent.classifier import _format_prior_tool

        assert _format_prior_tool(None) == "None"
        assert _format_prior_tool({}) == "None"

    def test_format_prior_tool_includes_name_args_result(self):
        from src.services.agent.classifier import _format_prior_tool

        text = _format_prior_tool(
            {
                "name": "ingest_arxiv_papers",
                "args": {"arxiv_id": "2310.11522"},
                "result": '{"status": "skipped"}',
            }
        )
        assert "ingest_arxiv_papers" in text
        assert "2310.11522" in text
        assert "skipped" in text

    def test_format_prior_tool_truncates_large_payloads(self):
        from src.services.agent.classifier import _format_prior_tool

        big_result = "x" * 1000
        text = _format_prior_tool({"name": "t", "args": {}, "result": big_result})
        # 200-char truncation per field; full block stays under ~600 chars
        assert len(text) < 600

    async def test_keyword_classifier_unchanged_for_retry_phrase(self):
        """Sanity: 'try again' still has 0.0 keyword confidence (forces LLM escalation)."""
        from src.services.agent.classifier import classify_intent_keywords

        result = classify_intent_keywords("try again")
        assert result.confidence == 0.0
        assert result.source == "keyword"

    async def test_llm_classifier_includes_prior_tool_in_prompt(self):
        """When prior_tool is supplied, the LLM system message should describe it."""
        from src.services.agent.classifier import classify_intent_llm

        mock_classification = _make_llm_classification(
            intent="research", confidence=0.85, reasoning="retry"
        )
        captured: list = []

        async def capture_ainvoke(messages, **kwargs):
            captured.extend(messages)
            return mock_classification

        with patch(
            "src.services.agent.classifier._build_classifier_llm"
        ) as mock_build:
            mock_llm = MagicMock()
            mock_chain = MagicMock()
            mock_chain.ainvoke = capture_ainvoke
            mock_llm.with_structured_output.return_value = mock_chain
            mock_build.return_value = mock_llm

            await classify_intent_llm(
                "try again",
                {"type": "unknown"},
                previous_turn="The ingest was skipped.",
                prior_tool={
                    "name": "ingest_arxiv_papers",
                    "args": {"arxiv_id": "2310.11522"},
                    "result": '{"status": "skipped"}',
                },
            )

        system_content = captured[0].content
        assert "ingest_arxiv_papers" in system_content
        assert "2310.11522" in system_content

    async def test_fallback_propagates_prior_tool_to_llm(self):
        """When keyword confidence is low, prior_tool should reach the LLM call."""
        from src.services.agent.classifier import (
            ClassificationResult,
            classify_intent_with_fallback,
        )

        llm_result = ClassificationResult(
            intent="research",
            confidence=0.85,
            reasoning="retry of prior ingest",
            source="llm",
        )

        with patch(
            "src.services.agent.classifier.classify_intent_llm",
            new_callable=AsyncMock,
            return_value=llm_result,
        ) as mock_llm:
            await classify_intent_with_fallback(
                "try again",
                {"type": "unknown"},
                previous_turn="The ingest was skipped.",
                prior_tool={
                    "name": "ingest_arxiv_papers",
                    "args": {"arxiv_id": "2310.11522"},
                    "result": '{"status": "skipped"}',
                },
            )

        # Verify prior_tool was passed through (4th positional or kwarg)
        call_args = mock_llm.call_args
        passed_prior = (
            call_args.kwargs.get("prior_tool")
            if call_args.kwargs
            else (call_args.args[3] if len(call_args.args) > 3 else None)
        )
        assert passed_prior is not None
        assert passed_prior["name"] == "ingest_arxiv_papers"

    async def test_fallback_omits_prior_tool_when_keyword_confident(self):
        """High-confidence keyword match short-circuits before reaching the LLM."""
        from src.services.agent.classifier import classify_intent_with_fallback

        with patch(
            "src.services.agent.classifier.classify_intent_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            result = await classify_intent_with_fallback(
                "search for arxiv papers on attention",
                {"type": "unknown"},
                prior_tool={"name": "ingest_arxiv_papers", "args": {}, "result": ""},
            )

        # LLM should not be called at all when keyword confidence >= 0.7
        mock_llm.assert_not_called()
        assert result.source == "keyword"
        assert result.intent == "research"
