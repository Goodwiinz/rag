"""Unit tests for the cached, dependency-aware readiness probe.

Covers the audit item that wires the k8s readiness probe to
``/health/readiness`` (dependency-aware) instead of the unconditional
``/health`` handler, and adds a short in-process cache so kubelet polling
doesn't open a fresh DB + Redis connection on every hit.
"""

import asyncio

import pytest
from fastapi import HTTPException

from src.health import endpoints as ep
from src.health.checker import HealthCheckResult, HealthStatus


def _result(component: str, status: HealthStatus) -> HealthCheckResult:
    return HealthCheckResult(
        component=component,
        status=status,
        message=f"{component} {status.value}",
        response_time=0.001,
    )


class _StubChecker:
    """Health checker double that counts dependency-check invocations."""

    def __init__(self, statuses=None, slow=False):
        # statuses: component -> HealthStatus (default HEALTHY)
        self._statuses = statuses or {}
        self._slow = slow
        self.calls = {}

    async def _check(self, component: str) -> HealthCheckResult:
        self.calls[component] = self.calls.get(component, 0) + 1
        if self._slow:
            await asyncio.sleep(0.02)
        return _result(component, self._statuses.get(component, HealthStatus.HEALTHY))

    async def check_database(self) -> HealthCheckResult:
        return await self._check("database")

    async def check_redis(self) -> HealthCheckResult:
        return await self._check("redis")

    async def check_neo4j(self) -> HealthCheckResult:  # must never be called
        return await self._check("neo4j")


@pytest.fixture(autouse=True)
def _reset_readiness_state():
    """Reset the module-level readiness cache and flags around each test."""
    ep._readiness_cached_result = None
    ep._readiness_last_check_time = 0.0
    ep._readiness_lock = None
    ep._llm_config_ready = True
    original_ttl = ep._readiness_cache_ttl
    yield
    ep._readiness_cached_result = None
    ep._readiness_last_check_time = 0.0
    ep._readiness_lock = None
    ep._llm_config_ready = True
    ep._readiness_cache_ttl = original_ttl


@pytest.mark.unit
async def test_readiness_ready_when_deps_healthy(monkeypatch):
    stub = _StubChecker()
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)

    result = await ep.readiness_probe()

    assert result["status"] == "ready"
    assert stub.calls == {"database": 1, "redis": 1}


@pytest.mark.unit
async def test_readiness_caches_within_ttl(monkeypatch):
    """Repeated probes inside the TTL must not re-hit DB/Redis."""
    stub = _StubChecker()
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)

    for _ in range(5):
        assert (await ep.readiness_probe())["status"] == "ready"

    # Only the first probe actually evaluated the dependencies.
    assert stub.calls == {"database": 1, "redis": 1}


@pytest.mark.unit
async def test_readiness_reevaluates_after_ttl(monkeypatch):
    stub = _StubChecker()
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)

    await ep.readiness_probe()
    assert stub.calls == {"database": 1, "redis": 1}

    # Force the cache to look expired.
    ep._readiness_last_check_time -= ep._readiness_cache_ttl + 1

    await ep.readiness_probe()
    assert stub.calls == {"database": 2, "redis": 2}


@pytest.mark.unit
async def test_readiness_concurrent_probes_evaluate_once(monkeypatch):
    """A burst of concurrent probes triggers a single dependency evaluation."""
    stub = _StubChecker(slow=True)
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)

    results = await asyncio.gather(*(ep.readiness_probe() for _ in range(10)))

    assert all(r["status"] == "ready" for r in results)
    assert stub.calls == {"database": 1, "redis": 1}


@pytest.mark.unit
async def test_readiness_unhealthy_dependency_returns_503(monkeypatch):
    stub = _StubChecker(statuses={"redis": HealthStatus.UNHEALTHY})
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)

    with pytest.raises(HTTPException) as exc:
        await ep.readiness_probe()

    assert exc.value.status_code == 503
    assert "redis" in exc.value.detail


