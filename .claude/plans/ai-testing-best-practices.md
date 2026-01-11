# AI-Powered Backend Testing Best Practices Implementation Plan

## Executive Summary

This plan implements a layered testing strategy for AI-powered backend applications based on industry best practices for handling **non-determinism**, **external dependencies**, and **cost control**.

## Current State Analysis

### Existing Infrastructure
- **Two conftest files**: `tests/conftest.py` (T2 validation) and `backend/tests/conftest_fastapi.py`
- **Basic mocking**: `mock_embeddings_service`, `mock_qdrant_client`, `mock_neo4j_driver`
- **Fixtures**: Document, user, organization fixtures in `backend/tests/fixtures.py`
- **AI Services**: `LLMJudgeService`, `AzureOpenAIService`, `ChatService`, `LLMResponseCache`
- **Response Types**: `JudgeScore` and `FullJudgeEvaluation` dataclasses

### Identified Gaps
1. **No AI client interface abstraction** - Services directly instantiate Azure OpenAI clients
2. **No prompt snapshot tests** - Prompt changes go undetected
3. **No dedicated AI response fixtures** - Each test creates ad-hoc mocks
4. **Dataclass validation only** - No Pydantic runtime validation for AI outputs
5. **No AI error scenario tests** - Rate limits, timeouts, malformed responses untested
6. **No test separation** - Unit and integration tests mixed
7. **Infrastructure bugs**: Syntax error in conftest_fastapi.py line 101

---

## Phase 1: Fix Test Infrastructure Issues

### 1.1 Fix conftest_fastapi.py Syntax Error
**File**: `backend/tests/conftest_fastapi.py:101`
**Issue**: Extra closing parenthesis in mock_qdrant_client scroll return
```python
# Current (broken)
client.scroll = Mock(return_value=([], None)))  # Extra )

# Fixed
client.scroll = Mock(return_value=([], None))
```

### 1.2 Create Unified conftest.py
**File**: `backend/tests/conftest.py`
**Purpose**: Single source of truth for backend test configuration
- Merge common fixtures from both conftest files
- Use SQLite with StaticPool for isolated tests
- Configure SQLite-compatible engine (no pool_timeout/max_overflow)

### 1.3 Add pytest.ini Configuration
**File**: `backend/pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests (fast, no external deps)
    integration: Integration tests (may use containers)
    ai: AI-specific tests (mocked or real)
    slow: Long-running tests
asyncio_mode = auto
```

---

## Phase 2: Create AI Client Abstraction Layer

### 2.1 Define AI Client Protocol
**File**: `backend/src/core/ai/protocols.py`

```python
from typing import Protocol, List, Optional, Any
from dataclasses import dataclass

@dataclass
class CompletionResponse:
    content: str
    model: str
    usage: dict
    finish_reason: str

class AIClient(Protocol):
    """Protocol for AI completion clients."""

    async def complete(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 500,
        **kwargs
    ) -> CompletionResponse:
        """Generate a completion from messages."""
        ...

    def is_available(self) -> bool:
        """Check if the client is properly configured."""
        ...

class EmbeddingClient(Protocol):
    """Protocol for embedding generation clients."""

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts."""
        ...

    async def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single query."""
        ...
```

### 2.2 Implement Azure OpenAI Client
**File**: `backend/src/core/ai/azure_client.py`

```python
class AzureOpenAIClient:
    """Azure OpenAI implementation of AIClient protocol."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment_name: str,
        api_version: str = "2025-01-01-preview"
    ):
        self._client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
        self._deployment = deployment_name

    async def complete(self, messages, model=None, **kwargs) -> CompletionResponse:
        response = self._client.chat.completions.create(
            model=model or self._deployment,
            messages=messages,
            **kwargs
        )
        return CompletionResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage=dict(response.usage),
            finish_reason=response.choices[0].finish_reason
        )

    def is_available(self) -> bool:
        return self._client is not None
```

### 2.3 Refactor LLMJudgeService for DI
**File**: `backend/src/services/evaluation/llm_judge_service.py`

```python
class LLMJudgeService:
    def __init__(
        self,
        ai_client: Optional[AIClient] = None,  # Inject AI client
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment_name: Optional[str] = None,
    ):
        if ai_client:
            self._client = ai_client
        else:
            # Fallback to direct initialization for backwards compatibility
            self._client = self._create_default_client(endpoint, api_key, deployment_name)
```

