"""Phase 6 — per-turn tool-call dedupe helper.

Covers canonical key derivation and turn-scoped cache lookup.
Reference trace: 019e18f0 (13+ search_arxiv repeats in one turn).
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.services.agent.tool_dedupe import (
    build_deduped_execution_entry,
    build_deduped_tool_message,
    dedupe_key,
    find_cached_tool_results,
)


@pytest.mark.unit
def test_dedupe_key_stable_across_arg_order():
    a = dedupe_key("search_arxiv", {"query": "transformers", "max_results": 5})
    b = dedupe_key("search_arxiv", {"max_results": 5, "query": "transformers"})
    assert a == b


@pytest.mark.unit
def test_dedupe_key_drops_none_values():
    a = dedupe_key("search_arxiv", {"query": "x", "categories": None})
    b = dedupe_key("search_arxiv", {"query": "x"})
    assert a == b


@pytest.mark.unit
def test_dedupe_key_strips_whitespace_in_strings():
    a = dedupe_key("search_arxiv", {"query": "transformers"})
    b = dedupe_key("search_arxiv", {"query": "  transformers  "})
    assert a == b


@pytest.mark.unit
def test_dedupe_key_distinct_tools_distinct_keys():
    assert dedupe_key("search_arxiv", {"q": "x"}) != dedupe_key(
        "search_documents", {"q": "x"}
    )


@pytest.mark.unit
def test_dedupe_key_distinct_args_distinct_keys():
    assert dedupe_key("search_arxiv", {"query": "a"}) != dedupe_key(
        "search_arxiv", {"query": "b"}
    )


def _execution(tc_id: str, name: str, args: dict, status: str = "completed") -> dict:
    return {
        "id": tc_id,
        "tool_name": name,
        "tool_display_name": name.replace("_", " ").title(),
        "args": args,
        "status": status,
        "result": {"papers": []},
        "duration_ms": 12,
    }


@pytest.mark.unit
def test_find_cached_in_same_turn():
    """Repeat call within the same turn → cache hit."""
    messages = [
        HumanMessage(content="Find transformer papers"),
        AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "search_arxiv", "args": {"query": "t"}}],
        ),
        ToolMessage(content="result1", tool_call_id="call_1"),
    ]
    tool_executions = [_execution("call_1", "search_arxiv", {"query": "t"})]
    new_calls = [
        {"id": "call_2", "name": "search_arxiv", "args": {"query": "t"}},
    ]
    cached = find_cached_tool_results(new_calls, messages, tool_executions)
    assert "call_2" in cached
    assert cached["call_2"]["id"] == "call_1"


@pytest.mark.unit
def test_no_cache_across_turn_boundary():
    """A new HumanMessage resets the turn — prior executions don't count."""
    messages = [
        HumanMessage(content="first turn"),
        AIMessage(
            content="",
            tool_calls=[{"id": "old", "name": "search_arxiv", "args": {"query": "t"}}],
        ),
        ToolMessage(content="r", tool_call_id="old"),
        AIMessage(content="done"),
        HumanMessage(content="second turn"),
    ]
    tool_executions = [_execution("old", "search_arxiv", {"query": "t"})]
    new_calls = [
        {"id": "fresh", "name": "search_arxiv", "args": {"query": "t"}},
    ]
    cached = find_cached_tool_results(new_calls, messages, tool_executions)
    assert cached == {}


@pytest.mark.unit
def test_different_args_no_hit():
    messages = [
        HumanMessage(content="q"),
        AIMessage(
            content="",
            tool_calls=[{"id": "a", "name": "search_arxiv", "args": {"query": "x"}}],
        ),
        ToolMessage(content="r", tool_call_id="a"),
    ]
    tool_executions = [_execution("a", "search_arxiv", {"query": "x"})]
    new_calls = [{"id": "b", "name": "search_arxiv", "args": {"query": "y"}}]
    assert find_cached_tool_results(new_calls, messages, tool_executions) == {}


@pytest.mark.unit
def test_failed_executions_not_cached():
    """A failed tool execution must remain retryable.

    Trace 019e1910 showed arxiv search hang for 93s and return a transient
    error. The agent's retry hit the cached failure → no recovery path.
    Only ``status="completed"`` entries should be cached.
    """
    messages = [
        HumanMessage(content="q"),
        AIMessage(
            content="",
            tool_calls=[{"id": "a", "name": "search_arxiv", "args": {"q": "x"}}],
        ),
        ToolMessage(content='{"error":"transient"}', tool_call_id="a"),
    ]
    tool_executions = [_execution("a", "search_arxiv", {"q": "x"}, status="failed")]
    new_calls = [{"id": "b", "name": "search_arxiv", "args": {"q": "x"}}]
    assert find_cached_tool_results(new_calls, messages, tool_executions) == {}


