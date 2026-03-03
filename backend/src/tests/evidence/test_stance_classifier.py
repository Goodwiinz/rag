"""
Unit tests for StanceClassifier service
"""

import asyncio
import hashlib
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from src.services.evidence.stance_classifier import (
    BatchClassificationLimitError,
    BatchClassificationTimeoutError,
    StanceClassificationResult,
    StanceClassifier,
)
from src.services.evidence.cache import EvidenceCacheService


@pytest.fixture
def mock_cache_service():
    """Mock cache service"""
    cache = Mock(spec=EvidenceCacheService)
    cache.get_stance_classification = AsyncMock(return_value=None)
    cache.set_stance_classification = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def stance_classifier(mock_cache_service):
    """StanceClassifier instance with mocked cache"""
    return StanceClassifier(cache_service=mock_cache_service)


@pytest.fixture
def sample_claim():
    """Sample claim for testing"""
    return "Vitamin D supplementation reduces COVID-19 severity"


@pytest.fixture
def sample_supporting_excerpt():
    """Sample excerpt that supports the claim"""
    return "Our meta-analysis found that vitamin D supplementation significantly reduced ICU admission rates and mortality in COVID-19 patients (p<0.001)."


@pytest.fixture
def sample_opposing_excerpt():
    """Sample excerpt that opposes the claim"""
    return "No significant difference was observed in COVID-19 outcomes between patients receiving vitamin D supplementation and controls (p=0.45)."


@pytest.fixture
def sample_neutral_excerpt():
    """Sample excerpt that is neutral"""
    return "Vitamin D levels were measured in all participants at baseline. The supplementation group received 1000 IU daily."


class TestStanceClassificationResult:
    """Test StanceClassificationResult model"""

    def test_valid_result(self):
        """Test valid result creation"""
        result = StanceClassificationResult(
            stance="supporting",
            confidence=0.85,
            justification_excerpt="Test excerpt"
        )

        assert result.stance == "supporting"
        assert result.confidence == 0.85
        assert result.justification_excerpt == "Test excerpt"

    def test_validation_error_invalid_confidence(self):
        """Test validation error for invalid confidence"""
        with pytest.raises(Exception):  # Pydantic validation error
            StanceClassificationResult(
                stance="supporting",
                confidence=1.5,  # Invalid confidence
                justification_excerpt="Test"
            )


