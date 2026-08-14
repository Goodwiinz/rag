"""Regression tests for compare_and_set_status — the /confirm double-resume guard.

A HITL confirmation must be claimed exactly once: two workers racing on the
same awaiting_confirmation job must not both schedule a resume (which would
execute a destructive tool twice). compare_and_set_status is the atomic gate;
these cover its in-memory (Redis-unavailable, single-process) path
deterministically.
"""

import json
import time
from types import SimpleNamespace
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
            # Operational error (ConnectionError ⊂ OSError) → triggers fallback.
            raise ConnectionError("redis down mid-op")

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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cas_fails_closed_without_redis_in_shared_environment():
    with (
        patch.object(js, "_get_redis", AsyncMock(return_value=None)),
        patch.object(
            js,
            "get_settings",
            return_value=SimpleNamespace(is_throwaway_environment=False),
        ),
    ):
        js._l1["j4"] = {
            "status": "awaiting_confirmation",
            "created_at": time.time(),
        }
        with pytest.raises(js.ConfirmationCoordinationUnavailable):
            await js.compare_and_set_status("j4", "awaiting_confirmation", "running")

    assert js._l1["j4"]["status"] == "awaiting_confirmation"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cas_recovers_when_redis_commits_then_response_is_lost():
    class _Redis:
        def __init__(self):
            self.value = json.dumps(
                {"status": "awaiting_confirmation", "created_at": time.time()}
            )

        async def get(self, _key):
            return self.value

        def pipeline(self, *, transaction):
            assert transaction is True
            return _AmbiguousPipe(self)

    class _AmbiguousPipe:
        def __init__(self, redis):
            self.redis = redis
            self.queued = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def watch(self, _key):
            return None

        async def get(self, _key):
            return self.redis.value

        async def ttl(self, _key):
            return 60

        def multi(self):
            return None

        def setex(self, _key, _ttl, value):
            self.queued = value

        async def execute(self):
            self.redis.value = self.queued
            raise ConnectionError("response lost after commit")

    redis = _Redis()
    with (
        patch.object(js, "_get_redis", AsyncMock(return_value=redis)),
        patch.object(
            js,
            "get_settings",
            return_value=SimpleNamespace(is_throwaway_environment=False),
        ),
    ):
        result = await js.compare_and_set_status(
            "j5", "awaiting_confirmation", "running"
        )

    assert result == "claimed"
    assert json.loads(redis.value)["status"] == "running"