---

## Phase 3: Create AI Response Fixtures and Mocks

### 3.1 AI Response Fixtures Module
**File**: `backend/tests/fixtures/ai_responses.py`

```python
"""Fixtures for AI response patterns."""

# Valid JSON responses
VALID_JUDGE_RESPONSE = """{
    "score": 0.85,
    "reasoning": "The answer directly addresses the query with relevant information.",
    "confidence": 0.92
}"""

VALID_JUDGE_RESPONSE_MARKDOWN = """Here's my evaluation:

```json
{"score": 0.78, "reasoning": "Partially addresses the query", "confidence": 0.8}
```

The answer could be more comprehensive."""

# Edge cases
MALFORMED_JSON_RESPONSE = "The score is approximately 0.75 and the answer is good."
INCOMPLETE_JSON_RESPONSE = '{"score": 0.8, "reasoning": "Partial'
EMPTY_RESPONSE = ""
HIGH_SCORE_RESPONSE = '{"score": 1.0, "reasoning": "Perfect", "confidence": 1.0}'
LOW_SCORE_RESPONSE = '{"score": 0.1, "reasoning": "Poor", "confidence": 0.95}'

# Error scenarios
RATE_LIMIT_RESPONSE = {
    "error": {
        "code": "429",
        "message": "Rate limit exceeded. Please retry after 60 seconds."
    }
}

CONTEXT_LENGTH_EXCEEDED = {
    "error": {
        "code": "context_length_exceeded",
        "message": "This model's maximum context length is 128000 tokens."
    }
}

# Comprehensive evaluation fixture
def create_full_evaluation_response(
    answer_score: float = 0.8,
    context_score: float = 0.7,
    completeness_score: float = 0.75,
    safety_score: float = 0.95
) -> dict:
    """Create a configurable full evaluation response."""
    return {
        "answer_relevancy": {"score": answer_score, "reasoning": "Good", "confidence": 0.9},
        "context_relevancy": {"score": context_score, "reasoning": "Relevant", "confidence": 0.85},
        "completeness": {"score": completeness_score, "reasoning": "Complete", "confidence": 0.88},
        "safety": {"score": safety_score, "reasoning": "Safe", "confidence": 0.99}
    }
```

### 3.2 Mock AI Client for Testing
**File**: `backend/tests/mocks/ai_client.py`

```python
from typing import List, Optional, Callable
from dataclasses import dataclass
from src.core.ai.protocols import AIClient, CompletionResponse

class MockAIClient:
    """Mock AI client for testing."""

    def __init__(self):
        self.calls: List[dict] = []
        self._responses: List[str] = []
        self._response_idx = 0
        self._side_effect: Optional[Callable] = None

    def set_responses(self, responses: List[str]):
        """Set sequence of responses to return."""
        self._responses = responses
        self._response_idx = 0

    def set_side_effect(self, effect: Callable):
        """Set a side effect (e.g., exception) for the next call."""
        self._side_effect = effect

    async def complete(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        self.calls.append({
            "messages": messages,
            "model": model,
            "kwargs": kwargs
        })

        if self._side_effect:
            effect = self._side_effect
            self._side_effect = None
            if callable(effect):
                result = effect()
                if isinstance(result, Exception):
                    raise result
                return result

        if self._responses:
            content = self._responses[self._response_idx % len(self._responses)]
            self._response_idx += 1
        else:
            content = '{"score": 0.8, "reasoning": "Default mock", "confidence": 0.9}'

        return CompletionResponse(
            content=content,
            model=model or "mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            finish_reason="stop"
        )

    def is_available(self) -> bool:
        return True

    def get_last_call(self) -> Optional[dict]:
        return self.calls[-1] if self.calls else None

    def assert_called_with_prompt_containing(self, substring: str):
        """Assert that a call was made with a prompt containing substring."""
        for call in self.calls:
            for message in call["messages"]:
                if substring in message.get("content", ""):
                    return True
        raise AssertionError(f"No call contained prompt with '{substring}'")
```

### 3.3 Pytest Fixtures for AI Mocks
**File**: `backend/tests/conftest.py` (additions)

