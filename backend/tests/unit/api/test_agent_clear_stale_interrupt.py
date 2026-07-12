"""Unit tests for ``_clear_stale_pending_confirmation`` in jobs.py.

When the CLI's ``/new`` (or any abandoned interrupt) leaves a thread with a
populated ``pending_confirmation`` in the LangGraph checkpoint, the next
fresh ``HumanMessage`` would otherwise re-fire the old interrupt and block
the turn. The helper detects that case and wipes the pending state.

Since the return type changed from ``bool`` to ``Optional[list[str]]``:
- truthy checks still work (non-empty list is truthy)
- None replaces False for "nothing to clear" / error paths
- a list of tool names is returned when state is cleared
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agent.agent_execution_service import _clear_stale_pending_confirmation


def _make_graph(
    pending: dict | None,
    *,
    raise_on_get: bool = False,
    raise_on_update: bool = False,
    interrupt_value: dict | None = None,
) -> MagicMock:
    """Build a graph mock with a configurable checkpoint snapshot.

    A live interrupt is signalled by a pending task carrying `.interrupts`
    (`pending_confirmation` is always `{}` while live) — modelled here as
    present whenever ``pending`` is truthy, matching the original tests' intent.

    ``interrupt_value`` lets tests inject a specific interrupt payload shape,
    e.g. ``{"tools": [{"name": "create_project"}]}``.
    """
    iv = interrupt_value if interrupt_value is not None else {}
    snapshot = MagicMock()
    snapshot.values = {"pending_confirmation": pending or {}}
    snapshot.tasks = (
        (SimpleNamespace(interrupts=[SimpleNamespace(value=iv)]),) if pending else ()
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
    async def test_clears_when_pending_confirmation_present(self) -> None:
        graph = _make_graph({"pending_tools": ["create_project_note"]})
        config = {"configurable": {"thread_id": "abandoned-thread"}}

        cleared = await _clear_stale_pending_confirmation(graph, config)

        # Returns a non-empty list (truthy) — wipe happened.
        assert cleared  # truthy: list with at least one entry
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

    async def test_noop_when_pending_confirmation_empty(self) -> None:
        graph = _make_graph({})
        config = {"configurable": {"thread_id": "fresh-thread"}}

        cleared = await _clear_stale_pending_confirmation(graph, config)

        assert cleared is None
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

        assert cleared is None
        graph.aupdate_state.assert_not_called()

    async def test_noop_when_snapshot_is_none(self) -> None:
        graph = MagicMock()
        graph.aget_state = AsyncMock(return_value=None)
        graph.aupdate_state = AsyncMock()

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "new"}}
        )

        assert cleared is None
        graph.aupdate_state.assert_not_called()

    async def test_swallows_aget_state_errors(self) -> None:
        graph = _make_graph({"x": 1}, raise_on_get=True)

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "broken"}}
        )

        assert cleared is None
        graph.aupdate_state.assert_not_called()

    async def test_swallows_aupdate_state_errors(self) -> None:
        graph = _make_graph({"x": 1}, raise_on_update=True)

        cleared = await _clear_stale_pending_confirmation(
            graph, {"configurable": {"thread_id": "broken"}}
        )

        # Update raised, so the helper reports failure rather than falsely
        # claiming success — but it must not propagate the exception.
        assert cleared is None

    # ------------------------------------------------------------------
    # Observability: dropped tool names + WARNING log
    # ------------------------------------------------------------------

    async def test_returns_tool_names_and_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Interrupt with a tools list → tool names returned + WARNING logged."""
        iv = {"tools": [{"name": "create_project"}], "message": "confirm?"}
        graph = _make_graph({"some": "data"}, interrupt_value=iv)
        config = {"configurable": {"thread_id": "t-obs-001"}}

        import logging

        with caplog.at_level(logging.WARNING, logger="src.services.agent.agent_execution_service"):
            result = await _clear_stale_pending_confirmation(graph, config)

        # Returned list contains the tool name.
        assert result == ["create_project"]

        # aupdate_state was called (the wipe still ran).
        graph.aupdate_state.assert_awaited_once()

        # A WARNING was emitted that names the tool and the thread.
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warning_records, "Expected at least one WARNING log record"
        combined = " ".join(r.getMessage() for r in warning_records)
        assert "create_project" in combined
        assert "t-obs-001" in combined

    async def test_no_interrupt_returns_none_no_update(self) -> None:
        """No interrupt in tasks → returns None, aupdate_state never called."""
        graph = _make_graph(None)  # empty tasks
        config = {"configurable": {"thread_id": "t-clean-001"}}

        result = await _clear_stale_pending_confirmation(graph, config)

        assert result is None
        graph.aupdate_state.assert_not_called()
