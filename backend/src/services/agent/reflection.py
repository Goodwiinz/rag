"""Reflection gate for agent response quality evaluation.

Uses a lightweight LLM to evaluate whether the agent's response
adequately addresses the user's request before proceeding to
memory save / END.  When quality is insufficient, the gate routes
back to the LLM node for another attempt (max 2 rounds).
"""

import asyncio
import logging
from typing import Any, Callable, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from src.services.agent.llm_factory import build_lightweight_llm

logger = logging.getLogger(__name__)

# Hard wall-clock cap for a single reflection LLM call. Prevents a hung
# Azure endpoint from blocking the whole agent turn.
_REFLECTION_LLM_TIMEOUT_SECONDS = 20.0

# Cache the reflection LLM at module scope. The settings/endpoint are
# resolved at import time once and reused across every reflection call,
# saving a ~50ms client-build round-trip per turn.
_REFLECTION_LLM = None
_REFLECTION_LLM_LOCK = asyncio.Lock()


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


class ReflectionResult(BaseModel):
    """Structured output from the reflection LLM."""

    passed: bool
    issues: list[str]
    severity: Literal["none", "minor", "major"]


# ---------------------------------------------------------------------------
# LLM construction
# ---------------------------------------------------------------------------


def _build_reflection_llm():
    """Return a cached lightweight LLM for reflection evaluation."""
    global _REFLECTION_LLM
    if _REFLECTION_LLM is not None:
        return _REFLECTION_LLM
    # 4096 tokens: gpt-5-mini reasoning tokens count against
    # max_completion_tokens. 512 cap caused LengthFinishReasonError in trace
    # 019e1555 (research_reflection_gate). See classifier.py for context.
    _REFLECTION_LLM = build_lightweight_llm(
        max_tokens=4096,
        request_timeout=_REFLECTION_LLM_TIMEOUT_SECONDS,
    )
    return _REFLECTION_LLM


# ---------------------------------------------------------------------------
# Intent-specific evaluation criteria
# ---------------------------------------------------------------------------


_INTENT_CRITERIA: dict[str, str] = {
    "research": (
        "Evaluate the assistant's response against these research-quality criteria:\n"
        "1. Did the assistant execute relevant tools (search, ingest, etc.)?\n"
        "2. Are any referenced document IDs real UUIDs (not fabricated)?\n"
        "3. Does the response fully address the user's request?\n"
        "4. Is the information specific rather than generic filler?"
    ),
    "writing": (
        "Evaluate the assistant's response against these writing-quality criteria:\n"
        "1. Are sources properly referenced or cited?\n"
        "2. Is the output substantive (not a vague outline or placeholder)?\n"
        "3. Does the format match what the user requested (draft, summary, note, etc.)?\n"
        "4. Is the content well-structured and coherent?"
    ),
}


def _criteria_for_intent(intent: str) -> str:
    """Return evaluation criteria for the given intent."""
    return _INTENT_CRITERIA.get(
        intent,
        (
            "Evaluate the assistant's response for general quality:\n"
            "1. Does the response address the user's question?\n"
            "2. Is the information accurate and helpful?\n"
            "3. Is the response complete?"
        ),
    )


# ---------------------------------------------------------------------------
# Core reflection function
# ---------------------------------------------------------------------------


_REFLECTION_SYSTEM_PROMPT = (
    "You are a response-quality evaluator for an AI research assistant. "
    "Your job is to decide whether the assistant's last response adequately "
    "addresses the user's original request.\n\n"
    "Return a structured evaluation with:\n"
    "- passed: true if the response is acceptable, false otherwise\n"
    "- issues: a list of specific problems found (empty if passed)\n"
    "- severity: 'none' if passed, 'minor' for small issues that don't need "
    "a redo, 'major' for significant problems that warrant another attempt\n\n"
    "{criteria}"
)


# Minimum content length for reflection to be worthwhile. Responses shorter
# than this with no tool calls are too trivial to benefit from critique.
_REFLECTION_MIN_CONTENT_CHARS = 200