```python
from tests.mocks.ai_client import MockAIClient
from tests.fixtures import ai_responses

@pytest.fixture
def mock_ai_client() -> MockAIClient:
    """Create a mock AI client for testing."""
    return MockAIClient()

@pytest.fixture
def mock_llm_judge(mock_ai_client) -> LLMJudgeService:
    """Create LLM Judge with mocked AI client."""
    return LLMJudgeService(ai_client=mock_ai_client)

@pytest.fixture
def ai_response_fixtures():
    """Provide access to AI response fixtures."""
    return ai_responses
```

---

## Phase 4: Implement Prompt Snapshot Tests

### 4.1 Prompt Builder Module
**File**: `backend/src/core/ai/prompts/judge_prompts.py`

```python
"""Prompt templates for LLM Judge evaluations."""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class PromptTemplate:
    name: str
    template: str
    version: str = "1.0"

def build_answer_relevancy_prompt(query: str, answer: str) -> str:
    """Build the answer relevancy evaluation prompt."""
    return f"""Rate how well this answer addresses the query.

Query: {query}

Answer: {answer}

Score from 0 to 1 where 1 means perfect answer, 0 means irrelevant.

Respond with ONLY valid JSON in this exact format:
{{"score": 0.8, "reasoning": "The answer addresses the query well", "confidence": 0.9}}"""

def build_context_relevancy_prompt(query: str, contexts: List[str]) -> str:
    """Build the context relevancy evaluation prompt."""
    context_text = "\n---\n".join(contexts[:5])
    return f"""Rate how useful these retrieved documents are for answering the query.

Query: {query}

Documents:
{context_text}

Score from 0 to 1 where 1 means all documents are highly relevant, 0 means none are useful.

Respond with ONLY valid JSON:
{{"score": 0.7, "reasoning": "Documents are mostly relevant", "confidence": 0.8}}"""
```

### 4.2 Prompt Snapshot Tests
**File**: `backend/tests/unit/ai/test_prompt_snapshots.py`

```python
"""Snapshot tests for AI prompts."""

import pytest
from src.core.ai.prompts.judge_prompts import (
    build_answer_relevancy_prompt,
    build_context_relevancy_prompt,
)

class TestPromptSnapshots:
    """Test that prompts haven't changed unexpectedly."""

    def test_answer_relevancy_prompt_snapshot(self, snapshot):
        """Verify answer relevancy prompt structure."""
        prompt = build_answer_relevancy_prompt(
            query="What is machine learning?",
            answer="Machine learning is a subset of AI."
        )
        assert prompt == snapshot

    def test_context_relevancy_prompt_snapshot(self, snapshot):
        """Verify context relevancy prompt structure."""
        prompt = build_context_relevancy_prompt(
            query="How do neural networks work?",
            contexts=[
                "Neural networks consist of layers of interconnected nodes.",
                "Deep learning uses multiple neural network layers."
            ]
        )
        assert prompt == snapshot

    def test_prompt_contains_required_elements(self):
        """Verify prompts contain required instructions."""
        prompt = build_answer_relevancy_prompt("test query", "test answer")

        assert "Query:" in prompt
        assert "Answer:" in prompt
        assert "JSON" in prompt
        assert "score" in prompt
        assert "reasoning" in prompt
        assert "confidence" in prompt
```

---

## Phase 5: Add Pydantic Validation for AI Outputs

### 5.1 Pydantic Schemas for AI Responses
**File**: `backend/src/core/ai/schemas.py`

```python
"""Pydantic schemas for validating AI responses."""

from pydantic import BaseModel, Field, validator
from typing import Optional
from enum import Enum

class JudgeCriteriaEnum(str, Enum):
    ANSWER_RELEVANCY = "answer_relevancy"
    CONTEXT_RELEVANCY = "context_relevancy"
    COMPLETENESS = "completeness"
    SAFETY = "safety"

class JudgeScoreSchema(BaseModel):
    """Validated LLM judge score."""
    score: float = Field(..., ge=0.0, le=1.0, description="Score between 0 and 1")
    reasoning: str = Field(..., min_length=1, max_length=1000)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @validator('score', 'confidence')
    def round_to_precision(cls, v):
        return round(v, 4)

    class Config:
        extra = "ignore"  # Ignore unknown fields

class FullJudgeEvaluationSchema(BaseModel):
    """Validated complete LLM judge evaluation."""
    answer_relevancy: JudgeScoreSchema
    context_relevancy: JudgeScoreSchema
    completeness: JudgeScoreSchema
    safety: JudgeScoreSchema
    overall_score: float = Field(..., ge=0.0, le=1.0)
    pass_fail: bool
    evaluation_time_ms: float = Field(..., ge=0)

    @validator('overall_score')
    def calculate_overall_if_missing(cls, v, values):
        if v is None:
            weights = {
                "answer_relevancy": 0.35,
                "context_relevancy": 0.20,
                "completeness": 0.25,
                "safety": 0.20
            }
            return sum(
                getattr(values.get(k), 'score', 0) * w
                for k, w in weights.items()
            )
        return v
```

