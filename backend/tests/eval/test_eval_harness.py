"""Unit tests for the eval harness contract + plan_adherence evaluator.

These are pure-function tests — no LangSmith, no graph execution — so they run
in the normal unit suite (no LANGCHAIN_API_KEY needed). They pin:
- the dataset/harness input contract (`_build_initial_state`) that silently
  broke before (nested `case` rows, fixture-arg leaks, empty questions);
- the null-reference guards on the evaluators (vacuous-pass bug);
- the new `plan_adherence` trajectory evaluator.
"""

import pytest
from langchain_core.messages import HumanMessage


@pytest.mark.unit
class TestBuildInitialState:
    def test_flat_question(self):
        from tests.eval.test_agent_regression import _build_initial_state

        st = _build_initial_state({"question": "hi"})
        assert st["messages"][0].content == "hi"

    def test_nested_case_is_unwrapped(self):
        from tests.eval.test_agent_regression import _build_initial_state

        st = _build_initial_state(
            {"case": {"question": "hello", "page_context": {"type": "project"}}}
        )
        assert st["messages"][0].content == "hello"
        assert st["page_context"] == {"type": "project"}

    def test_empty_or_fixture_leak_raises(self):
        from tests.eval.test_agent_regression import _build_initial_state

        with pytest.raises(ValueError):
            _build_initial_state(
                {"experiment_prefix": "x", "langsmith_dataset_name": "y"}
            )
        with pytest.raises(ValueError):
            _build_initial_state({"question": ""})

    def test_messages_passthrough(self):
        from tests.eval.test_agent_regression import _build_initial_state

        msgs = [HumanMessage(content="q")]
        st = _build_initial_state({"messages": msgs})
        assert st["messages"] is msgs


@pytest.mark.unit
class TestEvaluatorGuards:
    def test_intent_match_missing_reference_fails(self):
        from tests.eval.test_agent_regression import intent_match

        assert intent_match({"intent": "general"}, {})["score"] == 0
        assert intent_match({"intent": "general"}, None)["score"] == 0

    def test_intent_match_present(self):
        from tests.eval.test_agent_regression import intent_match

        assert intent_match({"intent": "general"}, {"intent": "general"})["score"] == 1
        assert intent_match({"intent": "research"}, {"intent": "general"})["score"] == 0

    def test_tool_subset_missing_reference_fails(self):
        from tests.eval.test_agent_regression import tool_subset_match

        # No expected_tools KEY → null reference → fail (not vacuous pass).
        assert tool_subset_match({"tool_calls": []}, {})["score"] == 0

    def test_tool_subset_legit_empty_tuple_passes(self):
        from tests.eval.test_agent_regression import tool_subset_match

        # Key present, value () → legitimately "no tools expected" → pass.
        assert (
            tool_subset_match({"tool_calls": ["x"]}, {"expected_tools": ()})["score"]
            == 1
        )

    def test_tool_subset_in_order(self):
        from tests.eval.test_agent_regression import tool_subset_match

        assert (
            tool_subset_match(
                {"tool_calls": ["a", "b"]}, {"expected_tools": ("a", "b")}
            )["score"]
            == 1
        )
        assert (
            tool_subset_match({"tool_calls": ["b"]}, {"expected_tools": ("a",)})["score"]
            == 0
        )


def _run(plan, executed_tool_names):
    """Build a dict-shaped run for plan_adherence with an empty inputs set."""
    messages = [
        {
            "type": "ai",
            "id": f"ai-{i}",
            "tool_calls": [{"id": f"tc-{i}", "name": name, "args": {}}],
        }
        for i, name in enumerate(executed_tool_names)
    ]
    return {"inputs": {"messages": []}, "outputs": {"plan": plan, "messages": messages}}


@pytest.mark.unit
class TestPlanAdherence:
    def test_empty_plan_is_vacuously_adherent(self):
        from tests.eval.langsmith_trajectory_evaluators import plan_adherence

        assert plan_adherence(_run([], []))["score"] == 1
        assert plan_adherence(_run(None, []))["score"] == 1

    def test_description_only_plan_is_vacuous(self):
        from tests.eval.langsmith_trajectory_evaluators import plan_adherence

        plan = [{"step": 1, "description": "think", "tool": ""}]
        assert plan_adherence(_run(plan, []))["score"] == 1

    def test_all_steps_executed_in_order(self):
        from tests.eval.langsmith_trajectory_evaluators import plan_adherence

        plan = [
            {"step": 1, "tool": "search_arxiv"},
            {"step": 2, "tool": "summarize_document"},
        ]
        score = plan_adherence(_run(plan, ["search_arxiv", "summarize_document"]))["score"]
        assert score == 1

    def test_partial_execution_scores_fraction(self):
        from tests.eval.langsmith_trajectory_evaluators import plan_adherence

        plan = [
            {"step": 1, "tool": "search_arxiv"},
            {"step": 2, "tool": "summarize_document"},
        ]
        score = plan_adherence(_run(plan, ["search_arxiv"]))["score"]
        assert 0 < score < 1

    def test_skipped_step_does_not_score_full(self):
        from tests.eval.langsmith_trajectory_evaluators import plan_adherence

        plan = [{"step": 1, "tool": "search_arxiv"}]
        assert plan_adherence(_run(plan, []))["score"] == 0
