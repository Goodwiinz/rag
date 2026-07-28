"""Regression: a transient error *returned* in a tool payload isn't cached.

retry_transient only retries raised exceptions, not a tool that returns
{"error": <transient>}. Such a result was marked status="completed", so the
dedupe cache (which caches only completed executions) served the stale error on
the LLM's retry, silently defeating it. A returned error payload must be
status="failed" (transient ⇒ error_increment 0, so it doesn't trip the error
ceiling but is no longer a dedupe cache candidate).
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agent._nodes_tools import _execute_single_tool


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transient_payload_error_marked_failed_not_completed():
    executor = AsyncMock(return_value={"error": "request timeout, please retry"})

    with patch("src.services.agent._nodes_tools._get_execute_tool", return_value=executor):
        result = await _execute_single_tool(
            {"name": "document_search", "args": {"q": "x"}, "id": "t1"},
            {"configurable": {"user_id": "u1"}},
            {},
        )

    # Not "completed" → excluded from the dedupe cache → retriable on re-plan.
    assert result["execution"]["status"] == "failed"
    # Transient ⇒ does not count toward the error ceiling.
    assert result["error_increment"] == 0
