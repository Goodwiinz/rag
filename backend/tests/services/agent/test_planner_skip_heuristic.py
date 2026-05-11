"""Phase 3 regression — planner skip heuristic threshold bump 8 → 12.

Trace 019e1554 showed planner spinning 52s on a borderline query that
the agent could have answered in one tool call. Bumping the min-word
threshold from 8 to 12 avoids the expensive plan-generation LLM call
for queries the main LLM handles fine.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.services.agent.planner import make_planner_node


def _state(query: str) -> dict:
    return {
        "messages": [HumanMessage(content=query)],
        # Project-mode page context: planner only runs when a project is
        # active (Phase 7.4 added the no-project early skip).
        "page_context": {
            "type": "project",
            "project_id": "00000000-0000-0000-0000-000000000001",
        },
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skip_for_short_query_under_12_words():
    """11-word queries skip planner entirely (no complexity LLM call)."""
    node = make_planner_node(tool_names=["search_arxiv"])

    query = "summarize this paper and add it to my project now"  # 10 words
    assert len(query.split()) < 12

    with patch(
        "src.services.agent.planner.check_complexity",
        new=AsyncMock(side_effect=AssertionError("complexity should be skipped")),
    ):
        result = await node(_state(query), config={})

    assert result == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skip_for_conversational_starter_under_18_words():
    """Conversational starter (yes/no/what) with <18 words bypasses planner."""
    node = make_planner_node(tool_names=["search_arxiv"])

    query = "what would you do if you were me asked to find papers please"  # 14 words
    with patch(
        "src.services.agent.planner.check_complexity",
        new=AsyncMock(side_effect=AssertionError("should be skipped")),
    ):
        result = await node(_state(query), config={})

    assert result == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_long_substantive_query_invokes_complexity_check():
    """Long substantive queries (≥12 words, non-conversational starter)
    proceed to the complexity check."""
    node = make_planner_node(tool_names=["search_arxiv"])

    query = (
        "Find recent transformer architecture papers ingest them attach to "
        "project and summarize the findings for me carefully"
    )
    assert len(query.split()) >= 12

    with patch(
        "src.services.agent.planner.check_complexity",
        new=AsyncMock(return_value=1),
    ) as cc:
        result = await node(_state(query), config={})

    cc.assert_awaited_once()
    # step_count < 3 → no plan generated, returns {}
    assert result == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skip_bypassed_for_actionable_verb_start():
    """Short imperatives starting with an actionable verb still reach the
    complexity check. Regression for trace where 'Add arxiv X to my library'
    short-circuited and called zero tools."""
    node = make_planner_node(tool_names=["ingest_arxiv_papers"])

    query = "Add arxiv 1706.03762 to my library"  # 6 words
    assert len(query.split()) < 12

    with patch(
        "src.services.agent.planner.check_complexity",
        new=AsyncMock(return_value=1),
    ) as cc:
        result = await node(_state(query), config={})

    cc.assert_awaited_once()
    assert result == {}  # complexity returned 1 → no plan, but heuristic
                         # did not short-circuit before the check ran.


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skip_bypassed_for_arxiv_id():
    """Queries containing an arxiv ID always reach the complexity check
    regardless of length or starting word."""
    node = make_planner_node(tool_names=["ingest_arxiv_papers"])

    query = "1706.03762 please"
    with patch(
        "src.services.agent.planner.check_complexity",
        new=AsyncMock(return_value=1),
    ) as cc:
        result = await node(_state(query), config={})

    cc.assert_awaited_once()
    assert result == {}


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "Hello!",
        "Thanks for your help!",
        "What can you do?",
        "yes",
        "no thanks",
    ],
    ids=["greeting", "thanks", "capability", "yes", "no_thanks"],
)
async def test_skip_preserved_for_conversational(query: str) -> None:
    """Conversational/greeting queries keep skipping — bypass must not regress."""
    node = make_planner_node(tool_names=["search_arxiv"])

    with patch(
        "src.services.agent.planner.check_complexity",
        new=AsyncMock(side_effect=AssertionError("complexity should be skipped")),
    ):
        result = await node(_state(query), config={})

    assert result == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skip_in_chat_mode_no_project():
    """Phase 7.4: planner skips entirely when no project context is active.

    Plans only matter when the agent will execute a multi-step ingest +
    add-to-project flow. In chat mode the plan is never followed, so
    generating one wastes a complexity LLM call.
    """
    node = make_planner_node(tool_names=["search_arxiv"])
    chat_state = {
        "messages": [
            HumanMessage(
                content=(
                    "Find recent transformer papers, ingest them, and "
                    "summarize each for me carefully please now"
                )
            )
        ],
        "page_context": {"type": "chat", "project_id": None},
    }
    with patch(
        "src.services.agent.planner.check_complexity",
        new=AsyncMock(side_effect=AssertionError("complexity should be skipped")),
    ):
        result = await node(chat_state, config={})

    assert result == {}
