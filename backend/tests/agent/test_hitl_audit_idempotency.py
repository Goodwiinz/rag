"""Pin the HITL audit single-write-per-decision invariant.

LangGraph replays interrupt nodes from the top on Command(resume=...):
- hitl_log_raised (pre-interrupt) re-fires on replay and must be log-only —
  it must never write the durable agent_hitl_audit row.
- record_hitl_decision (post-interrupt) runs once per decision and is the
  only path to _write_hitl_audit_row.
"""

import inspect
from unittest.mock import AsyncMock, patch

from src.services.agent import _nodes_tools
from src.services.agent._nodes_tools import (
    hitl_log_raised,
    interrupt_node,
    record_hitl_decision,
)
from src.services.agent.subgraphs.research_agent import research_interrupt_node
from src.services.agent.subgraphs.writing_agent import writing_interrupt_node

CONFIG = {
    "configurable": {
        # Ids-only configurable (audit B8); empty user_id = anonymous actor.
        "user_id": "",
        "thread_id": "thread-1",
    }
}
CALLS = [{"name": "create_note", "args": {"title": "t"}}]


def test_log_raised_replay_never_writes_audit_row():
    """Test A: the pre-interrupt log path re-fires on replay; no durable write."""
    with patch.object(_nodes_tools, "_write_hitl_audit_row", new=AsyncMock()) as mock:
        hitl_log_raised(CONFIG, CALLS)
        hitl_log_raised(CONFIG, CALLS)  # simulated node replay
    mock.assert_not_awaited()


async def test_record_decision_writes_exactly_one_approve_row():
    """Test B: confirmed=True -> exactly one durable row, decision approve."""
    with patch.object(_nodes_tools, "_write_hitl_audit_row", new=AsyncMock()) as mock:
        await record_hitl_decision(CONFIG, CALLS, confirmed=True)
    mock.assert_awaited_once()
    kwargs = mock.await_args.kwargs
    assert kwargs["confirmed"] is True
    assert kwargs["tool_names"] == ["create_note"]
    assert kwargs["thread_id"] == "thread-1"


async def test_record_decision_writes_exactly_one_reject_row():
    with patch.object(_nodes_tools, "_write_hitl_audit_row", new=AsyncMock()) as mock:
        await record_hitl_decision(CONFIG, CALLS, confirmed=False)
    mock.assert_awaited_once()
    assert mock.await_args.kwargs["confirmed"] is False


def test_audit_row_decision_mapping():
    """The confirmed flag maps to approve/reject in the row writer source."""
    src = inspect.getsource(_nodes_tools._write_hitl_audit_row)
    assert '"approve" if confirmed else "reject"' in src


def test_interrupt_nodes_record_decision_only_after_interrupt():
    """Test C: in every interrupt node, record_hitl_decision comes textually
    after the interrupt() call — i.e. only on the resume (post-decision) path.
    """
    for node in (interrupt_node, writing_interrupt_node, research_interrupt_node):
        src = inspect.getsource(node)
        assert "record_hitl_decision" in src, node.__name__
        assert src.index("record_hitl_decision(") > src.index("interrupt("), (
            f"{node.__name__}: audit write moved before interrupt() — "
            "it would re-fire on every LangGraph replay"
        )
        # And the log-only helper is the only thing before the interrupt.
        assert src.index("hitl_log_raised(") < src.index("interrupt("), node.__name__
