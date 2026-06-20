"""Tests for the fabricated-tool-success reflection guard.

Covers ``_detect_fabricated_tool_success`` and the ``_should_skip_reflection``
interaction, ensuring the deterministic guard fires when the AI claims a
creation happened but no creation tool actually executed, and stays silent
when the model is being honest.
"""

import pytest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent.reflection import (
    ReflectionResult,
    _detect_fabricated_tool_success,
    _should_skip_reflection,
    make_reflection_gate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    *,
    ai_content: str | list,
    tool_executions: list | None = None,
    intent: str = "research",
    reflection_count: int = 0,
) -> dict:
    """Build a minimal state dict with a single HumanMessage + AIMessage."""
    return {
        "messages": [
            HumanMessage(content="Please create a project for my NLP research"),
            AIMessage(content=ai_content),
        ],
        "tool_executions": tool_executions if tool_executions is not None else [],
        "intent": intent,
        "reflection_count": reflection_count,
    }


def _completed_create_project_te() -> dict:
    """A completed create_project tool execution."""
    return {
        "tool_name": "create_project",
        "status": "completed",
        "result": {
            "project_id": "b3f9e2d4-abc1-2345-6789-abcdef012345",
            "name": "NLP Research",
            "status": "active",
        },
    }


# ---------------------------------------------------------------------------
# Tests: _detect_fabricated_tool_success
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectFabricatedToolSuccess:
    def test_plain_text_fabrication_fires(self):
        """AI claims project created with a project_id in prose but no tool ran."""
        state = _make_state(
            ai_content=(
                "Project created (project_id: b3f9e2d4-abc1-2345-6789-abcdef012345),"
                " status active."
            ),
            tool_executions=[],
        )
        issue = _detect_fabricated_tool_success(state)
        assert issue is not None
        assert "fabricated" in issue

    def test_inline_json_fabrication_fires(self):
        """AI embeds a JSON blob with project_id but no creation tool ran."""
        state = _make_state(
            ai_content=(
                'Here is the result: {"project_id":"b3f9e2d4-abc1-2345-6789-abcdef012345",'
                '"status":"active"}'
            ),
            tool_executions=[],
        )
        issue = _detect_fabricated_tool_success(state)
        assert issue is not None

    def test_prose_created_the_project_fires(self):
        """'I have created the project for NLP' with no tool → fabrication."""
        state = _make_state(
            ai_content="I have created the project for NLP research.",
            tool_executions=[],
        )
        issue = _detect_fabricated_tool_success(state)
        assert issue is not None

    def test_honest_disclosure_suppresses_flag(self):
        """When AI honestly says it couldn't save, no fabrication flag."""
        state = _make_state(
            ai_content=(
                "I couldn't save it because no project_id was provided. "
                "Would you like me to create a project first?"
            ),
            tool_executions=[],
        )
        assert _detect_fabricated_tool_success(state) is None

    def test_real_success_suppresses_flag(self):
        """AI says created + create_project completed → no fabrication."""
        state = _make_state(
            ai_content="Project created successfully. You can find it in your dashboard.",
            tool_executions=[_completed_create_project_te()],
        )
        assert _detect_fabricated_tool_success(state) is None

    def test_non_creation_tool_only_fires(self):
        """Only ingest_arxiv_papers completed — NOT a creation tool — so flag fires."""
        state = _make_state(
            ai_content="Project created (project_id: b3f9e2d4-abc1-2345-6789-abcdef012345).",
            tool_executions=[
                {
                    "tool_name": "ingest_arxiv_papers",
                    "status": "completed",
                    "result": {"ingested_count": 2},
                }
            ],
        )
        issue = _detect_fabricated_tool_success(state)
        assert issue is not None

    def test_no_ai_message_returns_none(self):
        """Defensive: state with no AIMessage should not crash."""
        state = {
            "messages": [HumanMessage(content="create a project")],
            "tool_executions": [],
        }
        assert _detect_fabricated_tool_success(state) is None

    def test_multimodal_content_list_fires(self):
        """AIMessage.content as a list of blocks is scanned for the claim."""
        state = _make_state(
            ai_content=[
                {"type": "text", "text": "Done! "},
                {
                    "type": "text",
                    "text": "project_id: b3f9e2d4-abc1-2345-6789-abcdef012345 is active.",
                },
            ],
            tool_executions=[],
        )
        assert _detect_fabricated_tool_success(state) is not None

    def test_create_project_note_completed_suppresses_flag(self):
        """create_project_note is a valid creation tool; its completion is enough."""
        state = _make_state(
            ai_content="Note saved to your project.",
            tool_executions=[
                {
                    "tool_name": "create_project_note",
                    "status": "completed",
                    "result": {"note_id": "abc123"},
                }
            ],
        )
        assert _detect_fabricated_tool_success(state) is None

    def test_create_draft_completed_suppresses_flag(self):
        """create_draft completion counts as a real creation."""
        state = _make_state(
            ai_content="Draft created for your NLP project.",
            tool_executions=[
                {
                    "tool_name": "create_draft",
                    "status": "completed",
                    "result": {"draft_id": "d001"},
                }
            ],
        )
        assert _detect_fabricated_tool_success(state) is None

    def test_add_document_to_project_completed_suppresses_flag(self):
        """add_document_to_project completion counts as a real creation."""
        state = _make_state(
            ai_content="Added the document to the project.",
            tool_executions=[
                {
                    "tool_name": "add_document_to_project",
                    "status": "completed",
                    "result": {},
                }
            ],
        )
        assert _detect_fabricated_tool_success(state) is None

    def test_creation_tool_with_failed_status_still_fires(self):
        """A creation tool that failed (status=failed) does not count as ran."""
        state = _make_state(
            ai_content="Project created (project_id: b3f9e2d4-abc1-2345-6789-abcdef012345).",
            tool_executions=[
                {
                    "tool_name": "create_project",
                    "status": "failed",
                    "result": {"error": "DB timeout"},
                }
            ],
        )
        issue = _detect_fabricated_tool_success(state)
        assert issue is not None

    def test_note_created_fires_without_tool(self):
        """'note saved' pattern triggers the guard with no tool execution."""
        state = _make_state(
            ai_content="Your note has been saved to the project.",
            tool_executions=[],
        )
        issue = _detect_fabricated_tool_success(state)
        assert issue is not None

    def test_added_document_to_project_fires_without_tool(self):
        """'added X to the project' phrase triggers the guard."""
        state = _make_state(
            ai_content="I have added the paper to the project.",
            tool_executions=[],
        )
        issue = _detect_fabricated_tool_success(state)
        assert issue is not None