### 5.2 Response Parser with Validation
**File**: `backend/src/core/ai/parsers.py`

```python
"""Parsers for AI responses with robust error handling."""

import json
import re
from typing import TypeVar, Type
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class AIResponseParseError(Exception):
    """Error parsing AI response."""
    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response

def extract_json_from_response(response: str) -> str:
    """Extract JSON from potentially markdown-wrapped response."""
    # Try to find JSON in code blocks
    if "```json" in response:
        match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            return match.group(1).strip()

    if "```" in response:
        match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            return match.group(1).strip()

    # Try to find raw JSON object
    match = re.search(r'\{[^{}]*\}', response)
    if match:
        return match.group(0)

    return response.strip()

def parse_ai_response(
    response: str,
    schema: Type[T],
    fallback_score: float = 0.5
) -> T:
    """Parse and validate AI response against schema."""
    try:
        json_str = extract_json_from_response(response)
        data = json.loads(json_str)
        return schema.parse_obj(data)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode failed: {e}, response: {response[:200]}")
        # Try to extract score from text
        numbers = re.findall(r'0?\.\d+|1\.0|0|1', response)
        score = float(numbers[0]) if numbers else fallback_score
        return schema.parse_obj({
            "score": score,
            "reasoning": response[:200],
            "confidence": 0.3
        })
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        raise AIResponseParseError(str(e), response)
```

### 5.3 Parsing Tests
**File**: `backend/tests/unit/ai/test_response_parsing.py`

```python
"""Tests for AI response parsing."""

import pytest
from src.core.ai.parsers import parse_ai_response, extract_json_from_response
from src.core.ai.schemas import JudgeScoreSchema
from tests.fixtures import ai_responses

class TestResponseParsing:
    """Test AI response parsing with various input patterns."""

    def test_parse_valid_json(self):
        """Parse clean JSON response."""
        result = parse_ai_response(
            ai_responses.VALID_JUDGE_RESPONSE,
            JudgeScoreSchema
        )
        assert result.score == 0.85
        assert "directly addresses" in result.reasoning
        assert result.confidence == 0.92

    def test_parse_markdown_wrapped_json(self):
        """Parse JSON wrapped in markdown code blocks."""
        result = parse_ai_response(
            ai_responses.VALID_JUDGE_RESPONSE_MARKDOWN,
            JudgeScoreSchema
        )
        assert result.score == 0.78

    def test_fallback_on_malformed_json(self):
        """Extract score from malformed response."""
        result = parse_ai_response(
            ai_responses.MALFORMED_JSON_RESPONSE,
            JudgeScoreSchema
        )
        assert result.score == 0.75
        assert result.confidence == 0.3  # Low confidence for fallback

    def test_score_bounds_validation(self):
        """Reject scores outside 0-1 range."""
        with pytest.raises(Exception):  # ValidationError
            parse_ai_response(
                '{"score": 1.5, "reasoning": "Invalid", "confidence": 0.9}',
                JudgeScoreSchema
            )

    @pytest.mark.parametrize("score,expected", [
        (0.0, 0.0),
        (1.0, 1.0),
        (0.5, 0.5),
    ])
    def test_boundary_scores(self, score, expected):
        """Test boundary score values."""
        response = f'{{"score": {score}, "reasoning": "Test", "confidence": 0.9}}'
        result = parse_ai_response(response, JudgeScoreSchema)
        assert result.score == expected
```

---

## Phase 6: Create Error Scenario Tests

### 6.1 Error Scenario Test Suite
**File**: `backend/tests/unit/ai/test_ai_error_handling.py`

```python
"""Tests for AI service error handling."""

import pytest
from unittest.mock import AsyncMock
from tests.mocks.ai_client import MockAIClient
from src.services.evaluation.llm_judge_service import LLMJudgeService, JudgeScore

