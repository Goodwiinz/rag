"""Integration tests for agent v2 component interactions."""

import pytest
from unittest.mock import AsyncMock, patch

from src.services.agent.classifier import classify_intent_keywords
from src.services.agent.error_recovery import classify_error, ToolError
from src.services.agent.reflection import make_reflection_gate, ReflectionResult

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Keyword Classifier Tests
# ---------------------------------------------------------------------------


async def test_classifier_keyword_fallback():
    """classify_intent_keywords('search arxiv papers') returns intent='research'."""
    result = classify_intent_keywords("search arxiv papers")

    assert result.intent == "research"
    assert result.source == "keyword"
    assert result.confidence > 0


async def test_classifier_writing_detection():
    """classify_intent_keywords('write a literature review draft') returns intent='writing'."""
    result = classify_intent_keywords("write a literature review draft")

    assert result.intent == "writing"
    assert result.source == "keyword"
    assert result.confidence > 0


async def test_classifier_kg_detection():
    """classify_intent_keywords('extract entities from document') returns intent='knowledge_graph'."""
    result = classify_intent_keywords("extract entities from document")

    assert result.intent == "knowledge_graph"
    assert result.source == "keyword"
    assert result.confidence > 0


# ---------------------------------------------------------------------------
# Error Classification Tests
# ---------------------------------------------------------------------------


async def test_error_classification_transient():
    """classify_error with TimeoutError returns category='transient'."""
    import asyncio

    error = classify_error("search_arxiv", asyncio.TimeoutError("timeout"))

    assert error.category == "transient"
    assert isinstance(error, ToolError)


async def test_error_classification_user_fixable():
    """classify_error with PermissionError returns category='user_fixable'."""
    error = classify_error("search_documents", PermissionError("denied"))

    assert error.category == "user_fixable"
    assert isinstance(error, ToolError)


# ---------------------------------------------------------------------------
# Reflection Gate Tests
# ---------------------------------------------------------------------------


async def test_reflection_routing():
    """make_reflection_gate routes pass->'proceed', fail->'revise'."""
    _node_fn, route_fn = make_reflection_gate()

    # A passing result should route to "proceed"
    state_pass = {
        "_reflection_result": ReflectionResult(
            passed=True, issues=[], severity="none"
        ),
        "reflection_count": 1,
    }
    assert route_fn(state_pass) == "proceed"

    # A failing result with major severity and budget remaining should route to "revise"
    state_fail = {
        "_reflection_result": ReflectionResult(
            passed=False, issues=["Incomplete answer"], severity="major"
        ),
        "reflection_count": 1,
    }
    assert route_fn(state_fail) == "revise"

    # A failing result with minor severity should still proceed
    state_minor = {
        "_reflection_result": ReflectionResult(
            passed=False, issues=["Small issue"], severity="minor"
        ),
        "reflection_count": 1,
    }
    assert route_fn(state_minor) == "proceed"

    # A failing result at max reflection count should proceed
    state_max = {
        "_reflection_result": ReflectionResult(
            passed=False, issues=["Incomplete"], severity="major"
        ),
        "reflection_count": 2,
    }
    assert route_fn(state_max) == "proceed"

    # No reflection result should proceed
    state_none = {"reflection_count": 0}
    assert route_fn(state_none) == "proceed"
