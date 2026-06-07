"""Eval-suite fixtures.

Skips the entire eval module if LangSmith credentials are missing so the
suite stays optional in local/CI environments without API keys.
"""
from __future__ import annotations

import os

import pytest


def _has_llm_creds() -> bool:
    """True if Azure/OpenAI chat creds are configured (see llm_factory)."""
    endpoint = os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT") or os.environ.get(
        "AZURE_OPENAI_ENDPOINT"
    )
    api_key = os.environ.get("AZURE_OPENAI_CHAT_API_KEY") or os.environ.get(
        "AZURE_OPENAI_API_KEY"
    )
    return bool(endpoint and api_key)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    del config  # required by pytest hook signature
    # Two independent gates:
    #   - langsmith: needs the LangSmith dataset round-trip (LANGCHAIN_API_KEY).
    #   - golden:    needs only LLM creds; this is the fast per-PR agent gate,
    #     decoupled from LangSmith so it can run on PRs that have LLM creds
    #     but no LangSmith key.
    skip_langsmith = (
        None
        if os.environ.get("LANGCHAIN_API_KEY")
        else pytest.mark.skip(reason="LANGCHAIN_API_KEY not set")
    )
    skip_golden = (
        None
        if _has_llm_creds()
        else pytest.mark.skip(reason="LLM credentials (AZURE_OPENAI_CHAT_*) not set")
    )
    for item in items:
        if skip_langsmith is not None and "langsmith" in item.keywords:
            item.add_marker(skip_langsmith)
        if skip_golden is not None and "golden" in item.keywords:
            item.add_marker(skip_golden)


@pytest.fixture(scope="session")
def langsmith_dataset_name() -> str:
    return os.environ.get(
        "AGENT_EVAL_DATASET_NAME", "agent-accuracy-benchmark"
    )


@pytest.fixture(scope="session")
def experiment_prefix() -> str:
    return os.environ.get("AGENT_EVAL_EXPERIMENT_PREFIX", "agent-regression")
