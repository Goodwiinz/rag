"""Tests for agent reflection gate module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.agent.reflection import (
    ReflectionResult,
    make_reflection_gate,
    reflect_on_response,
)


def _make_state(
    *,
    intent: str = "research",
    reflection_count: int = 0,
    messages: list | None = None,
    _reflection_result: "ReflectionResult | None" = None,
) -> dict:
    """Build a minimal AgentState dict for reflection tests."""
    from langchain_core.messages import AIMessage, HumanMessage

    if messages is None:
        messages = [
            HumanMessage(content="Find papers on transformers"),
            AIMessage(content="I found several papers about transformers."),
        ]

    state: dict = {
        "messages": messages,
        "page_context": {},
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": "test-thread",
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "pending_confirmation": {},
        "user_confirmed": False,
        "intent": intent,
        "user_memories": [],
        "plan": [],
        "reflection_count": reflection_count,
        "compaction_count": 0,
        "intent_confidence": 0.8,
        "last_error_info": {},
    }
    if _reflection_result is not None:
        state["_reflection_result"] = _reflection_result
    return state


@pytest.mark.unit
class TestReflectionResult:
    def test_passed_result(self):
        result = ReflectionResult(passed=True, issues=[], severity="none")
        assert result.passed is True
        assert result.issues == []
        assert result.severity == "none"

    def test_failed_result_with_issues(self):
        result = ReflectionResult(
            passed=False,
            issues=["No tool calls observed", "Response does not address full request"],
            severity="major",
        )
        assert result.passed is False
        assert len(result.issues) == 2
        assert result.severity == "major"


@pytest.mark.unit
class TestReflectOnResponse:
    @pytest.mark.asyncio
    async def test_returns_reflection_result(self):
        """reflect_on_response should return a ReflectionResult."""
        from langchain_core.messages import AIMessage

        mock_result = ReflectionResult(passed=True, issues=[], severity="none")

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_result)
        mock_llm.with_structured_output.return_value = mock_structured

        with patch(
            "src.services.agent.reflection._build_reflection_llm",
            return_value=mock_llm,
        ):
            result = await reflect_on_response(
                last_ai_message=AIMessage(content="Here are papers on transformers."),
                original_user_message="Find papers on transformers",
                plan=None,
                intent="research",
            )

        assert isinstance(result, ReflectionResult)
        assert result.passed is True


@pytest.mark.unit
class TestMakeReflectionGate:
    @pytest.mark.asyncio
    async def test_good_response_passes(self):
        """A passing reflection should route to 'proceed'."""
        good_result = ReflectionResult(passed=True, issues=[], severity="none")

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=good_result)
        mock_llm.with_structured_output.return_value = mock_structured

        node_fn, route_fn = make_reflection_gate()

        state = _make_state(intent="research", reflection_count=0)
        config = {"configurable": {}}

        with patch(
            "src.services.agent.reflection._build_reflection_llm",
            return_value=mock_llm,
        ):
            updates = await node_fn(state, config)

        assert updates["reflection_count"] == 1
        assert updates["_reflection_result"].passed is True

        # Apply updates to state for routing
        state.update(updates)
        route = route_fn(state)
        assert route == "proceed"

    @pytest.mark.asyncio
    async def test_bad_response_triggers_revision(self):
        """A major severity failure should route to 'revise'."""
        bad_result = ReflectionResult(
            passed=False,
            issues=["No tools were executed", "Response is superficial"],
            severity="major",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=bad_result)
        mock_llm.with_structured_output.return_value = mock_structured

        node_fn, route_fn = make_reflection_gate()

        state = _make_state(intent="research", reflection_count=0)
        config = {"configurable": {}}

        with patch(
            "src.services.agent.reflection._build_reflection_llm",
            return_value=mock_llm,
        ):
            updates = await node_fn(state, config)

        assert updates["reflection_count"] == 1
        assert updates["_reflection_result"].passed is False

        state.update(updates)
        route = route_fn(state)
        assert route == "revise"

    @pytest.mark.asyncio
    async def test_max_rounds_respected(self):
        """When reflection_count >= 2, the node should skip (no LLM call)."""
        node_fn, route_fn = make_reflection_gate()

        state = _make_state(intent="research", reflection_count=2)
        config = {"configurable": {}}

        # No LLM mock needed — it should skip entirely
        updates = await node_fn(state, config)

        assert updates["reflection_count"] == 2
        assert "_reflection_result" not in updates

        state.update(updates)
        route = route_fn(state)
        assert route == "proceed"

    @pytest.mark.asyncio
    async def test_general_intent_skips(self):
        """Intent 'general' should be skipped by the default filter."""
        node_fn, route_fn = make_reflection_gate()

        state = _make_state(intent="general", reflection_count=0)
        config = {"configurable": {}}

        updates = await node_fn(state, config)

        assert updates["reflection_count"] == 0
        assert "_reflection_result" not in updates

        state.update(updates)
        route = route_fn(state)
        assert route == "proceed"

    @pytest.mark.asyncio
    async def test_knowledge_graph_intent_skips(self):
        """Intent 'knowledge_graph' should be skipped by the default filter."""
        node_fn, route_fn = make_reflection_gate()

        state = _make_state(intent="knowledge_graph", reflection_count=0)
        config = {"configurable": {}}

        updates = await node_fn(state, config)

        assert updates["reflection_count"] == 0
        assert "_reflection_result" not in updates

        state.update(updates)
        route = route_fn(state)
        assert route == "proceed"

    @pytest.mark.asyncio
    async def test_minor_severity_proceeds(self):
        """A minor severity issue should route to 'proceed', not 'revise'."""
        minor_result = ReflectionResult(
            passed=False,
            issues=["Could use more detail"],
            severity="minor",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=minor_result)
        mock_llm.with_structured_output.return_value = mock_structured

        node_fn, route_fn = make_reflection_gate()

        state = _make_state(intent="writing", reflection_count=0)
        config = {"configurable": {}}

        with patch(
            "src.services.agent.reflection._build_reflection_llm",
            return_value=mock_llm,
        ):
            updates = await node_fn(state, config)

        assert updates["reflection_count"] == 1
        assert updates["_reflection_result"].severity == "minor"

        state.update(updates)
        route = route_fn(state)
        assert route == "proceed"
