"""Unit tests for the server-authored SSE error-category classifier (W2).

``classify_agent_error`` is the only place an exception becomes a wire
``category``; ``error_frame_payload`` is the only place an ``error`` frame's
payload is built. These tests pin both — the classification table (including
the ordering hazards: ``APITimeoutError`` IS an ``APIError``, ``RateLimitError``
IS an ``APIStatusError``) and the flat ``{"error": str, "category": str}``
shape that the wire contract requires.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

from src.services.agent._errors import classify_agent_error, error_frame_payload
from src.shared.enums import AgentErrorCategory

pytestmark = pytest.mark.unit


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://example.invalid/v1/chat/completions")


def _rate_limit_error() -> RateLimitError:
    response = httpx.Response(429, request=_request())
    return RateLimitError("slow down", response=response, body=None)


def _api_status_error() -> Any:
    from openai import APIStatusError

    response = httpx.Response(500, request=_request())
    return APIStatusError("upstream boom", response=response, body=None)


def test_builtin_timeout_is_upstream_timeout() -> None:
    assert classify_agent_error(TimeoutError()) is AgentErrorCategory.UPSTREAM_TIMEOUT


def test_asyncio_timeout_is_upstream_timeout() -> None:
    assert (
        classify_agent_error(asyncio.TimeoutError())
        is AgentErrorCategory.UPSTREAM_TIMEOUT
    )


def test_sdk_timeout_is_upstream_timeout_not_model_error() -> None:
    """``APITimeoutError`` subclasses ``APIError`` — the timeout branch must be
    checked first or every deadline overrun would read as ``model_error``."""
    assert isinstance(APITimeoutError(request=_request()), APIError)
    assert (
        classify_agent_error(APITimeoutError(request=_request()))
        is AgentErrorCategory.UPSTREAM_TIMEOUT
    )


def test_rate_limit_error_is_rate_limited_not_model_error() -> None:
    """``RateLimitError`` is an ``APIStatusError`` — order hazard, same shape."""
    exc = _rate_limit_error()
    assert isinstance(exc, APIError)
    assert classify_agent_error(exc) is AgentErrorCategory.RATE_LIMITED


def test_other_api_status_errors_are_model_error() -> None:
    assert classify_agent_error(_api_status_error()) is AgentErrorCategory.MODEL_ERROR


def test_api_connection_error_is_model_error() -> None:
    assert (
        classify_agent_error(APIConnectionError(request=_request()))
        is AgentErrorCategory.MODEL_ERROR
    )


def test_cancelled_error_maps_to_cancelled_when_passed() -> None:
    """The classifier maps the value; it never swallows cancellation — callers
    still catch ``CancelledError`` ahead of ``Exception`` and re-raise."""
    assert (
        classify_agent_error(asyncio.CancelledError()) is AgentErrorCategory.CANCELLED
    )


def test_unknown_exception_defaults_to_internal() -> None:
    assert (
        classify_agent_error(RuntimeError("who knows")) is AgentErrorCategory.INTERNAL
    )
    assert classify_agent_error(ValueError("nope")) is AgentErrorCategory.INTERNAL


def test_error_frame_payload_from_exception_is_flat_and_safe() -> None:
    payload = error_frame_payload(RuntimeError("secret connection string"))
    assert set(payload) == {"error", "category"}
    assert isinstance(payload["error"], str)
    # client_safe_error must not leak the exception text.
    assert "secret connection string" not in payload["error"]
    assert payload["category"] == AgentErrorCategory.INTERNAL.value


def test_error_frame_payload_derives_category_from_the_exception() -> None:
    payload = error_frame_payload(_rate_limit_error())
    assert payload["category"] == AgentErrorCategory.RATE_LIMITED.value


def test_error_frame_payload_explicit_category_wins() -> None:
    payload = error_frame_payload(
        TimeoutError(), AgentErrorCategory.CHECKPOINT_UNAVAILABLE
    )
    assert payload["category"] == AgentErrorCategory.CHECKPOINT_UNAVAILABLE.value


def test_error_frame_payload_from_literal_message_is_verbatim() -> None:
    payload = error_frame_payload(
        "Thread not found", AgentErrorCategory.INVALID_REQUEST
    )
    assert payload == {"error": "Thread not found", "category": "invalid_request"}


def test_error_frame_payload_literal_without_category_defaults_internal() -> None:
    payload = error_frame_payload("something broke")
    assert payload == {"error": "something broke", "category": "internal"}


def test_category_values_are_plain_strings_on_the_wire() -> None:
    """The frame must JSON-serialize to a string, not an enum repr."""
    import json

    payload = error_frame_payload("x", AgentErrorCategory.CONFLICT)
    assert json.loads(json.dumps(payload))["category"] == "conflict"
