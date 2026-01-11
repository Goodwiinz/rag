"""
Tests for AI Response Parsing

Tests the robust parsing utilities for AI responses.
"""

import pytest
from src.core.ai.parsers import (
    parse_ai_response,
    extract_json_from_response,
    extract_score_from_text,
    AIResponseParseError
)
from src.core.ai.schemas import JudgeScoreSchema


class TestExtractJsonFromResponse:
    """Test JSON extraction from various response formats."""
    
    def test_extract_clean_json(self):
        """Extract already clean JSON."""
        response = '{"score": 0.8, "reasoning": "Good", "confidence": 0.9}'
        result = extract_json_from_response(response)
        assert result == response
    
    def test_extract_json_from_markdown_code_block(self):
        """Extract JSON from ```json block."""
        response = '''Here's my evaluation:

```json
{"score": 0.85, "reasoning": "Well done", "confidence": 0.92}
```

That concludes my review.'''
        result = extract_json_from_response(response)
        assert '"score": 0.85' in result
    
    def test_extract_json_from_plain_code_block(self):
        """Extract JSON from plain ``` block."""
        response = '''Analysis:

```
{"score": 0.75, "reasoning": "Average", "confidence": 0.8}
```'''
        result = extract_json_from_response(response)
        assert '"score": 0.75' in result
    
    def test_extract_json_embedded_in_text(self):
        """Extract JSON embedded in explanatory text."""
        response = 'The evaluation is {"score": 0.9, "reasoning": "Excellent", "confidence": 0.95} based on my analysis.'
        result = extract_json_from_response(response)
        assert '"score": 0.9' in result
    
    def test_empty_response_returns_empty_dict(self):
        """Empty response returns empty JSON object."""
        result = extract_json_from_response("")
        assert result == "{}"
    
    def test_whitespace_only_response(self):
        """Whitespace-only response returns empty JSON object."""
        result = extract_json_from_response("   \n\t  ")
        assert result == "{}"


class TestExtractScoreFromText:
    """Test score extraction from unstructured text."""
    
    def test_extract_explicit_score(self):
        """Extract explicitly mentioned score."""
        text = "The score is 0.85 for this response."
        assert extract_score_from_text(text) == 0.85
    
    def test_extract_score_with_colon(self):
        """Extract score after colon."""
        text = "Relevancy score: 0.7"
        assert extract_score_from_text(text) == 0.7
    
    def test_extract_percentage(self):
        """Extract percentage and convert to decimal."""
        text = "The answer is 85% relevant."
        assert extract_score_from_text(text) == 0.85
    
    def test_extract_decimal_from_text(self):
        """Extract decimal number from text."""
        text = "I would rate this 0.75 overall."
        assert extract_score_from_text(text) == 0.75
    
    def test_no_score_returns_none(self):
        """Return None when no score found."""
        text = "This is a great response with no numbers."
        assert extract_score_from_text(text) is None
    
    def test_prefer_score_keyword(self):
        """Prefer explicit 'score' mention over random numbers."""
        text = "There are 5 reasons. Score: 0.8"
        assert extract_score_from_text(text) == 0.8


