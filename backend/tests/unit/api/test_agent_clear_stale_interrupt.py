"""Unit tests for ``_clear_stale_pending_confirmation`` in jobs.py.

When the CLI's ``/new`` (or any abandoned interrupt) leaves a thread with a
live HITL interrupt in the LangGraph checkpoint, the next fresh
``HumanMessage`` would otherwise re-fire the old interrupt and block the turn.
The helper detects that case and wipes the pending state.

Liveness is signalled by a pending task carrying ``.interrupts`` — NOT by the
stored ``pending_confirmation`` value, which is only ever written back as
``{}``. The fixture below models those two axes **independently** so a
regression to the old inverted ``if not pending_confirmation`` predicate
cannot hide behind a fixture that conflates them.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.agent.jobs import _clear_stale_pending_confirmation


def _make_graph(
    *,
    has_interrupt: bool,
    pending_confirmation: dict | None = None,
    raise_on_get: bool = False,
    raise_on_update: bool = False,
) -> MagicMock:
    """Build a graph mock with a configurable checkpoint snapshot.

    ``has_interrupt`` controls the only signal the helper is allowed to key off:
    a pending task carrying ``.interrupts``. ``pending_confirmation`` is modelled
    separately (default falsy ``{}``) precisely so a test can assert it does NOT
    drive the decision — set it truthy with ``has_interrupt=False`` to prove the
    inverted predicate stays dead.
    """
    snapshot = MagicMock()
    snapshot.values = {"pending_confirmation": pending_confirmation or {}}
    snapshot.tasks = (
        (SimpleNamespace(interrupts=[SimpleNamespace(value={})]),)
        if has_interrupt
        else ()
    )
    graph = MagicMock()
    if raise_on_get:
        graph.aget_state = AsyncMock(side_effect=RuntimeError("checkpointer down"))
    else:
        graph.aget_state = AsyncMock(return_value=snapshot)
    if raise_on_update:
        graph.aupdate_state = AsyncMock(side_effect=RuntimeError("update failed"))
    else:
        graph.aupdate_state = AsyncMock(return_value=None)
    return graph


@pytest.mark.unit
@pytest.mark.asyncio
class TestClearStalePendingConfirmation:
    async def test_clears_when_live_interrupt_present(self) -> None:
        graph = _make_graph(has_interrupt=True)
        config = {"configurable": {"thread_id": "abandoned-thread"}}

        cleared = await _clear_stale_pending_confirmation(graph, config)

        assert cleared is True
        graph.aupdate_state.assert_awaited_once_with(
            config,
            {
                "pending_confirmation": {},
                "user_confirmed": False,
                "tool_loop_count": 0,
                "error_count": 0,
                "reflection_count": 0,
            },
        )

    async def test_noop_when_no_live_interrupt(self) -> None:
        graph = _make_graph(has_interrupt=False)
        config = {"configurable": {"thread_id": "fresh-thread"}}

        cleared = await _clear_stale_pending_confirmation(graph, config)

        assert cleared is False
        graph.aupdate_state.assert_not_called()

    async def test_noop_when_pending_value_set_but_no_live_interrupt(self) -> None:
        """Regression guard for the inverted predicate.

        A truthy ``pending_confirmation`` with NO live interrupt must be a no-op:
        the decision keys off ``snapshot.tasks[].interrupts``, never the stored
        value. The old ``if not pending_confirmation`` predicate would (wrongly)
        proceed to clear here and fail this test.
        """
        graph = _make_graph(
            has_interrupt=False,
            pending_confirmation={"pending_tools": ["create_project_note"]},
        )
        config = {"configurable": {"thread_id": "stale-value-no-interrupt"}}

        cleared = await _clear_stale_pending_confirmation(graph, config)

        assert cleared is False
        graph.aupdate_state.assert_not_called()

    async def test_noop_when_snapshot_has_no_values(self) -> None:
        graph = MagicMock()
        empty_snapshot = MagicMock()
        empty_snapshot.values = None
        graph.aget_state = AsyncMock(return_value=empty_snapshot)
        graph.aupdate_state = AsyncMock()

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "new"}}
        )

        assert cleared is False
        graph.aupdate_state.assert_not_called()

    async def test_noop_when_snapshot_is_none(self) -> None:
        graph = MagicMock()
        graph.aget_state = AsyncMock(return_value=None)
        graph.aupdate_state = AsyncMock()

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "new"}}
        )

        assert cleared is False
        graph.aupdate_state.assert_not_called()

    async def test_swallows_aget_state_errors(self) -> None:
        graph = _make_graph(has_interrupt=True, raise_on_get=True)

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "broken"}}
        )

        assert cleared is False
        graph.aupdate_state.assert_not_called()

    async def test_swallows_aupdate_state_errors(self) -> None:
        # has_interrupt=True so the liveness check passes and execution reaches
        # aupdate_state — otherwise the update-error path would never be exercised.
        graph = _make_graph(has_interrupt=True, raise_on_update=True)

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "broken"}}
        )

        # Update raised, so the helper reports failure rather than falsely
        # claiming success — but it must not propagate the exception.
        assert cleared is False
