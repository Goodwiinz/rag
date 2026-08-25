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

    def test_tool_subset_empty_tuple_requires_no_calls(self):
        from tests.eval.test_agent_regression import tool_subset_match

        assert (
            tool_subset_match({"tool_calls": []}, {"expected_tools": ()})["score"] == 1
        )
        assert (
            tool_subset_match({"tool_calls": ["x"]}, {"expected_tools": ()})["score"]
            == 0
        )

    def test_tool_subset_none_explicitly_skips_tool_scoring(self):
        from tests.eval.test_agent_regression import tool_subset_match

        assert (
            tool_subset_match({"tool_calls": ["x"]}, {"expected_tools": None})["score"]
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
            tool_subset_match({"tool_calls": ["b"]}, {"expected_tools": ("a",)})[
                "score"
            ]
            == 0
        )
        # Order matters: expected (a, b) is NOT satisfied by actual [b, a].
        assert (
            tool_subset_match(
                {"tool_calls": ["b", "a"]}, {"expected_tools": ("a", "b")}
            )["score"]
            == 0
        )

    def test_intent_match_empty_actual_fails(self):
        # "" is never a valid classified intent: a run that produced no intent
        # must fail even when the reference is also "" (polluted row).
        from tests.eval.test_agent_regression import intent_match

        assert intent_match({"intent": ""}, {"intent": ""})["score"] == 0
        assert intent_match({}, {"intent": "general"})["score"] == 0

    def test_intent_match_accept_intents_membership(self):
        # A row may list a set of acceptable routes; the exact intent plus any
        # accept_intents member all pass.
        from tests.eval.test_agent_regression import intent_match

        ref = {"intent": "writing", "accept_intents": ["research"]}
        assert intent_match({"intent": "research"}, ref)["score"] == 1
        assert intent_match({"intent": "writing"}, ref)["score"] == 1
        assert intent_match({"intent": "knowledge_graph"}, ref)["score"] == 0
        # accept_intents alone (no exact intent key) is a valid reference.
        assert (
            intent_match({"intent": "data"}, {"accept_intents": ["data", "research"]})[
                "score"
            ]
            == 1
        )

    def test_tool_match_any(self):
        from tests.eval.test_agent_regression import tool_subset_match

        ref = {"expected_tools": ("a", "b", "c"), "tool_match": "any"}
        # Any one of the expected tools present, order-free -> pass.
        assert tool_subset_match({"tool_calls": ["z", "b"]}, ref)["score"] == 1
        # None present -> fail.
        assert tool_subset_match({"tool_calls": ["z"]}, ref)["score"] == 0
        # Default (no tool_match) stays strict ordered-subsequence.
        ref_default = {"expected_tools": ("a", "b")}
        assert tool_subset_match({"tool_calls": ["b", "a"]}, ref_default)["score"] == 0


_UNSET = object()


class _FakeExample:
    """Minimal stand-in for a LangSmith example (has .id and .metadata)."""

    def __init__(self, ex_id, golden_case=_UNSET):
        self.id = ex_id
        if golden_case is _UNSET:
            self.metadata = {}  # polluted row: no golden_case key
        else:
            self.metadata = {"golden_case": golden_case}


@pytest.mark.unit
class TestPartitionExamples:
    def test_orphans_with_missing_metadata_are_not_collapsed(self):
        # The bug: keying orphans by golden_case (None) collapsed every
        # metadata-less polluted row to one, so --clean deleted only one.
        from tests.eval.upload_golden import _partition_examples

        examples = [_FakeExample("o1"), _FakeExample("o2"), _FakeExample("o3")]
        by_name, orphans = _partition_examples(examples, local_names={"x"})
        assert by_name == {}
        assert {o.id for o in orphans} == {"o1", "o2", "o3"}

    def test_known_cases_mapped_unknown_are_orphans(self):
        from tests.eval.upload_golden import _partition_examples

        examples = [
            _FakeExample("a", "greeting_hi"),
            _FakeExample("b", "stale_removed_case"),
        ]
        by_name, orphans = _partition_examples(examples, local_names={"greeting_hi"})
        assert set(by_name) == {"greeting_hi"}
        assert [o.id for o in orphans] == ["b"]

    def test_duplicate_of_known_name_is_orphaned(self):
        # Two remote rows for the same local case: keep one, orphan the rest
        # so the remote exactly mirrors local.
        from tests.eval.upload_golden import _partition_examples

        examples = [_FakeExample("first", "ack_yes"), _FakeExample("dup", "ack_yes")]
        by_name, orphans = _partition_examples(examples, local_names={"ack_yes"})
        assert by_name["ack_yes"].id == "first"
        assert [o.id for o in orphans] == ["dup"]