def _last_ai_message(state: dict) -> AIMessage | None:
    """Return the most recent AIMessage in state, or None."""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage):
            return msg
    return None


def _should_skip_reflection(state: dict) -> tuple[bool, str]:
    """Decide whether to skip the reflection LLM call.

    Skip conditions (cheap, deterministic checks that avoid a ~944 token
    critique LLM call when the response is too trivial to benefit from
    one):

    1. Latest AIMessage content is shorter than
       ``_REFLECTION_MIN_CONTENT_CHARS`` AND has no tool_calls.
    2. ``state["tool_executions"]`` is empty AND the latest AIMessage has
       no tool_calls (no tools ran -> nothing tool-grounded to critique).

    Args:
        state: The current agent state dict.

    Returns:
        ``(skip, reason)`` — ``skip`` is True when the reflection LLM
        call should be bypassed; ``reason`` is a short human-readable
        string suitable for logging and test assertions.
    """
    last_ai = _last_ai_message(state)
    if last_ai is None:
        # Defer to existing missing-message handling in the node.
        return (False, "no-ai-message")

    tool_calls = getattr(last_ai, "tool_calls", None) or []
    has_tool_calls = bool(tool_calls)

    content = last_ai.content or ""
    content_len = len(content) if isinstance(content, str) else 0

    if not has_tool_calls and content_len < _REFLECTION_MIN_CONTENT_CHARS:
        return (
            True,
            f"short-output ({content_len} < {_REFLECTION_MIN_CONTENT_CHARS} chars, no tool_calls)",
        )

    tool_executions = state.get("tool_executions", []) or []
    if not has_tool_calls and not tool_executions:
        return (True, "no-tools (tool_executions empty, no tool_calls)")

    return (False, "")


async def reflect_on_response(
    last_ai_message: AIMessage,
    original_user_message: str,
    plan: Optional[list] = None,
    intent: str = "research",
) -> ReflectionResult:
    """Evaluate the quality of the agent's last response.

    Args:
        last_ai_message: The AI message to evaluate.
        original_user_message: The user's original request.
        plan: Optional advisory plan steps (for plan-aware evaluation).
        intent: The classified intent (research, writing, etc.).

    Returns:
        A ``ReflectionResult`` with pass/fail, issues, and severity.
    """
    llm = _build_reflection_llm()
    structured_llm = llm.with_structured_output(ReflectionResult)

    criteria = _criteria_for_intent(intent)
    system_text = _REFLECTION_SYSTEM_PROMPT.format(criteria=criteria)

    plan_text = ""
    if plan:
        plan_lines: list[str] = []
        for i, step in enumerate(plan):
            if isinstance(step, dict):
                summary = step.get("description") or step.get("step") or str(step)
            else:
                # Plan items can occasionally be raw strings (e.g. when an
                # external producer skips the dict envelope). Fall back to
                # ``str(step)`` instead of crashing with ``AttributeError``.
                summary = str(step)
            plan_lines.append(f"  {i + 1}. {summary}")
        plan_text = "\n\nAdvisory plan the agent was following:\n" + "\n".join(plan_lines)

    raw_content = last_ai_message.content
    if isinstance(raw_content, list):
        # Multimodal content (list of content blocks). Render only the text
        # parts so the reflection prompt stays human-readable.
        text_parts: list[str] = []
        for block in raw_content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
        rendered_content = "\n".join(text_parts) or "(no text content)"
    elif isinstance(raw_content, str) and raw_content:
        rendered_content = raw_content
    else:
        rendered_content = "(no content)"

    user_prompt = (
        f"## User's original request\n{original_user_message}\n\n"
        f"## Assistant's response\n{rendered_content}"
        f"{plan_text}"
    )

    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_prompt},
    ]

    result = await structured_llm.ainvoke(messages)
    return result


# ---------------------------------------------------------------------------
# Reflection gate factory
# ---------------------------------------------------------------------------


