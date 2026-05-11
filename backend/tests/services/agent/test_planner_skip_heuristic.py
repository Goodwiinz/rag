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
        "page_context": {},
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
