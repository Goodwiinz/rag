"""B4: cheap Redis pre-check in ``enqueue_summarization``.

The worker's ``should_summarize`` rate-limits ~every turn away via a 5-min
Redis key. ``enqueue_summarization`` does a sync ``EXISTS`` on that same key
so most turns skip the ``.delay()`` broker round-trip, while staying
degrade-safe (a Redis error must still enqueue).
"""

from unittest.mock import Mock

import src.services.threads.thread_summarization_service as svc
from src.tasks.summarize_thread_task import summarize_thread_task


def _wire(monkeypatch, *, exists_return=False, exists_raises=False):
    delay = Mock()
    monkeypatch.setattr(summarize_thread_task, "delay", delay)

    fake_redis = Mock()
    if exists_raises:
        fake_redis.exists.side_effect = RuntimeError("redis down")
    else:
        fake_redis.exists.return_value = exists_return
    monkeypatch.setattr(svc, "_sync_redis_client", lambda: fake_redis)
    return delay, fake_redis


def test_key_present_skips_enqueue(monkeypatch):
    delay, fake_redis = _wire(monkeypatch, exists_return=True)

    svc.enqueue_summarization("thread-123")

    fake_redis.exists.assert_called_once_with(
        "thread_summary:thread-123:last_generated"
    )
    delay.assert_not_called()


def test_key_absent_enqueues_once_with_str(monkeypatch):
    delay, _ = _wire(monkeypatch, exists_return=False)

    svc.enqueue_summarization("thread-123")

    delay.assert_called_once_with("thread-123")


def test_redis_error_is_degrade_safe(monkeypatch):
    delay, _ = _wire(monkeypatch, exists_raises=True)

    svc.enqueue_summarization("thread-123")

    # Redis down must not swallow the enqueue.
    delay.assert_called_once_with("thread-123")


def test_rate_limit_key_format_pins_worker_contract():
    # Must match the worker's should_summarize / _set_rate_limit key byte-for-byte.
    assert svc.rate_limit_key("abc") == "thread_summary:abc:last_generated"
