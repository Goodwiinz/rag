"""Init-failure behaviour of the LangGraph durability gate (audit X3).

When the Postgres-backed checkpointer / memory store fails to initialise:

- durability required (shared env, e.g. the live ``ENVIRONMENT=dev``
  deployment) -> ``get_checkpointer`` / ``get_memory_store`` raise a
  ``RuntimeError`` naming the failing dependency, and the singleton stays
  unset so a later call retries cleanly (no half-initialised saver/store
  is ever handed out);
- durability not required (local/CI throwaway env, or the
  ``ALLOW_MEMORY_FALLBACK`` break-glass override) -> they fall back to
  ``MemorySaver`` / ``InMemoryStore``.

The Postgres failure is simulated by patching the shared pool getter, so
these tests never touch a real database. On hosts without libpq the
``langgraph.checkpoint.postgres`` import fails before the pool getter
runs — both paths land in the same except-block, so assertions avoid
depending on which exact exception fired.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

import src.services.agent.checkpointer as checkpointer_mod
import src.services.agent.memory as memory_mod
from src.core import config as config_mod
from src.services.agent._pool_utils import require_durable_or_fallback
from src.services.agent.checkpointer import get_checkpointer, reset_checkpointer
from src.services.agent.memory import get_memory_store, reset_memory_store

pytestmark = pytest.mark.unit


async def _pool_raises(uri: str):
    raise ConnectionError("simulated: postgres unreachable")


@pytest.fixture(autouse=True)
async def _clean_singletons():
    """Isolate the module-level singletons from other tests."""
    await reset_checkpointer()
    await reset_memory_store()
    yield
    await reset_checkpointer()
    await reset_memory_store()


@pytest.fixture
def set_env(monkeypatch: pytest.MonkeyPatch):
    def _set(environment: str, allow_fallback: bool = False) -> None:
        monkeypatch.setattr(config_mod.settings, "ENVIRONMENT", environment)
        monkeypatch.setattr(
            config_mod.settings, "ALLOW_MEMORY_FALLBACK", allow_fallback
        )

    return _set


@pytest.fixture
def _postgres_down(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(checkpointer_mod, "get_shared_langgraph_pool", _pool_raises)
    monkeypatch.setattr(memory_mod, "get_shared_langgraph_pool", _pool_raises)


# ---------------------------------------------------------------------------
# require_durable_or_fallback — the gate itself
# ---------------------------------------------------------------------------


def test_gate_raises_when_durability_required(set_env) -> None:
    set_env("dev")
    cause = ConnectionError("postgres down")

    with pytest.raises(RuntimeError, match="Postgres checkpointer") as excinfo:
        require_durable_or_fallback("Postgres checkpointer", cause)

    # Clear error naming the failing dependency, chained to the real cause.
    assert excinfo.value.__cause__ is cause
    assert "durable agent state" in str(excinfo.value)
    assert "ALLOW_MEMORY_FALLBACK" in str(excinfo.value)


def test_gate_returns_when_env_is_throwaway(set_env) -> None:
    set_env("development")
    assert (
        require_durable_or_fallback(
            "Postgres checkpointer", ConnectionError("postgres down")
        )
        is None
    )


def test_gate_returns_when_override_set(set_env) -> None:
    set_env("dev", allow_fallback=True)
    assert (
        require_durable_or_fallback(
            "Postgres memory store", ConnectionError("postgres down")
        )
        is None
    )


# ---------------------------------------------------------------------------
# get_checkpointer
# ---------------------------------------------------------------------------


async def test_checkpointer_raises_in_shared_env(set_env, _postgres_down) -> None:
    set_env("dev")

    with pytest.raises(RuntimeError, match="Postgres checkpointer") as excinfo:
        await get_checkpointer()
    assert excinfo.value.__cause__ is not None

    # The singleton must NOT be poisoned by a half-initialised saver: the
    # next call retries init (and fails again) instead of short-circuiting
    # on a non-None global and handing out a saver whose setup() failed.
    assert checkpointer_mod._checkpointer is None
    with pytest.raises(RuntimeError, match="Postgres checkpointer"):
        await get_checkpointer()


async def test_checkpointer_falls_back_in_throwaway_env(
    set_env, _postgres_down
) -> None:
    set_env("development")

    checkpointer = await get_checkpointer()

    assert isinstance(checkpointer, MemorySaver)


async def test_checkpointer_falls_back_with_override(set_env, _postgres_down) -> None:
    set_env("dev", allow_fallback=True)

    checkpointer = await get_checkpointer()

    assert isinstance(checkpointer, MemorySaver)


# ---------------------------------------------------------------------------
# get_memory_store
# ---------------------------------------------------------------------------


async def test_memory_store_raises_in_shared_env(set_env, _postgres_down) -> None:
    set_env("dev")

    with pytest.raises(RuntimeError, match="Postgres memory store") as excinfo:
        await get_memory_store()
    assert excinfo.value.__cause__ is not None

    # Same no-poisoned-singleton guarantee as the checkpointer.
    assert memory_mod._store is None
    with pytest.raises(RuntimeError, match="Postgres memory store"):
        await get_memory_store()


async def test_memory_store_falls_back_in_throwaway_env(
    set_env, _postgres_down
) -> None:
    set_env("development")

    store = await get_memory_store()

    assert isinstance(store, InMemoryStore)


async def test_memory_store_falls_back_with_override(set_env, _postgres_down) -> None:
    set_env("dev", allow_fallback=True)

    store = await get_memory_store()

    assert isinstance(store, InMemoryStore)


async def test_memory_store_testing_fast_path(set_env, _postgres_down) -> None:
    """ENVIRONMENT=testing keeps its InMemoryStore fast path (no Postgres)."""
    set_env("testing")

    store = await get_memory_store()

    assert isinstance(store, InMemoryStore)
