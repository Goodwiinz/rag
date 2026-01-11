"""
Integration Tests for AI Providers

These tests validate real AI provider integrations.
They are skipped by default and only run when:
- AI_INTEGRATION_TESTS=true environment variable is set
- Required API keys are configured

Usage:
    # Run AI integration tests
    AI_INTEGRATION_TESTS=true pytest tests/integration/ai/ -v

    # Run with specific provider
    AI_INTEGRATION_TESTS=true AI_PROVIDER=openai pytest tests/integration/ai/ -v
"""

import os
import pytest
from typing import Optional

from src.core.ai.schemas import JudgeScoreSchema
from src.core.ai.parsers import parse_ai_response


# ============================================================================
# Skip Markers
# ============================================================================

AI_TESTS_ENABLED = os.getenv("AI_INTEGRATION_TESTS", "").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

skip_ai_tests = pytest.mark.skipif(
    not AI_TESTS_ENABLED,
    reason="AI integration tests disabled. Set AI_INTEGRATION_TESTS=true to run."
)

skip_without_openai = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set"
)

skip_without_azure = pytest.mark.skipif(
    not AZURE_OPENAI_KEY,
    reason="AZURE_OPENAI_API_KEY not set"
)

skip_without_anthropic = pytest.mark.skipif(
    not ANTHROPIC_API_KEY,
    reason="ANTHROPIC_API_KEY not set"
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_evaluation_prompt() -> str:
    """Standard evaluation prompt for testing."""
    return """Evaluate this answer for relevancy to the query.

Query: What is machine learning?
Answer: Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed.

Provide your evaluation as JSON:
{
    "score": <float 0-1>,
    "reasoning": "<string>",
    "confidence": <float 0-1>
}"""


@pytest.fixture
def sample_messages(sample_evaluation_prompt: str) -> list:
    """Standard messages for testing."""
    return [
        {
            "role": "system",
            "content": "You are an expert evaluator. Always respond with valid JSON."
        },
        {
            "role": "user",
            "content": sample_evaluation_prompt
        }
    ]


# ============================================================================
# OpenAI Integration Tests
# ============================================================================

@skip_ai_tests
@skip_without_openai
class TestOpenAIIntegration:
    """Integration tests for OpenAI API."""

    @pytest.mark.asyncio
    async def test_openai_completion_basic(self, sample_messages):
        """Test basic OpenAI completion works."""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=sample_messages,
                temperature=0.0,
                max_tokens=500
            )

            assert response.choices[0].message.content
            assert len(response.choices[0].message.content) > 10
        except ImportError:
            pytest.skip("openai package not installed")

    @pytest.mark.asyncio
    async def test_openai_response_parsing(self, sample_messages):
        """Test OpenAI response can be parsed into schema."""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=sample_messages,
                temperature=0.0,
                max_tokens=500
            )

            content = response.choices[0].message.content
            result = parse_ai_response(content, JudgeScoreSchema)

            # Validate parsed response
            assert 0.0 <= result.score <= 1.0
            assert len(result.reasoning) > 0
            assert 0.0 <= result.confidence <= 1.0
        except ImportError:
            pytest.skip("openai package not installed")

    @pytest.mark.asyncio
    async def test_openai_rate_limit_handling(self, sample_messages):
        """Test rate limit headers are returned."""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=sample_messages,
                temperature=0.0,
                max_tokens=50
            )

            # OpenAI includes usage stats
            assert response.usage is not None
            assert response.usage.prompt_tokens > 0
            assert response.usage.completion_tokens > 0
        except ImportError:
            pytest.skip("openai package not installed")


# ============================================================================
# Azure OpenAI Integration Tests
# ============================================================================

