"""W-B3: every path that produces a summary must set the rate-limit key.

The fallback (no vendor API keys — the Azure-only dev config) and timeout
paths previously skipped _set_rate_limit, so every eligible turn re-enqueued,
regenerated, and re-committed the summary."""

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.services.threads.thread_summarization_service import (
    SUMMARY_INFLIGHT_LEASE_SECONDS,
    SUMMARY_RATE_LIMIT_SECONDS,
    ThreadSummarizationService,
    inflight_key,
    rate_limit_key,
)


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
        patch.object(service, "_acquire_inflight", return_value="caller-token"),
        patch.object(service, "_release_inflight") as release,
        patch.object(service, "_update_thread_summary") as update,
        patch.object(service, "_set_rate_limit") as set_rl,
    ):
        settings.OPENAI_API_KEY = None
        settings.ANTHROPIC_API_KEY = None
        summary = await service.generate_summary(thread.id, force=True)

    assert summary == "fallback summary"
    update.assert_called_once()
    set_rl.assert_called_once_with(thread.id)
    release.assert_called_once_with(thread.id, "caller-token")


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
        patch.object(service, "_acquire_inflight", return_value="caller-token"),
        patch.object(service, "_release_inflight") as release,
        patch.object(service, "_set_rate_limit") as set_rl,
    ):
        settings.OPENAI_API_KEY = "sk-test"
        settings.ANTHROPIC_API_KEY = None
        summary = await service.generate_summary(thread.id, force=True)

    assert summary == "fallback summary"
    set_rl.assert_called_once_with(thread.id)
    release.assert_called_once_with(thread.id, "caller-token")


@pytest.mark.asyncio
async def test_force_is_blocked_by_existing_inflight_lease() -> None:
    service, thread = _service_with_thread()
    redis_client = MagicMock()
    redis_client.set.return_value = None
    service._redis_client = redis_client

    with (
        patch("src.services.threads.thread_summarization_service.settings") as settings,
        patch.object(service, "_generate_fallback_summary") as fallback,
    ):
        settings.OPENAI_API_KEY = None
        settings.ANTHROPIC_API_KEY = None
        summary = await service.generate_summary(thread.id, force=True)

    assert summary is thread.summary
    fallback.assert_not_called()
    redis_client.set.assert_called_once()
    assert redis_client.set.call_args.kwargs == {
        "nx": True,
        "ex": SUMMARY_INFLIGHT_LEASE_SECONDS,
    }


@pytest.mark.asyncio
async def test_generation_exception_releases_only_caller_token() -> None:
    service, thread = _service_with_thread()
    redis_client = MagicMock()
    redis_client.set.return_value = True
    service._redis_client = redis_client

    with (
        patch("src.services.threads.thread_summarization_service.settings") as settings,
        patch.object(
            service, "_generate_with_openai", side_effect=RuntimeError("boom")
        ),
    ):
        settings.OPENAI_API_KEY = "sk-test"
        settings.ANTHROPIC_API_KEY = None
        summary = await service.generate_summary(thread.id, force=True)

    assert summary is None
    token = redis_client.set.call_args.args[1]
    eval_args = redis_client.eval.call_args.args
    assert eval_args[2:] == (inflight_key(thread.id), token)


@pytest.mark.asyncio
async def test_persisted_summary_sets_cooldown_and_clears_lease() -> None:
    service, thread = _service_with_thread()
    redis_client = MagicMock()
    redis_client.set.return_value = True
    service._redis_client = redis_client

    with (
        patch("src.services.threads.thread_summarization_service.settings") as settings,
        patch.object(
            service, "_generate_fallback_summary", return_value="fallback summary"
        ),
        patch.object(service, "_update_thread_summary"),
    ):
        settings.OPENAI_API_KEY = None
        settings.ANTHROPIC_API_KEY = None
        summary = await service.generate_summary(thread.id, force=True)

    assert summary == "fallback summary"
    redis_client.setex.assert_called_once_with(
        rate_limit_key(thread.id),
        SUMMARY_RATE_LIMIT_SECONDS,
        redis_client.setex.call_args.args[2],
    )
    token = redis_client.set.call_args.args[1]
    assert redis_client.eval.call_args.args[2:] == (inflight_key(thread.id), token)
