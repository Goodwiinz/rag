"""Adaptive planner for multi-step agent queries.

Estimates query complexity and generates an execution plan when the
query requires three or more tool calls. Uses structured output from
an LLM to produce validated Pydantic models.
"""

import logging
from typing import Any, Callable, Dict, List

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from src.services.agent.llm_factory import build_lightweight_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ComplexityCheck(BaseModel):
    """Estimated number of tool calls a query requires."""

    step_count: int


class PlanStep(BaseModel):
    """A single step in an agent execution plan."""

    step: int
    description: str
    tool: str
    args_hint: dict
    depends_on: list[int]


class AgentPlan(BaseModel):
    """Full execution plan produced by the planner LLM."""

    steps: list[PlanStep]
    reasoning: str


# ---------------------------------------------------------------------------
# LLM construction (mirrors graph.py _build_llm with configurable model)
# ---------------------------------------------------------------------------


def _build_planner_llm():
    """Build a lightweight LLM for the planner."""
    return build_lightweight_llm(max_tokens=1024)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


async def check_complexity(
    query: str, tool_names: list[str], page_context: dict
) -> int:
    """Estimate the number of tool calls needed for a query.

    Uses the lightweight model with structured output for fast, cheap estimation.
    Returns the estimated step_count.
    """
    llm = _build_planner_llm()
    structured_llm = llm.with_structured_output(ComplexityCheck)

    prompt = (
        "You are an AI planning assistant. Estimate the number of tool calls "
        "needed to answer the following user query.\n\n"
        f"Available tools: {', '.join(tool_names)}\n"
        f"Page context: {page_context}\n\n"
        f"User query: {query}\n\n"
        "Return only the estimated step_count (integer)."
    )

    result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
    return result.step_count


async def generate_plan(
    query: str, tool_names: list[str], page_context: dict
) -> AgentPlan:
    """Generate an execution plan for a complex query.

    Uses the main chat model (needs reasoning quality) with structured output.
    Returns a validated AgentPlan with ordered steps.
    """
    from src.services.agent.graph import _build_llm

    llm = _build_llm()
    structured_llm = llm.with_structured_output(AgentPlan)

    prompt = (
        "You are an AI planning assistant. Given the user query and available "
        "tools, generate a step-by-step execution plan.\n\n"
        f"Available tools: {', '.join(tool_names)}\n"
        f"Page context: {page_context}\n\n"
        f"User query: {query}\n\n"
        "For each step, specify:\n"
        "- step: sequential step number starting at 1\n"
        "- description: what this step does\n"
        "- tool: which tool to use (must be one of the available tools)\n"
        "- args_hint: suggested arguments (can reference prior steps)\n"
        "- depends_on: list of step numbers this step depends on\n\n"
        "Also provide reasoning explaining the overall approach."
    )

    result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
    return result


# ---------------------------------------------------------------------------
# Graph node factory
# ---------------------------------------------------------------------------


def make_planner_node(
    tool_names: list[str],
) -> Callable:
    """Return a LangGraph node function that conditionally plans.

    The returned async function:
    1. Skips if ``state["plan"]`` is already populated.
    2. Checks complexity -- if step_count < 3, skips (simple query).
    3. Generates a full plan and returns it as serialized dicts.
    """

    async def planner_node(state: Dict[str, Any], config: RunnableConfig) -> dict:
        # Skip if a plan already exists for THIS turn. ``preprocessing_node``
        # clears stale plans at the start of every new user turn, so any
        # ``state["plan"]`` we see here was produced by an earlier pass
        # within the current turn (e.g. a revise loop) and must be reused.
        if state.get("plan"):
            return {}

        # Extract the last user message for planning
        messages = state.get("messages", [])
        query = ""
        for msg in reversed(messages):
            content = getattr(msg, "content", None)
            if content and (
                isinstance(msg, HumanMessage) or getattr(msg, "type", None) == "human"
            ):
                query = content
                break

        if not query:
            return {}

        # Fast heuristic: skip complexity LLM call for obviously simple queries
        words = query.split()
        if len(words) < 8:
            return {}
        conversational_starts = {
            "hi", "hello", "hey", "thanks", "thank", "ok", "okay",
            "yes", "no", "sure", "what", "who", "when", "where",
            "why", "is", "are", "can", "could", "would", "will",
        }
        if words[0].lower().rstrip("?!,") in conversational_starts and len(words) < 15:
            return {}

        page_context = state.get("page_context", {})

        # 2. Check complexity
        try:
            step_count = await check_complexity(query, tool_names, page_context)
        except Exception:
            logger.warning("Complexity check failed, skipping planner", exc_info=True)
            return {}

        if step_count < 3:
            return {}

        # 3. Generate plan
        try:
            plan = await generate_plan(query, tool_names, page_context)
        except Exception:
            logger.warning("Plan generation failed, skipping planner", exc_info=True)
            return {}

        # Defensive guard: an empty plan adds no value but does occupy the
        # ``plan`` slot, which would skip planning on subsequent turns and
        # confuse the reflection-prompt rendering. Treat it as no-plan.
        if not plan.steps:
            logger.info("Planner returned 0-step plan; treating as no plan")
            return {}

        return {"plan": [step.model_dump() for step in plan.steps]}

    return planner_node
