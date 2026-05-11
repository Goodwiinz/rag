"""Unit tests for the adaptive planner module.

Tests complexity checking, plan generation, and planner node behavior
with mocked LLM calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.services.agent.planner import (
    AgentPlan,
    ComplexityCheck,
    PlanStep,
    check_complexity,
    generate_plan,
    make_planner_node,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOL_NAMES = ["search_arxiv", "search_documents", "create_note", "ingest_arxiv"]
PAGE_CONTEXT = {"project_id": "proj-123", "document_id": "doc-456"}


def _mock_llm_structured(return_value):
    """Create a mock LLM that supports with_structured_output().ainvoke()."""
    mock_llm = MagicMock()
    structured = AsyncMock(return_value=return_value)
    mock_llm.with_structured_output.return_value.ainvoke = structured
    return mock_llm


# ---------------------------------------------------------------------------
# test_complexity_check_simple
# ---------------------------------------------------------------------------


class TestComplexityCheck:
    async def test_complexity_check_simple(self):
        """'Search for papers' should return step_count < 3."""
        mock_llm = _mock_llm_structured(ComplexityCheck(step_count=1))

        with patch(
            "src.services.agent.planner._build_planner_llm", return_value=mock_llm
        ):
            result = await check_complexity(
                "search for papers", TOOL_NAMES, PAGE_CONTEXT
            )

        assert result < 3

    async def test_complexity_check_complex(self):
        """Multi-step query should return step_count >= 3."""
        mock_llm = _mock_llm_structured(ComplexityCheck(step_count=5))

        with patch(
            "src.services.agent.planner._build_planner_llm", return_value=mock_llm
        ):
            result = await check_complexity(
                "Find transformer papers on arXiv, ingest them, "
                "then create a literature review note summarizing the key findings",
                TOOL_NAMES,
                PAGE_CONTEXT,
            )

        assert result >= 3


# ---------------------------------------------------------------------------
# test_generate_plan_returns_valid_plan
# ---------------------------------------------------------------------------


class TestGeneratePlan:
    async def test_generate_plan_returns_valid_plan(self):
        """generate_plan should return an AgentPlan with valid PlanSteps."""
        expected_plan = AgentPlan(
            steps=[
                PlanStep(
                    step=1,
                    description="Search arXiv for transformer papers",
                    tool="search_arxiv",
                    args_hint={"query": "transformer architectures"},
                    depends_on=[],
                ),
                PlanStep(
                    step=2,
                    description="Ingest the top result",
                    tool="ingest_arxiv",
                    args_hint={"paper_id": "<from step 1>"},
                    depends_on=[1],
                ),
                PlanStep(
                    step=3,
                    description="Create a summary note",
                    tool="create_note",
                    args_hint={"title": "Transformer Summary"},
                    depends_on=[2],
                ),
            ],
            reasoning="The user wants a multi-step research workflow.",
        )

        mock_llm = _mock_llm_structured(expected_plan)

        with patch(
            "src.services.agent.graph._build_llm", return_value=mock_llm
        ):
            result = await generate_plan(
                "Find transformer papers, ingest them, create a summary note",
                TOOL_NAMES,
                PAGE_CONTEXT,
            )

        assert isinstance(result, AgentPlan)
        assert len(result.steps) == 3
        for step in result.steps:
            assert isinstance(step, PlanStep)
            assert step.tool in TOOL_NAMES
            assert step.description
        assert result.reasoning


# ---------------------------------------------------------------------------
# test_planner_node_skips_if_plan_exists
# ---------------------------------------------------------------------------


class TestPlannerNode:
    async def test_planner_node_skips_if_plan_exists(self):
        """Node should return empty dict when state['plan'] is already populated."""
        node_fn = make_planner_node(TOOL_NAMES)

        state = {
            "messages": [HumanMessage(content="Do something complex")],
            "page_context": PAGE_CONTEXT,
            "plan": [{"step": 1, "tool": "search_arxiv", "description": "existing"}],
        }

        result = await node_fn(state, {})
        assert result == {}

    async def test_planner_node_skips_simple_queries(self):
        """Node should return empty dict when complexity step_count < 3."""
        mock_llm_complexity = _mock_llm_structured(ComplexityCheck(step_count=2))

        with patch(
            "src.services.agent.planner._build_planner_llm",
            return_value=mock_llm_complexity,
        ):
            node_fn = make_planner_node(TOOL_NAMES)

            state = {
                "messages": [HumanMessage(content="search for papers")],
                "page_context": PAGE_CONTEXT,
                "plan": [],
            }

            result = await node_fn(state, {})

        assert result == {}

    async def test_planner_node_generates_plan_for_complex_queries(self):
        """Node should generate and return plan for complex queries."""
        expected_plan = AgentPlan(
            steps=[
                PlanStep(
                    step=1,
                    description="Search arXiv",
                    tool="search_arxiv",
                    args_hint={"query": "transformers"},
                    depends_on=[],
                ),
                PlanStep(
                    step=2,
                    description="Ingest paper",
                    tool="ingest_arxiv",
                    args_hint={"paper_id": "123"},
                    depends_on=[1],
                ),
                PlanStep(
                    step=3,
                    description="Create note",
                    tool="create_note",
                    args_hint={"title": "Summary"},
                    depends_on=[2],
                ),
            ],
            reasoning="Multi-step research workflow",
        )

        mock_llm_complexity = _mock_llm_structured(ComplexityCheck(step_count=5))
        mock_llm_plan = _mock_llm_structured(expected_plan)

        with (
            patch(
                "src.services.agent.planner._build_planner_llm",
                return_value=mock_llm_complexity,
            ),
            patch(
                "src.services.agent.graph._build_llm",
                return_value=mock_llm_plan,
            ),
        ):
            node_fn = make_planner_node(TOOL_NAMES)

            state = {
                "messages": [
                    HumanMessage(
                        # Phase 1 raised the skip threshold to 12 words.
                        content=(
                            "Find recent transformer papers, ingest them into my "
                            "project, summarize each, and create a research note"
                        )
                    )
                ],
                "page_context": PAGE_CONTEXT,
                "plan": [],
            }

            result = await node_fn(state, {})

        assert "plan" in result
        assert len(result["plan"]) == 3
        assert result["plan"][0]["tool"] == "search_arxiv"
        assert result["plan"][2]["depends_on"] == [2]