def _run(plan, executed_tool_names):
    """Build a dict-shaped run for plan_adherence with a current-turn boundary."""
    messages = [{"type": "human", "id": "human-current"}] + [
        {
            "type": "ai",
            "id": f"ai-{i}",
            "tool_calls": [{"id": f"tc-{i}", "name": name, "args": {}}],
        }
        for i, name in enumerate(executed_tool_names)
    ]
    return {
        "inputs": {"messages": [{"type": "human", "id": "human-current"}]},
        "outputs": {"plan": plan, "messages": messages},
    }


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
        score = plan_adherence(_run(plan, ["search_arxiv", "summarize_document"]))[
            "score"
        ]
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


def _traj(tool_calls):
    """Build a current-turn run from a list of (name, args_dict) tool calls."""
    messages = [{"type": "human", "id": "human-current"}] + [
        {
            "type": "ai",
            "id": f"ai-{i}",
            "tool_calls": [{"id": f"tc-{i}", "name": name, "args": args}],
        }
        for i, (name, args) in enumerate(tool_calls)
    ]
    return {
        "inputs": {"messages": [{"type": "human", "id": "human-current"}]},
        "outputs": {"messages": messages},
    }


def _live_shaped_turn():
    """A cumulative LangGraph history containing a completed prior turn."""
    return {
        "inputs": {
            "messages": [
                {"type": "human", "id": "human-old"},
                {"type": "human", "id": "human-current"},
            ]
        },
        "outputs": {
            "messages": [
                {"type": "human", "id": "human-old"},
                {
                    "type": "ai",
                    "id": "ai-old",
                    "tool_calls": [
                        {"id": "tc-old", "name": "search_documents", "args": {}}
                    ],
                },
                {"type": "tool", "id": "tool-old", "tool_call_id": "tc-old"},
                {"type": "human", "id": "human-current"},
                {
                    "type": "ai",
                    "id": "ai-current",
                    "tool_calls": [
                        {"id": "tc-current", "name": "do_kb_retrieve", "args": {}}
                    ],
                },
                {"type": "tool", "id": "tool-current", "tool_call_id": "tc-current"},
                {"type": "ai", "id": "final-current", "content": "Answer"},
            ]
        },
    }


@pytest.mark.unit
class TestNoToolLoop:
    def test_consecutive_duplicate_scores_zero(self):
        from tests.eval.langsmith_trajectory_evaluators import no_tool_loop

        assert no_tool_loop(_traj([("a", {}), ("a", {})]))["score"] == 0

    def test_oscillation_three_times_scores_zero(self):
        # A,B,A,B,A — "a" with identical args appears 3x, never adjacent.
        from tests.eval.langsmith_trajectory_evaluators import no_tool_loop

        calls = [
            ("a", {"q": 1}),
            ("b", {}),
            ("a", {"q": 1}),
            ("b", {}),
            ("a", {"q": 1}),
        ]
        assert no_tool_loop(_traj(calls))["score"] == 0

    def test_two_non_consecutive_repeats_pass(self):
        # A,B,A — same call twice, not a loop yet (threshold is 3).
        from tests.eval.langsmith_trajectory_evaluators import no_tool_loop

        assert no_tool_loop(_traj([("a", {}), ("b", {}), ("a", {})]))["score"] == 1

    def test_distinct_calls_pass(self):
        from tests.eval.langsmith_trajectory_evaluators import no_tool_loop

        assert no_tool_loop(_traj([("a", {}), ("b", {}), ("c", {})]))["score"] == 1

    def test_same_name_different_args_not_a_loop(self):
        from tests.eval.langsmith_trajectory_evaluators import no_tool_loop

        calls = [("a", {"q": 1}), ("a", {"q": 2}), ("a", {"q": 3})]
        assert no_tool_loop(_traj(calls))["score"] == 1

    def test_prior_turn_duplicates_do_not_fail_current_turn(self):
        from tests.eval.langsmith_trajectory_evaluators import no_tool_loop

        run = _live_shaped_turn()
        messages = run["outputs"]["messages"]
        messages[1]["tool_calls"] = [
            {"id": f"tc-old-{i}", "name": "search_documents", "args": {}}
            for i in range(3)
        ]
        assert no_tool_loop(run)["score"] == 1


