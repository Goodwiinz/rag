"""Tests for tag_trace_intent in observability.py.

Covers:
- No-op when get_current_run_tree() returns None.
- No-op when intent is empty.
- Tags + metadata are set on the root run when a fake RunTree is present.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.services.agent.observability import tag_trace_intent


def test_noop_when_no_run_tree() -> None:
    """tag_trace_intent must not raise when there is no active run context."""
    with patch(
        "langsmith.run_helpers.get_current_run_tree",
        return_value=None,
    ):
        # Should return without error — any exception is a bug.
        tag_trace_intent("research")


def test_noop_when_intent_empty() -> None:
    """tag_trace_intent must return immediately for an empty intent string."""
    # We do NOT patch get_current_run_tree here; if the function doesn't
    # short-circuit on the empty check it would try to import langsmith in a
    # context where the tree might not be available — an empty string is the
    # earliest possible bail-out.
    tag_trace_intent("")
    tag_trace_intent("   "[:0])  # another falsy string for completeness


def test_tags_and_metadata_set_on_root_run() -> None:
    """With a fake root RunTree, add_tags and add_metadata are called correctly."""
    added_tags: list[str] = []
    added_metadata: list[dict] = []

    # Simulate the RunTree interface used by tag_trace_intent.
    fake_root = SimpleNamespace(
        id="root-id",
        trace_id="root-id",
        tags=[],
        parent_run=None,
        add_tags=lambda tag: added_tags.append(tag),
        add_metadata=lambda meta: added_metadata.append(meta),
    )

    with patch(
        "langsmith.run_helpers.get_current_run_tree",
        return_value=fake_root,
    ):
        tag_trace_intent("research")

    assert (
        "intent:research" in added_tags
    ), f"Expected 'intent:research' in add_tags calls, got: {added_tags}"
    assert any(
        m.get("intent") == "research" for m in added_metadata
    ), f"Expected metadata with intent='research', got: {added_metadata}"


def test_tag_not_duplicated_when_already_present() -> None:
    """tag_trace_intent should not add a duplicate tag if it's already set."""
    added_tags: list[str] = []
    added_metadata: list[dict] = []

    fake_root = SimpleNamespace(
        id="root-id",
        trace_id="root-id",
        tags=["intent:research"],  # tag already present
        parent_run=None,
        add_tags=lambda tag: added_tags.append(tag),
        add_metadata=lambda meta: added_metadata.append(meta),
    )

    with patch(
        "langsmith.run_helpers.get_current_run_tree",
        return_value=fake_root,
    ):
        tag_trace_intent("research")

    assert "intent:research" not in added_tags, (
        "add_tags should not have been called when tag already exists; "
        f"got: {added_tags}"
    )


def test_walks_to_root_via_parent_run() -> None:
    """tag_trace_intent must walk up through parent_run to reach the root."""
    added_tags: list[str] = []
    added_metadata: list[dict] = []

    fake_root = SimpleNamespace(
        id="root-id",
        trace_id="root-id",
        tags=[],
        parent_run=None,
        add_tags=lambda tag: added_tags.append(tag),
        add_metadata=lambda meta: added_metadata.append(meta),
    )
    fake_child = SimpleNamespace(
        id="child-id",
        trace_id="root-id",
        tags=[],
        parent_run=fake_root,
        add_tags=lambda tag: (_ for _ in ()).throw(
            AssertionError("should not tag child")
        ),
        add_metadata=lambda meta: (_ for _ in ()).throw(
            AssertionError("should not meta child")
        ),
    )

    with patch(
        "langsmith.run_helpers.get_current_run_tree",
        return_value=fake_child,
    ):
        tag_trace_intent("writing")

    assert (
        "intent:writing" in added_tags
    ), f"Expected root to be tagged, got: {added_tags}"
    assert any(
        m.get("intent") == "writing" for m in added_metadata
    ), f"Expected root metadata, got: {added_metadata}"
