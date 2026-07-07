"""tool_start args preview must be PII-redacted on BOTH the main and confirm
streams. The confirm/resume path previously used a raw ``str(tool_input)``,
leaking emails/phones from doc content over the browser-visible SSE payload.
Both paths now route through ``_tool_args_preview``.
"""

from __future__ import annotations

import pytest

from src.api.agent.streaming import _tool_args_preview

pytestmark = pytest.mark.unit


def test_preview_redacts_email():
    tool_input = {"query": "email jane@example.com about the paper"}
    preview = _tool_args_preview(tool_input)
    assert "jane@example.com" not in preview
    assert "<email>" in preview
    # Guard against a revert to a raw ``str(tool_input)[:500]`` (the old
    # confirm-path bug): the unredacted render would still contain the email.
    assert "jane@example.com" in str(tool_input)


def test_preview_empty_input_is_empty_string():
    assert _tool_args_preview({}) == ""
    assert _tool_args_preview(None) == ""


def test_preview_caps_after_redaction():
    long_clean = {"q": "a" * 1000}
    assert len(_tool_args_preview(long_clean)) == 500
