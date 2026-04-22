"""Tests for structured error recovery module."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock


@pytest.mark.unit
class TestClassifyError:
    def test_timeout_is_transient(self):
        from src.services.agent.error_recovery import classify_error
        err = classify_error("search_arxiv", asyncio.TimeoutError())
        assert err.category == "transient"

    def test_connection_error_is_transient(self):
        from src.services.agent.error_recovery import classify_error
        err = classify_error("search_arxiv", ConnectionError("reset"))
        assert err.category == "transient"

    def test_not_found_payload_is_recoverable(self):
        from src.services.agent.error_recovery import classify_error_from_payload
        err = classify_error_from_payload(
            "add_document_to_project",
            {"error": "Document abc123 not found"}
        )
        assert err.category == "recoverable"
        assert "ingest" in err.suggestion.lower()

    def test_permission_denied_is_user_fixable(self):
        from src.services.agent.error_recovery import classify_error
        err = classify_error("search_documents", PermissionError("org mismatch"))
        assert err.category == "user_fixable"

    def test_generic_exception_is_fatal(self):
        from src.services.agent.error_recovery import classify_error
        err = classify_error("search_arxiv", RuntimeError("unexpected"))
        assert err.category == "fatal"

    def test_hint_for_known_tool_error(self):
        from src.services.agent.error_recovery import classify_error_from_payload
        err = classify_error_from_payload(
            "ingest_arxiv_papers",
            {"error": "timed out after 120s"}
        )
        assert err.category == "transient"

    def test_no_results_is_recoverable(self):
        from src.services.agent.error_recovery import classify_error_from_payload
        err = classify_error_from_payload(
            "search_arxiv",
            {"error": "No results found"}
        )
        assert err.category == "recoverable"
        assert "broader" in err.suggestion.lower()


@pytest.mark.unit
class TestToolErrorFormat:
    def test_to_tool_message_content(self):
        from src.services.agent.error_recovery import ToolError
        err = ToolError(
            category="recoverable",
            message="Document not found",
            suggestion="Ingest it first",
        )
        content = err.to_tool_message_content()
        parsed = json.loads(content)
        assert parsed["error"] == "Document not found"
        assert parsed["error_type"] == "recoverable"
        assert parsed["suggestion"] == "Ingest it first"


@pytest.mark.unit
class TestRetryTransient:
    @pytest.mark.asyncio
    async def test_retries_on_transient_then_succeeds(self):
        from src.services.agent.error_recovery import retry_transient

        call_count = 0
        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncio.TimeoutError()
            return {"result": "ok"}

        result = await retry_transient(flaky_fn, max_attempts=3, base_delay=0.01)
        assert result == {"result": "ok"}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        from src.services.agent.error_recovery import retry_transient

        async def always_fails():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await retry_transient(always_fails, max_attempts=3, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates_immediately(self):
        """CancelledError must never be retried — it means the caller aborted."""
        from src.services.agent.error_recovery import retry_transient

        call_count = 0

        async def fn():
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await retry_transient(fn, max_attempts=3, base_delay=0.01)

        assert call_count == 1
