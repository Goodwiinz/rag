"""Unit tests for the readiness-critical health checks.

Regression coverage for the outage where the k8s readiness probe
(/health/readiness, critical checks = ["database", "redis"]) was wedged
because both checks opened their own DIY connections:

* ``check_database`` opened a fresh ``asyncpg.connect()`` per probe and
  exhausted Supabase's 25-client session-mode pooler
  ("(EMAXCONNSESSION) max clients reached in session mode").
* ``check_redis`` mangled the deployed ``rediss://`` (TLS) URL by
  prepending ``redis://``, so the scheme token was parsed as the host
  ("Error -2 connecting to rediss:6379").

The fixes reuse the app's async SQLAlchemy engine and pass the Redis URL
straight to ``from_url``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.health.checker import HealthChecker, HealthCheckResult, HealthStatus

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_readiness_cache():
    """Clear the module-level readiness cache so each readiness test evaluates
    freshly instead of returning a neighbouring test's cached outcome."""
    from src.health import endpoints

    endpoints._readiness_cached_result = None
    endpoints._readiness_last_check_time = 0.0
    yield
    endpoints._readiness_cached_result = None
    endpoints._readiness_last_check_time = 0.0


# --------------------------------------------------------------------------- #
# Async engine test doubles
# --------------------------------------------------------------------------- #
class _FakeAsyncConn:
    def __init__(self, scalar_value=1, raise_exc=None):
        self._scalar_value = scalar_value
        self._raise_exc = raise_exc

    async def scalar(self, *args, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._scalar_value


class _FakeConnectCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakeEngine:
    """Stands in for src.core.database.async_engine."""

    def __init__(self, conn):
        self._conn = conn
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        return _FakeConnectCtx(self._conn)


# --------------------------------------------------------------------------- #
# BUG 1 — check_database reuses the app engine (never asyncpg.connect)
# --------------------------------------------------------------------------- #
async def test_check_database_uses_app_engine_not_asyncpg(monkeypatch):
    import asyncpg

    connect_mock = MagicMock(
        side_effect=AssertionError("asyncpg.connect must not be called")
    )
    monkeypatch.setattr(asyncpg, "connect", connect_mock)

    fake_engine = _FakeEngine(_FakeAsyncConn(scalar_value=1))
    monkeypatch.setattr("src.core.database.async_engine", fake_engine)

    checker = HealthChecker({"database_url": "postgresql://user:pass@host/db"})
    result = await checker.check_database()

    assert result.status is HealthStatus.HEALTHY
    assert result.component == "database"
    assert result.response_time >= 0
    # The engine connection was borrowed exactly once...
    assert fake_engine.connect_calls == 1
    # ...and no raw asyncpg connection was ever opened.
    connect_mock.assert_not_called()


async def test_check_database_failure_is_unhealthy(monkeypatch):
    fake_engine = _FakeEngine(_FakeAsyncConn(raise_exc=RuntimeError("boom")))
    monkeypatch.setattr("src.core.database.async_engine", fake_engine)

    checker = HealthChecker({"database_url": "postgresql://user:pass@host/db"})
    result = await checker.check_database()

    assert result.status is HealthStatus.UNHEALTHY
    assert "boom" in result.message


async def test_check_database_unexpected_result_is_unhealthy(monkeypatch):
    fake_engine = _FakeEngine(_FakeAsyncConn(scalar_value=0))
    monkeypatch.setattr("src.core.database.async_engine", fake_engine)

    checker = HealthChecker({"database_url": "postgresql://user:pass@host/db"})
    result = await checker.check_database()

    assert result.status is HealthStatus.UNHEALTHY


async def test_check_database_missing_url_is_unknown():
    checker = HealthChecker({})
    result = await checker.check_database()

    assert result.status is HealthStatus.UNKNOWN


# --------------------------------------------------------------------------- #
# BUG 2 — check_redis passes the rediss:// URL through untouched
# --------------------------------------------------------------------------- #
def _fake_redis_client():
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


async def test_check_redis_passes_full_rediss_url_to_from_url(monkeypatch):
    client = _fake_redis_client()
    from_url_mock = MagicMock(return_value=client)
    monkeypatch.setattr("src.health.checker.aioredis.from_url", from_url_mock)

    url = "rediss://default:secret@db-redis.example.com:6379/0"
    checker = HealthChecker({"redis_url": url})
    result = await checker.check_redis()

    assert result.status is HealthStatus.HEALTHY
    from_url_mock.assert_called_once()
    # The TLS URL is passed verbatim as the first positional arg — no
    # "redis://" prefix mangling that would turn "rediss" into the host.
    args, _kwargs = from_url_mock.call_args
    assert args[0] == url
    client.ping.assert_awaited_once()
    client.close.assert_awaited_once()


async def test_check_redis_ping_false_is_unhealthy(monkeypatch):
    client = _fake_redis_client()
    client.ping = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "src.health.checker.aioredis.from_url", MagicMock(return_value=client)
    )

    checker = HealthChecker({"redis_url": "rediss://host:6379"})
    result = await checker.check_redis()

    assert result.status is HealthStatus.UNHEALTHY
    client.close.assert_awaited_once()


async def test_check_redis_connection_error_is_unhealthy(monkeypatch):
    from_url_mock = MagicMock(side_effect=OSError("Error -2 connecting to rediss:6379"))
    monkeypatch.setattr("src.health.checker.aioredis.from_url", from_url_mock)

    checker = HealthChecker({"redis_url": "rediss://host:6379"})
    result = await checker.check_redis()

    assert result.status is HealthStatus.UNHEALTHY
    assert "Error -2" in result.message


async def test_check_redis_missing_url_is_unknown():
    checker = HealthChecker({})
    result = await checker.check_redis()

    assert result.status is HealthStatus.UNKNOWN


# --------------------------------------------------------------------------- #
# Readiness endpoint: 503 -> 200 transition
# --------------------------------------------------------------------------- #
def _result(component, status):
    return HealthCheckResult(
        component=component, status=status, message="stub", response_time=0.01
    )


async def test_readiness_returns_503_when_critical_component_unhealthy(monkeypatch):
    from src.health import endpoints

    endpoints.set_llm_config_ready(True)
    checker = endpoints.get_health_checker()
    monkeypatch.setattr(
        checker,
        "check_database",
        AsyncMock(return_value=_result("database", HealthStatus.UNHEALTHY)),
    )
    monkeypatch.setattr(
        checker,
        "check_redis",
        AsyncMock(return_value=_result("redis", HealthStatus.HEALTHY)),
    )

    with pytest.raises(HTTPException) as exc_info:
        await endpoints.readiness_probe()

    assert exc_info.value.status_code == 503
    assert "database" in str(exc_info.value.detail)


async def test_readiness_returns_ready_when_all_critical_healthy(monkeypatch):
    from src.health import endpoints

    endpoints.set_llm_config_ready(True)
    checker = endpoints.get_health_checker()
    monkeypatch.setattr(
        checker,
        "check_database",
        AsyncMock(return_value=_result("database", HealthStatus.HEALTHY)),
    )
    monkeypatch.setattr(
        checker,
        "check_redis",
        AsyncMock(return_value=_result("redis", HealthStatus.HEALTHY)),
    )

    result = await endpoints.readiness_probe()

    assert result["status"] == "ready"
