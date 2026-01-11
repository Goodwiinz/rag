"""
AI Response Fixtures

Provides standardized test fixtures for AI response patterns,
including valid responses, edge cases, and error scenarios.

Usage:
    from tests.fixtures.ai_responses import VALID_JUDGE_RESPONSE
    
    mock_client.set_response(VALID_JUDGE_RESPONSE)
"""

from typing import Dict, Any, List


# ============================================================================
# Valid Response Fixtures
# ============================================================================

VALID_JUDGE_RESPONSE = """{
    "score": 0.85,
    "reasoning": "The answer directly addresses the query with relevant and accurate information. The response covers the key aspects of the question.",
    "confidence": 0.92
}"""

VALID_JUDGE_RESPONSE_MINIMAL = '{"score": 0.75, "reasoning": "Good", "confidence": 0.8}'

VALID_JUDGE_RESPONSE_MARKDOWN = """Here's my evaluation of the answer:

```json
{"score": 0.78, "reasoning": "The answer partially addresses the query but could be more comprehensive.", "confidence": 0.8}
```

The response demonstrates basic understanding but lacks depth in some areas."""

VALID_JUDGE_RESPONSE_MARKDOWN_NO_TAG = """I've analyzed the response:

```
{"score": 0.82, "reasoning": "Well-structured answer with good examples", "confidence": 0.88}
```

Overall a solid response."""


# ============================================================================
# Edge Case Fixtures
# ============================================================================

HIGH_SCORE_RESPONSE = '{"score": 1.0, "reasoning": "Perfect answer that fully addresses the query with comprehensive detail.", "confidence": 1.0}'

LOW_SCORE_RESPONSE = '{"score": 0.1, "reasoning": "The answer is largely irrelevant to the query and contains inaccuracies.", "confidence": 0.95}'

ZERO_SCORE_RESPONSE = '{"score": 0.0, "reasoning": "Completely off-topic response.", "confidence": 0.99}'

BOUNDARY_SCORE_RESPONSE = '{"score": 0.5, "reasoning": "Mediocre answer with mixed relevance.", "confidence": 0.5}'


# ============================================================================
# Malformed Response Fixtures
# ============================================================================

MALFORMED_JSON_RESPONSE = "The score is approximately 0.75 and the answer is good overall. The confidence level is around 80%."

INCOMPLETE_JSON_RESPONSE = '{"score": 0.8, "reasoning": "This response was cut off during'

EMPTY_RESPONSE = ""

WHITESPACE_ONLY_RESPONSE = "   \n\t  \n  "

HTML_WRAPPED_RESPONSE = """<response>
{"score": 0.7, "reasoning": "Needs improvement", "confidence": 0.6}
</response>"""

EXTRA_TEXT_BEFORE_JSON = """Based on my analysis, here is the evaluation:

I found that {"score": 0.85, "reasoning": "Good answer", "confidence": 0.9} represents the quality.

This concludes my review."""


# ============================================================================
# Error Scenario Fixtures
# ============================================================================

RATE_LIMIT_ERROR_RESPONSE = {
    "error": {
        "code": "429",
        "message": "Rate limit exceeded. Please retry after 60 seconds.",
        "type": "rate_limit_exceeded"
    }
}

CONTEXT_LENGTH_EXCEEDED_RESPONSE = {
    "error": {
        "code": "context_length_exceeded", 
        "message": "This model's maximum context length is 128000 tokens. You requested 150000 tokens.",
        "type": "invalid_request_error"
    }
}

CONTENT_FILTER_RESPONSE = {
    "error": {
        "code": "content_filter",
        "message": "The response was filtered due to the prompt triggering Azure OpenAI's content management policy.",
        "type": "content_filter"
    }
}

AUTHENTICATION_ERROR_RESPONSE = {
    "error": {
        "code": "401",
        "message": "Invalid API key provided.",
        "type": "authentication_error"
    }
}


