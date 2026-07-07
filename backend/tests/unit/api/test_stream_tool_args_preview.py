"""``_tool_args_preview`` shapes the SSE ``tool_start.args`` field.

Two properties it must hold:
1. **Object shape (M2):** a dict tool input returns a dict, NOT a Python-repr
   string. The frontend's args summarizer ignores non-object args, so the old
   ``str(tool_input)`` rendered nothing live while the persisted object
   rendered on reload — the live preview never worked.
2. **PII redaction (#1046):** values are redacted before the payload leaves the
   server (browser-visible SSE), on both the main and confirm/resume streams.
"""

from __future__ import annotations

import pytest

from src.api.agent.streaming import _tool_args_preview

pytestmark = pytest.mark.unit


def test_dict_input_returns_object_not_repr_string():
    # M2 regression: a Python-repr string would make the frontend render no
    # live args preview (summarizeToolArgs ignores non-objects).
    preview = _tool_args_preview({"query": "transformers", "max_results": 5})
    assert isinstance(preview, dict)
    assert preview["query"] == "transformers"


def test_non_string_scalars_preserved():
    preview = _tool_args_preview({"max_results": 5, "rerank": True, "x": None})
    assert preview == {"max_results": 5, "rerank": True, "x": None}


def test_dict_values_are_pii_redacted():
    tool_input = {"query": "email jane@example.com about the paper"}
    preview = _tool_args_preview(tool_input)
    assert "jane@example.com" not in preview["query"]
    assert "<email>" in preview["query"]
    # Guard against a revert to raw args: the unredacted render would leak it.
    assert "jane@example.com" in str(tool_input)


def test_nested_values_are_redacted():
    preview = _tool_args_preview(
        {"filter": {"author": "jane@example.com"}, "tags": ["call 555-123-4567"]}
    )
    assert "jane@example.com" not in preview["filter"]["author"]
    assert "555-123-4567" not in preview["tags"][0]


def test_non_dict_input_falls_back_to_redacted_string():
    preview = _tool_args_preview("email jane@example.com")
    assert isinstance(preview, str)
    assert "jane@example.com" not in preview


def test_empty_inputs():
    assert _tool_args_preview({}) == {}
    assert _tool_args_preview(None) == ""


def test_long_string_value_capped_after_redaction():
    preview = _tool_args_preview({"q": "a" * 1000})
    assert len(preview["q"]) == 500


def test_non_json_scalar_is_stringified_so_payload_stays_serializable():
    # A non-JSON-safe value (datetime here) must not pass through raw — the
    # emit-site json.dumps would otherwise raise and break the SSE stream.
    import datetime as _dt
    import json

    from src.api.agent.streaming import _redact_tool_args

    preview = _tool_args_preview({"since": _dt.datetime(2026, 1, 1)})
    assert isinstance(preview["since"], str)
    json.dumps(preview)  # must not raise

    # Non-string scalars that ARE JSON-safe keep their type.
    assert _redact_tool_args(5) == 5
    assert _redact_tool_args(True) is True
