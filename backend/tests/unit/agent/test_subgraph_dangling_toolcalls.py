"""Regression tests for M11 (dangling tool_calls on breaker-exit / HITL
deny) and L2 (HITL audit-row write failure logged at DEBUG, not ERROR).

M11: ``should_continue`` (subgraphs/_factory.py) routes straight to the
reflection gate when ``error_count >= 3`` -- BEFORE checking whether the
last AIMessage still carries unanswered ``tool_calls`` (the tool node
never ran for that batch). The HITL-deny branch has the same shape:
``interrupt_node_fn`` appends a cancellation AIMessage without ever
answering the pending ``tool_calls``. Both leave an OpenAI-invalid
message shape in the checkpoint: ``agent_execution_service.
_run_agent_graph``'s reversed-walk extraction (``for msg in
reversed(messages): if msg.type == "ai" and msg.content: ...``) skips
the content-less tool_calls AIMessage and falls back to a STALE prior
turn's answer, and a same-turn reflection revise-loop would hand the LLM
an invalid history.

L2: ``_write_hitl_audit_row`` swallows a failed durable "who approved
this destructive action" write at ``logger.debug`` -- invisible at
default log level.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.services.agent import _nodes_tools
from src.services.agent.reflection import ReflectionResult
from src.services.agent.subgraphs import research_agent
from src.services.agent.subgraphs.research_agent import (
    RESEARCH_DESTRUCTIVE_TOOLS,
    research_interrupt_node,
)

pytestmark = pytest.mark.unit


def _extract_last_ai_content(messages: list) -> str:
    """Verbatim copy of agent_execution_service._run_agent_graph's
    extraction walk (~lines 2280-2283), so the regression assertion below
    exercises the SAME predicate production code runs, not a stand-in."""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return msg.content
    return ""


# ---------------------------------------------------------------------------
# M11 -- HITL deny leaves last.tool_calls unanswered
# ---------------------------------------------------------------------------


async def test_deny_answers_every_pending_tool_call_before_cancellation(monkeypatch):
    """A denied destructive batch must get a ToolMessage per tool_call_id,
    all ordered before the cancellation AIMessage."""
    tool_a, tool_b = sorted(RESEARCH_DESTRUCTIVE_TOOLS)[:2]
    dangling = AIMessage(
        content="",
        tool_calls=[
            {"id": "tc-1", "name": tool_a, "args": {}},
            {"id": "tc-2", "name": tool_b, "args": {}},
        ],
    )
    state = {"messages": [HumanMessage(content="go"), dangling]}

    monkeypatch.setattr(
        "src.services.agent.subgraphs._factory.interrupt",
        lambda _payload: {"confirmed": False},
    )
    with patch.object(_nodes_tools, "_write_hitl_audit_row", new=AsyncMock()):
        result = await research_interrupt_node(state, {"configurable": {}})

    messages = result["messages"]
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert {m.tool_call_id for m in tool_messages} == {"tc-1", "tc-2"}

    cancellation_index = next(
        i
        for i, m in enumerate(messages)
        if isinstance(m, AIMessage) and "cancelled" in str(m.content).lower()
    )
    tool_message_indices = [
        i for i, m in enumerate(messages) if isinstance(m, ToolMessage)
    ]
    assert tool_message_indices, "no placeholder ToolMessages were emitted"
    assert all(i < cancellation_index for i in tool_message_indices)


# ---------------------------------------------------------------------------
# M11 -- breaker-exit (error_count >= 3) leaves last.tool_calls unanswered
# ---------------------------------------------------------------------------


async def test_breaker_exit_answers_every_pending_tool_call(monkeypatch):
    """error_count >= 3 with a trailing tool_calls AIMessage must reach the
    reflection gate with every pending call answered and a content-bearing
    final AIMessage -- the shape extraction requires."""
    monkeypatch.setattr(
        "src.services.agent.reflection.reflect_on_response",
        AsyncMock(
            return_value=ReflectionResult(passed=True, issues=[], severity="none")
        ),
    )
    dangling = AIMessage(
        content="",
        tool_calls=[
            {"id": "tc-9", "name": "search_arxiv", "args": {"query": "x"}},
            {"id": "tc-10", "name": "search_arxiv", "args": {"query": "y"}},
        ],
    )
    state = {
        "messages": [HumanMessage(content="find papers"), dangling],
        "error_count": 3,
        "intent": "research",
        "tool_executions": [],
        "reflection_count": 0,
    }

    result = await research_agent._parts.reflection_node(state, {"configurable": {}})

    messages = result.get("messages", [])
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert {m.tool_call_id for m in tool_messages} == {"tc-9", "tc-10"}
    assert (
        messages
    ), "reflection gate appended nothing for a dangling tool_calls AIMessage"
    assert isinstance(messages[-1], AIMessage)
    assert messages[
        -1
    ].content, "final message must carry content for extraction to find"


async def test_breaker_exit_extraction_finds_this_turn_not_prior_turn(monkeypatch):
    """The reversed-walk extraction predicate must land on THIS turn's
    (degraded) answer, not a stale AIMessage from an earlier turn."""
    monkeypatch.setattr(
        "src.services.agent.reflection.reflect_on_response",
        AsyncMock(
            return_value=ReflectionResult(passed=True, issues=[], severity="none")
        ),
    )
    prior_turn_answer = AIMessage(content="Here are last turn's results.")
    dangling = AIMessage(
        content="",
        tool_calls=[{"id": "tc-77", "name": "search_arxiv", "args": {}}],
    )
    history = [
        HumanMessage(content="first question"),
        prior_turn_answer,
        HumanMessage(content="second question"),
        dangling,
    ]
    state = {
        "messages": history,
        "error_count": 3,
        "intent": "research",
        "tool_executions": [],
        "reflection_count": 0,
    }

    result = await research_agent._parts.reflection_node(state, {"configurable": {}})
    appended = result.get("messages", [])
    full_history = history + appended

    extracted = _extract_last_ai_content(full_history)
    assert extracted != prior_turn_answer.content
    assert appended, "nothing appended -- extraction fell through to the prior turn"
    assert extracted == appended[-1].content


# ---------------------------------------------------------------------------
# L2 -- HITL audit-row write failure must be visible at ERROR
# ---------------------------------------------------------------------------


async def test_hitl_audit_row_failure_logs_at_error(caplog):
    with patch(
        "src.core.database.AsyncSessionLocal",
        side_effect=RuntimeError("db unavailable"),
    ):
        with caplog.at_level(logging.DEBUG, logger="src.services.agent._nodes_tools"):
            await _nodes_tools._write_hitl_audit_row(
                user_id="",
                org_id="",
                thread_id="thread-1",
                tool_names=["create_project"],
                tool_args=[{}],
                confirmed=False,
            )

    matching = [r for r in caplog.records if "hitl audit row write failed" in r.message]
    assert matching, "expected a 'hitl audit row write failed' log record"
    assert matching[0].levelno == logging.ERROR
