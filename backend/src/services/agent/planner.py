"""Adaptive planner for multi-step agent queries.

Estimates query complexity and generates an execution plan when the
query requires three or more tool calls. Uses structured output from
an LLM to produce validated Pydantic models.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Union

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.services.agent.llm_factory import build_lightweight_llm

logger = logging.getLogger(__name__)


ACTIONABLE_VERBS: frozenset[str] = frozenset(
    {
        "add", "ingest", "import", "save", "find", "search",
        "summarize", "summarise", "grab", "get", "show",
        "fetch", "download", "extract", "list", "create",
    }
)
_CONVERSATIONAL_STARTS: frozenset[str] = frozenset(
    {
        "hi", "hello", "hey", "thanks", "thank", "ok", "okay",
        "yes", "no", "sure", "what", "who", "when", "where",
        "why", "is", "are", "can", "could", "would", "will",
    }
)
_LEADING_PUNCTUATION = "?!,:"
_ARXIV_ID_RE = re.compile(r"\b\d{4}\.\d{4,5}\b")


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
    # ``tool`` is conceptually required but LLMs occasionally emit a final
    # "summarize / present results" step with no tool. Default to "" so the
    # whole plan doesn't fail validation; downstream consumers already treat
    # the plan as advisory and gracefully ignore empty tool names.
    tool: str = ""
    # Accept dict (preferred, structured) or str (LLM descriptive form).
    # Observed planner traces (019e1554) showed gpt-5 returning args_hint as
    # a string like "query='X'; max_results=5" which failed strict dict
    # validation with 5 errors. Accept both; downstream consumers normalize.
    args_hint: Union[dict, str] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)


class AgentPlan(BaseModel):
    """Full execution plan produced by the planner LLM."""

    steps: list[PlanStep]
    # Some models omit the top-level reasoning field even when explicitly
    # asked for it. Don't fail the whole plan over a missing rationale.
    reasoning: str = ""


# ---------------------------------------------------------------------------
# LLM construction (mirrors graph.py _build_llm with configurable model)
# ---------------------------------------------------------------------------


def _build_planner_llm():
    """Build a lightweight LLM for the planner.

    2048 tokens covers gpt-5-mini reasoning headroom for the complexity
    check structured-output call. The main plan generation uses the
    full-strength LLM via ``graph._build_llm`` (4096 tokens).
    """
    return build_lightweight_llm(max_tokens=2048)


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
        "Estimate the number of tool calls needed to answer the following "
        "user query.\n\n"
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
    structured_llm = llm.with_structured_output(AgentPlan, method="function_calling")

    prompt = (
        "Given the user query and available tools, generate a step-by-step "
        "execution plan.\n\n"
        f"Available tools: {', '.join(tool_names)}\n"
        f"Page context: {page_context}\n\n"
        f"User query: {query}\n\n"
        "For each step, specify:\n"
        "- step: sequential step number starting at 1\n"
        "- description: what this step does\n"
        "- tool: which tool to use — MUST be one of the available tools "
        "listed above; do not invent tool names; do not leave blank. "
        "If a step is purely summarisation with no tool call, omit it "
        "from the plan entirely.\n"
        "- args_hint: suggested arguments (can reference prior steps)\n"
        "- depends_on: list of step numbers this step depends on\n\n"
        "Also provide a top-level ``reasoning`` string explaining the "
        "overall approach (required)."
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

        # Plans only matter when there's a project context to organize the
        # multi-step output into (ingest → add to project → list). In chat
        # mode the agent runs ad-hoc and the plan is never executed —
        # generating one wastes 1-2s + a complexity LLM call. Skip.
        page_context = state.get("page_context") or {}
        if page_context.get("type") != "project":
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

        # Fast heuristic: skip complexity LLM call for obviously simple queries.
        # Bumped from 8 → 12 tokens after trace 019e1554 showed a 52s planner
        # spin on a query the LLM would have handled in one tool call anyway.
        # Tool-trigger detection runs first so short imperatives like
        # "Add arxiv 1706.03762 to my library" still reach the planner.
        words = query.split()
        first_word = words[0].lower().rstrip(_LEADING_PUNCTUATION) if words else ""
        needs_tool = (
            first_word in ACTIONABLE_VERBS
            or bool(_ARXIV_ID_RE.search(query))
        )

        if not needs_tool:
            if len(words) < 12:
                return {}
            if first_word in _CONVERSATIONAL_STARTS and len(words) < 18:
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
        # ``plan`` may also be ``None`` if the structured-output LLM call
        # returned an unparseable response without raising.
        if plan is None or not plan.steps:
            logger.info("Planner returned no plan; treating as no plan")
            return {}

        return {"plan": [step.model_dump() for step in plan.steps]}

    return planner_node
