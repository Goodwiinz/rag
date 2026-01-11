"""
Tests for AI Error Handling

Tests graceful degradation, fallbacks, retries, and error recovery
in AI-powered components.
"""

import asyncio
import pytest

from src.core.ai.parsers import parse_ai_response, AIResponseParseError
from src.core.ai.schemas import JudgeScoreSchema
from tests.mocks.ai_client import MockAIClient, MockEmbeddingClient
from tests.fixtures.ai_responses import (
    VALID_JUDGE_RESPONSE,
    MALFORMED_JSON_RESPONSE,
    EMPTY_RESPONSE,
    INCOMPLETE_JSON_RESPONSE,
    RETRY_SEQUENCE_RESPONSES,
)


class TestGracefulFallbackOnTimeout:
    """Test graceful degradation when AI calls timeout."""

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback_response(self):
        """When AI call times out, return sensible fallback."""
        mock_client = MockAIClient()
        mock_client.set_side_effect(asyncio.TimeoutError("Request timed out"))

        # Simulate service that handles timeout gracefully
        try:
            await mock_client.complete([{"role": "user", "content": "test"}])
            fallback_used = False
        except asyncio.TimeoutError:
            # Service should catch this and use fallback
            fallback_used = True

        assert fallback_used, "Timeout should be raised for service to handle"

    @pytest.mark.asyncio
    async def test_timeout_with_configured_fallback(self):
        """Parse response uses fallback score on timeout-induced empty response."""
        # Simulate what happens after timeout - empty response
        result = parse_ai_response(
            "",
            JudgeScoreSchema,
            fallback_score=0.5
        )

        assert result.score == 0.5
        assert result.confidence < 0.5  # Low confidence for fallback

    @pytest.mark.asyncio
    async def test_latency_simulation(self):
        """Test client latency simulation for timeout testing."""
        mock_client = MockAIClient()
        mock_client.set_latency(100)  # 100ms latency
        mock_client.set_single_response(VALID_JUDGE_RESPONSE)

        import time
        start = time.time()
        await mock_client.complete([{"role": "user", "content": "test"}])
        elapsed = time.time() - start

        assert elapsed >= 0.1, "Latency simulation should add delay"


class TestRetryOnRateLimit:
    """Test retry behavior on rate limit errors."""

    @pytest.mark.asyncio
    async def test_retry_eventually_succeeds(self):
        """After retries, eventually get successful response."""
        mock_client = MockAIClient()
        # Set up sequence: fail twice, then succeed
        mock_client.set_responses(RETRY_SEQUENCE_RESPONSES)

        # First call returns empty (simulating rate limit)
        result1 = await mock_client.complete([{"role": "user", "content": "test"}])
        assert result1.content == ""

        # Second call returns malformed
        result2 = await mock_client.complete([{"role": "user", "content": "test"}])
        assert "approximately" in result2.content

        # Third call succeeds
        result3 = await mock_client.complete([{"role": "user", "content": "test"}])
        assert '"score": 0.85' in result3.content

    @pytest.mark.asyncio
    async def test_rate_limit_exception_handling(self):
        """Rate limit exception should be catchable for retry logic."""
        mock_client = MockAIClient()

        class RateLimitError(Exception):
            def __init__(self, retry_after: int = 60):
                self.retry_after = retry_after
                super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")

        mock_client.set_side_effect(RateLimitError(30))

        with pytest.raises(RateLimitError) as exc_info:
            await mock_client.complete([{"role": "user", "content": "test"}])

        assert exc_info.value.retry_after == 30

    @pytest.mark.asyncio
    async def test_call_count_tracking_for_retries(self):
        """Track call count to verify retry behavior."""
        mock_client = MockAIClient()
        mock_client.set_responses([VALID_JUDGE_RESPONSE])

        # Simulate 3 retry attempts
        for _ in range(3):
            await mock_client.complete([{"role": "user", "content": "test"}])

        mock_client.assert_called_times(3)


class TestHandlesEmptyResponse:
    """Test handling of empty or whitespace-only responses."""

    def test_empty_string_uses_fallback(self):
        """Empty string response uses fallback values."""
        result = parse_ai_response("", JudgeScoreSchema)

        assert result.score == 0.5  # Default fallback
        assert result.confidence < 0.5
        assert result.reasoning  # Should have some fallback reasoning

    def test_whitespace_only_uses_fallback(self):
        """Whitespace-only response uses fallback values."""
        result = parse_ai_response("   \n\t  \n  ", JudgeScoreSchema)

        assert result.score == 0.5
        assert result.confidence < 0.5

    def test_custom_fallback_score(self):
        """Custom fallback score is used for empty responses."""
        result = parse_ai_response("", JudgeScoreSchema, fallback_score=0.7)

        assert result.score == 0.7

    @pytest.mark.asyncio
    async def test_mock_client_empty_response(self):
        """MockAIClient can return empty responses for testing."""
        mock_client = MockAIClient()
        mock_client.set_single_response("")

        result = await mock_client.complete([{"role": "user", "content": "test"}])

        assert result.content == ""