def _final(content, tool_calls=None):
    """Build a run whose only output message is a final AI message."""
    msg = {"type": "ai", "id": "final", "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"inputs": {"messages": []}, "outputs": {"messages": [msg]}}


@pytest.mark.unit
class TestTerminatesWithAnswer:
    def test_str_answer_passes(self):
        from tests.eval.langsmith_trajectory_evaluators import terminates_with_answer

        assert terminates_with_answer(_final("here is the answer"))["score"] == 1

    def test_empty_str_fails(self):
        from tests.eval.langsmith_trajectory_evaluators import terminates_with_answer

        assert terminates_with_answer(_final("   "))["score"] == 0

    def test_empty_list_fails(self):
        from tests.eval.langsmith_trajectory_evaluators import terminates_with_answer

        assert terminates_with_answer(_final([]))["score"] == 0

    def test_tool_use_only_block_list_fails(self):
        from tests.eval.langsmith_trajectory_evaluators import terminates_with_answer

        content = [{"type": "tool_use", "name": "x", "input": {}}]
        assert terminates_with_answer(_final(content))["score"] == 0

    def test_whitespace_text_block_fails(self):
        from tests.eval.langsmith_trajectory_evaluators import terminates_with_answer

        content = [{"type": "text", "text": "   "}]
        assert terminates_with_answer(_final(content))["score"] == 0

    def test_real_text_block_passes(self):
        from tests.eval.langsmith_trajectory_evaluators import terminates_with_answer

        content = [{"type": "text", "text": "the answer"}]
        assert terminates_with_answer(_final(content))["score"] == 1

    def test_pending_tool_calls_fails(self):
        from tests.eval.langsmith_trajectory_evaluators import terminates_with_answer

        run = _final("ignored", tool_calls=[{"id": "1", "name": "x", "args": {}}])
        assert terminates_with_answer(run)["score"] == 0


@pytest.mark.unit
class TestToolCallValidity:
    def _run(self, messages):
        boundary = {"type": "human", "id": "human-current"}
        return {
            "inputs": {"messages": [boundary]},
            "outputs": {"messages": [boundary, *messages]},
        }

    def test_matched_call_passes(self):
        from tests.eval.langsmith_trajectory_evaluators import tool_call_validity

        msgs = [
            {
                "type": "ai",
                "id": "a1",
                "tool_calls": [{"id": "c1", "name": "x", "args": {}}],
            },
            {"type": "tool", "id": "t1", "tool_call_id": "c1"},
        ]
        assert tool_call_validity(self._run(msgs))["score"] == 1

    def test_missing_tool_message_fails(self):
        from tests.eval.langsmith_trajectory_evaluators import tool_call_validity

        msgs = [
            {
                "type": "ai",
                "id": "a1",
                "tool_calls": [{"id": "c1", "name": "x", "args": {}}],
            },
        ]
        assert tool_call_validity(self._run(msgs))["score"] == 0

    def test_orphan_tool_message_fails(self):
        from tests.eval.langsmith_trajectory_evaluators import tool_call_validity

        msgs = [
            {
                "type": "ai",
                "id": "a1",
                "tool_calls": [{"id": "c1", "name": "x", "args": {}}],
            },
            {"type": "tool", "id": "t1", "tool_call_id": "c1"},
            {"type": "tool", "id": "t2", "tool_call_id": "c9"},  # orphan
        ]
        assert tool_call_validity(self._run(msgs))["score"] == 0

    def test_unmatched_prior_turn_call_does_not_fail_current_turn(self):
        from tests.eval.langsmith_trajectory_evaluators import tool_call_validity

        run = _live_shaped_turn()
        run["outputs"]["messages"] = [
            message
            for message in run["outputs"]["messages"]
            if message.get("id") != "tool-old"
        ]
        assert tool_call_validity(run)["score"] == 1


@pytest.mark.unit
class TestCurrentTurnBoundary:
    def test_extract_messages_keeps_only_current_turn_suffix(self):
        from tests.eval.langsmith_trajectory_evaluators import _extract_messages

        messages = _extract_messages(_live_shaped_turn())
        assert [message["id"] for message in messages] == [
            "ai-current",
            "tool-current",
            "final-current",
        ]

    def test_prior_plan_call_does_not_distort_current_plan_step(self):
        from tests.eval.langsmith_trajectory_evaluators import plan_adherence

        run = _live_shaped_turn()
        run["outputs"]["plan"] = [
            {"step": 1, "tool": "do_kb_retrieve"},
            {"step": 2, "tool": "summarize_document"},
        ]
        result = plan_adherence(run)
        assert result["score"] == 0.5
        assert "search_documents" not in result["comment"]

    @pytest.mark.parametrize(
        "evaluator, run",
        [
            (
                "tool_call_validity",
                {"outputs": {"messages": [{"type": "ai", "id": "a"}]}},
            ),
            ("no_tool_loop", {"outputs": {"messages": [{"type": "ai", "id": "a"}]}}),
            (
                "plan_adherence",
                {
                    "outputs": {
                        "plan": [{"step": 1, "tool": "do_kb_retrieve"}],
                        "messages": [{"type": "ai", "id": "a"}],
                    }
                },
            ),
        ],
    )
    def test_missing_human_boundary_fails_closed(self, evaluator, run):
        from tests.eval import langsmith_trajectory_evaluators as rules

        result = getattr(rules, evaluator)(run)
        assert result["score"] == 0
        assert "turn boundary" in result["comment"].lower()


@pytest.mark.unit
class TestGoldenCaseInvariants:
    def test_tool_expectation_serialization_preserves_ignore_vs_none(self):
        from tests.eval.golden_examples import GoldenCase
        from tests.eval.upload_golden import _example_payload

        ignored = GoldenCase("ignore", "q", "general")
        no_tools = GoldenCase("none", "q", "general", ())

        assert _example_payload(ignored)[1]["expected_tools"] is None
        assert _example_payload(no_tools)[1]["expected_tools"] == []

    def test_all_case_names_unique(self):
        # A duplicate name would silently shadow a case in the dataset upsert
        # (keyed by golden_case name) and in pytest ids.
        from collections import Counter

        from tests.eval.golden_examples import LOCAL_CASES

        dups = [n for n, c in Counter(c.name for c in LOCAL_CASES).items() if c > 1]
        assert not dups, f"duplicate golden case names: {dups}"

    def test_every_local_case_has_replay_cassette(self):
        # Staleness guard (B2 Phase 3): a golden case with no recorded cassette
        # would silently skip the creds-free replay gate. Fail loud so a newly
        # added case must be recorded (record_golden_cassette.py) before merge.
        from tests.eval._replay_llm import CASSETTE_DIR
        from tests.eval.golden_examples import LOCAL_CASES

        missing = [
            c.name
            for c in LOCAL_CASES
            if not (CASSETTE_DIR / f"{c.name}.json").exists()
        ]
        assert not missing, (
            "golden cases missing a replay cassette — record with "
            f"`python -m tests.eval.record_golden_cassette {' '.join(missing)}`: {missing}"
        )


@pytest.mark.unit
class TestKnownToolsRegistry:
    def test_known_tools_matches_live_registry(self):
        # KNOWN_TOOLS is hardcoded in the (sandbox-uploaded) evaluator module;
        # this drift test fails if it diverges from the real tool registry.
        from src.services.agent.subgraphs.data_agent import DATA_TOOLS
        from src.services.agent.subgraphs.research_agent import RESEARCH_TOOLS
        from src.services.agent.subgraphs.writing_agent import WRITING_TOOLS
        from src.services.agent.tools import ALL_TOOLS
        from tests.eval.langsmith_trajectory_evaluators import KNOWN_TOOLS

        live = {t.name for t in ALL_TOOLS}
        for lst in (RESEARCH_TOOLS, DATA_TOOLS, WRITING_TOOLS):
            live |= {t.name for t in lst}
        assert set(KNOWN_TOOLS) == live, (
            f"KNOWN_TOOLS drift: missing={live - set(KNOWN_TOOLS)} "
            f"extra={set(KNOWN_TOOLS) - live}"
        )


@pytest.mark.unit
class TestPlanAdherenceRegistryFilter:
    def test_hallucinated_tool_step_excluded(self):
        # A real tool executed + a hallucinated planned step the agent could
        # never run -> the bogus step is excluded, score is full.
        from tests.eval.langsmith_trajectory_evaluators import plan_adherence

        plan = [
            {"step": 1, "tool": "search_arxiv"},
            {"step": 2, "tool": "totally_made_up_tool"},
        ]
        assert plan_adherence(_run(plan, ["search_arxiv"]))["score"] == 1

    def test_all_hallucinated_is_vacuous(self):
        from tests.eval.langsmith_trajectory_evaluators import plan_adherence

        plan = [{"step": 1, "tool": "made_up_a"}, {"step": 2, "tool": "made_up_b"}]
        assert plan_adherence(_run(plan, []))["score"] == 1


@pytest.mark.unit
class TestEvaluatorExtractorRoundTrip:
    def test_every_metric_extracts_and_runs(self):
        # The extractor must bundle all helpers + constants each evaluator
        # references; a missing name would NameError only in the LangSmith
        # sandbox. _extract_function now exec+smoke-calls internally, so a
        # broken blob raises here at "upload" time.
        from tests.eval.upload_trajectory_rules import (
            EVALUATORS_FILE,
            METRICS,
            _extract_function,
        )

        src = EVALUATORS_FILE.read_text()
        smoke_run = {
            "inputs": {"messages": [{"type": "human", "id": "human-current"}]},
            "outputs": {
                "messages": [
                    {"type": "human", "id": "human-current"},
                    {
                        "type": "ai",
                        "tool_calls": [
                            {
                                "id": "call-list-projects",
                                "name": "list_projects",
                                "args": {},
                            },
                            {
                                "id": "call-create-project",
                                "name": "create_project",
                                "args": {"name": "Synthetic Project"},
                            },
                        ],
                    },
                    {
                        "type": "tool",
                        "tool_call_id": "call-list-projects",
                        "content": "no existing projects",
                    },
                    {
                        "type": "tool",
                        "tool_call_id": "call-create-project",
                        "content": "created",
                    },
                    {"type": "ai", "content": "Project created."},
                ],
                "plan": [
                    {"step": 1, "tool": "list_projects"},
                    {"step": 2, "tool": "create_project"},
                ],
            },
        }
        for fn_name, _label in METRICS:
            blob = _extract_function(src, fn_name)
            assert "def perform_eval(" in blob
            ns: dict = {}
            exec(compile(blob, f"<{fn_name}>", "exec"), ns)
            result = ns["perform_eval"](smoke_run)
            assert result["score"] == 1
            if fn_name == "no_tool_loop":
                assert "no loop possible" not in result["comment"].lower()
                assert result["comment"] == "2 tool calls, no spinning detected."

    def test_extracted_plan_adherence_bundles_known_tools(self):
        from tests.eval.upload_trajectory_rules import (
            EVALUATORS_FILE,
            _extract_function,
        )

        blob = _extract_function(EVALUATORS_FILE.read_text(), "plan_adherence")
        assert "KNOWN_TOOLS = frozenset(" in blob

        ns: dict = {}
        exec(compile(blob, "<plan_adherence>", "exec"), ns)
        result = ns["perform_eval"](
            {
                "outputs": {
                    "messages": [
                        {"type": "human", "id": "human-current"},
                        {
                            "type": "ai",
                            "tool_calls": [
                                {
                                    "id": "call-current",
                                    "name": "create_project",
                                    "args": {"name": "Synthetic Project"},
                                }
                            ],
                        },
                    ],
                    "plan": [{"step": 1, "tool": "create_project"}],
                }
            }
        )

        assert result["score"] == 1
        assert result["comment"] == "All 1 planned tool-step(s) executed in order."

    def test_known_tools_extraction_does_not_bundle_unrelated_constant(self):
        from tests.eval.upload_trajectory_rules import (
            EVALUATORS_FILE,
            _extract_function,
        )

        source = 'UNRELATED_TOOLS = frozenset({"must-not-bundle"})\n' + (
            EVALUATORS_FILE.read_text()
        )
        blob = _extract_function(source, "plan_adherence")

        assert "KNOWN_TOOLS = frozenset(" in blob
        assert "UNRELATED_TOOLS" not in blob
        assert "must-not-bundle" not in blob


from pydantic import BaseModel as _PydBaseModel


class _FakeIntent(_PydBaseModel):
    intent: str
    confidence: float = 0.0


def _cassette(calls):
    from tests.eval._replay_llm import GoldenCassette

    return GoldenCassette({"case": "t", "calls": calls})


@pytest.mark.unit
class TestGoldenReplayLLM:
    @pytest.mark.asyncio
    async def test_structured_output_returns_recorded_instance(self):
        from tests.eval._replay_llm import GoldenReplayLLM

        fake = GoldenReplayLLM(
            _cassette(
                [
                    {
                        "slot": 0,
                        "kind": "structured",
                        "schema": "_FakeIntent",
                        "payload": {"intent": "research", "confidence": 0.9},
                    },
                ]
            )
        )
        chain = fake.with_structured_output(_FakeIntent)
        result = await chain.ainvoke(["msg"])
        assert isinstance(result, _FakeIntent)
        assert result.intent == "research" and result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_bind_tools_returns_scripted_tool_call(self):
        from tests.eval._replay_llm import GoldenReplayLLM

        fake = GoldenReplayLLM(
            _cassette(
                [
                    {
                        "slot": 0,
                        "kind": "tool",
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "name": "do_kb_retrieve",
                                    "args": {"q": "x"},
                                    "id": "c0",
                                }
                            ],
                        },
                    },
                ]
            )
        )
        msg = await fake.bind_tools([]).ainvoke(["msg"])
        assert [tc["name"] for tc in msg.tool_calls] == ["do_kb_retrieve"]

    @pytest.mark.asyncio
    async def test_tool_exhaustion_returns_terminal_message(self):
        # Script spent -> tool-less AIMessage ends the loop gracefully.
        from tests.eval._replay_llm import GoldenReplayLLM

        msg = await GoldenReplayLLM(_cassette([])).bind_tools([]).ainvoke(["m"])
        assert msg.tool_calls == []

    @pytest.mark.asyncio
    async def test_text_path(self):
        from tests.eval._replay_llm import GoldenReplayLLM

        fake = GoldenReplayLLM(
            _cassette(
                [
                    {
                        "slot": 0,
                        "kind": "text",
                        "message": {"content": "the answer", "tool_calls": []},
                    },
                ]
            )
        )
        msg = await fake.ainvoke(["msg"])
        assert msg.content == "the answer"

    @pytest.mark.asyncio
    async def test_structured_exhaustion_fails_loud(self):
        # An un-recorded structured call must raise, never silently go live.
        from tests.eval._replay_llm import CassetteExhausted, GoldenReplayLLM

        with pytest.raises(CassetteExhausted):
            await (
                GoldenReplayLLM(_cassette([]))
                .with_structured_output(_FakeIntent)
                .ainvoke(["m"])
            )

    def test_replay_disabled_by_default(self):
        # Phase 1 must stay inert unless explicitly enabled.
        import os

        from tests.eval._replay_llm import replay_enabled

        assert replay_enabled() == (os.environ.get("AGENT_GOLDEN_REPLAY") == "1")


