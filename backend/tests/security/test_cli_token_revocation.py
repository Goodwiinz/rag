"""CLI-token revocation: per-user revoked-before cutoff, fail-open on Redis loss."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.core import cli_token_revocation as ctr


def _epoch(dt: datetime) -> int:
    return int(dt.timestamp())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_token_issued_before_cutoff_is_revoked() -> None:
    now = datetime.now(timezone.utc)
    client = AsyncMock()
    client.get = AsyncMock(return_value=str(_epoch(now)))  # revoked-before = now
    with patch.object(ctr, "_get_redis", AsyncMock(return_value=client)):
        revoked = await ctr.is_cli_token_revoked(
            "user-1", now - timedelta(hours=1)  # issued before the cutoff
        )
    assert revoked is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_token_issued_after_cutoff_is_valid() -> None:
    now = datetime.now(timezone.utc)
    client = AsyncMock()
    client.get = AsyncMock(return_value=str(_epoch(now - timedelta(hours=1))))
    with patch.object(ctr, "_get_redis", AsyncMock(return_value=client)):
        revoked = await ctr.is_cli_token_revoked("user-1", now)  # issued after
    assert revoked is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_cutoff_means_not_revoked() -> None:
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)  # no revoked-before key
    with patch.object(ctr, "_get_redis", AsyncMock(return_value=client)):
        assert await ctr.is_cli_token_revoked("user-1", datetime.now(timezone.utc)) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fail_open_when_redis_unavailable() -> None:
    with patch.object(ctr, "_get_redis", AsyncMock(return_value=None)):
        assert await ctr.is_cli_token_revoked("user-1", datetime.now(timezone.utc)) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fail_open_on_redis_error() -> None:
    client = AsyncMock()
    client.get = AsyncMock(side_effect=RuntimeError("redis down"))
    with patch.object(ctr, "_get_redis", AsyncMock(return_value=client)):
        assert await ctr.is_cli_token_revoked("user-1", datetime.now(timezone.utc)) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_issued_at_is_not_revoked() -> None:
    # Never call Redis if the token has no issued_at.
    get_redis = AsyncMock()
    with patch.object(ctr, "_get_redis", get_redis):
        assert await ctr.is_cli_token_revoked("user-1", None) is False
    get_redis.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revoke_writes_cutoff_with_ttl() -> None:
    client = AsyncMock()
    client.set = AsyncMock()
    with patch.object(ctr, "_get_redis", AsyncMock(return_value=client)):
        await ctr.revoke_user_cli_tokens("user-1")
    client.set.assert_awaited_once()
    args, kwargs = client.set.call_args
    assert args[0] == "cli_revoked_before:user-1"
    assert kwargs.get("ex") == ctr._TTL_SECONDS


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revoke_noop_without_redis() -> None:
    with patch.object(ctr, "_get_redis", AsyncMock(return_value=None)):
        await ctr.revoke_user_cli_tokens("user-1")  # must not raise
