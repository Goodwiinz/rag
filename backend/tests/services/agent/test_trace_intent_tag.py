"""Tests for tag_trace_intent in observability.py.

It patches the ROOT run (identified by RunTree.trace_id) directly via
Client.update_run(run_id=trace_id, tags=[...]) — the RunTree-walk + add_tags
approach didn't land under astream_events. In a sync test there is no running
loop, so the fire-and-forget path falls back to the inline patch and we can
assert synchronously.

Covers:
- No-op when get_current_run_tree() returns None.
- No-op when intent is empty.
- The root run (trace_id) is patched with the intent tag.
- Only tags are patched (tenant metadata in `extra` is never touched).
- Never raises when the client errors.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.services.agent.observability import tag_trace_intent


def _fake_rt(trace_id: str = "root-trace-id") -> SimpleNamespace:
    # Current node run tree; trace_id == the root run's id.
    return SimpleNamespace(id="node-id", trace_id=trace_id)


def test_noop_when_no_run_tree() -> None:
    """No active run context → no patch, no raise."""
    client = MagicMock()
    with (
        patch("langsmith.run_helpers.get_current_run_tree", return_value=None),
        patch("src.services.agent.observability._get_ls_client", return_value=client),
    ):
        tag_trace_intent("research")
    client.update_run.assert_not_called()


def test_noop_when_intent_empty() -> None:
    """Empty intent short-circuits before any SDK access."""
    client = MagicMock()
    with patch("src.services.agent.observability._get_ls_client", return_value=client):
        tag_trace_intent("")
    client.update_run.assert_not_called()


def test_patches_root_run_by_trace_id_with_intent_tag() -> None:
    """The root run (trace_id) is patched with the intent tag."""
    client = MagicMock()
    with (
        patch(
            "langsmith.run_helpers.get_current_run_tree",
            return_value=_fake_rt("root-trace-id"),
        ),
        patch("src.services.agent.observability._get_ls_client", return_value=client),
    ):
        tag_trace_intent("research")

    client.update_run.assert_called_once()
    _args, kwargs = client.update_run.call_args
    assert kwargs.get("run_id") == "root-trace-id" or (
        _args and _args[0] == "root-trace-id"
    )
    assert kwargs.get("tags") == ["intent:research"]
    # Must NOT patch extra/metadata (would clobber tenant metadata on the root).
    assert "extra" not in kwargs


def test_noop_when_no_trace_id() -> None:
    """A run tree without a trace_id can't identify the root → no patch."""
    client = MagicMock()
    rt = SimpleNamespace(id="node-id", trace_id=None)
    with (
        patch("langsmith.run_helpers.get_current_run_tree", return_value=rt),
        patch("src.services.agent.observability._get_ls_client", return_value=client),
    ):
        tag_trace_intent("writing")
    client.update_run.assert_not_called()


def test_never_raises_on_client_error() -> None:
    """A failing update_run must be swallowed — observability never breaks the agent."""
    client = MagicMock()
    client.update_run.side_effect = RuntimeError("boom")
    with (
        patch(
            "langsmith.run_helpers.get_current_run_tree",
            return_value=_fake_rt(),
        ),
        patch("src.services.agent.observability._get_ls_client", return_value=client),
    ):
        # Should not raise.
        tag_trace_intent("data")