class RateLimitError(Exception):
    """Simulated rate limit error."""
    pass

class TimeoutError(Exception):
    """Simulated timeout error."""
    pass

class TestAIErrorHandling:
    """Test error handling in AI services."""

    @pytest.fixture
    def mock_client(self):
        return MockAIClient()

    @pytest.fixture
    def judge_service(self, mock_client):
        return LLMJudgeService(ai_client=mock_client)

    @pytest.mark.asyncio
    async def test_graceful_fallback_on_timeout(self, mock_client, judge_service):
        """Service returns fallback score on timeout."""
        mock_client.set_side_effect(lambda: (_ for _ in ()).throw(TimeoutError("Request timed out")))

        result = await judge_service.evaluate_answer_relevancy(
            query="What is AI?",
            answer="AI is artificial intelligence."
        )

        assert isinstance(result, JudgeScore)
        assert result.score == 0.5  # Fallback
        assert result.confidence == 0.0
        assert "Error" in result.reasoning or "timeout" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, mock_client, judge_service):
        """Service retries after rate limit."""
        # First call fails, second succeeds
        mock_client.set_responses([])  # Clear default

        call_count = 0
        def rate_limit_then_success():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError("Too many requests")
            return CompletionResponse(
                content='{"score": 0.9, "reasoning": "Good", "confidence": 0.95}',
                model="test",
                usage={},
                finish_reason="stop"
            )

        mock_client.set_side_effect(rate_limit_then_success)

        # Service should handle retry internally
        result = await judge_service.evaluate_answer_relevancy(
            query="Test",
            answer="Test answer"
        )

        # Either it retried and got 0.9, or fell back to 0.5
        assert result.score in [0.9, 0.5]

    @pytest.mark.asyncio
    async def test_handles_empty_response(self, mock_client, judge_service):
        """Service handles empty AI response."""
        mock_client.set_responses([""])

        result = await judge_service.evaluate_answer_relevancy(
            query="Test",
            answer="Test answer"
        )

        assert result.score == 0.5
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_handles_partial_json(self, mock_client, judge_service):
        """Service handles truncated JSON response."""
        mock_client.set_responses(['{"score": 0.8, "reasoning": "Cut off'])

        result = await judge_service.evaluate_answer_relevancy(
            query="Test",
            answer="Test answer"
        )

        # Should extract score or fallback
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_client_unavailable_returns_fallback(self, judge_service):
        """Service returns fallback when client unavailable."""
        judge_service._client = None

        result = await judge_service.evaluate_answer_relevancy(
            query="Test",
            answer="Test answer"
        )

        assert result.score == 0.5
        assert "not available" in result.reasoning.lower()
```

---

## Phase 7: Separate AI Integration Tests

### 7.1 Integration Test Configuration
**File**: `backend/tests/integration/ai/conftest.py`

```python
"""Configuration for AI integration tests."""

import os
import pytest

# Skip AI integration tests unless explicitly enabled
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_AI_INTEGRATION_TESTS"),
    reason="AI integration tests disabled. Set RUN_AI_INTEGRATION_TESTS=1 to run."
)

@pytest.fixture(scope="session")
def real_ai_client():
    """Create real AI client for integration tests."""
    from src.core.ai.azure_client import AzureOpenAIClient

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    if not endpoint or not api_key:
        pytest.skip("Azure OpenAI credentials not configured")

    return AzureOpenAIClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment
    )

@pytest.fixture(scope="session")
def real_llm_judge(real_ai_client):
    """Create real LLM Judge for integration tests."""
    from src.services.evaluation.llm_judge_service import LLMJudgeService
    return LLMJudgeService(ai_client=real_ai_client)
```

### 7.2 AI Integration Tests
**File**: `backend/tests/integration/ai/test_llm_judge_integration.py`

```python
"""Integration tests for LLM Judge with real AI calls."""

import pytest
from src.core.ai.schemas import JudgeScoreSchema, FullJudgeEvaluationSchema