# ============================================================================
# Full Evaluation Fixtures
# ============================================================================

def create_full_evaluation_response(
    answer_score: float = 0.8,
    context_score: float = 0.7,
    completeness_score: float = 0.75,
    safety_score: float = 0.95
) -> Dict[str, Any]:
    """
    Create a configurable full evaluation response fixture.
    
    Args:
        answer_score: Answer relevancy score (0-1).
        context_score: Context relevancy score (0-1).
        completeness_score: Completeness score (0-1).
        safety_score: Safety score (0-1).
        
    Returns:
        Dictionary matching FullJudgeEvaluation structure.
    """
    weights = {
        "answer_relevancy": 0.35,
        "context_relevancy": 0.20,
        "completeness": 0.25,
        "safety": 0.20
    }
    
    overall = (
        answer_score * weights["answer_relevancy"] +
        context_score * weights["context_relevancy"] +
        completeness_score * weights["completeness"] +
        safety_score * weights["safety"]
    )
    
    pass_fail = all([
        answer_score >= 0.7,
        context_score >= 0.6,
        completeness_score >= 0.6,
        safety_score >= 0.9
    ])
    
    return {
        "answer_relevancy": {
            "score": answer_score,
            "reasoning": "Answer relevancy evaluation",
            "confidence": 0.9
        },
        "context_relevancy": {
            "score": context_score,
            "reasoning": "Context relevancy evaluation",
            "confidence": 0.85
        },
        "completeness": {
            "score": completeness_score,
            "reasoning": "Completeness evaluation",
            "confidence": 0.88
        },
        "safety": {
            "score": safety_score,
            "reasoning": "Safety evaluation",
            "confidence": 0.99
        },
        "overall_score": round(overall, 4),
        "pass_fail": pass_fail,
        "evaluation_time_ms": 1250.5
    }


def create_judge_score_response(
    score: float = 0.8,
    reasoning: str = "Test evaluation",
    confidence: float = 0.9
) -> str:
    """
    Create a JSON string for a single judge score.
    
    Args:
        score: Evaluation score (0-1).
        reasoning: Explanation text.
        confidence: Confidence level (0-1).
        
    Returns:
        JSON string for the score.
    """
    import json
    return json.dumps({
        "score": score,
        "reasoning": reasoning,
        "confidence": confidence
    })


# ============================================================================
# Response Sequences (for testing retries, etc.)
# ============================================================================

RETRY_SEQUENCE_RESPONSES: List[str] = [
    "",  # First call fails with empty
    MALFORMED_JSON_RESPONSE,  # Second call fails with malformed
    VALID_JUDGE_RESPONSE  # Third call succeeds
]

DEGRADING_CONFIDENCE_RESPONSES: List[str] = [
    '{"score": 0.9, "reasoning": "High confidence", "confidence": 0.95}',
    '{"score": 0.85, "reasoning": "Medium confidence", "confidence": 0.7}',
    '{"score": 0.8, "reasoning": "Lower confidence", "confidence": 0.5}',
]


# ============================================================================
# Query/Answer Pairs for Testing
# ============================================================================

SAMPLE_QA_PAIRS = [
    {
        "query": "What is machine learning?",
        "answer": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
        "contexts": [
            "Machine learning involves algorithms that learn patterns from data.",
            "AI systems can improve their performance over time through machine learning."
        ],
        "expected_relevancy": 0.9
    },
    {
        "query": "What is the capital of France?",
        "answer": "The capital of France is Paris.",
        "contexts": ["Paris is the capital and largest city of France."],
        "expected_relevancy": 0.95
    },
    {
        "query": "How do neural networks work?",
        "answer": "I don't know anything about that topic.",
        "contexts": [
            "Neural networks consist of interconnected nodes organized in layers.",
            "Deep learning uses neural networks with many hidden layers."
        ],
        "expected_relevancy": 0.1  # Poor answer
    }
]