# ---------------------------------------------------------------------------
# Tests: _should_skip_reflection does NOT skip on fabrication
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSkipReflectionFabricationGate:
    def test_skip_not_triggered_when_fabrication_detected(self):
        """When _detect_fabricated_tool_success fires, _should_skip_reflection
        must return (False, …) even though tool_executions is empty — the
        deterministic check needs to run and hard-fail the node."""
        state = _make_state(
            ai_content=(
                "project_id: b3f9e2d4-abc1-2345-6789-abcdef012345, status: active. "
                "Project created for your NLP research."
            ),
            tool_executions=[],
        )
        skip, reason = _should_skip_reflection(state)
        assert skip is False
        assert "fabricat" in reason

    def test_skip_still_applies_for_clean_tool_less_turn(self):
        """A tool-less turn with NO creation claim should still skip."""
        state = _make_state(
            ai_content="Sure, I can help with that!",
            tool_executions=[],
        )
        skip, reason = _should_skip_reflection(state)
        # "Sure, I can help with that!" is < 200 chars, no tool_calls → short-output
        assert skip is True


# ---------------------------------------------------------------------------
# Tests: end-to-end gate node integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGateNodeFabricationIntegration:
    @pytest.mark.asyncio
    async def test_gate_hard_fails_on_fabrication_without_llm(self):
        """End-to-end: gate must short-circuit BEFORE calling the reflection
        LLM when a fabrication is detected."""
        node_fn, _ = make_reflection_gate(intent_filter={"research"})
        state = _make_state(
            ai_content=(
                "I have created the project for NLP. "
                "project_id: b3f9e2d4-abc1-2345-6789-abcdef012345, status: active."
            ),
            tool_executions=[],
            intent="research",
            reflection_count=0,
        )

        with patch("src.services.agent.reflection._build_reflection_llm") as mock_build:
            updates = await node_fn(state, {"configurable": {}})
            assert mock_build.called is False

        result = updates["_reflection_result"]
        assert result.passed is False
        assert result.severity == "major"
        assert any("fabricated" in issue for issue in result.issues)
        assert updates["reflection_count"] == 1

    @pytest.mark.asyncio
    async def test_gate_respects_max_rounds_on_fabrication(self):
        """At reflection_count == 2, the max-round guard fires BEFORE the
        fabrication detector — the node returns early with no result."""
        node_fn, _ = make_reflection_gate(intent_filter={"research"})
        state = _make_state(
            ai_content="project_id: b3f9e2d4-abc1-2345-6789-abcdef012345 active.",
            tool_executions=[],
            intent="research",
            reflection_count=2,
        )

        with patch("src.services.agent.reflection._build_reflection_llm") as mock_build:
            updates = await node_fn(state, {"configurable": {}})
            assert mock_build.called is False

        assert updates["reflection_count"] == 2
        assert "_reflection_result" not in updates
