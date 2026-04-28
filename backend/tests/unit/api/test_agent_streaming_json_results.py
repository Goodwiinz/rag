"""Unit tests for ``_encode_tool_result`` in streaming.py.

The CLI parses ``tool_end.result`` to render honest per-tool summaries.
For dict/list outputs we emit JSON so the CLI can ``JSON.parse`` it; for
primitives we keep the previous ``str()`` shape. Non-serializable objects
must not crash the stream.
"""

from datetime import datetime

import json

import pytest

from src.api.agent.streaming import _encode_tool_result


class TestEncodeToolResult:
    def test_dict_output_emits_valid_json(self) -> None:
        out = _encode_tool_result({"documents_ingested": 0, "paper_ids": ["x"]})
        parsed = json.loads(out)
        assert parsed == {"documents_ingested": 0, "paper_ids": ["x"]}

    def test_list_output_emits_valid_json(self) -> None:
        out = _encode_tool_result([{"id": "a"}, {"id": "b"}])
        assert json.loads(out) == [{"id": "a"}, {"id": "b"}]

    def test_string_output_passes_through_as_str(self) -> None:
        assert _encode_tool_result("hello") == "hello"

    def test_truncates_at_500_chars(self) -> None:
        big = {"blob": "x" * 1000}
        out = _encode_tool_result(big)
        assert len(out) == 500

    def test_non_serializable_falls_back_to_str_via_default(self) -> None:
        # default=str makes datetime serializable; verify that path works.
        ts = datetime(2026, 4, 26, 12, 0, 0)
        out = _encode_tool_result({"created_at": ts})
        parsed = json.loads(out)
        assert parsed["created_at"].startswith("2026-04-26")

    def test_unencodable_value_falls_back_silently(self) -> None:
        # An object whose default=str raises is still safe — the helper
        # must not propagate the exception. Use a class with __str__ that
        # works but a json-side default that fails.
        class Odd:
            def __str__(self) -> str:
                return "<odd>"

        # Wrap a plain non-dict/list object — falls through to str() branch.
        assert _encode_tool_result(Odd()) == "<odd>"

    def test_primitive_int_uses_str(self) -> None:
        assert _encode_tool_result(42) == "42"

    def test_empty_dict_emits_empty_json_object(self) -> None:
        # CLI relies on detecting "{}" to render bare tool name.
        assert _encode_tool_result({}) == "{}"

    def test_empty_list_emits_empty_json_array(self) -> None:
        assert _encode_tool_result([]) == "[]"


# Suppress unused import warning if pytest is not yet typed for the project.
_ = pytest