@pytest.mark.unit
async def test_readiness_check_exception_is_folded_into_not_ready(monkeypatch):
    """A raising checker becomes a cached not-ready result, not a re-hit loop."""

    class _RaisingChecker:
        def __init__(self):
            self.calls = 0

        async def check_database(self):
            self.calls += 1
            raise RuntimeError("boom")

        async def check_redis(self):  # pragma: no cover - never reached
            raise AssertionError("redis should not be reached")

    stub = _RaisingChecker()
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)

    with pytest.raises(HTTPException) as exc:
        await ep.readiness_probe()
    assert exc.value.status_code == 503

    # Second probe within TTL reuses the cached not-ready result (no re-hit).
    with pytest.raises(HTTPException):
        await ep.readiness_probe()
    assert stub.calls == 1


@pytest.mark.unit
async def test_readiness_llm_config_not_ready_skips_dependency_calls(monkeypatch):
    """A missing LLM config short-circuits before any DB/Redis call."""
    stub = _StubChecker()
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)
    ep._llm_config_ready = False

    with pytest.raises(HTTPException) as exc:
        await ep.readiness_probe()

    assert exc.value.status_code == 503
    assert "LLM configuration incomplete" in exc.value.detail
    assert stub.calls == {}  # no dependency checks were run


@pytest.mark.unit
def test_startup_readiness_strict_env_bad_config_blocks():
    """Strict (non-throwaway) env + missing LLM config → not ready (503 later)."""
    assert ep.resolve_startup_readiness(
        llm_config_ok=False, is_throwaway_env=False
    ) is (False)


@pytest.mark.unit
def test_startup_readiness_throwaway_env_bad_config_stays_ready():
    """Throwaway local/CI env + missing LLM config → stays ready (warn only)."""
    assert ep.resolve_startup_readiness(llm_config_ok=False, is_throwaway_env=True) is (
        True
    )


@pytest.mark.unit
@pytest.mark.parametrize("is_throwaway", [True, False])
def test_startup_readiness_good_config_ready_everywhere(is_throwaway):
    """Valid LLM config → ready in every environment class."""
    assert (
        ep.resolve_startup_readiness(llm_config_ok=True, is_throwaway_env=is_throwaway)
        is True
    )


@pytest.mark.unit
async def test_readiness_strict_env_bad_config_returns_503(monkeypatch):
    """End-to-end: strict-env startup decision flips the flag → probe 503s."""
    stub = _StubChecker()
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)
    # Mirror the main.py startup wiring for a strict env with bad config.
    ep.set_llm_config_ready(
        ep.resolve_startup_readiness(llm_config_ok=False, is_throwaway_env=False)
    )

    with pytest.raises(HTTPException) as exc:
        await ep.readiness_probe()

    assert exc.value.status_code == 503
    assert "LLM configuration incomplete" in exc.value.detail
    assert stub.calls == {}  # short-circuited before dependency checks


@pytest.mark.unit
async def test_readiness_throwaway_env_bad_config_stays_ready(monkeypatch):
    """End-to-end: throwaway-env startup decision keeps the pod ready."""
    stub = _StubChecker()
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)
    ep.set_llm_config_ready(
        ep.resolve_startup_readiness(llm_config_ok=False, is_throwaway_env=True)
    )

    result = await ep.readiness_probe()

    assert result["status"] == "ready"
    assert stub.calls == {"database": 1, "redis": 1}


@pytest.mark.unit
async def test_readiness_only_checks_database_and_redis(monkeypatch):
    """Optional backends (e.g. Neo4j) must not gate readiness."""
    stub = _StubChecker()
    monkeypatch.setattr(ep, "get_health_checker", lambda: stub)

    await ep.readiness_probe()

    assert "neo4j" not in stub.calls
    assert set(stub.calls) == {"database", "redis"}