class TestStanceClassifier:
    """Test StanceClassifier service"""

    def test_build_classification_prompt(self, stance_classifier, sample_claim, sample_supporting_excerpt):
        """Test prompt building"""
        prompt = stance_classifier._build_classification_prompt(sample_claim, sample_supporting_excerpt)

        assert sample_claim in prompt
        assert sample_supporting_excerpt in prompt
        assert "supporting" in prompt
        assert "opposing" in prompt
        assert "neutral" in prompt
        assert "not_addressed" in prompt
        assert "JSON" in prompt

    def test_generate_cache_key(self, stance_classifier):
        """Test cache key generation"""
        claim_hash = "abc123"
        source_id = str(uuid4())
        excerpt_hash = "def456"

        key = stance_classifier._generate_cache_key(claim_hash, source_id, excerpt_hash)

        assert claim_hash in key
        assert source_id in key
        assert excerpt_hash in key
        assert stance_classifier.model_version in key
        assert key.startswith("stance:")

    @patch('src.services.evidence.stance_classifier.openai')
    async def test_classify_with_openai_success(self, mock_openai, stance_classifier, sample_claim, sample_supporting_excerpt):
        """Test successful OpenAI classification"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "stance": "supporting",
            "confidence": 0.92,
            "justification_excerpt": "meta-analysis found significant reduction"
        })

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.AsyncOpenAI.return_value = mock_client

        with patch('src.services.evidence.stance_classifier.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"

            result = await stance_classifier._classify_with_openai(
                sample_claim, sample_supporting_excerpt, "gpt-4o-mini"
            )

        assert result is not None
        assert result.stance == "supporting"
        assert result.confidence == 0.92
        assert "meta-analysis" in result.justification_excerpt

    @patch('src.services.evidence.stance_classifier.openai')
    async def test_classify_with_openai_invalid_json(self, mock_openai, stance_classifier, sample_claim, sample_supporting_excerpt):
        """Test OpenAI with invalid JSON response"""
        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON response"

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.AsyncOpenAI.return_value = mock_client

        with patch('src.services.evidence.stance_classifier.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"

            result = await stance_classifier._classify_with_openai(
                sample_claim, sample_supporting_excerpt, "gpt-4o-mini"
            )

        assert result is None

    @patch('src.services.evidence.stance_classifier.openai')
    async def test_classify_with_openai_missing_fields(self, mock_openai, stance_classifier, sample_claim, sample_supporting_excerpt):
        """Test OpenAI with missing required fields"""
        # Mock response missing confidence field
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "stance": "supporting",
            "justification_excerpt": "test"
            # Missing confidence field
        })

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.AsyncOpenAI.return_value = mock_client

        with patch('src.services.evidence.stance_classifier.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"

            result = await stance_classifier._classify_with_openai(
                sample_claim, sample_supporting_excerpt, "gpt-4o-mini"
            )

        assert result is None

    async def test_classify_stance_with_cache_hit(self, stance_classifier, sample_claim, mock_cache_service):
        """Test classification with cache hit"""
        claim_hash = "test_hash"
        source_id = uuid4()
        excerpt = sample_claim

        # Mock cache hit
        cached_result = {
            "source_id": str(source_id),
            "stance": "supporting",
            "confidence": 0.85,
            "justification_excerpt": "cached excerpt",
            "model_version": "gpt-4o-mini-2024-07-18"
        }
        mock_cache_service.get_stance_classification.return_value = cached_result

        result = await stance_classifier.classify_stance(sample_claim, claim_hash, source_id, excerpt)

        assert result == cached_result
        mock_cache_service.get_stance_classification.assert_called_once()
        cache_key = mock_cache_service.get_stance_classification.call_args[0][0]
        expected_excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16]
        assert expected_excerpt_hash in cache_key
        mock_cache_service.set_stance_classification.assert_not_called()

    @patch('src.services.evidence.stance_classifier.StanceClassifier._classify_with_fallback')
    async def test_classify_stance_with_cache_miss(self, mock_classify, stance_classifier, sample_claim, mock_cache_service):
        """Test classification with cache miss"""
        claim_hash = "test_hash"
        source_id = uuid4()
        excerpt = sample_claim

        # Mock cache miss
        mock_cache_service.get_stance_classification.return_value = None

        # Mock successful classification
        mock_result = StanceClassificationResult(
            stance="supporting",
            confidence=0.90,
            justification_excerpt="test excerpt"
        )
        mock_classify.return_value = mock_result

        result = await stance_classifier.classify_stance(sample_claim, claim_hash, source_id, excerpt)

        assert result["stance"] == "supporting"
        assert result["confidence"] == 0.90
        assert result["source_id"] == str(source_id)
        mock_cache_service.get_stance_classification.assert_called_once()
        mock_cache_service.set_stance_classification.assert_called_once()

    @patch('src.services.evidence.stance_classifier.StanceClassifier.classify_stance')
    async def test_classify_sources_batch(self, mock_classify, stance_classifier, sample_claim):
        """Test batch classification"""
        sources = [
            {"source_id": uuid4(), "excerpt": "excerpt 1"},
            {"source_id": uuid4(), "excerpt": "excerpt 2"}
        ]

        # Mock individual classifications
        mock_classify.side_effect = [
            {"stance": "supporting", "confidence": 0.85},
            {"stance": "opposing", "confidence": 0.80}
        ]

        results = await stance_classifier.classify_sources_batch(
            sample_claim, "test_hash", sources
        )

        assert len(results) == 2
        assert results[0]["stance"] == "supporting"
        assert results[1]["stance"] == "opposing"
        assert mock_classify.call_count == 2

    @patch('src.services.evidence.stance_classifier.StanceClassifier.classify_stance')
    async def test_classify_sources_batch_with_failures(self, mock_classify, stance_classifier, sample_claim):
        """Test batch classification with some failures"""
        sources = [
            {"source_id": uuid4(), "excerpt": "excerpt 1"},
            {"source_id": uuid4(), "excerpt": "excerpt 2"}
        ]

        # Mock one success, one failure
        mock_classify.side_effect = [
            {"stance": "supporting", "confidence": 0.85},
            Exception("Classification failed")
        ]

        results = await stance_classifier.classify_sources_batch(
            sample_claim, "test_hash", sources
        )

        assert len(results) == 2
        assert results[0]["stance"] == "supporting"
        assert results[1] is None  # Failed classification

    async def test_classify_sources_batch_limit_enforced(self, stance_classifier, sample_claim):
        """Batch should reject requests over configured source limit."""
        stance_classifier.max_batch_sources = 1
        sources = [
            {"source_id": uuid4(), "excerpt": "excerpt 1"},
            {"source_id": uuid4(), "excerpt": "excerpt 2"},
        ]

        with pytest.raises(BatchClassificationLimitError):
            await stance_classifier.classify_sources_batch(sample_claim, "test_hash", sources)

    async def test_classify_sources_batch_timeout_enforced(self, stance_classifier, sample_claim):
        """Batch should fail with timeout when processing exceeds configured total timeout."""
        stance_classifier.batch_timeout_seconds = 0.01

        async def slow_classify(*args, **kwargs):
            await asyncio.sleep(0.05)
            return {"stance": "supporting", "confidence": 0.9}

        sources = [{"source_id": uuid4(), "excerpt": "excerpt 1"}]

        with patch.object(stance_classifier, "classify_stance", side_effect=slow_classify):
            with pytest.raises(BatchClassificationTimeoutError):
                await stance_classifier.classify_sources_batch(sample_claim, "test_hash", sources)