@pytest.mark.asyncio
async def test_runner_harvests_interrupt_tool_calls(monkeypatch):
    """Destructive tools trigger interrupt() for HITL and never reach the
    top-level message history; the runner must harvest their names from the
    __interrupt__ payload. A golden case cannot isolate this branch."""
    import tests.eval.test_agent_regression as reg

    class _Interrupt:
        value = {"tools": [{"name": "create_project", "args": {}}]}

    class FakeGraph:
        async def astream(self, initial_state, stream_mode=None):
            yield {"__interrupt__": (_Interrupt(),)}

    monkeypatch.setattr(reg, "compile_agent_graph", lambda: FakeGraph())
    out = await reg._run_agent({"question": "create a project called X"})
    assert "create_project" in out["tool_calls"]


@pytest.mark.asyncio
async def test_runner_preserves_general_path_tool_calls(monkeypatch):
    """Regression: under stream_mode="updates" the runner must merge the
    messages channel with the add_messages reducer, not dict.update (which
    replaced the list and dropped every general-path tool call)."""
    from langchain_core.messages import AIMessage, ToolMessage

    import tests.eval.test_agent_regression as reg

    class FakeGraph:
        async def astream(self, initial_state, stream_mode=None):
            yield {
                "llm_node": {
                    "messages": [
                        AIMessage(
                            content="",
                            id="m1",
                            tool_calls=[
                                {
                                    "type": "tool_call",
                                    "name": "do_kb_retrieve",
                                    "id": "1",
                                    "args": {},
                                }
                            ],
                        )
                    ]
                }
            }
            yield {
                "tool_node": {
                    "messages": [ToolMessage(content="hits", tool_call_id="1", id="m2")]
                }
            }
            yield {
                "llm_node": {
                    "messages": [AIMessage(content="final answer", id="m3")],
                    "intent": "general",
                }
            }

    monkeypatch.setattr(reg, "compile_agent_graph", lambda: FakeGraph())
    out = await reg._run_agent({"question": "what does our kb say?"})
    assert out["intent"] == "general"
    assert "do_kb_retrieve" in out["tool_calls"], (
        "general-path tool call was clobbered — messages channel not merged "
        "with the add_messages reducer"
    )


