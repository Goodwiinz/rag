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
def test_writing_loader_returns_non_empty():
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    body = load_agents_md("writing")
    assert body
    assert "summarize_document" in body
    assert "RECOVERY ONLY" in body


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
