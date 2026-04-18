"""Integration tests for agent error recovery flows."""

import asyncio

import pytest

from src.services.agent.error_recovery import (
    ToolError,
    classify_error,
    classify_error_from_payload,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Transient Errors
# ---------------------------------------------------------------------------


async def test_transient_errors():
    """TimeoutError, ConnectionError are classified as category='transient'."""
    timeout_err = classify_error("search_arxiv", asyncio.TimeoutError("request timed out"))
    assert timeout_err.category == "transient"

    conn_err = classify_error("search_documents", ConnectionError("connection refused"))
    assert conn_err.category == "transient"

    # OSError is also transient (unless it's a PermissionError subclass)
    os_err = classify_error("search_arxiv", OSError("network unreachable"))
    assert os_err.category == "transient"


# ---------------------------------------------------------------------------
# Recoverable Errors
# ---------------------------------------------------------------------------


async def test_recoverable_errors():
    """'not found' payload returns category='recoverable' with a non-empty suggestion."""
    error = classify_error_from_payload(
        "add_document_to_project",
        {"error": "Document not found in the database"},
    )

    assert error.category == "recoverable"
    assert error.suggestion  # non-empty


# ---------------------------------------------------------------------------
# User-Fixable Errors
# ---------------------------------------------------------------------------


async def test_user_fixable_errors():
    """PermissionError returns category='user_fixable'."""
    error = classify_error("search_documents", PermissionError("access denied"))

    assert error.category == "user_fixable"
    assert error.suggestion  # non-empty


# ---------------------------------------------------------------------------
# State Format
# ---------------------------------------------------------------------------


async def test_error_info_state_format():
    """ToolError.to_state_info() returns dict with category, message, suggestion keys."""
    tool_error = ToolError(
        category="recoverable",
        message="Document not found",
        suggestion="Try a different document ID.",
    )

    info = tool_error.to_state_info()

    assert isinstance(info, dict)
    assert "category" in info
    assert "message" in info
    assert "suggestion" in info

    assert info["category"] == "recoverable"
    assert info["message"] == "Document not found"
    assert info["suggestion"] == "Try a different document ID."

    # Also verify to_tool_message_content produces valid JSON
    import json

    content = tool_error.to_tool_message_content()
    parsed = json.loads(content)
    assert parsed["error"] == "Document not found"
    assert parsed["error_type"] == "recoverable"
    assert parsed["suggestion"] == "Try a different document ID."
