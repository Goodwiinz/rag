"""Phase 5 regression — consecutive HumanMessages collapse to the latest.

Trace 019e1885 showed a cancelled "Find recent transformer papers" turn
leave its HumanMessage in the checkpoint. When the user typed "hi" next,
the prior sanitizer concatenated them into one combined intent and the
LLM answered the older abandoned query. Supersession (keep latest only)
matches user mental model: the new message replaces the abandoned one.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.services.agent.graph import _sanitize_messages


@pytest.mark.unit
def test_consecutive_human_messages_keep_latest_only():
    raw = [
        HumanMessage(content="Find recent transformer papers"),
        HumanMessage(content="hi"),
    ]
    out = _sanitize_messages(raw)
    assert len(out) == 1
    assert isinstance(out[0], HumanMessage)
    assert out[0].content == "hi"


@pytest.mark.unit
def test_three_consecutive_human_messages_collapse_to_last():
    raw = [
        HumanMessage(content="first"),
        HumanMessage(content="second"),
        HumanMessage(content="third"),
    ]
    out = _sanitize_messages(raw)
    assert len(out) == 1
    assert out[0].content == "third"


@pytest.mark.unit
def test_human_then_ai_then_human_preserved():
    """Normal turn-taking is unaffected — only consecutive Humans collapse."""
    raw = [
        HumanMessage(content="hello"),
        AIMessage(content="hi back"),
        HumanMessage(content="now do X"),
    ]
    out = _sanitize_messages(raw)
    assert len(out) == 3
    assert [m.content for m in out] == ["hello", "hi back", "now do X"]


@pytest.mark.unit
def test_supersession_works_with_tool_messages_in_between():
    """A tool round-trip between two Human msgs preserves both."""
    raw = [
        HumanMessage(content="search"),
        AIMessage(
            content="",
            tool_calls=[{"id": "t1", "name": "search_arxiv", "args": {}}],
        ),
        ToolMessage(content='{"papers": []}', tool_call_id="t1"),
        AIMessage(content="found nothing"),
        HumanMessage(content="thanks"),
    ]
    out = _sanitize_messages(raw)
    # Tool round-trip + final Human kept; no collapse triggered.
    assert any(isinstance(m, ToolMessage) for m in out)
    assert out[-1].content == "thanks"
