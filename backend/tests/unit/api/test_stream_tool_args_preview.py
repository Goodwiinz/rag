"""tool_start args preview must be PII-redacted on BOTH the main and confirm
streams. The confirm/resume path previously used a raw ``str(tool_input)``,
leaking emails/phones from doc content over the browser-visible SSE payload.
Both paths now route through ``_tool_args_preview``.

Contract (round-3 M2): the preview is a JSON OBJECT — the frontend consumes
``args`` via ``Object.entries``, so a repr string meant the live args preview
never rendered. Values are redact-first-then-cap strings.
"""

from __future__ import annotations

import pytest

from src.api.agent.streaming import _tool_args_preview

pytestmark = pytest.mark.unit


def test_preview_redacts_email():
    tool_input = {"query": "email jane@example.com about the paper"}
    preview = _tool_args_preview(tool_input)
    assert preview == {"query": "email <email> about the paper"}
    # Guard against a revert to a raw ``str(v)`` render (the old confirm-path
    # bug): the unredacted input still contains the email.
    assert "jane@example.com" in str(tool_input)


def test_preview_empty_input_is_empty_object():
    assert _tool_args_preview({}) == {}
    assert _tool_args_preview(None) == {}


def test_preview_caps_values_after_redaction():
    long_clean = {"q": "a" * 1000}
    assert len(_tool_args_preview(long_clean)["q"]) == 500


def test_preview_non_dict_input_wraps_as_object():
    preview = _tool_args_preview("call jane@example.com")
    assert preview == {"input": "call <email>"}
