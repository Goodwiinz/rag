"""Unit tests for the writing fast-skip heuristic and timeout constant.

Covers:
- ``_is_simple_writing_flow`` — True/False cases
- ``PLANNER_LLM_TIMEOUT_SECONDS`` locked to 8
- Integration with ``make_planner_node``: simple writing queries in a project
  context must return {} without invoking check_complexity or generate_plan.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.services.agent.planner import (
    PLANNER_LLM_TIMEOUT_SECONDS,
    _is_simple_writing_flow,
    make_planner_node,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_state(query: str) -> dict:
    """Build a minimal planner state dict with project-mode page context."""
    return {
        "messages": [HumanMessage(content=query)],
        "page_context": {
            "type": "project",
            "project_id": "00000000-0000-0000-0000-000000000001",
        },
    }


# ---------------------------------------------------------------------------
# 1. Constant lock — catches accidental regression
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_planner_llm_timeout_is_8() -> None:
    """PLANNER_LLM_TIMEOUT_SECONDS must be 8 (lowered from 20)."""
    assert PLANNER_LLM_TIMEOUT_SECONDS == 8


# ---------------------------------------------------------------------------
# 2. _is_simple_writing_flow — True cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "query",
    [
        "summarize this document",
        "summarise the attached paper",
        "create a note about the results",
        "draft an intro",
        "write a note on section 3",
        "draft the abstract",
        "write a short summary",
        "create a note",
        "summarize this",
    ],
    ids=[
        "summarize-doc",
        "summarise-paper",
        "create-note",
        "draft-intro",
        "write-note-section",
        "draft-abstract",
        "write-summary",
        "create-note-bare",
        "summarize-this",
    ],
)
def test_is_simple_writing_flow_true(query: str) -> None:
    assert _is_simple_writing_flow(query) is True, f"Expected True for: {query!r}"


# ---------------------------------------------------------------------------
# 3. _is_simple_writing_flow — False cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "query",
    [
        # conjunction implies two steps
        "summarize X and compare it with Y",
        # sequential conjunction
        "draft a section then add citations",
        # question, not imperative
        "what should I write?",
        # empty string
        "",
        # long multi-clause request (>20 words)
        (
            "summarize all the papers in the project, extract the key findings, "
            "write a comparative analysis, add it as a note, and then export the draft"
        ),
        # coordinating conjunction "also"
        "create a note about X and also update the bibliography",
        # multiple commas
        "draft intro, add citations, then export",
        # non-writing verb
        "search for recent papers on transformers",
        # question mark mid-sentence
        "summarize this document, but what format?",
        # "then" conjunction
        "write a draft then summarize it",
        # "additionally" conjunction
        "summarize the paper additionally create a note",
    ],
    ids=[
        "conjunction-and-compare",
        "sequential-then",
        "question",
        "empty",
        "long-multi-clause",
        "also-conjunction",
        "multi-comma",
        "non-writing-verb",
        "question-mark-mid",
        "then-conjunction",
        "additionally-conjunction",
    ],
)
def test_is_simple_writing_flow_false(query: str) -> None:
    assert _is_simple_writing_flow(query) is False, f"Expected False for: {query!r}"


# ---------------------------------------------------------------------------
# 4. Integration: simple writing query in project context skips LLM calls
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planner_node_skips_llm_for_simple_writing_query() -> None:
    """A simple single-tool writing query must short-circuit before any LLM call.

    check_complexity and generate_plan are patched to raise if called so the
    test fails loudly if the fast-skip path is not exercised.
    """
    node = make_planner_node(
        tool_names=["summarize_document", "create_project_note", "create_draft"]
    )

    query = "summarize this document"

    with (
        patch(
            "src.services.agent.planner.check_complexity",
            new=AsyncMock(
                side_effect=AssertionError("check_complexity must not be called")
            ),
        ) as mock_cc,
        patch(
            "src.services.agent.planner.generate_plan",
            new=AsyncMock(
                side_effect=AssertionError("generate_plan must not be called")
            ),
        ) as mock_gp,
    ):
        result = await node(_project_state(query), config={})

    mock_cc.assert_not_awaited()
    mock_gp.assert_not_awaited()
    assert result == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planner_node_does_not_skip_multi_step_writing_query() -> None:
    """A writing query with a conjunction must NOT be fast-skipped — it should
    proceed to check_complexity (which may still return a low count)."""
    node = make_planner_node(tool_names=["summarize_document", "create_project_note"])

    query = "summarize this paper and create a note with the key findings"

    with patch(
        "src.services.agent.planner.check_complexity",
        new=AsyncMock(return_value=1),
    ) as mock_cc:
        result = await node(_project_state(query), config={})

    # check_complexity must have been called (fast-skip did NOT fire)
    mock_cc.assert_awaited_once()
    # step_count=1 < 3 → no plan
    assert result == {}
