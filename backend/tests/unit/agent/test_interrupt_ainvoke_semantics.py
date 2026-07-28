"""Proves how LangGraph surfaces `interrupt()` after `ainvoke()` returns.

Three agent-facing code paths need to detect a paused-for-confirmation graph:
- `streaming.py` (SSE `/stream`) — after `astream_events()` completes, calls
  `graph.aget_state(config)` and checks `snapshot.tasks[*].interrupts`. This is
  the PRIMARY, correct mechanism; `except GraphInterrupt` around the stream is
  a secondary defensive catch (verifies checkpoint persistence in the rare case
  the exception does fire), not the thing HITL confirmations actually rely on.
- `jobs.py:run_agent_graph` (`/execute`) and `scripts/synthetic_traffic.py`
  call plain `graph.ainvoke()` wrapped ONLY in `except GraphInterrupt`, with no
  state-based fallback.

A LangSmith trace audit (2026-07-01) of synthetic-traffic runs found the
`create_project`/`ingest` scenarios (the only two `expect_interrupt=True`
scenarios) never trip that `except GraphInterrupt` — `resumes` stayed 0 across
every sampled run — even though the LLM emitted a real destructive tool_call
and `interrupt_node` ran `interrupt()` as the terminal node (confirmed: no
`tool_node` ran afterward in that same turn, so the destructive tool never
executed — this fails SAFE, it just never surfaces the confirmation prompt).

This test proves why with a minimal, isolated graph (no app code, no DB, no
LLM, no network): `ainvoke()` on an interrupted graph returns NORMALLY with
`__interrupt__` in the returned state dict — `GraphInterrupt` is not raised to
the caller. `except GraphInterrupt` around a plain `ainvoke()` call is dead
code for this graph/LangGraph-version combination; the reliable detection is
checking the returned state directly (or `aget_state`, as streaming.py does).
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Interrupt, interrupt
from typing_extensions import TypedDict

pytestmark = pytest.mark.unit


class _State(TypedDict, total=False):
    confirmed: bool


def _pause_node(state: _State) -> dict:
    response = interrupt({"message": "confirm?"})
    return {"confirmed": bool(response and response.get("confirmed"))}


def _build_graph():
    g = StateGraph(_State)
    g.add_node("pause", _pause_node)
    g.add_edge(START, "pause")
    g.add_edge("pause", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_ainvoke_returns_interrupt_in_state_without_raising():
    """The scenario every ainvoke()-based caller in this codebase hits."""
    graph = _build_graph()
    config = {"configurable": {"thread_id": "t-1"}}

    # No exception — `except GraphInterrupt` around this call never fires.
    final_state = await graph.ainvoke({}, config=config)

    assert "__interrupt__" in final_state
    interrupts = final_state["__interrupt__"]
    assert len(interrupts) == 1
    assert isinstance(interrupts[0], Interrupt)
    assert interrupts[0].value == {"message": "confirm?"}

    # Resuming via the state-returned interrupt works correctly — this part of
    # jobs.py / synthetic_traffic.py's existing resume logic is fine; only the
    # initial detection (the except block) is the gap.
    resumed = await graph.ainvoke(Command(resume={"confirmed": True}), config=config)
    assert "__interrupt__" not in resumed
    assert resumed["confirmed"] is True


@pytest.mark.asyncio
async def test_aget_state_also_surfaces_the_pending_interrupt():
    """Mirrors streaming.py's actual (correct) detection mechanism: after
    astream_events() consumes to completion with no exception, it calls
    aget_state(config) and checks snapshot.tasks[*].interrupts — this is the
    real primary path real users' HITL confirmations go through."""
    graph = _build_graph()
    config = {"configurable": {"thread_id": "t-2"}}

    await graph.ainvoke({}, config=config)

    snapshot = await graph.aget_state(config)
    pending_tasks = snapshot.tasks if snapshot else ()
    has_interrupt = any(getattr(t, "interrupts", None) for t in pending_tasks)
    assert has_interrupt is True

    confirmation_details = {}
    for task in pending_tasks:
        for intr in getattr(task, "interrupts", []):
            confirmation_details = intr.value
            break
    assert confirmation_details == {"message": "confirm?"}
