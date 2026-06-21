"""Regression: filtered_tool_node clears tools_all_deduped when all calls skipped.

When a subgraph LLM emits only out-of-scope tool calls, filtered_tool_node
takes an early return. It previously omitted ``tools_all_deduped``, so a stale
``True`` from a prior turn survived in the checkpointed state and
``route_after_*_tool_node`` wrongly diverted to force_synthesis instead of the
re-plan path. The early return must explicitly set it False.
"""

import pytest
from langchain_core.messages import AIMessage

from src.services.agent._nodes_tools import make_filtered_tool_node


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_skipped_calls_reset_tools_all_deduped():
    node = make_filtered_tool_node({"in_scope_tool"})

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "out_of_scope_tool", "args": {}, "id": "tc-1"}],
            )
        ],
        # Stale value left by a previous turn.
        "tools_all_deduped": True,
        "tool_executions": [],
        "tool_loop_count": 0,
    }

    result = await node(state, {})

    # Early return fired (no allowed calls) and the stale flag is cleared.
    assert result["tools_all_deduped"] is False
    assert result["tool_loop_count"] == 1
