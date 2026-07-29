"""Persisted tool args are redacted at serve time (round-3 S3 residual).

#1046 redacted the live SSE ``tool_start`` preview but rows persisted by
``persist_assistant_message`` keep raw args, and both message-serving
funnels (agent ``get_thread_messages`` and threads ``_format_message_response``)
returned ``msg.tool_executions`` verbatim — so a page reload re-leaked the
PII the live stream had redacted. Serve-time redaction also covers rows
persisted before the fix.
"""

from __future__ import annotations

import pytest

from src.services.agent._pii_redact import redact_tool_executions

pytestmark = pytest.mark.unit

PII_ARGS = {
    "query": "email bob@example.com about doc",
    "nested": {"token": "sk-ant-abcdefghijklmnopqrstuvwxyz1234"},
    "max_results": 5,
}


def test_args_redacted_structure_preserved():
    entries = [
        {
            "id": "te-1",
            "tool_name": "search_documents",
            "args": PII_ARGS,
            "status": "success",
            "result": "ok",
        }
    ]
    out = redact_tool_executions(entries)
    args = out[0]["args"]
    assert "bob@example.com" not in str(args)
    assert "<email>" in args["query"]
    assert "sk-ant-" not in str(args)
    assert args["max_results"] == 5
    # non-args fields untouched; input not mutated in place
    assert out[0]["result"] == "ok"
    assert entries[0]["args"]["query"].startswith("email bob@example.com")


def test_none_and_empty_pass_through():
    assert redact_tool_executions(None) is None
    assert redact_tool_executions([]) == []


def test_legacy_non_dict_entry_survives():
    # A legacy/unknown entry shape must not 500 the messages endpoint.
    out = redact_tool_executions(["opaque-legacy-entry"])
    assert out == ["opaque-legacy-entry"]


def test_serving_funnels_call_redaction():
    # Pin that both browser-serving funnels route through the redactor, so
    # neither can silently drift back to raw ``msg.tool_executions``.
    import inspect

    from src.api.agent import execute
    from src.api.threads import threads

    assert "redact_tool_executions(msg.tool_executions)" in inspect.getsource(
        execute.get_thread_messages
    )
    assert "redact_tool_executions(message.tool_executions)" in inspect.getsource(
        threads._format_message_response
    )
