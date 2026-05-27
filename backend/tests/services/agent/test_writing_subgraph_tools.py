"""Regression tests for writing-subgraph tool surface.

Covers ``search_documents`` (title → document_id resolution) and the
recovery-path inclusion of ``ingest_arxiv_papers`` so that queries like
"Summarize arxiv 2201.00978" can auto-chain ``summarize_document``
(recoverable) → ``ingest_arxiv_papers`` → retry ``summarize_document``
instead of dead-ending in a refusal.
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
def test_writing_prompt_documents_recovery_path() -> None:
    """System prompt must constrain ingest to the recovery path only."""
    prompt = _build_writing_system_prompt()
    assert "ingest_arxiv_papers" in prompt
    assert "RECOVERY ONLY" in prompt
    assert "error_type='recoverable'" in prompt
    assert "Never call this tool unprompted" in prompt


@pytest.mark.unit
def test_writing_tool_surface_unchanged_for_core_tools() -> None:
    """Core writing tools must remain available — ingest is additive."""
    expected_core = {
        "search_documents",
        "create_draft",
        "create_project_note",
        "export_bibliography",
        "summarize_document",
        "compare_documents",
    }
    assert expected_core.issubset(set(WRITING_TOOL_NAMES_LIST))


@pytest.mark.unit
def test_search_documents_present_in_writing_tools() -> None:
    """Writing subgraph must have search_documents for title → ID resolution."""
    assert "search_documents" in WRITING_TOOL_NAMES_LIST
    assert any(t.name == "search_documents" for t in WRITING_TOOLS)


@pytest.mark.unit
def test_search_documents_not_destructive() -> None:
    """search_documents is read-only — must NOT trigger HITL gate."""
    assert "search_documents" not in WRITING_DESTRUCTIVE_TOOLS


@pytest.mark.unit
def test_writing_prompt_instructs_search_before_summarize() -> None:
    """System prompt must guide LLM to search first and never ask for IDs."""
    prompt = _build_writing_system_prompt()
    assert "search_documents" in prompt
    assert "Never ask the user for a document_id" in prompt
