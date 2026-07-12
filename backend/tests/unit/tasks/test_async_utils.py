"""Unit tests for the shared Celery async boundary helper (`run_async`).

The helper runs coroutines on a single long-lived event loop hosted on a daemon
thread, replacing the per-call ``asyncio.run`` sites in the document-processing
tasks (audit B7 follow-up).
"""

import asyncio

import pytest

from src.tasks._async_utils import run_async


@pytest.mark.unit
def test_run_async_returns_coroutine_result():
    async def coro():
        await asyncio.sleep(0)
        return 21 * 2

    assert run_async(coro()) == 42


@pytest.mark.unit
def test_run_async_propagates_exception():
    async def boom():
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        run_async(boom())


@pytest.mark.unit
def test_run_async_reuses_single_loop_across_calls():
    async def which_loop():
        return id(asyncio.get_running_loop())

    first = run_async(which_loop())
    second = run_async(which_loop())

    # The whole point of the helper: one persistent loop reused for every call,
    # not a fresh loop torn down per call (which churns loop-bound resources).
    assert first == second


@pytest.mark.unit
def test_run_async_loop_is_not_the_callers_thread_loop():
    async def coro():
        return "ok"

    # Caller has no running loop; the coroutine still completes because it runs
    # on the helper's background loop.
    assert run_async(coro()) == "ok"