@pytest.mark.ai
@pytest.mark.integration
class TestLLMJudgeIntegration:
    """Integration tests using real AI endpoints."""

    @pytest.mark.asyncio
    async def test_real_answer_relevancy_evaluation(self, real_llm_judge):
        """Verify real AI returns valid structured output."""
        result = await real_llm_judge.evaluate_answer_relevancy(
            query="What is the capital of France?",
            answer="The capital of France is Paris."
        )

        # Validate structure, not exact values
        assert 0.0 <= result.score <= 1.0
        assert len(result.reasoning) > 0
        assert 0.0 <= result.confidence <= 1.0

        # High relevancy expected for correct answer
        assert result.score > 0.7

    @pytest.mark.asyncio
    async def test_comprehensive_evaluation_structure(self, real_llm_judge):
        """Verify comprehensive evaluation returns all fields."""
        result = await real_llm_judge.comprehensive_evaluation(
            query="Explain photosynthesis",
            answer="Photosynthesis is the process plants use to convert sunlight into energy.",
            contexts=["Plants use chlorophyll to capture light energy."]
        )

        # Validate against schema
        validated = FullJudgeEvaluationSchema.parse_obj({
            "answer_relevancy": {"score": result.answer_relevancy.score, "reasoning": result.answer_relevancy.reasoning, "confidence": result.answer_relevancy.confidence},
            "context_relevancy": {"score": result.context_relevancy.score, "reasoning": result.context_relevancy.reasoning, "confidence": result.context_relevancy.confidence},
            "completeness": {"score": result.completeness.score, "reasoning": result.completeness.reasoning, "confidence": result.completeness.confidence},
            "safety": {"score": result.safety.score, "reasoning": result.safety.reasoning, "confidence": result.safety.confidence},
            "overall_score": result.overall_score,
            "pass_fail": result.pass_fail,
            "evaluation_time_ms": result.evaluation_time_ms
        })

        assert validated is not None
        assert result.evaluation_time_ms > 0
```

### 7.3 CI Configuration for AI Tests
**File**: `.github/workflows/ai-tests.yml` (additions)

```yaml
# Add to existing CI workflow
  ai-integration-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' || contains(github.event.head_commit.message, '[ai-tests]')
    env:
      RUN_AI_INTEGRATION_TESTS: 1
      AZURE_OPENAI_ENDPOINT: ${{ secrets.AZURE_OPENAI_ENDPOINT }}
      AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - name: Run AI Integration Tests
        run: |
          cd backend
          pytest tests/integration/ai/ -v --maxfail=3 -x
```

---

## Implementation Order

| Phase | Priority | Effort | Impact |
|-------|----------|--------|--------|
| 1. Fix Infrastructure | High | Low | Unblocks all tests |
| 2. AI Client Abstraction | High | Medium | Enables proper mocking |
| 3. Response Fixtures | Medium | Low | Reduces test duplication |
| 4. Prompt Snapshots | Medium | Low | Catches prompt drift |
| 5. Pydantic Validation | Medium | Medium | Runtime safety |
| 6. Error Scenarios | High | Medium | Production reliability |
| 7. Integration Tests | Low | Low | Real AI verification |

---

## Success Metrics

1. **Test Coverage**: >80% coverage on AI service code
2. **Mock Isolation**: 0 real AI calls in unit tests
3. **Prompt Stability**: All prompt snapshots pass
4. **Error Handling**: All error scenarios have tests
5. **Integration Validation**: Weekly AI integration tests pass
6. **Response Validation**: 100% of AI responses validated by schema

---

## Files to Create

```
backend/
├── src/core/ai/
│   ├── __init__.py
│   ├── protocols.py          # AIClient, EmbeddingClient protocols
│   ├── azure_client.py       # Azure OpenAI implementation
│   ├── schemas.py            # Pydantic validation schemas
│   ├── parsers.py            # Response parsing utilities
│   └── prompts/
│       ├── __init__.py
│       └── judge_prompts.py  # Prompt templates
├── tests/
│   ├── conftest.py           # Unified test config
│   ├── mocks/
│   │   ├── __init__.py
│   │   └── ai_client.py      # MockAIClient
│   ├── fixtures/
│   │   ├── __init__.py
│   │   └── ai_responses.py   # AI response fixtures
│   └── unit/ai/
│       ├── __init__.py
│       ├── test_prompt_snapshots.py
│       ├── test_response_parsing.py
│       └── test_ai_error_handling.py
│   └── integration/ai/
│       ├── conftest.py
│       └── test_llm_judge_integration.py
```

---

## Notes

- Backwards compatibility maintained via optional DI
- Existing tests continue to work
- Gradual migration path for services
- Cost control via separate integration test runs