@pytest.mark.unit
def test_dedupe_does_not_chain_through_deduped_entries():
    """A deduped execution shouldn't be the cite-target for a third repeat."""
    messages = [
        HumanMessage(content="q"),
        AIMessage(
            content="",
            tool_calls=[{"id": "a", "name": "search_arxiv", "args": {"q": "x"}}],
        ),
        ToolMessage(content="r", tool_call_id="a"),
        AIMessage(
            content="",
            tool_calls=[{"id": "b", "name": "search_arxiv", "args": {"q": "x"}}],
        ),
        ToolMessage(content="dedup", tool_call_id="b"),
    ]
    tool_executions = [
        _execution("a", "search_arxiv", {"q": "x"}),
        _execution("b", "search_arxiv", {"q": "x"}, status="deduped"),
    ]
    new_calls = [{"id": "c", "name": "search_arxiv", "args": {"q": "x"}}]
    cached = find_cached_tool_results(new_calls, messages, tool_executions)
    assert cached["c"]["id"] == "a"


@pytest.mark.unit
def test_build_deduped_tool_message_includes_prefix_and_payload():
    cached = _execution("prev_id", "search_arxiv", {"q": "x"})
    msg = build_deduped_tool_message("new_id", cached)
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "new_id"
    assert msg.content.startswith("[deduped: same args as call prev_id]")
    assert "papers" in msg.content


@pytest.mark.unit
def test_build_deduped_execution_entry_shape():
    cached = _execution("prev_id", "search_arxiv", {"q": "x"})
    tc = {"id": "new_id", "name": "search_arxiv", "args": {"q": "x"}}
    entry = build_deduped_execution_entry("new_id", tc, cached)
    assert entry["id"] == "new_id"
    assert entry["status"] == "deduped"
    assert entry["duration_ms"] == 0
    assert entry["deduped_from"] == "prev_id"
    assert entry["tool_name"] == "search_arxiv"


@pytest.mark.unit
def test_short_circuits_on_empty_tool_calls():
    """Defensive: no tool_calls in the latest AIMessage → return {} fast,
    skipping turn-boundary walk and execution scan entirely."""
    messages = [
        HumanMessage(content="q"),
        AIMessage(
            content="",
            tool_calls=[{"id": "a", "name": "search_arxiv", "args": {"q": "x"}}],
        ),
        ToolMessage(content="r", tool_call_id="a"),
    ]
    tool_executions = [_execution("a", "search_arxiv", {"q": "x"})]
    assert find_cached_tool_results([], messages, tool_executions) == {}


@pytest.mark.unit
def test_lookup_bounded_when_executions_exceed_budget():
    """Pathological case: 100 completed in-turn executions get tail-clipped
    to the recent _CACHE_LOOKUP_BUDGET so dedupe_key runs at most that many
    times. Matches inside the recent window still cache; matches older than
    the cap are intentionally NOT consulted."""
    from src.services.agent.tool_dedupe import _CACHE_LOOKUP_BUDGET

    n = 100
    assert n > _CACHE_LOOKUP_BUDGET

    messages: list = [HumanMessage(content="q")]
    tool_executions: list[dict] = []
    for i in range(n):
        tc_id = f"call_{i}"
        # Every execution has a UNIQUE query so the only way a new tc
        # matches is to share args with a specific historical entry.
        args = {"query": f"q_{i}"}
        messages.append(
            AIMessage(
                content="",
                tool_calls=[{"id": tc_id, "name": "search_arxiv", "args": args}],
            )
        )
        messages.append(ToolMessage(content="ok", tool_call_id=tc_id))
        tool_executions.append(_execution(tc_id, "search_arxiv", args))

    # Match inside the recent-50 window (e.g. index 99 — the last entry).
    recent_match_args = {"query": "q_99"}
    # Match older than the cap (e.g. index 0 — the very first entry).
    old_match_args = {"query": "q_0"}

    new_calls = [
        {"id": "new_recent", "name": "search_arxiv", "args": recent_match_args},
        {"id": "new_old", "name": "search_arxiv", "args": old_match_args},
    ]
    cached = find_cached_tool_results(new_calls, messages, tool_executions)

    # Recent match cached; old match (beyond budget) not consulted.
    assert "new_recent" in cached
    assert cached["new_recent"]["id"] == "call_99"
    assert "new_old" not in cached