# ---------------------------------------------------------------------------
# Sweep failure collection — the vacuous-pass guard one level above the
# evaluators. The evaluators already refuse to pass on a null reference;
# these pin the same rule for the loop that consumes their scores.
# ---------------------------------------------------------------------------


class _FakeScore:
    """Minimal stand-in for a LangSmith EvaluationResult (.key / .score)."""

    def __init__(self, key, score):
        self.key = key
        self.score = score


class _FakeResult:
    """Minimal stand-in for one ``evaluate()`` result row.

    ``evaluation_results=None`` reproduces the shape that used to be skipped.
    """

    def __init__(self, ex_id, scores=_UNSET):
        self.example = _FakeExample(ex_id)
        if scores is _UNSET:
            self.evaluation_results = None
        else:
            self.evaluation_results = type("_Block", (), {"results": list(scores)})()


def _both(ex_id, intent=1, tools=1):
    return _FakeResult(
        ex_id,
        [_FakeScore("intent_match", intent), _FakeScore("tool_subset_match", tools)],
    )


@pytest.mark.unit
class TestCollectSweepFailures:
    def test_empty_results_score_nothing(self):
        """An empty sweep must be reported as 0 scored, not as a clean pass."""
        from tests.eval.test_agent_regression import collect_sweep_failures

        failures, scored = collect_sweep_failures([])
        assert scored == 0
        # No failures, but scored==0 is what the caller asserts on — the bug
        # was that `not failures` alone read as success.
        assert failures == []

    def test_missing_evaluation_results_is_a_failure_not_a_skip(self):
        from tests.eval.test_agent_regression import collect_sweep_failures

        failures, scored = collect_sweep_failures([_FakeResult("ex1")])
        assert scored == 1
        assert len(failures) == 1
        assert "ex1" in failures[0] and "no evaluation_results" in failures[0]

    def test_evaluator_that_never_ran_is_caught(self):
        """A missing key has no score to compare, so it needs its own check."""
        from tests.eval.test_agent_regression import collect_sweep_failures

        partial = _FakeResult("ex2", [_FakeScore("intent_match", 1)])
        failures, scored = collect_sweep_failures([partial])
        assert scored == 1
        assert any("tool_subset_match did not run" in f for f in failures)

    def test_empty_score_list_fails_both_keys(self):
        from tests.eval.test_agent_regression import collect_sweep_failures

        failures, _ = collect_sweep_failures([_FakeResult("ex3", [])])
        assert any("intent_match did not run" in f for f in failures)
        assert any("tool_subset_match did not run" in f for f in failures)

    def test_all_present_and_passing_yields_no_failures(self):
        from tests.eval.test_agent_regression import collect_sweep_failures

        failures, scored = collect_sweep_failures([_both("a"), _both("b")])
        assert scored == 2
        assert failures == []

    def test_low_score_still_reported(self):
        from tests.eval.test_agent_regression import collect_sweep_failures

        failures, _ = collect_sweep_failures([_both("c", tools=0)])
        assert failures == ["c: tool_subset_match=0"]
