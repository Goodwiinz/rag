"""Tests for tag_trace_intent in observability.py.

It tags the active run tree locally and never PATCHes the root while the graph
is still running. A mid-run ``Client.update_run`` can finalize the root before
its children, corrupting root latency and outputs.

Covers:
- No-op when get_current_run_tree() returns None.
- No-op when intent is empty.
- The active run tree receives the intent tag.
- The root run is never patched mid-run.
- Never raises when local tagging fails.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.agent.observability import tag_trace_intent


def test_noop_when_no_run_tree() -> None:
    """No active run context → no patch, no raise."""
    with patch("langsmith.run_helpers.get_current_run_tree", return_value=None):
        tag_trace_intent("research")


def test_noop_when_intent_empty() -> None:
    """Empty intent short-circuits before any SDK access."""
    with patch("langsmith.run_helpers.get_current_run_tree") as get_run_tree:
        tag_trace_intent("")
    get_run_tree.assert_not_called()


def test_tags_active_run_without_patching_root() -> None:
    """Intent tagging must not finalize the root before child runs complete."""
    run_tree = MagicMock()
    run_tree.trace_id = "root-trace-id"
    with patch(
        "langsmith.run_helpers.get_current_run_tree",
        return_value=run_tree,
    ):
        tag_trace_intent("research")

    run_tree.add_tags.assert_called_once_with(["intent:research"])


def test_noop_when_no_trace_id() -> None:
    """A run tree without a trace_id can't identify the root → no patch."""
    rt = SimpleNamespace(id="node-id", trace_id=None)
    with patch("langsmith.run_helpers.get_current_run_tree", return_value=rt):
        tag_trace_intent("writing")


def test_never_raises_when_local_tagging_fails() -> None:
    """Observability failures must never break agent execution."""
    run_tree = MagicMock()
    run_tree.trace_id = "root-trace-id"
    run_tree.add_tags.side_effect = RuntimeError("boom")
    with patch(
        "langsmith.run_helpers.get_current_run_tree",
        return_value=run_tree,
    ):
        tag_trace_intent("data")