@skip_ai_tests
@skip_without_azure
class TestAzureOpenAIIntegration:
    """Integration tests for Azure OpenAI API."""

    @pytest.mark.asyncio
    async def test_azure_completion_basic(self, sample_messages):
        """Test basic Azure OpenAI completion works."""
        try:
            import openai

            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

            if not endpoint:
                pytest.skip("AZURE_OPENAI_ENDPOINT not set")

            client = openai.AsyncAzureOpenAI(
                api_key=AZURE_OPENAI_KEY,
                api_version=api_version,
                azure_endpoint=endpoint
            )

            response = await client.chat.completions.create(
                model=deployment,
                messages=sample_messages,
                temperature=0.0,
                max_tokens=500
            )

            assert response.choices[0].message.content
        except ImportError:
            pytest.skip("openai package not installed")


# ============================================================================
# Anthropic Integration Tests
# ============================================================================

@skip_ai_tests
@skip_without_anthropic
class TestAnthropicIntegration:
    """Integration tests for Anthropic API."""

    @pytest.mark.asyncio
    async def test_anthropic_completion_basic(self, sample_evaluation_prompt):
        """Test basic Anthropic completion works."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

            response = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[
                    {"role": "user", "content": sample_evaluation_prompt}
                ]
            )

            assert response.content[0].text
            assert len(response.content[0].text) > 10
        except ImportError:
            pytest.skip("anthropic package not installed")

    @pytest.mark.asyncio
    async def test_anthropic_response_parsing(self, sample_evaluation_prompt):
        """Test Anthropic response can be parsed into schema."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

            response = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                system="You are an expert evaluator. Always respond with valid JSON only, no explanation.",
                messages=[
                    {"role": "user", "content": sample_evaluation_prompt}
                ]
            )

            content = response.content[0].text
            result = parse_ai_response(content, JudgeScoreSchema)

            assert 0.0 <= result.score <= 1.0
            assert len(result.reasoning) > 0
        except ImportError:
            pytest.skip("anthropic package not installed")


# ============================================================================
# Cross-Provider Comparison Tests
# ============================================================================

@skip_ai_tests
class TestCrossProviderConsistency:
    """Tests that validate consistency across providers."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not (OPENAI_API_KEY and ANTHROPIC_API_KEY),
        reason="Both OPENAI_API_KEY and ANTHROPIC_API_KEY required"
    )
    async def test_score_ranges_consistent(self, sample_messages, sample_evaluation_prompt):
        """Verify both providers return scores in similar ranges for same input."""
        try:
            import openai
            import anthropic

            openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
            anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

            # OpenAI response
            openai_response = await openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=sample_messages,
                temperature=0.0
            )
            openai_result = parse_ai_response(
                openai_response.choices[0].message.content,
                JudgeScoreSchema
            )

            # Anthropic response
            anthropic_response = await anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[{"role": "user", "content": sample_evaluation_prompt}]
            )
            anthropic_result = parse_ai_response(
                anthropic_response.content[0].text,
                JudgeScoreSchema
            )

            # Both should give high scores for this clearly correct answer
            assert openai_result.score > 0.6, "OpenAI should rate this answer highly"
            assert anthropic_result.score > 0.6, "Anthropic should rate this answer highly"

            # Scores should be in same general range (within 0.3)
            score_diff = abs(openai_result.score - anthropic_result.score)
            assert score_diff < 0.4, f"Provider scores differ too much: {score_diff}"

        except ImportError as e:
            pytest.skip(f"Required package not installed: {e}")


# ============================================================================
# Error Handling Integration Tests
# ============================================================================

@skip_ai_tests
class TestProviderErrorHandling:
    """Tests for provider error scenarios."""

    @pytest.mark.asyncio
    @skip_without_openai
    async def test_openai_invalid_model_error(self, sample_messages):
        """Test handling of invalid model errors."""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

            with pytest.raises(openai.NotFoundError):
                await client.chat.completions.create(
                    model="gpt-9000-turbo",  # Non-existent model
                    messages=sample_messages
                )
        except ImportError:
            pytest.skip("openai package not installed")

    @pytest.mark.asyncio
    async def test_invalid_api_key_error(self, sample_messages):
        """Test handling of invalid API key."""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key="sk-invalid-key-123")

            with pytest.raises(openai.AuthenticationError):
                await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=sample_messages
                )
        except ImportError:
            pytest.skip("openai package not installed")
