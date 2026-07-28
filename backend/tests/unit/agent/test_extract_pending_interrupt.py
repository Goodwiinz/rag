"""Unit tests for jobs.py's `_extract_pending_interrupt`.

Proves the fix for the bug found in a LangSmith trace audit (2026-07-01,
see test_interrupt_ainvoke_semantics.py): `run_agent_graph` and
`resume_agent_graph` relied only on `except GraphInterrupt` around
`ainvoke()`, which never fires with a checkpointer attached. This is the
shared helper both now call against `graph.aget_state(config)` — the same
`snapshot.tasks[*].interrupts` signal streaming.py's SSE path already uses.

No langgraph import needed: the helper only touches `.tasks` and
`.interrupts`/`.value` via getattr, so plain stand-ins are enough to pin its
contract without a live graph.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services.agent.agent_execution_service import _extract_pending_interrupt

pytestmark = pytest.mark.unit


def _snapshot(tasks):
    return SimpleNamespace(tasks=tasks)


def test_no_snapshot_returns_none():
    assert _extract_pending_interrupt(None) is None


def test_no_tasks_returns_none():
    assert _extract_pending_interrupt(_snapshot(())) is None


def test_task_without_interrupts_attr_returns_none():
    task = SimpleNamespace()  # no `.interrupts` at all
    assert _extract_pending_interrupt(_snapshot((task,))) is None


def test_task_with_empty_interrupts_returns_none():
    task = SimpleNamespace(interrupts=())
    assert _extract_pending_interrupt(_snapshot((task,))) is None


def test_pending_interrupt_returns_its_value():
    intr = SimpleNamespace(value={"tool": "create_project", "args": {"name": "x"}})
    task = SimpleNamespace(interrupts=(intr,))
    result = _extract_pending_interrupt(_snapshot((task,)))
    assert result == {"tool": "create_project", "args": {"name": "x"}}


def test_interrupt_with_falsy_value_returns_empty_dict_not_none():
    """A falsy `.value` must still short-circuit the caller as "interrupted",
    so the helper normalizes it to `{}` rather than None — the caller
    branches on `is not None`, not truthiness."""
    intr = SimpleNamespace(value=None)
    task = SimpleNamespace(interrupts=(intr,))
    result = _extract_pending_interrupt(_snapshot((task,)))
    assert result == {}
    assert result is not None
