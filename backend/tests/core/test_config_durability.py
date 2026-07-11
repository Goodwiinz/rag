"""Truth table for ``Settings.require_durable_agent_state`` (audit X3).

The predicate decides whether the LangGraph checkpointer / long-term
memory store may silently fall back to non-durable in-memory backends on
Postgres init failure. It must be keyed on "is this an explicit local/CI
throwaway process?" — NOT on a hard-coded allowlist of strict env names:
the old ``ENVIRONMENT in ("production", "staging")`` gate never fired in
the live ``ENVIRONMENT=dev`` deployment, so HITL resume and cross-restart
memory degraded invisibly.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.core.config import MEMORY_FALLBACK_ENVIRONMENTS, Settings

pytestmark = pytest.mark.unit


# Safe values for envs whose validators reject the localhost/weak-secret
# defaults (production/staging). Passed for every case so the truth table
# stays uniform regardless of ENVIRONMENT.
_SAFE_OVERRIDES: dict[str, Any] = {
    "DATABASE_URL": "postgresql://postgres:postgres@db.example.com:5432/app",
    "SECRET_KEY": "s" * 32,
    "JWT_SECRET_KEY": "j" * 32,
    "NEO4J_PASSWORD": "neo4j-password-for-durability-tests",
}


def _settings(environment: str, **overrides: Any) -> Settings:
    return Settings(ENVIRONMENT=environment, **{**_SAFE_OVERRIDES, **overrides})


@pytest.mark.parametrize(
    "environment",
    [
        # The live DOKS deployment — the case the retired
        # ("production", "staging") gate silently missed.
        "dev",
        "production",
        "staging",
        # Unrecognised env names fail closed: durability required.
        "qa",
        "prod-eu",
        "",
        # Normalisation: case/whitespace variants of shared envs.
        "DEV",
        " dev ",
    ],
)
def test_durability_required_in_shared_or_unknown_envs(environment: str) -> None:
    assert _settings(environment).require_durable_agent_state is True


@pytest.mark.parametrize(
    "environment",
    [
        # The repo's actual local/CI names.
        "development",
        "testing",
        # Conventional throwaway aliases.
        "local",
        "test",
        "ci",
        # Normalisation: case/whitespace variants.
        "TESTING",
        " development ",
    ],
)
def test_fallback_allowed_in_local_ci_throwaway_envs(environment: str) -> None:
    assert _settings(environment).require_durable_agent_state is False


def test_allow_memory_fallback_override_waives_durability() -> None:
    settings = _settings("dev", ALLOW_MEMORY_FALLBACK=True)
    assert settings.require_durable_agent_state is False


def test_allow_memory_fallback_defaults_off() -> None:
    settings = _settings("dev")
    assert settings.ALLOW_MEMORY_FALLBACK is False
    assert settings.require_durable_agent_state is True


def test_dev_is_not_a_fallback_environment() -> None:
    """Regression tripwire: ``dev`` is the SHARED deployed environment.

    Adding it to MEMORY_FALLBACK_ENVIRONMENTS would reintroduce the silent
    MemorySaver/InMemoryStore degradation this predicate exists to prevent
    (audit finding X3). ``development`` (local compose) is the throwaway;
    ``dev`` (DOKS, Supabase Postgres, real users) is not.
    """
    assert "dev" not in MEMORY_FALLBACK_ENVIRONMENTS
    assert "development" in MEMORY_FALLBACK_ENVIRONMENTS
