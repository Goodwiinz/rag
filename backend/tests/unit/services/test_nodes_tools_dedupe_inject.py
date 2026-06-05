"""Audit #10: project_id is injected into a tool call *before* the per-turn
dedupe key is computed, so a repeat call that omits project_id matches the
recorded (injected) execution and is deduped instead of re-running.
"""

from __future__ import annotations

import pytest

from src.services.agent._nodes_tools import _with_injected_project_id

pytestmark = pytest.mark.unit

_PROJECT_CTX = {"type": "project", "project_id": "p-1"}


def test_injects_when_omitted_on_project_page():
    out = _with_injected_project_id(
        {"name": "list_project_documents", "args": {}, "id": "1"}, _PROJECT_CTX
    )
    assert out["args"]["project_id"] == "p-1"
    assert out["id"] == "1" and out["name"] == "list_project_documents"


def test_does_not_override_explicit_project_id():
    out = _with_injected_project_id(
        {"name": "x", "args": {"project_id": "other"}, "id": "1"}, _PROJECT_CTX
    )
    assert out["args"]["project_id"] == "other"


def test_no_injection_when_not_a_project_page():
    out = _with_injected_project_id({"name": "x", "args": {}, "id": "1"}, {"type": "chat"})
    assert "project_id" not in out["args"]


def test_does_not_mutate_the_input_call():
    tc = {"name": "x", "args": {}, "id": "1"}
    _with_injected_project_id(tc, _PROJECT_CTX)
    assert tc["args"] == {}  # original tool_call left untouched
