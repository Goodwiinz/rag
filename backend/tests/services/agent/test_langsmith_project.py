"""LangSmith project name is derived authoritatively from the deploy env.

Guards the fix for trace fragmentation: a stale externally-injected
LANGSMITH_PROJECT (e.g. an old Infisical rag-agent-dev-local) must NOT win for
a recognised deploy env — the project is forced to rag-agent-{dev|staging|prod}.
"""

from __future__ import annotations

import os

import pytest

from src.services.agent.observability import (
    _normalize_deploy_env,
    configure_langsmith,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("dev", "dev"),
        ("development", "dev"),
        ("staging", "staging"),
        ("stage", "staging"),
        ("prod", "prod"),
        ("production", "prod"),
        ("PRODUCTION", "prod"),
        ("", None),
        ("test", None),
        ("ci", None),
    ],
)
def test_normalize_deploy_env(monkeypatch, raw, expected):
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", raw)
    assert _normalize_deploy_env() == expected


@pytest.mark.unit
def test_stale_project_overridden_for_known_env(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT_OVERRIDE", raising=False)
    # A stale injected value that previously fragmented traces:
    monkeypatch.setenv("LANGSMITH_PROJECT", "rag-agent-dev-local")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "rag-agent-dev-local")

    configure_langsmith()

    assert os.environ["LANGSMITH_PROJECT"] == "rag-agent-dev"
    assert os.environ["LANGCHAIN_PROJECT"] == "rag-agent-dev"


@pytest.mark.unit
def test_production_env_maps_to_prod_project(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT_OVERRIDE", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")

    configure_langsmith()

    assert os.environ["LANGSMITH_PROJECT"] == "rag-agent-prod"


@pytest.mark.unit
def test_override_always_wins(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT_OVERRIDE", "my-branch-project")

    configure_langsmith()

    assert os.environ["LANGSMITH_PROJECT"] == "my-branch-project"


@pytest.mark.unit
def test_unknown_env_honours_explicit_value(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "test")  # unrecognised → None
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT_OVERRIDE", raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT", "rag-agent-evals")

    configure_langsmith()

    assert os.environ["LANGSMITH_PROJECT"] == "rag-agent-evals"
