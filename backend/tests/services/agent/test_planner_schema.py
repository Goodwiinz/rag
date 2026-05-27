"""Phase 1 regression — AgentPlan schema accepts dict OR str args_hint.

Trace 019e1555 showed gpt-5-2025-08-07 emitting ``args_hint`` as a
descriptive string (``"query='X'; max_results=5"``) instead of a dict,
which raised ``5 validation errors for AgentPlan``. The fix relaxes
``args_hint`` to ``Union[dict, str]``.
"""

from __future__ import annotations

import pytest

from src.services.agent.planner import AgentPlan, PlanStep


@pytest.mark.unit
def test_plan_step_accepts_dict_args_hint():
    step = PlanStep(
        step=1,
        description="search arxiv",
        tool="search_arxiv",
        args_hint={"query": "machine learning healthcare", "max_results": 5},
        depends_on=[],
    )
    assert isinstance(step.args_hint, dict)
    assert step.args_hint["query"] == "machine learning healthcare"


@pytest.mark.unit
def test_plan_step_accepts_string_args_hint():
    """LLMs frequently emit args_hint as a descriptive sentence — accept it."""
    step = PlanStep(
        step=1,
        description="search",
        tool="search_arxiv",
        args_hint="query='Privacy-preserving ML for healthcare'; max_results=5",
        depends_on=[],
    )
    assert isinstance(step.args_hint, str)
    assert "Privacy-preserving" in step.args_hint


@pytest.mark.unit
def test_plan_step_defaults_args_hint_and_depends_on():
    step = PlanStep(step=1, description="x", tool="search_arxiv")
    assert step.args_hint == {}
    assert step.depends_on == []


@pytest.mark.unit
def test_agent_plan_round_trip_with_mixed_args_hint_forms():
    plan = AgentPlan(
        steps=[
            PlanStep(
                step=1,
                description="search",
                tool="search_arxiv",
                args_hint="query='x'",
            ),
            PlanStep(
                step=2,
                description="ingest",
                tool="ingest_arxiv_papers",
                args_hint={"arxiv_ids": ["2303.15563"]},
                depends_on=[1],
            ),
        ],
        reasoning="r",
    )
    assert len(plan.steps) == 2
    dumped = [s.model_dump() for s in plan.steps]
    assert dumped[0]["args_hint"] == "query='x'"
    assert dumped[1]["args_hint"] == {"arxiv_ids": ["2303.15563"]}
