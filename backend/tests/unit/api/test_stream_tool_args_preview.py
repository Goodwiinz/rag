"""``tool_start.args`` preview: emitted as a JSON object (so the frontend
activity strip renders a live "key: value" preview — ``summarizeToolArgs``
rejects non-objects) with every string value PII-redacted before it leaves the
server. Shared by the main and confirm/resume streams.
"""

from __future__ import annotations

import pytest

from src.api.agent.streaming import _tool_args_preview

pytestmark = pytest.mark.unit


def test_preview_returns_object_not_repr_string():
    # The old bug: str(tool_input) → the frontend's summarizeToolArgs rejects
    # non-objects, so the live preview never rendered. Must be a dict now.
    preview = _tool_args_preview({"query": "transformers", "max_results": 5})
    assert isinstance(preview, dict)
    assert preview == {"query": "transformers", "max_results": 5}


def test_preview_redacts_email_per_value():
    tool_input = {"query": "email jane@example.com about the paper"}
    preview = _tool_args_preview(tool_input)
    assert isinstance(preview, dict)
    assert "jane@example.com" not in preview["query"]
    assert "<email>" in preview["query"]
    # Guard against a revert that stops redacting: the raw input still has it.
    assert "jane@example.com" in str(tool_input)


def test_preview_preserves_non_string_scalars():
    preview = _tool_args_preview({"n": 5, "flag": True, "ratio": 0.5, "x": None})
    assert preview == {"n": 5, "flag": True, "ratio": 0.5, "x": None}


def test_preview_empty_input_is_empty_dict():
    assert _tool_args_preview({}) == {}
    assert _tool_args_preview(None) == {}


def test_preview_caps_each_string_value():
    preview = _tool_args_preview({"q": "a" * 1000})
    assert len(preview["q"]) == 500


def test_preview_non_dict_input_falls_back_to_redacted_string():
    # Rare non-dict tool input (e.g. a bare string) stays a capped, redacted
    # string rather than raising.
    preview = _tool_args_preview("email jane@example.com")
    assert isinstance(preview, str)
    assert "jane@example.com" not in preview
    assert "<email>" in preview
