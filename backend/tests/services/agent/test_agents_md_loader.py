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
    both duplicated the system's own gate and contradicted the loop example
    at "user pasted an arXiv ID, ingest it".

    Pins the two properties that resolve it: the gate is described as the
    system's, and an explicit instruction is carved out of "speculatively".
    """
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    body = load_agents_md("research")

    # The confirmation belongs to the system, not to a prose question.
    assert "calling one does not perform it" in body.lower()
    # An already-named target is not speculation.
    assert "call the tool" in body.lower()
    assert "did *not* ask for" in body.lower()
    # The bare imperative that produced the hedge must not stand alone.
    assert "trigger user confirmation. Don't fire them speculatively." not in body


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
