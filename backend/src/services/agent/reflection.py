"""Reflection gate for agent response quality evaluation.

Uses a lightweight LLM (gpt-4o-mini) to evaluate whether the agent's
response adequately addresses the user's request before proceeding
to memory save / END.  When quality is insufficient, the gate routes
back to the LLM node for another attempt (max 2 rounds).
"""

import logging
from typing import Any, Callable, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from src.core.config import get_settings

logger = logging.getLogger(__name__)


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
    """Build a lightweight LLM (gpt-4o-mini) for reflection evaluation.

    Follows the same Azure/OpenAI endpoint resolution as ``_build_llm``
    in ``graph.py`` but forces model=gpt-4o-mini and temperature=0.
    """
    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = (
        settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    )
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI endpoint and API key must be configured for reflection LLM. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    def _is_openai_compatible(ep: str) -> bool:
        return "/v1" in ep or "services.ai.azure.com" in ep

    if _is_openai_compatible(endpoint):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=api_key,
            base_url=endpoint,
            temperature=0,
            max_tokens=512,
        )
    else:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment="gpt-4o-mini",
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            temperature=0,
            max_tokens=512,
        )


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
        plan_items = "\n".join(
            f"  {i + 1}. {step.get('step', step)}" for i, step in enumerate(plan)
        )
        plan_text = f"\n\nAdvisory plan the agent was following:\n{plan_items}"

    user_prompt = (
        f"## User's original request\n{original_user_message}\n\n"
        f"## Assistant's response\n{last_ai_message.content or '(no content)'}"
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
        """
        intent = state.get("intent", "general")
        current_count = state.get("reflection_count", 0)

        # Skip if intent not in filter
        if intent not in intent_filter:
            return {"reflection_count": current_count}

        # Skip if max rounds reached
        if current_count >= 2:
            return {"reflection_count": current_count}

        # Find last AI message and original user message
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
            result = await reflect_on_response(
                last_ai_message=last_ai_message,
                original_user_message=original_user_message,
                plan=plan,
                intent=intent,
            )
        except Exception as e:
            logger.warning("Reflection failed, proceeding anyway: %s", e)
            return {"reflection_count": current_count + 1}

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