def make_reflection_gate(
    intent_filter: set[str] | None = None,
) -> tuple[Callable, Callable]:
    """Create the reflection gate node function and routing function.

    Args:
        intent_filter: Set of intents that should be reflected on.
            Defaults to ``{"research", "writing"}``.

    Returns:
        A tuple of ``(node_function, routing_function)`` suitable for
        use in a LangGraph StateGraph.
    """
    if intent_filter is None:
        intent_filter = {"research", "writing"}

    async def reflection_node(state: dict, config: RunnableConfig) -> dict:
        """Evaluate the last AI response and decide whether to revise.

        Skips reflection when:
        - The intent is not in the filter set.
        - The reflection count has reached the maximum (2).
        - The latest AIMessage is too trivial to critique (see
          ``_should_skip_reflection``): short content with no tool_calls,
          or no tools were executed and no pending tool_calls.
        """
        intent = state.get("intent", "general")
        current_count = state.get("reflection_count", 0)

        # Skip if intent not in filter
        if intent not in intent_filter:
            return {"reflection_count": current_count}

        # Skip if max rounds reached
        if current_count >= 2:
            return {"reflection_count": current_count}

        # Cheap pre-LLM gate: skip critique for trivial / tool-less turns.
        skip, reason = _should_skip_reflection(state)
        if skip:
            logger.debug("Reflection skipped: %s", reason)
            return {
                "reflection_count": current_count,
                "_reflection_result": ReflectionResult(
                    passed=True, issues=[], severity="none"
                ),
            }

        # Find last AI message and most recent user message (the request
        # being addressed in this turn). The reverse scan intentionally
        # picks the latest HumanMessage so multi-turn conversations
        # critique the response against the current turn's question, not
        # the very first one.
        last_ai_message: AIMessage | None = None
        original_user_message: str = ""

        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and last_ai_message is None:
                last_ai_message = msg
            if isinstance(msg, HumanMessage) and not original_user_message:
                original_user_message = msg.content
            if last_ai_message is not None and original_user_message:
                break

        if last_ai_message is None or not original_user_message:
            logger.debug("Reflection skipped: missing AI or user message")
            return {"reflection_count": current_count}

        plan = state.get("plan")

        try:
            result = await asyncio.wait_for(
                reflect_on_response(
                    last_ai_message=last_ai_message,
                    original_user_message=original_user_message,
                    plan=plan,
                    intent=intent,
                ),
                timeout=_REFLECTION_LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Reflection LLM timed out after %.1fs; proceeding without revision",
                _REFLECTION_LLM_TIMEOUT_SECONDS,
            )
            # Don't burn a retry budget slot for an infrastructure failure.
            return {
                "reflection_count": current_count,
                "_reflection_result": ReflectionResult(
                    passed=True, issues=[], severity="none"
                ),
            }
        except Exception as e:
            logger.warning("Reflection failed, proceeding anyway: %s", e)
            # Don't burn a retry budget slot — let the agent recover on the
            # next turn with full budget, and clear any stale result so the
            # router defaults to ``proceed``.
            return {
                "reflection_count": current_count,
                "_reflection_result": ReflectionResult(
                    passed=True, issues=[], severity="none"
                ),
            }

        return {
            "reflection_count": current_count + 1,
            "_reflection_result": result,
        }

    def reflection_route(state: dict) -> str:
        """Route based on reflection result.

        Returns:
            ``"proceed"`` — continue to memory_save_node / END.
            ``"revise"`` — loop back to llm_node for another attempt.
        """
        result: ReflectionResult | None = state.get("_reflection_result")

        if result is None:
            return "proceed"

        if result.passed:
            return "proceed"

        if result.severity == "minor":
            return "proceed"

        # Major severity: route to revise if we still have budget
        current_count = state.get("reflection_count", 0)
        if result.severity == "major" and current_count < 2:
            return "revise"

        return "proceed"

    return reflection_node, reflection_route
