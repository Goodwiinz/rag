"""Adaptive planner for multi-step agent queries.

Estimates query complexity and generates an execution plan when the
query requires three or more tool calls. Uses structured output from
an LLM to produce validated Pydantic models.
"""

import asyncio
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
# Trace 019e69f4: complexity LLM returned >=3 for "Add arXiv X to project Y",
# triggering a 25s generate_plan call on the full model-router deployment.
# The research LLM handles this in 1-2 tool rounds without a formal plan.
_SIMPLE_ADD_TARGET_RE = re.compile(
    r"\b(project|library|collection)\b", re.IGNORECASE
)

# Wall-clock cap for planner LLM calls. Keeps the node inside the ~30s HTTP
# budget when complexity + plan generation run back-to-back (trace 019e69f4).
PLANNER_LLM_TIMEOUT_SECONDS = 20


def _is_simple_add_flow(query: str) -> bool:
    """Return True for single-target ingest/add imperatives.

    Example: "Add arXiv 2401.12345 to project My Project"
    """
    words = query.split()
    if not words:
        return False
    first_word = words[0].lower().rstrip(_LEADING_PUNCTUATION)
    if first_word not in {"add", "ingest", "import", "save"}:
        return False
    if not _ARXIV_ID_RE.search(query):
        return False
    if not _SIMPLE_ADD_TARGET_RE.search(query):
        return False
    return len(words) <= 15


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


def _build_planner_llm(max_tokens: int = 2048):
    """Build a lightweight LLM for planner structured-output calls."""
    return build_lightweight_llm(max_tokens=max_tokens)


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

    Uses the lightweight deployment with structured output. Trace 019e69f4
    showed the full model-router call stalling ~25s on a simple add-to-project
    query; gpt-5-mini handles plan JSON fine and stays inside the HTTP budget.
    Returns a validated AgentPlan with ordered steps.
    """
    llm = _build_planner_llm(max_tokens=4096)
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


def render_plan_directive(plan: list[dict] | None) -> str | None:
    """Render the planner's plan into an execution directive for an executor LLM.

    The planner writes its plan to ``state["plan"]``, but the executor LLM
    nodes historically only ever read ``state["messages"]`` — so the plan was
    consumed only by the reflection gate and ledger and never reached the
    model that acts. Trace 019ea8f0 showed the planner correctly choosing
    ``create_draft`` → ``create_project_note`` while the executor ignored it
    and refused, demanding document_id / arXiv IDs the user can't supply.
    Injecting this directive into the executor prompt closes the
    plan→execute handoff. Shared by writing/research/data subgraphs and the
    main ``llm_node`` so the four executors behave consistently.
    """
    if not plan:
        return None
    lines: list[str] = []
    for step in plan:
        tool = (step.get("tool") or "").strip()
        desc = (step.get("description") or "").strip()
        if not desc:
            continue
        if tool and tool.upper() != "N/A":
            args = step.get("args_hint")
            arg_str = f"  args: {args}" if args else ""
            lines.append(f"{step.get('step', '?')}. [{tool}] {desc}{arg_str}")
        else:
            lines.append(f"{step.get('step', '?')}. {desc}")
    if not lines:
        return None
    plan_block = "\n".join(lines)
    return (
        "ACTIVE PLAN (produced by the planner for this turn — follow it). "
        "Execute the next incomplete step now by emitting the listed tool "
        "call. Do NOT ask the user for document_ids or arXiv IDs that you can "
        "resolve yourself via the available ingest/search tools — search or "
        "ingest first, then continue.\n"
        f"{plan_block}"
    )


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

        # Trace 019e6a08: complexity check alone took ~17s on dev; adding
        # generate_plan pushed the turn past the ~30s HTTP cancel budget.
        # Simple ingest-and-add imperatives need neither complexity nor plan.
        if _is_simple_add_flow(query):
            logger.info("Skipping planner entirely for simple add flow")
            return {}

        # 2. Check complexity
        try:
            step_count = await asyncio.wait_for(
                check_complexity(query, tool_names, page_context),
                timeout=PLANNER_LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Complexity check exceeded %ds; skipping planner",
                PLANNER_LLM_TIMEOUT_SECONDS,
            )
            return {}
        except Exception:
            logger.warning("Complexity check failed, skipping planner", exc_info=True)
            return {}

        if step_count < 3:
            return {}

        # 3. Generate plan
        try:
            plan = await asyncio.wait_for(
                generate_plan(query, tool_names, page_context),
                timeout=PLANNER_LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Plan generation exceeded %ds; skipping planner",
                PLANNER_LLM_TIMEOUT_SECONDS,
            )
            return {}
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
