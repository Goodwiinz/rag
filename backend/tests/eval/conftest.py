"""Eval-suite fixtures.

Skips the entire eval module if LangSmith credentials are missing so the
suite stays optional in local/CI environments without API keys.
"""
from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    del config  # required by pytest hook signature
    if os.environ.get("LANGCHAIN_API_KEY"):
        return
    skip_marker = pytest.mark.skip(reason="LANGCHAIN_API_KEY not set")
    for item in items:
        if "langsmith" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def langsmith_dataset_name() -> str:
    return os.environ.get(
        "AGENT_EVAL_DATASET_NAME", "agent-accuracy-benchmark"
    )


@pytest.fixture(scope="session")
def experiment_prefix() -> str:
    return os.environ.get("AGENT_EVAL_EXPERIMENT_PREFIX", "agent-regression")
