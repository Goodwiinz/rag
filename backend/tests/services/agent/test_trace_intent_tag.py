"""Tests for tag_trace_intent in observability.py.

It tags the active run tree locally and never PATCHes the root while the graph
is still running. A mid-run ``Client.update_run`` can finalize the root before
its children, corrupting root latency and outputs.

Covers:
- No-op when get_current_run_tree() returns None.
- No-op when intent is empty.
- The trace root receives the intent tag.
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


def test_tags_trace_root_without_patching_root() -> None:
    """Intent tags must land on the root before it naturally closes."""
    root = MagicMock()
    root.trace_id = "root-trace-id"
    root.parent_run = None
    run_tree = MagicMock(parent_run=root)
    run_tree.trace_id = root.trace_id
    with patch(
        "langsmith.run_helpers.get_current_run_tree",
        return_value=run_tree,
    ):
        tag_trace_intent("research")

    run_tree.add_tags.assert_not_called()
    root.add_tags.assert_called_once_with(["intent:research"])


def test_tags_callback_tracer_root_when_run_tree_has_only_parent_id() -> None:
    """LangSmith's child RunTree may expose only ``parent_run_id``."""
    root = MagicMock()
    child = MagicMock()
    child.trace_id = "root-trace-id"
    child.parent_run = None
    callbacks = SimpleNamespace(
        handlers=[SimpleNamespace(run_map={child.trace_id: root})]
    )
    config_var = SimpleNamespace(get=lambda: {"callbacks": callbacks})
    with (
        patch("langsmith.run_helpers.get_current_run_tree", return_value=child),
        patch(
            "langchain_core.runnables.config.var_child_runnable_config",
            config_var,
        ),
    ):
        tag_trace_intent("writing")

    child.add_tags.assert_not_called()
    root.add_tags.assert_called_once_with(["intent:writing"])


def test_noop_when_no_trace_id() -> None:
    """A run tree without a trace_id can't identify the root → no patch."""
    rt = SimpleNamespace(id="node-id", trace_id=None)
    with patch("langsmith.run_helpers.get_current_run_tree", return_value=rt):
        tag_trace_intent("writing")


def test_never_raises_when_local_tagging_fails() -> None:
    """Observability failures must never break agent execution."""
    run_tree = MagicMock()
    run_tree.trace_id = "root-trace-id"
    run_tree.parent_run = None
    run_tree.add_tags.side_effect = RuntimeError("boom")
    with patch(
        "langsmith.run_helpers.get_current_run_tree",
        return_value=run_tree,
    ):
        tag_trace_intent("data")
