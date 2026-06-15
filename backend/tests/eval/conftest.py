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
    from tests.eval._replay_llm import replay_enabled

    # Under AGENT_GOLDEN_REPLAY the fake model is installed at every LLM seam,
    # so golden cases run creds-free and must NOT be skipped — otherwise the
    # replay lane is vacuously green (green-but-blind).
    skip_golden = (
        None
        if _has_llm_creds() or replay_enabled()
        else pytest.mark.skip(reason="LLM credentials (AZURE_OPENAI_CHAT_*) not set")
    )
    for item in items:
        if skip_langsmith is not None and "langsmith" in item.keywords:
            item.add_marker(skip_langsmith)
        if skip_golden is not None and "golden" in item.keywords:
            item.add_marker(skip_golden)


@pytest.fixture(autouse=True)
def _golden_replay(monkeypatch, request):
    """Install the deterministic replay model at all LLM construction seams
    when AGENT_GOLDEN_REPLAY=1, so golden cases run creds-free + deterministic.

    Inert otherwise (Phase 1 default), and only acts on a parametrized golden
    case (one with a ``case`` param) — never on the dataset sweep or the pure
    unit tests.
    """
    from tests.eval._replay_llm import replay_enabled

    if not replay_enabled():
        return
    callspec = getattr(request.node, "callspec", None)
    if callspec is None or "case" not in callspec.params:
        return

    from tests.eval._replay_llm import GoldenReplayLLM, load_cassette

    case = callspec.params["case"]
    fake = GoldenReplayLLM(load_cassette(case.name))

    from src.services.agent import (
        classifier,
        compactor,
        graph,
        llm_factory,
        planner,
        reflection,
    )

    # Clear all build + result caches so the fake is actually constructed
    # (4.2 in the design — otherwise a previously-built real client leaks).
    llm_factory.reset_llm_caches()
    graph._LLM_CACHE.clear()
    monkeypatch.setattr(classifier, "_CLASSIFIER_LLM", None, raising=False)
    monkeypatch.setattr(reflection, "_REFLECTION_LLM", None, raising=False)
    monkeypatch.setattr(compactor, "_COMPACTOR_LLM", None, raising=False)

    # Three construction seams + three module-top rebinds (reflection/planner/
    # compactor `from ... import build_lightweight_llm` bind a local name).
    for module, attr in (
        (llm_factory, "build_lightweight_llm"),
        (llm_factory, "build_synthesis_llm"),
        (graph, "_build_llm"),
        (reflection, "build_lightweight_llm"),
        (planner, "build_lightweight_llm"),
        (compactor, "build_lightweight_llm"),
    ):
        monkeypatch.setattr(module, attr, lambda *a, **k: fake, raising=False)

    # Phase 5: stub tool execution so replay touches no infra (DB/Neo4j/Qdrant/
    # arXiv). Golden cases assert tool-call names + intent, not tool results.
    from tests.eval._replay_llm import stub_tool_executor

    monkeypatch.setattr(graph, "_get_execute_tool", lambda: stub_tool_executor, raising=False)


@pytest.fixture(scope="session")
def langsmith_dataset_name() -> str:
    return os.environ.get(
        "AGENT_EVAL_DATASET_NAME", "agent-accuracy-benchmark"
    )


@pytest.fixture(scope="session")
def experiment_prefix() -> str:
    return os.environ.get("AGENT_EVAL_EXPERIMENT_PREFIX", "agent-regression")
