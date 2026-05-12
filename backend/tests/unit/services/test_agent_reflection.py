"""Tests for agent reflection gate module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.agent.reflection import (
    ReflectionResult,
    _detect_ingest_success_lie,
    _ingest_zero_count,
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

    def test_skips_when_only_failure_is_transient_and_acknowledged(self):
        """Phase 8: transient external failure + substantive acknowledgment
        → skip critique. The agent cannot recover by regenerating; reflection
        has nothing useful to say (trace e8d8b1ad / arXiv 429)."""
        from langchain_core.messages import AIMessage, HumanMessage

        long_text = (
            "I hit an arXiv rate limit (HTTP 429) while searching. Want me to "
            "retry the same search now? If you'd prefer, tell me a subtopic "
            "(e.g., medical imaging, EHR prediction, federated learning, "
            "clinical NLP) and I'll search that specifically once arXiv is "
            "available again."
        )
        assert len(long_text) >= 200  # sanity: must clear the short-output gate
        state = {
            "messages": [
                HumanMessage(content="grab me more papers"),
                AIMessage(content=long_text),
            ],
            "tool_executions": [
                {
                    "tool_name": "search_arxiv",
                    "status": "failed",
                    "result": {
                        "error": "ArXiv rate limited (HTTP 429).",
                        "error_type": "transient",
                        "suggestion": "Retry in 60 seconds.",
                    },
                },
            ],
        }
        skip, reason = _should_skip_reflection(state)
        assert skip is True
        assert "transient-failure-acknowledged" in reason

    def test_does_not_skip_when_failure_is_not_transient(self):
        """Auth/validation failures ARE worth critiquing — agent could
        apologize, suggest re-auth, etc. — so the transient skip must NOT
        fire on permanent failures."""
        from langchain_core.messages import AIMessage, HumanMessage

        long_text = "I tried but got an error. " * 20
        state = {
            "messages": [
                HumanMessage(content="search docs"),
                AIMessage(content=long_text),
            ],
            "tool_executions": [
                {
                    "tool_name": "search_documents",
                    "status": "failed",
                    "result": {
                        "error": "Permission denied",
                        "error_type": "permanent",
                    },
                },
            ],
        }
        skip, _reason = _should_skip_reflection(state)
        assert skip is False

    def test_does_not_skip_on_mixed_failure_types(self):
        """If even one failure is non-transient, reflection still runs —
        the agent might be able to address the permanent failure separately."""
        from langchain_core.messages import AIMessage, HumanMessage

        long_text = "I had partial results. " * 20
        state = {
            "messages": [
                HumanMessage(content="search both"),
                AIMessage(content=long_text),
            ],
            "tool_executions": [
                {
                    "tool_name": "search_arxiv",
                    "status": "failed",
                    "result": {"error_type": "transient"},
                },
                {
                    "tool_name": "search_documents",
                    "status": "failed",
                    "result": {"error_type": "permanent"},
                },
            ],
        }
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


@pytest.mark.unit
class TestIngestSuccessLieDetection:
    """Deterministic guard for the ingest_arxiv_papers hallucination from
    trace 019e1a1d: tool returned ingested_count=0 but the AI told the
    user "Done — I added one paper". The reflector must hard-fail without
    waiting for the LLM critique to maybe-notice.
    """

    def _ingest_te(self, *, status: str, count: int, paper_ids=None) -> dict:
        return {
            "tool_name": "ingest_arxiv_papers",
            "status": "completed",
            "result": {
                "status": status,
                "ingested_count": count,
                "paper_ids": paper_ids or ["2605.10286"],
            },
        }

    def test_ingest_zero_count_detects_failed_status(self):
        assert _ingest_zero_count(
            self._ingest_te(status="ingestion_failed", count=0)
        )

    def test_ingest_zero_count_detects_partial_status(self):
        assert _ingest_zero_count(
            self._ingest_te(status="ingestion_partial", count=1)
        )

    def test_ingest_zero_count_ignores_complete(self):
        assert not _ingest_zero_count(
            self._ingest_te(status="ingestion_complete", count=3)
        )

    def test_ingest_zero_count_ignores_other_tools(self):
        assert not _ingest_zero_count(
            {
                "tool_name": "search_arxiv",
                "status": "completed",
                "result": {"ingested_count": 0},
            }
        )

    def test_ingest_zero_count_ignores_non_dict(self):
        assert not _ingest_zero_count("not a dict")
        assert not _ingest_zero_count(None)

    def test_detect_lie_when_ai_claims_added(self):
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="add 3 papers"),
                AIMessage(content="Done — I added one paper to your project."),
            ],
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        issue = _detect_ingest_success_lie(state)
        assert issue is not None
        assert "2605.10286" in issue

    def test_no_lie_when_ai_discloses_failure(self):
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="add 3 papers"),
                AIMessage(
                    content=(
                        "Ingestion failed — 0 papers were added. The arXiv "
                        "IDs may not be indexed yet."
                    )
                ),
            ],
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        assert _detect_ingest_success_lie(state) is None

    def test_no_lie_when_no_success_verb(self):
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="add 3 papers"),
                AIMessage(content="Here are some candidate papers to consider."),
            ],
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        assert _detect_ingest_success_lie(state) is None

    def test_no_lie_when_ingest_succeeded(self):
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="add 3 papers"),
                AIMessage(content="I added 3 papers to your project."),
            ],
            "tool_executions": [
                self._ingest_te(status="ingestion_complete", count=3)
            ],
        }
        assert _detect_ingest_success_lie(state) is None

    @pytest.mark.asyncio
    async def test_gate_hard_fails_on_ingest_lie_without_llm(self):
        """End-to-end: gate must short-circuit BEFORE invoking the LLM."""
        from langchain_core.messages import AIMessage, HumanMessage

        node_fn, _ = make_reflection_gate(intent_filter={"research"})
        state = {
            "messages": [
                HumanMessage(
                    content="can you add 3 papers about Health Care in ML"
                ),
                AIMessage(
                    content=(
                        "Done — I added one paper to your project. "
                        "doc_id: ca00cf23-c306-4d33-927d-e6ca65f8d0ad"
                    )
                ),
            ],
            "intent": "research",
            "reflection_count": 0,
            "tool_executions": [
                self._ingest_te(
                    status="ingestion_failed",
                    count=0,
                    paper_ids=["2605.10286", "2605.09384", "2605.09137"],
                )
            ],
        }

        with patch(
            "src.services.agent.reflection._build_reflection_llm"
        ) as mock_build:
            updates = await node_fn(state, {"configurable": {}})
            assert mock_build.called is False

        result = updates["_reflection_result"]
        assert result.passed is False
        assert result.severity == "major"
        assert any("ingest" in issue.lower() for issue in result.issues)
        # Counter increments — this DOES burn a retry slot since the
        # agent should regenerate with the truthful failure message.
        assert updates["reflection_count"] == 1

    def test_happy_path_skip_does_not_mask_ingest_lie(self):
        """``_should_skip_reflection`` must NOT short-circuit when an
        ingest tool returned ingested_count=0, even if its execution
        status is ``completed`` (no Python exception)."""
        from langchain_core.messages import AIMessage, HumanMessage

        long_claim = (
            "I added the three papers you asked about to your project. "
            "They are now in your project and ready for further analysis "
            "and citation. Let me know if you'd like detailed summaries "
            "for any of them, or if you want me to extract specific "
            "datasets, baselines, or results from each one."
        )
        state = _make_state(
            messages=[
                HumanMessage(content="add 3 papers"),
                AIMessage(content=long_claim),
            ],
            tool_executions=[
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        )
        skip, _reason = _should_skip_reflection(state)
        assert skip is False

    @pytest.mark.parametrize(
        "verb_phrase",
        [
            "Added the paper to your project.",
            "I imported all three papers.",
            "Ingested the requested arXiv IDs.",
            "Papers attached to your project successfully.",
            "Saved them to your library.",
            "Loaded the documents.",
            "ADDED to the project.",
        ],
    )
    def test_detect_lie_across_success_verb_variants(self, verb_phrase):
        """Every verb in _INGEST_SUCCESS_CLAIM_RE must trip the guard."""
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="add 3 papers"),
                AIMessage(content=verb_phrase),
            ],
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        assert _detect_ingest_success_lie(state) is not None

    @pytest.mark.parametrize(
        "disclosure_phrase",
        [
            "I tried but it failed.",
            "Could not import the papers.",
            "Couldn't fetch them from arXiv.",
            "0 paper landed in the corpus.",
            "Zero papers ingested.",
            "None of the papers were added.",
            "Was unable to ingest them.",
            "I did not import the papers.",
            "Didn't manage to add them.",
            "Hit an error while ingesting.",
        ],
    )
    def test_disclosure_phrase_suppresses_lie_flag(self, disclosure_phrase):
        """When the AI text owns the failure, do NOT flag a lie even if a
        success verb appears nearby. Regex must look for BOTH signals."""
        from langchain_core.messages import AIMessage, HumanMessage

        content = f"I added the papers. {disclosure_phrase}"
        state = {
            "messages": [
                HumanMessage(content="add 3 papers"),
                AIMessage(content=content),
            ],
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        assert _detect_ingest_success_lie(state) is None

    def test_substring_false_match_avoided(self):
        """Word boundaries: 'saddled', 'overloaded' must NOT register as
        success verbs (added/loaded). Regex uses ``\\b``."""
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="add papers"),
                AIMessage(
                    content=(
                        "The system felt overloaded and the request was "
                        "saddled with retries."
                    )
                ),
            ],
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        assert _detect_ingest_success_lie(state) is None

    def test_detect_lie_across_multiple_executions(self):
        """Mixed-batch: one ingest succeeds, another fails. Lie guard
        still fires; only failing paper_ids appear in the issue text."""
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="add 6 papers"),
                AIMessage(content="I added all six papers to your project."),
            ],
            "tool_executions": [
                self._ingest_te(
                    status="ingestion_complete",
                    count=3,
                    paper_ids=["a.1", "a.2", "a.3"],
                ),
                self._ingest_te(
                    status="ingestion_failed",
                    count=0,
                    paper_ids=["b.1", "b.2", "b.3"],
                ),
            ],
        }
        issue = _detect_ingest_success_lie(state)
        assert issue is not None
        assert "b.1" in issue and "b.2" in issue and "b.3" in issue
        assert "a.1" not in issue

    def test_detect_lie_with_multimodal_content(self):
        """AIMessage.content can be a list of content blocks. The text
        parts must still be scanned for success verbs."""
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="add papers"),
                AIMessage(
                    content=[
                        {"type": "text", "text": "Status update: "},
                        {"type": "text", "text": "I added the paper."},
                    ]
                ),
            ],
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        assert _detect_ingest_success_lie(state) is not None

    def test_no_lie_when_tool_executions_empty(self):
        """No ingest in history → guard returns None even if AI text
        contains 'added'."""
        from langchain_core.messages import AIMessage, HumanMessage

        state = {
            "messages": [
                HumanMessage(content="what was added last week?"),
                AIMessage(content="Two papers were added on Tuesday."),
            ],
            "tool_executions": [],
        }
        assert _detect_ingest_success_lie(state) is None

    def test_no_ai_message_returns_none(self):
        """Defensive: state with no AIMessage shouldn't crash."""
        from langchain_core.messages import HumanMessage

        state = {
            "messages": [HumanMessage(content="anything")],
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        assert _detect_ingest_success_lie(state) is None

    def test_legacy_result_shape_without_status_field(self):
        """Older tool output had ``ingested_count`` but no ``status``
        field. ``_ingest_zero_count`` must still detect it."""
        legacy_te = {
            "tool_name": "ingest_arxiv_papers",
            "status": "completed",
            "result": {"ingested_count": 0, "paper_ids": ["x.1"]},
        }
        assert _ingest_zero_count(legacy_te)

    def test_result_missing_returns_false(self):
        """Execution entry with no ``result`` key must not crash."""
        te = {"tool_name": "ingest_arxiv_papers", "status": "completed"}
        assert _ingest_zero_count(te) is False

    @pytest.mark.asyncio
    async def test_gate_respects_max_rounds_even_on_ingest_lie(self):
        """At reflection_count == 2 the gate must NOT keep failing.
        Retry budget caps regardless of detector type."""
        from langchain_core.messages import AIMessage, HumanMessage

        node_fn, _ = make_reflection_gate(intent_filter={"research"})
        state = {
            "messages": [
                HumanMessage(content="add papers"),
                AIMessage(content="Done — I added one paper."),
            ],
            "intent": "research",
            "reflection_count": 2,
            "tool_executions": [
                self._ingest_te(status="ingestion_failed", count=0)
            ],
        }
        with patch(
            "src.services.agent.reflection._build_reflection_llm"
        ) as mock_build:
            updates = await node_fn(state, {"configurable": {}})
            assert mock_build.called is False

        # At max rounds the node returns just the counter, no result.
        assert updates["reflection_count"] == 2
        assert "_reflection_result" not in updates