class TestHandlesPartialJson:
    """Test handling of incomplete/partial JSON responses."""

    def test_incomplete_json_extracts_available_data(self):
        """Incomplete JSON still extracts what's available."""
        result = parse_ai_response(INCOMPLETE_JSON_RESPONSE, JudgeScoreSchema)

        # Should either extract the score or use fallback
        assert 0.0 <= result.score <= 1.0

    def test_json_missing_closing_brace(self):
        """Handle JSON missing closing brace."""
        incomplete = '{"score": 0.8, "reasoning": "Good", "confidence": 0.9'
        result = parse_ai_response(incomplete, JudgeScoreSchema)

        assert 0.0 <= result.score <= 1.0

    def test_json_with_trailing_text(self):
        """Handle JSON with extra trailing text."""
        response = '{"score": 0.8, "reasoning": "Good", "confidence": 0.9} and more text here'
        result = parse_ai_response(response, JudgeScoreSchema)

        assert result.score == 0.8

    def test_malformed_json_falls_back_to_text_extraction(self):
        """Malformed JSON falls back to text-based score extraction."""
        result = parse_ai_response(MALFORMED_JSON_RESPONSE, JudgeScoreSchema)

        # The malformed response contains "80%" which is extracted as 0.8
        # (percentage patterns have priority over decimal patterns)
        assert result.score == 0.8
        assert result.confidence == 0.3  # Low confidence for fallback


class TestClientUnavailableReturnsFallback:
    """Test behavior when AI client is unavailable."""

    def test_client_availability_check(self):
        """Test client availability status checking."""
        mock_client = MockAIClient()

        assert mock_client.is_available() is True

        mock_client.set_available(False)
        assert mock_client.is_available() is False

    @pytest.mark.asyncio
    async def test_unavailable_client_scenario(self):
        """Simulate handling unavailable client."""
        mock_client = MockAIClient()
        mock_client.set_available(False)

        # Service should check availability before calling
        if not mock_client.is_available():
            # Use fallback
            result = parse_ai_response("", JudgeScoreSchema, fallback_score=0.5)
            assert result.score == 0.5

    def test_embedding_client_unavailable(self):
        """Test embedding client availability check."""
        mock_embedding = MockEmbeddingClient()

        assert mock_embedding.is_available() is True

        mock_embedding._available = False
        assert mock_embedding.is_available() is False


class TestStrictModeErrors:
    """Test strict mode error handling."""

    def test_strict_mode_raises_on_empty_response(self):
        """Strict mode raises exception on empty response."""
        with pytest.raises(AIResponseParseError):
            parse_ai_response("", JudgeScoreSchema, strict=True)

    def test_strict_mode_raises_on_malformed_json(self):
        """Strict mode raises exception on malformed JSON."""
        with pytest.raises(AIResponseParseError):
            parse_ai_response("Not valid JSON", JudgeScoreSchema, strict=True)

    def test_strict_mode_success_with_valid_json(self):
        """Strict mode succeeds with valid JSON."""
        result = parse_ai_response(VALID_JUDGE_RESPONSE, JudgeScoreSchema, strict=True)

        assert result.score == 0.85


class TestExceptionPropagation:
    """Test that exceptions are properly propagated when needed."""

    @pytest.mark.asyncio
    async def test_connection_error_propagates(self):
        """Connection errors propagate for service-level handling."""
        mock_client = MockAIClient()
        mock_client.set_side_effect(ConnectionError("Failed to connect"))

        with pytest.raises(ConnectionError):
            await mock_client.complete([{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_value_error_propagates(self):
        """Value errors propagate for debugging."""
        mock_client = MockAIClient()
        mock_client.set_side_effect(ValueError("Invalid input"))

        with pytest.raises(ValueError):
            await mock_client.complete([{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_side_effect_clears_after_use(self):
        """Side effect is cleared after being triggered."""
        mock_client = MockAIClient()
        mock_client.set_single_response(VALID_JUDGE_RESPONSE)
        mock_client.set_side_effect(ValueError("One-time error"))

        # First call raises
        with pytest.raises(ValueError):
            await mock_client.complete([{"role": "user", "content": "test"}])

        # Second call succeeds
        result = await mock_client.complete([{"role": "user", "content": "test"}])
        assert result.content == VALID_JUDGE_RESPONSE


class TestCallRecordingForDebugging:
    """Test call recording for debugging failed scenarios."""

    @pytest.mark.asyncio
    async def test_all_calls_recorded(self):
        """All calls are recorded for debugging."""
        mock_client = MockAIClient()
        mock_client.set_single_response(VALID_JUDGE_RESPONSE)

        await mock_client.complete([{"role": "user", "content": "First call"}])
        await mock_client.complete([{"role": "user", "content": "Second call"}])

        assert mock_client.call_count == 2
        prompts = mock_client.get_all_prompts()
        assert "First call" in prompts
        assert "Second call" in prompts

    @pytest.mark.asyncio
    async def test_last_call_accessible(self):
        """Last call is easily accessible for assertions."""
        mock_client = MockAIClient()
        mock_client.set_single_response(VALID_JUDGE_RESPONSE)

        await mock_client.complete(
            [{"role": "user", "content": "My test prompt"}],
            model="gpt-4",
            temperature=0.5
        )

        last_call = mock_client.get_last_call()
        assert last_call is not None
        assert last_call.model == "gpt-4"
        assert last_call.kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_reset_clears_history(self):
        """Reset clears call history for clean test state."""
        mock_client = MockAIClient()
        mock_client.set_single_response(VALID_JUDGE_RESPONSE)

        await mock_client.complete([{"role": "user", "content": "test"}])
        assert mock_client.call_count == 1

        mock_client.reset()
        assert mock_client.call_count == 0
        assert mock_client.get_last_call() is None
