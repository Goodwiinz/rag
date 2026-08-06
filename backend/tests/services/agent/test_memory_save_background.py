"""Verify that memory_save_node dispatches slow persistence off the critical path.

memory_save_node must return in well under 5 s even when save_memory (embed+PG)
and extract_insights (LLM) are slow, and the background task must eventually
complete. Gate-skip turns must dispatch NO background task.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent._nodes_memory import _BACKGROUND_TASKS, memory_save_node

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLOW_DELAY = 5  # seconds — slow enough that inline execution would be obvious


def _user() -> MagicMock:
    u = MagicMock()
    u.id = "user-bg-test"
    return u


def _config(thread_id: str = "thread-bg") -> dict:
    return {
        "configurable": {
            "current_user": _user(),
            "thread_id": thread_id,
        }
    }


def _tool_bearing_state() -> dict:
    """State that PASSES the save gate: research intent + tool executed."""
    return {
        "messages": [
            HumanMessage(content="find papers on diffusion models"),
            AIMessage(content="Here are 5 relevant papers…"),
        ],
        "intent": "research",
        "tool_executions": [{"tool_name": "search_arxiv", "status": "completed"}],
    }


def _general_no_tool_state() -> dict:
    """State that FAILS the save gate: general intent, no tools."""
    return {
        "messages": [
            HumanMessage(content="hi there"),
            AIMessage(content="Hello! How can I help?"),
        ],
        "intent": "general",
        "tool_executions": [],
    }


# ---------------------------------------------------------------------------
# Test 1 — node returns quickly; background task eventually runs
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_save_returns_before_slow_save_completes() -> None:
    """memory_save_node must NOT block on the 5-second save_memory stub.

    The drain (asyncio.gather) is performed INSIDE the patch context so the
    mocks are still active when the background coroutine actually executes.
    """
    ran: list[bool] = []
    store = MagicMock()

    async def slow_save(*args, **kwargs) -> None:  # type: ignore[misc]
        await asyncio.sleep(_SLOW_DELAY)
        ran.append(True)

    with (
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=store),
        ),
        patch(
            "src.services.agent.memory.save_memory",
            new=slow_save,
        ),
        patch(
            "src.services.agent.iteration_ledger.write_iteration",
        ),
    ):
        start = time.monotonic()
        result = await memory_save_node(_tool_bearing_state(), _config())
        elapsed = time.monotonic() - start

        # Node must return well before the 5-second stub would complete.
        assert (
            elapsed < 1.0
        ), f"memory_save_node blocked for {elapsed:.2f}s (expected < 1s)"
        # State shape is unchanged — node still returns {}.
        assert result == {}
        # save_memory has NOT run yet (it's in a background task).
        assert not ran, "save_memory ran synchronously — backgrounding did not work"

        # Now drain the background task while patches are still active.
        if _BACKGROUND_TASKS:
            await asyncio.gather(*list(_BACKGROUND_TASKS), return_exceptions=True)

    # After drain, save_memory should have been called by the background task.
    assert ran, "save_memory was never called by the background task"


# ---------------------------------------------------------------------------
# Test 2 — save-gate skip dispatches NO background task
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gate_skip_dispatches_no_background_task() -> None:
    """General/no-tool turns are gated out before any task is dispatched."""
    store = MagicMock()
    save_mock = AsyncMock(return_value=None)
    task_count_before = len(_BACKGROUND_TASKS)

    with (
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=store),
        ),
        patch(
            "src.services.agent.memory.save_memory",
            new=save_mock,
        ),
        patch(
            "src.services.agent.iteration_ledger.write_iteration",
        ),
    ):
        result = await memory_save_node(_general_no_tool_state(), _config())

    # Gate must fire before dispatch — no new tasks.
    assert len(_BACKGROUND_TASKS) == task_count_before
    save_mock.assert_not_called()
    assert result == {}
