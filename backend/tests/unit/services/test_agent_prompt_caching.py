"""Tests for the cacheable static prefix of ``llm_node``'s system prompt.

Azure OpenAI's gpt-4o family caches a system-message prefix automatically
when it is byte-identical across requests and ≥1024 tokens. We extract
the static portion as a module constant so dynamic state-derived content
(page context, intent, memories, retrieved docs) cannot leak into the
prefix and bust the cache.
"""

import pytest

from src.services.agent.graph import (
    SHARED_AGENT_RULES,
    _LLM_NODE_STATIC_PROMPT,
    _build_page_context_line,
)


@pytest.mark.unit
class TestStaticPromptPrefix:
    """The constant must contain only stable, request-independent content."""

    def test_does_not_leak_state_derived_phrasing(self) -> None:
        # Phrases that only appear when state is interpolated.
        leaks = [
            "is viewing the project",  # context_line, project page
            "currently on the",  # context_line, active tab
            "Project description:",  # context_line, project metadata
            "is on the",  # context_line, non-project page
            "Current intent:",  # intent guidance
            "Relevant past interactions:",  # user_memories block
            "Retrieved context:",  # retrieved docs block
        ]
        for phrase in leaks:
            assert phrase not in _LLM_NODE_STATIC_PROMPT, (
                f"Static prefix must not contain state-derived phrase {phrase!r}; "
                "moving it back into llm_node will bust prompt caching."
            )

    def test_contains_shared_rules(self) -> None:
        # The whole point: SHARED_AGENT_RULES is in the cacheable prefix,
        # not appended dynamically.
        assert SHARED_AGENT_RULES in _LLM_NODE_STATIC_PROMPT

    def test_contains_tool_listing(self) -> None:
        for tool in (
            "search_arxiv",
            "ingest_arxiv_papers",
            "search_documents",
            "create_project",
            "list_projects",
            "create_project_note",
            "summarize_document",
            "search_knowledge_graph",
            "export_bibliography",
        ):
            assert f"**{tool}**" in _LLM_NODE_STATIC_PROMPT, (
                f"Tool {tool} missing from static prefix"
            )

    def test_long_enough_for_provider_caching(self) -> None:
        # Azure gpt-4o requires ≥1024 tokens for the auto cache to engage.
        # ~3.5 chars/token is a conservative estimate, so 1024 * 3.5 = 3584.
        # The current prefix is materially longer, but enforce a floor so
        # accidental shrinkage doesn't silently disable caching.
        assert len(_LLM_NODE_STATIC_PROMPT) >= 3584, (
            f"Static prefix is {len(_LLM_NODE_STATIC_PROMPT)} chars — too "
            "short to reliably trigger Azure's automatic prefix cache."
        )


@pytest.mark.unit
class TestBuildPageContextLine:
    """``_build_page_context_line`` is the dynamic surface that must never
    bleed into the static constant. Verifies the renderer behaves correctly
    for the cases that previously lived inline in ``llm_node``."""

    def test_unknown_page_returns_empty(self) -> None:
        assert _build_page_context_line({}) == ""
        assert _build_page_context_line({"type": "unknown"}) == ""

    def test_project_page_renders_id_and_name(self) -> None:
        line = _build_page_context_line(
            {
                "type": "project",
                "project_id": "abc-123",
                "project_name": "RAG Research",
            }
        )
        assert "RAG Research" in line
        assert "abc-123" in line
        assert "this project" in line  # guidance about referring back

    def test_project_page_includes_active_tab(self) -> None:
        line = _build_page_context_line(
            {
                "type": "project",
                "project_id": "p1",
                "project_name": "X",
                "metadata": {"activeTab": "documents"},
            }
        )
        assert "documents tab" in line

    def test_project_page_includes_doc_count_and_description(self) -> None:
        line = _build_page_context_line(
            {
                "type": "project",
                "project_id": "p1",
                "project_name": "X",
                "metadata": {"documentCount": 7, "description": "About transformers"},
            }
        )
        assert "7 documents" in line
        assert "About transformers" in line

    def test_non_project_page_uses_label(self) -> None:
        line = _build_page_context_line({"type": "search", "label": "Search"})
        assert line == "The user is on the Search page."

    def test_non_project_page_falls_back_to_type(self) -> None:
        # No label → use the type itself.
        line = _build_page_context_line({"type": "settings"})
        assert line == "The user is on the settings page."

    def test_project_page_without_id_falls_through(self) -> None:
        # type="project" but no project_id → treated as non-project page.
        line = _build_page_context_line(
            {"type": "project", "label": "Projects"}
        )
        assert line == "The user is on the Projects page."
