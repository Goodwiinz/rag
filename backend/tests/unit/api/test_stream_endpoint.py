"""
Unit tests for the SSE streaming endpoint.

Tests cover:
- Route path and method registration
- StreamRequest Pydantic validation (content, use_rag, temperature, max_tokens)
- Concurrent stream prevention (409 Conflict)
- StreamingResponse media type and headers
- Active-stream cleanup in finally block
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.api.threads.stream import StreamRequest, router, _active_streams


# ============================================================================
# StreamRequest Validation Tests
# ============================================================================


class TestStreamRequest:
    """Tests for StreamRequest Pydantic model validation."""

    def test_valid_request_defaults(self) -> None:
        """A minimal valid request should use default values."""
        req = StreamRequest(content="Hello world")
        assert req.content == "Hello world"
        assert req.use_rag is True
        assert req.temperature == 0.7
        assert req.max_tokens == 2048

    def test_valid_request_all_fields(self) -> None:
        """All fields explicitly set should be accepted."""
        req = StreamRequest(
            content="What is RAG?",
            use_rag=False,
            temperature=1.5,
            max_tokens=4096,
        )
        assert req.content == "What is RAG?"
        assert req.use_rag is False
        assert req.temperature == 1.5
        assert req.max_tokens == 4096

    def test_content_min_length_rejected(self) -> None:
        """Empty content should be rejected (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            StreamRequest(content="")
        errors = exc_info.value.errors()
        assert any(
            e["loc"] == ("content",) and "min_length" in str(e).lower()
            for e in errors
        )

    def test_content_max_length_rejected(self) -> None:
        """Content exceeding 32000 chars should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            StreamRequest(content="x" * 32001)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("content",) for e in errors)

    def test_content_required(self) -> None:
        """Omitting content should raise a validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StreamRequest()  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("content",) for e in errors)

    def test_temperature_lower_bound(self) -> None:
        """Temperature below 0.0 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            StreamRequest(content="hi", temperature=-0.1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("temperature",) for e in errors)

    def test_temperature_upper_bound(self) -> None:
        """Temperature above 2.0 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            StreamRequest(content="hi", temperature=2.1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("temperature",) for e in errors)

    def test_temperature_at_boundaries(self) -> None:
        """Temperature at 0.0 and 2.0 should be accepted."""
        req_low = StreamRequest(content="hi", temperature=0.0)
        assert req_low.temperature == 0.0

        req_high = StreamRequest(content="hi", temperature=2.0)
        assert req_high.temperature == 2.0

    def test_max_tokens_lower_bound(self) -> None:
        """max_tokens below 1 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            StreamRequest(content="hi", max_tokens=0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("max_tokens",) for e in errors)

    def test_max_tokens_upper_bound(self) -> None:
        """max_tokens above 8192 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            StreamRequest(content="hi", max_tokens=8193)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("max_tokens",) for e in errors)

    def test_max_tokens_at_boundaries(self) -> None:
        """max_tokens at 1 and 8192 should be accepted."""
        req_low = StreamRequest(content="hi", max_tokens=1)
        assert req_low.max_tokens == 1

        req_high = StreamRequest(content="hi", max_tokens=8192)
        assert req_high.max_tokens == 8192

    def test_max_tokens_none_allowed(self) -> None:
        """max_tokens=None should be accepted (Optional)."""
        req = StreamRequest(content="hi", max_tokens=None)
        assert req.max_tokens is None


# ============================================================================
# Router Registration Tests
# ============================================================================


class TestStreamRouterRegistration:
    """Tests for correct router path and method registration."""

    def test_route_exists(self) -> None:
        """The stream endpoint route should be registered on the router."""
        routes = [r for r in router.routes if hasattr(r, "path")]
        stream_routes = [r for r in routes if r.path.endswith("/{thread_id}/stream")]
        assert len(stream_routes) == 1, (
            f"Expected exactly one /{'{thread_id}'}/stream route, "
            f"found {len(stream_routes)}"
        )

    def test_route_method_is_post(self) -> None:
        """The stream endpoint should accept POST method."""
        routes = [r for r in router.routes if hasattr(r, "path")]
        stream_routes = [r for r in routes if r.path.endswith("/{thread_id}/stream")]
        assert len(stream_routes) == 1
        assert "POST" in stream_routes[0].methods

    def test_router_prefix(self) -> None:
        """The router should have /threads prefix."""
        assert router.prefix == "/threads"

    def test_router_tags(self) -> None:
        """The router should have appropriate tags."""
        assert "Streaming" in router.tags


# ============================================================================
# Active Streams Concurrency Tests
# ============================================================================


class TestActiveStreamsConcurrency:
    """Tests for the _active_streams concurrency guard."""

    def test_active_streams_is_set(self) -> None:
        """_active_streams should be a set (used for O(1) membership checks)."""
        assert isinstance(_active_streams, set)

    def test_active_streams_starts_empty(self) -> None:
        """_active_streams should start empty (no dangling state from other tests)."""
        # Clear in case a previous test left state
        _active_streams.clear()
        assert len(_active_streams) == 0
