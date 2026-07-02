"""Retry policy of summarize_thread_task must stay narrow.

The old ``autoretry_for = (Exception,)`` retried permanent failures (invalid
UUID, integrity errors, code bugs) three times with backoff — pure latency and
log noise for outcomes that cannot change. LLM-call errors never reach the
task at all (ThreadSummarizationService catches them and degrades to a
fallback summary), so retrying is only worth it for transient
connection/timeout classes. This test pins that contract.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import InterfaceError, OperationalError

pytestmark = pytest.mark.unit

from src.tasks.summarize_thread_task import (
    TRANSIENT_ERRORS,
    SummarizationTask,
    summarize_thread_task,
)


def test_autoretry_is_exactly_the_transient_set():
    assert summarize_thread_task.autoretry_for == TRANSIENT_ERRORS
    assert SummarizationTask.autoretry_for == TRANSIENT_ERRORS


@pytest.mark.parametrize(
    "exc_type", [ConnectionError, TimeoutError, OperationalError, InterfaceError]
)
def test_transient_classes_are_retried(exc_type):
    assert issubclass(exc_type, TRANSIENT_ERRORS)


@pytest.mark.parametrize("exc_type", [ValueError, KeyError, RuntimeError, Exception])
def test_permanent_classes_are_not_retried(exc_type):
    # A bare Exception (or any permanent error) must NOT match the retry
    # filter — reintroducing (Exception,) makes this fail.
    assert not issubclass(exc_type, TRANSIENT_ERRORS)


def test_retry_bounds_unchanged():
    assert SummarizationTask.retry_kwargs == {"max_retries": 3, "countdown": 5}
    assert SummarizationTask.retry_backoff is True