class TestParseAiResponse:
    """Test full AI response parsing pipeline."""
    
    def test_parse_valid_json(self):
        """Parse clean JSON response."""
        response = '{"score": 0.85, "reasoning": "Good answer", "confidence": 0.92}'
        result = parse_ai_response(response, JudgeScoreSchema)
        
        assert result.score == 0.85
        assert result.reasoning == "Good answer"
        assert result.confidence == 0.92
    
    def test_parse_markdown_wrapped_json(self):
        """Parse JSON wrapped in markdown."""
        response = '''```json
{"score": 0.78, "reasoning": "Decent", "confidence": 0.8}
```'''
        result = parse_ai_response(response, JudgeScoreSchema)
        
        assert result.score == 0.78
    
    def test_fallback_on_malformed_json(self):
        """Fall back to text extraction for malformed JSON."""
        response = "The score is approximately 0.75 and the answer is good."
        result = parse_ai_response(response, JudgeScoreSchema)
        
        assert result.score == 0.75
        assert result.confidence == 0.3  # Low confidence for fallback
    
    def test_fallback_score_used_when_no_score_found(self):
        """Use fallback score when no score can be extracted."""
        response = "This is a good answer with no scores."
        result = parse_ai_response(response, JudgeScoreSchema, fallback_score=0.6)
        
        assert result.score == 0.6
        assert result.confidence < 0.5
    
    def test_strict_mode_raises_on_invalid_json(self):
        """Strict mode raises exception on parse errors."""
        response = "Not valid JSON at all"
        
        with pytest.raises(AIResponseParseError):
            parse_ai_response(response, JudgeScoreSchema, strict=True)
    
    def test_score_bounds_validation(self):
        """Validate that scores are within 0-1 bounds."""
        response = '{"score": 1.5, "reasoning": "Invalid score", "confidence": 0.9}'
        
        # Should fall back or raise depending on implementation
        result = parse_ai_response(response, JudgeScoreSchema)
        assert 0.0 <= result.score <= 1.0
    
    @pytest.mark.parametrize("score,expected", [
        (0.0, 0.0),
        (1.0, 1.0),
        (0.5, 0.5),
        (0.123456, 0.1235),  # Rounded to 4 decimals
    ])
    def test_boundary_scores(self, score, expected):
        """Test boundary and precision handling."""
        response = f'{{"score": {score}, "reasoning": "Test", "confidence": 0.9}}'
        result = parse_ai_response(response, JudgeScoreSchema)
        
        assert abs(result.score - expected) < 0.0001
    
    def test_empty_response_uses_fallback(self):
        """Empty response uses fallback values."""
        result = parse_ai_response("", JudgeScoreSchema)
        
        assert result.score == 0.5  # Default fallback
        assert "Empty" in result.reasoning or "Fallback" in result.reasoning
    
    def test_incomplete_json_extracts_available_data(self):
        """Incomplete JSON still extracts available data."""
        response = '{"score": 0.8, "reasoning": "Cut off'  # Incomplete
        result = parse_ai_response(response, JudgeScoreSchema)
        
        # Should either extract score or use fallback
        assert 0.0 <= result.score <= 1.0


class TestJudgeScoreSchemaValidation:
    """Test Pydantic schema validation directly."""
    
    def test_valid_score_schema(self):
        """Valid data passes validation."""
        data = {"score": 0.85, "reasoning": "Good", "confidence": 0.9}
        score = JudgeScoreSchema.model_validate(data)
        
        assert score.score == 0.85
        assert score.reasoning == "Good"
        assert score.confidence == 0.9
    
    def test_score_out_of_range_fails(self):
        """Score outside 0-1 range fails validation."""
        with pytest.raises(Exception):  # ValidationError
            JudgeScoreSchema.model_validate({
                "score": 1.5,
                "reasoning": "Invalid",
                "confidence": 0.9
            })
    
    def test_negative_score_fails(self):
        """Negative score fails validation."""
        with pytest.raises(Exception):
            JudgeScoreSchema.model_validate({
                "score": -0.1,
                "reasoning": "Invalid",
                "confidence": 0.9
            })
    
    def test_empty_reasoning_fails(self):
        """Empty reasoning fails validation."""
        with pytest.raises(Exception):
            JudgeScoreSchema.model_validate({
                "score": 0.8,
                "reasoning": "",
                "confidence": 0.9
            })
    
    def test_extra_fields_ignored(self):
        """Extra fields in response are ignored."""
        data = {
            "score": 0.8,
            "reasoning": "Good",
            "confidence": 0.9,
            "extra_field": "ignored"
        }
        score = JudgeScoreSchema.model_validate(data)
        
        assert not hasattr(score, "extra_field")
    
    def test_reasoning_stripped(self):
        """Reasoning whitespace is stripped."""
        data = {"score": 0.8, "reasoning": "  Trimmed  ", "confidence": 0.9}
        score = JudgeScoreSchema.model_validate(data)
        
        assert score.reasoning == "Trimmed"
