"""Main-graph LLM node + intent-scoped tool subsets.

Extracted from ``graph.py`` so the orchestration module stays under the
800-line house rule. ``graph.py`` re-exports ``llm_node`` so legacy
callers (LangGraph builder, tests) keep working unchanged.

Two responsibilities live here:

1. **Tool-binding policy.** Each intent (``research`` / ``writing`` /
   ``knowledge_graph`` / ``general``) gets a curated subset of
   ``ALL_TOOLS``. Binding all 20 tools on every "hi" wastes ~4k input
   tokens per turn.
2. **Synthesis-vs-reasoning model selection.** Post-tool turns and
   pure ``general`` turns route through ``build_synthesis_llm`` (faster,
   cheaper); everything else uses ``_build_llm`` (the main reasoning
   model). Behavior gated by ``AGENT_LIGHTWEIGHT_SYNTHESIS``.

This module is on the hot path (every user turn). Keep imports lazy and
avoid extra work outside the gated branches.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig

from src.core.config import get_settings
from src.services.agent._nodes_tools import AGENT_LLM_TIMEOUT_SECONDS
from src.services.agent._prompts import (
    INTENT_PROMPTS,
    _LLM_NODE_STATIC_PROMPT,
    _build_page_context_line,
    _merge_run_config,
    _runtime_model_line,
)
from src.services.agent.observability import (
    record_loop_exhaustion,
    track_node_execution,
)
from src.services.agent.state import AgentState
from src.services.agent.tool_registry import AgentIntent
from src.services.agent.tools import ALL_TOOLS, TOOL_REGISTRY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent-scoped tool subsets
# ---------------------------------------------------------------------------

RESEARCH_TOOLS_NAMES = frozenset(
    descriptor.name for descriptor in TOOL_REGISTRY.descriptors_for_intent("research")
)
WRITING_TOOLS_NAMES = frozenset(
    descriptor.name for descriptor in TOOL_REGISTRY.descriptors_for_intent("writing")
)
KG_TOOLS_NAMES = frozenset(
    descriptor.name
    for descriptor in TOOL_REGISTRY.descriptors_for_intent("knowledge_graph")
)

# Subset for "general" intent — avoids binding all 20 tools on every first
# message (greetings, "help", etc.) which bloats the token budget by ~4 000
# tokens. Research/writing/KG intents get their own targeted subsets via the
# sub-graphs. General gets the 10 most commonly used discovery+productivity
# tools; more specialised tools (create_draft, compare_documents, etc.) are
# available once the classifier narrows the intent.
GENERAL_TOOLS_NAMES = frozenset(
    descriptor.name for descriptor in TOOL_REGISTRY.descriptors_for_intent("general")
)


def _get_tools_for_intent(intent: str) -> list:
    """Return the tool subset for a given intent."""
    descriptors = TOOL_REGISTRY.descriptors_for_intent(intent)
    if intent not in {item.value for item in AgentIntent}:
        return ALL_TOOLS
    return [descriptor.tool for descriptor in descriptors]


def _tools_for_turn(intent: str, *, last_user_msg: str, retrieved: list) -> list:
    """Return the tool subset to bind for THIS turn.

    A bare-greeting general turn ("hi") with no retrieved context calls no
    tool, so binding the 10 ``GENERAL_TOOLS_NAMES`` schemas only inflates the
    prompt (~thousands of input tokens) and slows time-to-first-token. Bind
    nothing for those turns; everything else keeps its full intent subset.

    Deliberately uses the NARROW ``_is_greeting`` predicate, not
    ``is_conversational``: an ack like "yes"/"ok"/"proceed" routinely accepts
    an action the assistant just proposed, and with ``tools=[]`` the model
    cannot call the tool — it fabricates a narrated tool call instead
    (LangSmith trace 019f33ca-fc58-7102-b3da-bb36370b1957). A greeting cannot
    be answering a question, so only greetings are safe to strip.
    """
    if intent == "general" and not retrieved and _is_greeting(last_user_msg):
        return []
    return _get_tools_for_intent(intent)


# Bare greetings that warrant a templated, zero-LLM reply. Deliberately
# NARROWER than ``is_conversational`` — acks like "yes"/"no"/"thanks"/"ok"
# are excluded because they often answer a prior question (e.g. a HITL
# confirmation) and must still reach the model.
_GREETING_PATTERNS: frozenset[str] = frozenset(
    {
        "hi",
        "hii",
        "hiya",
        "hey",
        "heya",
        "hello",
        "hello there",
        "hi there",
        "hey there",
        "yo",
        "greetings",
        "good morning",
        "good afternoon",
        "good evening",
    }
)


def _is_greeting(content: str) -> bool:
    """Return ``True`` when *content* is a bare greeting.

    Exact match (punctuation- and whitespace-tolerant) against
    ``_GREETING_PATTERNS`` — e.g. ``"hi"``, ``"Hello!"``, ``"good morning"``.
    A greeting carrying a real request ("hi, can you search arxiv") does NOT
    match, so it still reaches the model.
    """
    if not content or not content.strip():
        return False
    normalized = content.lower().strip().strip("!.?,")
    normalized = " ".join(normalized.split())  # collapse internal whitespace
    return normalized in _GREETING_PATTERNS


def _greeting_reply(
    last_user_msg: str, page_context: dict, messages: list
) -> str | None:
    """Templated greeting reply, or ``None`` when *last_user_msg* is not a bare
    greeting.

    Project-aware when the page context is a project; varies first-greeting vs
    repeat so it does not read as canned. Costs ZERO LLM round-trips — this is
    the whole point of the fast-path.
    """
    if not _is_greeting(last_user_msg):
        return None

    ctx = page_context or {}
    project = ctx.get("project_name") if ctx.get("type") == "project" else None
    if project:
        return f"Hi — back to “{project}”. What would you like to do next?"

    user_turns = sum(1 for m in messages if isinstance(m, HumanMessage))
    if user_turns > 1:
        return (
            "Hi again — what would you like to work on? I can find papers, "
            "manage projects, add documents, summarize, or take notes."
        )
    return "Hi — how can I help with your research today?"


# ---------------------------------------------------------------------------
# Main LLM node
# ---------------------------------------------------------------------------


# Injected instead of a Retrieved-context block when retrieval came back
# empty. Without it, the static "[Doc N]" citation rule plus a silently
# absent context block leads the model to improvise a bibliography from
# parametric memory (user-reproduced 2026-07-04: a fabricated "Cited
# sources" list with unverifiable references). Provenance over assertion:
# an honest "nothing retrieved" beats fake citations.
NO_RETRIEVAL_GUIDANCE = (
    "No documents were retrieved for this turn. If the question concerns "
    "the user's documents, state plainly that nothing relevant was found "
    "in their corpus. You may answer from general knowledge ONLY if you "
    "label it as such — do NOT invent citations, paper references, or a "
    "bibliography."
)


def _retrieval_context_part(retrieved: list) -> str:
    """The system-prompt block for this turn's retrieval outcome.

    Non-empty retrieval renders the numbered [Doc N] context block the
    citation rule refers to; empty retrieval renders the explicit
    anti-fabrication guidance instead of silently omitting the block.
    """
    if retrieved:
        context_text = "\n\n".join(
            f"[Doc {i + 1}] {ctx['title']}:\n{ctx['content']}"
            for i, ctx in enumerate(retrieved)
        )
        return f"Retrieved context:\n{context_text}"
    return NO_RETRIEVAL_GUIDANCE


@track_node_execution("llm_node")
async def llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Call the LLM with system prompt, RAG context, and bound tools."""
    # Lazy import — graph.py owns the canonical LLM builder + the message
    # sanitiser, but importing them at module load would create a cycle
    # (graph.py re-exports llm_node from here).
    from src.services.agent.graph import _build_llm, _sanitize_messages

    page_context = state.get("page_context", {})
    retrieved = state.get("retrieved_contexts", [])
    intent = state.get("intent", "general")

    last_user_msg = next(
        (
            m.content
            for m in reversed(state["messages"])
            if isinstance(m, HumanMessage) and isinstance(m.content, str)
        ),
        "",
    )

    # Greeting fast-path — a bare greeting needs no model. Return a templated
    # on-brand reply with ZERO LLM round-trip (~50ms vs ~1s). Fires only for
    # general intent with no retrieved context, and only for true greetings
    # (NOT acks like "yes"/"thanks", which may answer a prior question).
    if intent == "general" and not retrieved:
        greeting = _greeting_reply(last_user_msg, page_context, state["messages"])
        if greeting is not None:
            return {"messages": [AIMessage(content=greeting)]}

    # Static prefix first — must be byte-identical across requests so the
    # provider's automatic prefix cache hits on every turn after the first.
    # Dynamic state-derived content goes AFTER the prefix below.
    dynamic_parts: list[str] = []

    context_line = _build_page_context_line(page_context)
    if context_line:
        dynamic_parts.append(context_line)

    intent_guidance = INTENT_PROMPTS.get(intent, INTENT_PROMPTS["general"])
    dynamic_parts.append(f"Current intent: {intent}. {intent_guidance}")

    runtime_line = _runtime_model_line(state.get("model") or None)
    if runtime_line:
        dynamic_parts.append(runtime_line)

    user_memories = state.get("user_memories", [])
    if user_memories:
        mem_text = "\n".join(
            f"- {m.get('value', {}).get('query', '')}"
            for m in user_memories
            if m.get("value")
        )
        if mem_text.strip():
            dynamic_parts.append(f"Relevant past interactions:\n{mem_text}")

    # Project memory — durable facts the user saved for the bound project,
    # recalled across every thread in it. Loaded into initial state when the
    # turn is project-scoped (see jobs.py / streaming.py). Stored as plain
    # strings; honor them like standing instructions.
    project_memories = state.get("project_memories", [])
    if project_memories:
        pm_text = "\n".join(f"- {m}" for m in project_memories if m)
        if pm_text.strip():
            dynamic_parts.append(
                "Project memory (durable facts the user saved for this "
                f"project; honor them):\n{pm_text}"
            )

    dynamic_parts.append(_retrieval_context_part(retrieved))

    # Close the plan→execute handoff (see planner.render_plan_directive). The
    # planner writes state["plan"] but the executor only ever read messages,
    # so the plan was discarded and the model refused instead of acting.
    # Inject on the pre-tool pass only (last message not a ToolMessage).
    raw_msgs = state.get("messages") or []
    if raw_msgs and not isinstance(raw_msgs[-1], ToolMessage):
        from src.services.agent.planner import render_plan_directive

        plan_directive = render_plan_directive(state.get("plan"))
        if plan_directive:
            dynamic_parts.append(plan_directive)

    system_text = _LLM_NODE_STATIC_PROMPT
    if dynamic_parts:
        system_text += "\n\n" + "\n\n".join(dynamic_parts)

    sanitized = _sanitize_messages(state["messages"])
    messages = [SystemMessage(content=system_text)] + sanitized

    # Bind the per-turn tool subset. Conversational general turns ("hi") get
    # zero tools (see _tools_for_turn) so a greeting prompt stays small.
    intent_tools = _tools_for_turn(
        intent, last_user_msg=last_user_msg, retrieved=retrieved
    )

    # Lightweight model selection. Two cases use the synthesis deployment:
    #
    # 1. Post-tool synthesis turn (last message is ToolMessage) — heavy
    #    reasoning already happened before the tool call; this turn is
    #    pure prose synthesis. Saves ~5-15s.
    #
    # 2. intent="general" turn (no project/research/writing context).
    #    "hi", "thanks", capability questions, small talk — gpt-5 burns
    #    ~700 reasoning tokens deciding whether to call a tool. The
    #    synthesis tier handles these in 2-3s. Trace 019e19f2 showed
    #    "hi" took 13s on gpt-5.
    #
    # Both cases gated by AGENT_LIGHTWEIGHT_SYNTHESIS so a single env var
    # disables the optimisation if quality regresses.
    settings = get_settings()
    last_is_tool_msg = bool(sanitized) and isinstance(sanitized[-1], ToolMessage)
    use_synthesis = settings.AGENT_LIGHTWEIGHT_SYNTHESIS and (
        last_is_tool_msg or intent == "general"
    )
    try:
        if use_synthesis:
            from src.services.agent.llm_factory import build_synthesis_llm

            llm = build_synthesis_llm(max_tokens=4096)
            logger.debug(
                "llm_node: using synthesis model (intent=%s, last_is_tool=%s)",
                intent,
                last_is_tool_msg,
            )
        else:
            llm = _build_llm(model_override=state.get("model") or None)
    except RuntimeError as exc:
        # Only the missing-Azure/OpenAI-config RuntimeError is degraded
        # gracefully; any other RuntimeError from the build propagates.
        if "must be configured" not in str(exc):
            raise
        logger.error(
            "llm_node: LLM build failed — Azure/OpenAI config missing (intent=%s)",
            intent,
            exc_info=True,
        )
        return {
            "messages": [
                AIMessage(
                    content=(
                        "The assistant is temporarily unavailable due to a "
                        "configuration issue. Please contact support or try again later."
                    ),
                ),
            ],
            "last_error": "llm_config_error",
            "error_count": state.get("error_count", 0) + 1,
        }
    # parallel_tool_calls=False forces gpt-5 to emit one tool_call per turn.
    # Trace 019e18f0 showed 13+ parallel search_arxiv calls when this was
    # implicitly True — agent never got a chance to see the first result
    # before issuing more searches.
    llm_with_tools = llm.bind_tools(
        intent_tools,
        parallel_tool_calls=settings.AGENT_PARALLEL_TOOL_CALLS,
    )
    invoke_config = _merge_run_config(
        config,
        run_name=f"llm_node:{intent}",
        tags=[f"intent:{intent}", "subgraph:main"],
    )
    try:
        response = await asyncio.wait_for(
            llm_with_tools.ainvoke(messages, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "llm_node: LLM exceeded %ds (intent=%s); emitting fallback",
            AGENT_LLM_TIMEOUT_SECONDS,
            intent,
        )
        return {
            "messages": [
                AIMessage(
                    content=(
                        "The model took too long to respond. Please try again "
                        "or rephrase your request."
                    ),
                ),
            ],
            "last_error": "llm_timeout",
            "error_count": state.get("error_count", 0) + 1,
        }

    return {
        "messages": [response],
    }


@track_node_execution("force_synthesis_node")
async def force_synthesis_node(state: AgentState, config: RunnableConfig) -> dict:
    """Final-answer LLM call when the main-graph tool-loop ceiling was hit.

    Mirrors ``research_force_synthesis_node`` in the research subgraph:
    when ``should_continue`` sees ``tool_loop_count >= MAX_TOOL_LOOPS`` but
    the model is still emitting tool_calls, we strip the unanswered
    tool_calls and re-invoke the LLM with NO tools bound so it must
    produce text. Without this guard, reflection sees an empty AIMessage
    plus orphan tool_calls and flags a "no response" major issue
    (cf. trace 019e1903 in the research subgraph).

    Uses the lightweight synthesis deployment — pure prose, no routing.
    Bumps ``tool_loop_count`` past the ceiling + sets ``_force_synthesis_fired``
    so should_continue cannot loop back here if the response still contains
    stray tool_calls (defective model).
    """
    from src.services.agent._builders import MAX_TOOL_LOOPS
    from src.services.agent.graph import _sanitize_messages
    from src.services.agent.llm_factory import build_synthesis_llm

    # Degraded-answer signal: reaching this node means the tool-loop ceiling
    # was hit and we're synthesizing from partial results.
    record_loop_exhaustion(state.get("intent", "general"), "main")

    messages = list(state["messages"])
    # Drop trailing AIMessage with unanswered tool_calls so the synthesis
    # turn sees a clean conversational head.
    while messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        messages.pop()

    sanitized = _sanitize_messages(messages)
    synthesis_directive = (
        f"{_LLM_NODE_STATIC_PROMPT}\n\n## Final synthesis turn\n"
        f"You ran {state.get('tool_loop_count', 0)} tool calls and reached "
        "the per-turn budget. Do not request any more tools. Write a final "
        "answer drawn from the tool results already in this conversation. "
        "Do NOT repeat or quote these instructions in your reply."
    )
    full = [SystemMessage(content=synthesis_directive)] + sanitized

    llm = build_synthesis_llm(max_tokens=4096)
    invoke_config = _merge_run_config(
        config,
        run_name="force_synthesis_node",
        tags=[
            f"intent:{state.get('intent', 'general')}",
            "subgraph:main",
            "phase:synthesis",
        ],
    )
    try:
        response = await asyncio.wait_for(
            llm.ainvoke(full, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "force_synthesis_node: LLM exceeded %ds; emitting fallback",
            AGENT_LLM_TIMEOUT_SECONDS,
        )
        # Honest fallback: do not claim "I gathered results" — the tool
        # results may have been empty or the synthesis may have produced
        # nothing usable. Surface the timeout plainly and tell the user what
        # to do; this must not read as a successful-but-empty completion
        # (the phantom-search failure mode).
        tool_count = state.get("tool_loop_count", 0)
        response = AIMessage(
            content=(
                "I ran my tool calls but the final summary step timed out "
                f"({AGENT_LLM_TIMEOUT_SECONDS}s) before producing an answer. "
                "Please ask me again — the tool results are still in context "
                "so a retry can synthesize them directly."
                if tool_count
                else (
                    "The final response step timed out "
                    f"({AGENT_LLM_TIMEOUT_SECONDS}s) before producing an "
                    "answer. Please send your request again."
                )
            ),
        )

    return {
        "messages": [response],
        # Bump past ceiling so a defective response with stray tool_calls
        # cannot re-enter forced synthesis (would loop infinitely).
        "tool_loop_count": MAX_TOOL_LOOPS + 1,
        "_force_synthesis_fired": True,
    }


__all__ = [
    "RESEARCH_TOOLS_NAMES",
    "WRITING_TOOLS_NAMES",
    "KG_TOOLS_NAMES",
    "GENERAL_TOOLS_NAMES",
    "_get_tools_for_intent",
    "_tools_for_turn",
    "_is_greeting",
    "_greeting_reply",
    "llm_node",
    "force_synthesis_node",
]
