"""Invariant guard for the langgraph control-flow exception hierarchy.

PR #800 fixed the agent node wrapper to treat GraphInterrupt (HITL confirm)
as control flow by catching ``GraphBubbleUp`` — the parent of both
``GraphInterrupt`` and ``ParentCommand``. If a future langgraph release moves
GraphInterrupt out from under GraphBubbleUp, the wrapper would silently start
logging HITL interrupts as ERROR again (and bumping AGENT_ERRORS). This test
fails loudly if that hierarchy assumption breaks, and confirms the wrapper's
``_CONTROL_FLOW_EXC`` still matches a real GraphInterrupt.
"""

import pytest

from src.services.agent.observability import _CONTROL_FLOW_EXC


@pytest.mark.unit
def test_graphinterrupt_subclasses_graphbubbleup():
    from langgraph.errors import GraphBubbleUp, GraphInterrupt, ParentCommand

    assert issubclass(GraphInterrupt, GraphBubbleUp)
    assert issubclass(ParentCommand, GraphBubbleUp)


@pytest.mark.unit
def test_control_flow_exc_is_populated_and_matches_graphinterrupt():
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Interrupt

    # Guard against the import-guarded fallback silently degrading to () in the
    # app runtime (langgraph is always present there).
    assert (
        _CONTROL_FLOW_EXC
    ), "_CONTROL_FLOW_EXC must be non-empty when langgraph is installed"

    exc = GraphInterrupt((Interrupt(value={"m": "x"}, id="i"),))
    assert isinstance(exc, _CONTROL_FLOW_EXC)
