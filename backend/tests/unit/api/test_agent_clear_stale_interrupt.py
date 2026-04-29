"""Unit tests for ``_clear_stale_pending_confirmation`` in jobs.py.

When the CLI's ``/new`` (or any abandoned interrupt) leaves a thread with a
populated ``pending_confirmation`` in the LangGraph checkpoint, the next
fresh ``HumanMessage`` would otherwise re-fire the old interrupt and block
the turn. The helper detects that case and wipes the pending state.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.agent.jobs import _clear_stale_pending_confirmation


def _make_graph(pending: dict | None, *, raise_on_get: bool = False, raise_on_update: bool = False) -> MagicMock:
    """Build a graph mock with a configurable checkpoint snapshot."""
    snapshot = MagicMock()
    snapshot.values = {"pending_confirmation": pending or {}}
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
    async def test_clears_when_pending_confirmation_present(self) -> None:
        graph = _make_graph({"pending_tools": ["create_project_note"]})
        config = {"configurable": {"thread_id": "abandoned-thread"}}

        cleared = await _clear_stale_pending_confirmation(graph, config)

        assert cleared is True
        graph.aupdate_state.assert_awaited_once_with(
            config,
            {"pending_confirmation": {}, "user_confirmed": False},
        )

    async def test_noop_when_pending_confirmation_empty(self) -> None:
        graph = _make_graph({})
        config = {"configurable": {"thread_id": "fresh-thread"}}

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
        graph = _make_graph({"x": 1}, raise_on_get=True)

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "broken"}}
        )

        assert cleared is False
        graph.aupdate_state.assert_not_called()

    async def test_swallows_aupdate_state_errors(self) -> None:
        graph = _make_graph({"x": 1}, raise_on_update=True)

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "broken"}}
        )

        # Update raised, so the helper reports failure rather than falsely
        # claiming success — but it must not propagate the exception.
        assert cleared is False
