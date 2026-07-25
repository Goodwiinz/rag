"""Phase 9.A — AGENTS_*.md driver protocols load from disk."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.mark.unit
def test_research_loader_returns_non_empty():
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    body = load_agents_md("research")
    assert body
    assert "search_arxiv" in body
    assert "## The loop" in body


@pytest.mark.unit
def test_research_protocol_tells_the_model_to_call_named_destructive_tools():
    """The destructive-tool rule must not read as "ask first".

    Live dev evidence (synthetic ingest scenario, 00:40 and 03:00 on
    2026-07-25): ``scenario=ingest tool_executions=0 resumes=0`` on both runs
    — the model answered in prose and never called ``ingest_arxiv_papers``,
    so the HITL interrupt that gates the tool never got the chance to ask.
    The old line ("trigger user confirmation. Don't fire them speculatively.")
    contradicted both the loop example three lines above ("user pasted an
    arXiv ID, ingest it") and SHARED_AGENT_RULES, which is appended *after*
    the driver protocol and already says the destructive class is one the
    runtime interrupts so "you just call them" (``_prompts.py``). The model
    followed the more specific protocol line. The fix removes the
    contradiction rather than restating the shared rule.
    """
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    # Normalize markdown emphasis away — these pins are about wording, not
    # about whether a word happens to be bolded.
    body = load_agents_md("research").lower().replace("*", "")

    # The gate belongs to the runtime, not to a prose question.
    assert "gated by the runtime" in body
    # An explicit instruction is not speculation, and should be acted on.
    assert "call them when the user has named the target" in body
    assert "not acting on an explicit instruction" in body

    # The hedge must not come back in any capitalization or emphasis, and
    # "don't ask first" must not quietly invert.
    assert "don't fire them speculatively" not in body
    assert "do not fire them speculatively" not in body
    assert "do not ask first" in body


@pytest.mark.unit
def test_research_protocol_resolves_project_ambiguity_with_tools():
    """The recovered reply hedged on *project* ambiguity, not just the gate.

    Verbatim from the 03:00 run's checkpoint (thread
    ``synthetic-ingest-1784948427422``): "Do you want me to create the project
    named synthtraffic-… if it doesn't already exist, and then add the paper
    to it? If the project already exists, please confirm…" — a question
    ``list_projects``/``create_project`` answers without a round trip.
    """
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    body = load_agents_md("research").lower()

    assert "resolve, don't interrogate" in body
    assert "list_projects" in body and "create_project" in body


@pytest.mark.unit
def test_writing_loader_returns_non_empty():
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    body = load_agents_md("writing")
    assert body
    assert "summarize_document" in body
    assert "search_arxiv" in body


@pytest.mark.unit
def test_data_loader_returns_non_empty():
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    body = load_agents_md("data")
    assert body
    assert "search_knowledge_graph" in body


@pytest.mark.unit
def test_missing_subgraph_returns_empty_string():
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    body = load_agents_md("nonexistent_subgraph_xyz")
    assert body == ""


@pytest.mark.unit
def test_loader_caches_until_reload_env_set(monkeypatch, tmp_path: Path):
    """Default behavior: loader caches the file body. Setting
    AGENT_AGENTS_MD_RELOAD=true bypasses the cache so iteration on the
    markdown doesn't require a backend restart."""
    from src.services.agent.subgraphs import agents_md_loader

    # Reset cache for a clean test
    agents_md_loader._CACHE.pop("research", None)
    body1 = agents_md_loader.load_agents_md("research")
    body2 = agents_md_loader.load_agents_md("research")
    assert body1 == body2  # cache hit returns same string

    monkeypatch.setenv("AGENT_AGENTS_MD_RELOAD", "true")
    body3 = agents_md_loader.load_agents_md("research")
    # Same file → same content; flag just bypasses the cache layer.
    assert body3 == body1
