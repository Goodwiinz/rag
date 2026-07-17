"""W-B3: every path that produces a summary must set the rate-limit key.

The fallback (no vendor API keys — the Azure-only dev config) and timeout
paths previously skipped _set_rate_limit, so every eligible turn re-enqueued,
regenerated, and re-committed the summary."""

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.services.threads.thread_summarization_service import ThreadSummarizationService


def _service_with_thread() -> tuple:
    db = MagicMock()
    thread = MagicMock(id=uuid4(), summary=None, message_count=5)
    message = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = thread
    (
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value
    ) = [message]
    service = ThreadSummarizationService(db=db)
    return service, thread


@pytest.mark.asyncio
async def test_fallback_path_sets_rate_limit() -> None:
    service, thread = _service_with_thread()
    with (
        patch("src.services.threads.thread_summarization_service.settings") as settings,
        patch.object(service, "_format_messages_for_prompt", return_value="x"),
        patch.object(
            service, "_generate_fallback_summary", return_value="fallback summary"
        ),
        patch.object(service, "_update_thread_summary") as update,
        patch.object(service, "_set_rate_limit") as set_rl,
    ):
        settings.OPENAI_API_KEY = None
        settings.ANTHROPIC_API_KEY = None
        summary = await service.generate_summary(thread.id, force=True)

    assert summary == "fallback summary"
    update.assert_called_once()
    set_rl.assert_called_once_with(thread.id)


@pytest.mark.asyncio
async def test_timeout_path_sets_rate_limit() -> None:
    service, thread = _service_with_thread()
    with (
        patch("src.services.threads.thread_summarization_service.settings") as settings,
        patch.object(service, "_format_messages_for_prompt", return_value="x"),
        patch.object(
            service, "_generate_with_openai", side_effect=asyncio.TimeoutError
        ),
        patch.object(
            service, "_generate_fallback_summary", return_value="fallback summary"
        ),
        patch.object(service, "_set_rate_limit") as set_rl,
    ):
        settings.OPENAI_API_KEY = "sk-test"
        settings.ANTHROPIC_API_KEY = None
        summary = await service.generate_summary(thread.id, force=True)

    assert summary == "fallback summary"
    set_rl.assert_called_once_with(thread.id)
