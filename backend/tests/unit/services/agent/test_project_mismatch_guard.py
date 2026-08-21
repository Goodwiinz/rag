"""A note/document must not silently land in a topic-guessed project.

Traced thread 9e151940: on the "RAG Evaluation" project page, the writing
subgraph called create_project_note with an explicit project_id it topic-matched
to "Cyber Agents" (jailbreak brief ~ cyber). _resolve_project_id honors any
valid UUID over the active page, so the note misfiled with no signal to the user.

Layer 1 (prompt) tells the model to omit project_id on a project page; this
layer makes a cross-project write LOUD in the tool result the model reports
back, independent of the HITL confirm gate.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services.agent.tools import _flag_project_mismatch, _page_project_conflict

pytestmark = pytest.mark.unit

_ACTIVE = "0c95e1e4-d97c-4afa-9178-79e1e3dfa705"
_OTHER = "6bef011c-7bca-4174-97e2-33b83e0cfd5c"


# ---------------------------------------------------------------------------
# _page_project_conflict — pure precedence logic
# ---------------------------------------------------------------------------


def test_conflict_when_target_differs_from_active_page() -> None:
    page = {"type": "project", "project_id": _ACTIVE}
    assert _page_project_conflict(_OTHER, page) == _ACTIVE


def test_no_conflict_when_target_matches_active_page() -> None:
    page = {"type": "project", "project_id": _ACTIVE}
    assert _page_project_conflict(_ACTIVE, page) is None


def test_no_conflict_when_no_project_page() -> None:
    # Not on a project page → the explicit id is the deliberate target.
    assert _page_project_conflict(_OTHER, {"type": "chat"}) is None
    assert _page_project_conflict(_OTHER, {}) is None


def test_no_conflict_when_target_unresolved() -> None:
    page = {"type": "project", "project_id": _ACTIVE}
    assert _page_project_conflict(None, page) is None


# ---------------------------------------------------------------------------
# _flag_project_mismatch — result annotation
# ---------------------------------------------------------------------------


def _own(**names: str):
    """Patch _verify_project_ownership to map id -> a named project stub."""

    async def _fake(pid, _db, _user):
        name = names.get(str(pid))
        return SimpleNamespace(name=name) if name else None

    return patch(
        "src.services.agent.tools_impl._verify_project_ownership",
        new=AsyncMock(side_effect=_fake),
    )


@pytest.mark.asyncio
async def test_mismatch_makes_the_write_loud() -> None:
    page = {"type": "project", "project_id": _ACTIVE}
    result = {
        "status": "success",
        "project_name": "Cyber Agents",
        "message": "Created note 'Brief' in project 'Cyber Agents'.",
    }
    with _own(**{_ACTIVE: "RAG Evaluation"}):
        out = await _flag_project_mismatch(
            result, _OTHER, page, db=object(), current_user=object()
        )

    assert out["project_mismatch"] is True
    assert "WARNING" in out["message"]
    assert "Cyber Agents" in out["message"]
    assert "RAG Evaluation" in out["message"]


@pytest.mark.asyncio
async def test_no_annotation_when_target_matches_page() -> None:
    page = {"type": "project", "project_id": _ACTIVE}
    result = {"status": "success", "project_name": "RAG Evaluation", "message": "ok"}
    with _own(**{_ACTIVE: "RAG Evaluation"}):
        out = await _flag_project_mismatch(
            result, _ACTIVE, page, db=object(), current_user=object()
        )

    assert "project_mismatch" not in out
    assert out["message"] == "ok"


@pytest.mark.asyncio
async def test_no_annotation_off_a_project_page() -> None:
    result = {"status": "success", "project_name": "Cyber Agents", "message": "ok"}
    out = await _flag_project_mismatch(
        result, _OTHER, {"type": "chat"}, db=object(), current_user=object()
    )
    assert "project_mismatch" not in out


@pytest.mark.asyncio
async def test_error_result_is_untouched() -> None:
    page = {"type": "project", "project_id": _ACTIVE}
    result = {"error": "boom"}
    out = await _flag_project_mismatch(
        result, _OTHER, page, db=object(), current_user=object()
    )
    assert out == {"error": "boom"}


@pytest.mark.asyncio
async def test_lookup_failure_does_not_break_the_write() -> None:
    page = {"type": "project", "project_id": _ACTIVE}
    result = {"status": "success", "project_name": "Cyber Agents", "message": "ok"}
    with patch(
        "src.services.agent.tools_impl._verify_project_ownership",
        new=AsyncMock(side_effect=RuntimeError("db down")),
    ):
        out = await _flag_project_mismatch(
            result, _OTHER, page, db=object(), current_user=object()
        )
    # Advisory only: the note still succeeded, result returned unmutated.
    assert out["message"] == "ok"


# ---------------------------------------------------------------------------
# Reachability: the layer-1 rule must live where the writing subgraph sees it
# ---------------------------------------------------------------------------


def test_note_project_rule_is_in_shared_rules_not_only_main_prompt() -> None:
    """The writing subgraph prompt = AGENTS_writing.md + SHARED_AGENT_RULES; it
    does NOT include _LLM_NODE_STATIC_PROMPT. The omit-project_id rule must be
    in SHARED_AGENT_RULES or it never reaches the subgraph that misfiled."""
    from src.services.agent._prompts import SHARED_AGENT_RULES

    section = SHARED_AGENT_RULES.split("## Resolving a save target", 1)[1]
    assert "OMIT project_id" in section
    assert "topic-matching silently files the note in the wrong project" in section
