"""
AI Response Parsers

Provides robust parsing utilities for AI responses, including:
- JSON extraction from markdown-wrapped responses
- Fallback parsing for malformed responses
- Schema validation

Usage:
    from src.core.ai.parsers import parse_ai_response
    from src.core.ai.schemas import JudgeScoreSchema
    
    result = parse_ai_response(ai_response_text, JudgeScoreSchema)
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AIResponseParseError(Exception):
    """Error parsing AI response."""

    def __init__(
        self, message: str, raw_response: str, cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.raw_response = raw_response
        self.cause = cause

    def __str__(self) -> str:
        return f"{self.args[0]} | Raw response: {self.raw_response[:200]}..."


def extract_json_from_response(response: str) -> str:
    """
    Extract JSON from potentially markdown-wrapped response.

    Handles common AI response patterns:
    - ```json ... ```
    - ``` ... ```
    - Raw JSON objects
    - JSON embedded in explanatory text

    Args:
        response: Raw AI response text.

    Returns:
        Extracted JSON string.
    """
    if not response:
        return "{}"

    response = response.strip()

    # Handle whitespace-only input
    if not response:
        return "{}"

    # Pattern 1: JSON in markdown code block with json tag
    if "```json" in response:
        match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            return match.group(1).strip()

    # Pattern 2: JSON in plain markdown code block
    if "```" in response:
        match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            # Verify it looks like JSON
            if candidate.startswith("{") or candidate.startswith("["):
                return candidate

    # Pattern 3: Find JSON object in text
    # Look for balanced braces
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response)
    if brace_match:
        return brace_match.group(0)

    # Pattern 4: If response starts with { or [, assume it's JSON
    if response.startswith("{") or response.startswith("["):
        return response

    # Return original if no JSON found
    return response


def extract_score_from_text(text: str) -> Optional[float]:
    """
    Extract a numeric score from unstructured text.

    Looks for patterns like:
    - "score: 0.8"
    - "0.85"
    - "85%"

    Args:
        text: Unstructured text that might contain a score.

    Returns:
        Extracted score as float, or None if not found.
    """
    # Pattern 1: Explicit score mention
    score_match = re.search(r"score[:\s]+(\d+\.?\d*)", text, re.IGNORECASE)
    if score_match:
        value = float(score_match.group(1))
        return value if value <= 1.0 else value / 100.0

    # Pattern 2: Percentage
    percent_match = re.search(r"(\d+)%", text)
    if percent_match:
        return float(percent_match.group(1)) / 100.0

    # Pattern 3: Decimal numbers between 0 and 1 with word boundaries
    # Use word boundaries to avoid matching version numbers like "3.14" or partial numbers
    decimal_matches = re.findall(r"\b(0\.\d+|1\.0(?!\d)|0(?!\.\d)|1(?!\.\d))\b", text)
    if decimal_matches:
        for match in decimal_matches:
            try:
                value = float(match)
                if 0.0 <= value <= 1.0:
                    return value
            except ValueError:
                continue

    return None


def parse_ai_response(
    response: str, schema: Type[T], fallback_score: float = 0.5, strict: bool = False
) -> T:
    """
    Parse and validate AI response against a Pydantic schema.

    Attempts multiple parsing strategies:
    1. Extract and parse JSON
    2. Handle markdown-wrapped JSON
    3. Fall back to text extraction for malformed responses

    Args:
        response: Raw AI response text.
        schema: Pydantic model class to validate against.
        fallback_score: Default score when parsing fails.
        strict: If True, raise exceptions on parse errors.

    Returns:
        Validated schema instance.

    Raises:
        AIResponseParseError: If strict=True and parsing fails.
    """
    if not response:
        if strict:
            raise AIResponseParseError("Empty response", "")
        return _create_fallback_response(schema, fallback_score, "Empty response")

    try:
        # Try to extract and parse JSON
        json_str = extract_json_from_response(response)
        data = json.loads(json_str)
        return schema.model_validate(data)

    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode failed: {e}, attempting fallback extraction")

        if strict:
            raise AIResponseParseError(f"JSON decode error: {e}", response, e)

        # Try to extract score from text
        score = extract_score_from_text(response)
        if score is not None:
            return _create_fallback_response(
                schema, score, response[:500], confidence=0.3
            )

        return _create_fallback_response(
            schema, fallback_score, response[:500], confidence=0.2
        )

    except ValidationError as e:
        logger.error(f"Schema validation failed: {e}")

        if strict:
            raise AIResponseParseError(f"Validation error: {e}", response, e)

        # Try partial extraction
        try:
            json_str = extract_json_from_response(response)
            data = json.loads(json_str)
            # Fill in missing required fields with defaults
            return _fill_missing_fields(schema, data, fallback_score)
        except Exception:
            return _create_fallback_response(
                schema, fallback_score, f"Validation failed: {e}"
            )


def _get_field_default(field_name: str, fallback_score: float = 0.5) -> Any:
    """Get default value for a schema field.

    Centralized source of truth for default values used in fallback responses.

    Args:
        field_name: The name of the schema field.
        fallback_score: The score to use for 'score' field.

    Returns:
        Default value for the field, or None if no default defined.
    """
    defaults = {
        "score": fallback_score,
        "confidence": 0.3,
        "reasoning": "Fallback value",
        "criteria": "unknown",
    }
    return defaults.get(field_name)


def _create_fallback_response(
    schema: Type[T], score: float, reasoning: str, confidence: float = 0.1
) -> T:
    """Create a fallback response when parsing fails.

    Always validates data to ensure schema constraints are met.
    Never bypasses Pydantic validation.
    """
    fields = schema.model_fields

    # Clamp values to valid ranges to ensure validation passes
    clamped_score = max(0.0, min(1.0, score))
    clamped_confidence = max(0.0, min(1.0, confidence))
    clean_reasoning = (
        reasoning[:2000].strip()
        if reasoning
        else "Fallback response - original parsing failed"
    )

    # Ensure reasoning is not empty (min_length=1 constraint)
    if not clean_reasoning:
        clean_reasoning = "Fallback response"

    data: Dict[str, Any] = {}

    # Use centralized defaults, with overrides for provided values
    if "score" in fields:
        data["score"] = clamped_score
    if "reasoning" in fields:
        data["reasoning"] = clean_reasoning
    if "confidence" in fields:
        data["confidence"] = clamped_confidence
    if "criteria" in fields:
        data["criteria"] = _get_field_default("criteria")

    logger.warning(
        f"Using fallback response for schema {schema.__name__}: "
        f"score={clamped_score}, confidence={clamped_confidence}"
    )

    try:
        return schema.model_validate(data)
    except ValidationError as e:
        logger.error(
            f"Fallback validation failed for {schema.__name__}: {e}. "
            f"Data: {data}. This should not happen - check schema requirements."
        )
        raise AIResponseParseError(
            f"Cannot create valid fallback for {schema.__name__}: {e}", str(data), e
        )


def _fill_missing_fields(
    schema: Type[T], data: Dict[str, Any], fallback_score: float
) -> T:
    """Fill in missing required fields with defaults."""
    fields = schema.model_fields

    for field_name in fields:
        if field_name not in data:
            default = _get_field_default(field_name, fallback_score)
            if default is not None:
                data[field_name] = default

    return schema.model_validate(data)


def safe_json_loads(text: str, default: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Safely parse JSON with a default fallback.

    Args:
        text: JSON string to parse.
        default: Default value if parsing fails.

    Returns:
        Parsed dictionary or default.
    """
    try:
        return json.loads(extract_json_from_response(text))
    except (json.JSONDecodeError, TypeError):
        return default or {}
