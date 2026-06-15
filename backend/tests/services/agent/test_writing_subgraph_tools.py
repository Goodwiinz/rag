"""Regression tests for writing-subgraph tool surface.

Covers the recovery-path inclusion of ``ingest_arxiv_papers`` so that
queries like "Summarize arxiv 2201.00978" can auto-chain
``summarize_document`` (recoverable) → ``ingest_arxiv_papers`` → retry
``summarize_document`` instead of dead-ending in a refusal.
"""

from __future__ import annotations

import pytest

from src.services.agent.subgraphs.writing_agent import (
    WRITING_DESTRUCTIVE_TOOLS,
    WRITING_TOOL_NAMES_LIST,
    WRITING_TOOLS,
    _build_writing_system_prompt,
)


@pytest.mark.unit
def test_ingest_arxiv_papers_present_in_writing_tools() -> None:
    """Recovery path requires the writing LLM to bind ingest_arxiv_papers."""
    assert "ingest_arxiv_papers" in WRITING_TOOL_NAMES_LIST
    assert any(t.name == "ingest_arxiv_papers" for t in WRITING_TOOLS)


@pytest.mark.unit
def test_ingest_arxiv_papers_marked_destructive() -> None:
    """ingest_arxiv_papers must trigger the writing-subgraph HITL gate."""
    assert "ingest_arxiv_papers" in WRITING_DESTRUCTIVE_TOOLS


@pytest.mark.unit
def test_search_arxiv_present_and_read_only() -> None:
    """Title resolution requires search_arxiv, and it must not be HITL-gated."""
    assert "search_arxiv" in WRITING_TOOL_NAMES_LIST
    assert any(t.name == "search_arxiv" for t in WRITING_TOOLS)
    # Read-only discovery — must NOT trigger the destructive-tool confirmation.
    assert "search_arxiv" not in WRITING_DESTRUCTIVE_TOOLS


@pytest.mark.unit
def test_writing_prompt_documents_title_resolution() -> None:
    """System prompt must tell the agent to resolve titles itself, not ask for ids."""
    prompt = _build_writing_system_prompt()
    assert "ingest_arxiv_papers" in prompt
    assert "search_arxiv" in prompt
    # The protocol must cover the title → search → ingest path.
    assert "title" in prompt.lower()


@pytest.mark.unit
def test_writing_tool_surface_unchanged_for_core_tools() -> None:
    """Core writing tools must remain available — ingest is additive."""
    expected_core = {
        "create_draft",
        "create_project_note",
        "export_bibliography",
        "summarize_document",
        "compare_documents",
    }
    assert expected_core.issubset(set(WRITING_TOOL_NAMES_LIST))
