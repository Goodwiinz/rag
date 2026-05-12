"""Tests for agent reflection gate module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.agent.reflection import (
    ReflectionResult,
    _should_skip_reflection,
    make_reflection_gate,
    reflect_on_response,
)


def _make_state(
    *,
    intent: str = "research",
    reflection_count: int = 0,
    messages: list | None = None,
    tool_executions: list | None = None,
    _reflection_result: "ReflectionResult | None" = None,
) -> dict:
    """Build a minimal AgentState dict for reflection tests.

    Defaults represent a substantive, tool-grounded research turn so the
    pre-LLM skip gate (``_should_skip_reflection``) does not short-circuit
    tests that exercise the reflection LLM path. Tests that want the skip
    behaviour pass shorter content / empty ``tool_executions`` explicitly.
    """
    from langchain_core.messages import AIMessage, HumanMessage

    if messages is None:
        messages = [
            HumanMessage(content="Find papers on transformers"),
            AIMessage(
                content=(
                    "I found several papers about transformer architectures. "
                    "The key contributions span attention mechanisms, scaling "
                    "behaviour, and downstream task transfer. Below is a brief "
                    "synthesis of the most cited results so you can decide "
                    "which to read first."
                )
            ),
        ]
    if tool_executions is None:
        # Phase 5 added a "happy-path" skip in _should_skip_reflection that
        # bypasses the LLM when content >= 200 chars AND every tool_execution
        # is "completed". Tests exercising the reflection LLM path force the
        # gate open by including one failed execution.
        tool_executions = [
            {"tool_name": "search_arxiv", "status": "completed"},
            {"tool_name": "search_documents", "status": "failed"},
        ]

    state: dict = {
        "messages": messages,
        "page_context": {},
        "retrieved_contexts": [],
        "tool_executions": tool_executions,
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


# ---------------------------------------------------------------------------
# Skip-reflection heuristic
# ---------------------------------------------------------------------------


class TestShouldSkipReflection:
    """Cheap, deterministic gate that runs before the reflection LLM call.

    Saves ~944 tokens / call on trivial outputs and tool-less turns.
    """

    def test_skips_short_content_without_tool_calls(self):
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="hi"),
                AIMessage(content="OK."),
            ],
            "tool_executions": [],
        }
        skip, reason = _should_skip_reflection(state)
        assert skip is True
        assert "short-output" in reason

    def test_skips_when_no_tools_ran_and_no_pending_tool_calls(self):
        from langchain_core.messages import AIMessage, HumanMessage

        # Long content but no tools were executed AND no pending tool_calls.
        long_text = "Here is a long substantive answer. " * 20  # > 200 chars
        state = {
            "messages": [
                HumanMessage(content="quick question"),
                AIMessage(content=long_text),
            ],
            "tool_executions": [],
        }
        skip, reason = _should_skip_reflection(state)
        assert skip is True
        assert "no-tools" in reason

    def test_skips_happy_path_when_all_tools_completed(self):
        """Phase 5 perf gate: long answer + all tools succeeded → skip critique."""
        from langchain_core.messages import AIMessage, HumanMessage

        long_text = "Detailed grounded answer. " * 20
        state = {
            "messages": [
                HumanMessage(content="find papers"),
                AIMessage(content=long_text),
            ],
            "tool_executions": [{"tool_name": "search_arxiv", "status": "completed"}],
        }
        skip, reason = _should_skip_reflection(state)
        assert skip is True
        assert "happy-path" in reason

    def test_does_not_skip_when_a_tool_failed(self):
        """A failed tool execution forces critique even when content is long."""
        from langchain_core.messages import AIMessage, HumanMessage

        long_text = "Detailed grounded answer. " * 20
        state = {
            "messages": [
                HumanMessage(content="find papers"),
                AIMessage(content=long_text),
            ],
            "tool_executions": [
                {"tool_name": "search_arxiv", "status": "failed"},
            ],
        }
        skip, reason = _should_skip_reflection(state)
        assert skip is False
        assert reason == ""

    def test_does_not_skip_when_pending_tool_calls(self):
        from langchain_core.messages import AIMessage, HumanMessage

        # Short content but the AIMessage carries pending tool_calls — the
        # gate must NOT skip because the next turn will run those tools and
        # we want reflection on the grounded result.
        state = {
            "messages": [
                HumanMessage(content="search arxiv"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"id": "tc1", "name": "search_arxiv", "args": {"query": "x"}}
                    ],
                ),
            ],
            "tool_executions": [],
        }
        skip, reason = _should_skip_reflection(state)
        assert skip is False

    def test_no_ai_message_falls_through(self):
        from langchain_core.messages import HumanMessage

        state = {"messages": [HumanMessage(content="hi")], "tool_executions": []}
        skip, _reason = _should_skip_reflection(state)
        assert skip is False

    @pytest.mark.asyncio
    async def test_gate_node_skips_llm_for_trivial_writing_turn(self):
        """End-to-end: the writing-intent gate must NOT call the critique LLM
        when the response is a one-liner with no tools."""
        from langchain_core.messages import AIMessage, HumanMessage

        node_fn, _route_fn = make_reflection_gate(intent_filter={"writing"})
        state = {
            "messages": [
                HumanMessage(content="thanks"),
                AIMessage(content="You're welcome."),
            ],
            "intent": "writing",
            "reflection_count": 0,
            "tool_executions": [],
        }

        with patch(
            "src.services.agent.reflection._build_reflection_llm"
        ) as mock_build:
            updates = await node_fn(state, {"configurable": {}})
            assert mock_build.called is False

        assert updates["_reflection_result"].passed is True
        # Reflection counter unchanged when we skip.
        assert updates["reflection_count"] == 0
