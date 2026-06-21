"""Regression tests for compare_and_set_status — the /confirm double-resume guard.

A HITL confirmation must be claimed exactly once: two workers racing on the
same awaiting_confirmation job must not both schedule a resume (which would
execute a destructive tool twice). compare_and_set_status is the atomic gate;
these cover its in-memory (Redis-unavailable, single-process) path
deterministically.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent import job_store as js


@pytest.fixture(autouse=True)
def _clear_l1():
    js._l1.clear()
    yield
    js._l1.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cas_claims_exactly_once():
    with patch.object(js, "_get_redis", AsyncMock(return_value=None)):
        js._l1["j1"] = {"status": "awaiting_confirmation", "created_at": time.time()}

        first = await js.compare_and_set_status(
            "j1", "awaiting_confirmation", "running"
        )
        second = await js.compare_and_set_status(
            "j1", "awaiting_confirmation", "running"
        )

    assert first == "claimed"
    assert second == "conflict"  # the racing duplicate loses
    assert js._l1["j1"]["status"] == "running"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cas_missing_job():
    with patch.object(js, "_get_redis", AsyncMock(return_value=None)):
        assert (
            await js.compare_and_set_status("nope", "awaiting_confirmation", "running")
            == "missing"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cas_conflict_when_not_in_expected_status():
    with patch.object(js, "_get_redis", AsyncMock(return_value=None)):
        js._l1["j2"] = {"status": "completed", "created_at": time.time()}
        assert (
            await js.compare_and_set_status("j2", "awaiting_confirmation", "running")
            == "conflict"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cas_falls_back_to_memory_on_redis_error():
    """A Redis operational error must degrade to the in-memory transition, not
    silently drop the claim (which would stall a HITL confirm)."""

    class _BadPipe:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def watch(self, *a):
            raise RuntimeError("redis down mid-op")

    bad = MagicMock()
    bad.pipeline = MagicMock(return_value=_BadPipe())

    js._l1["j3"] = {
        "status": "awaiting_confirmation",
        "created_at": time.time(),
        "user_id": "u",
    }
    with patch.object(js, "_get_redis", AsyncMock(return_value=bad)):
        result = await js.compare_and_set_status(
            "j3", "awaiting_confirmation", "running"
        )

    assert result == "claimed"
    assert js._l1["j3"]["status"] == "running"
