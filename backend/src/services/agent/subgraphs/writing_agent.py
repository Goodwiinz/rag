"""Writing Agent sub-graph.

Specialized for content creation, summarization, and bibliography tasks.
Tools: create_draft, create_project_note, export_bibliography,
       summarize_document, compare_documents
"""

import asyncio
import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from src.services.agent.compactor import make_compactor_node
from src.services.agent.graph import _sanitize_messages
from src.services.agent.planner import make_planner_node
from src.services.agent.reflection import make_reflection_gate
from src.services.agent.state import AgentState
from src.services.agent.tools import (
    compare_documents,
    create_draft,
    create_project_note,
    export_bibliography,
    ingest_arxiv_papers,
    search_arxiv,
    summarize_document,
)

logger = logging.getLogger(__name__)

WRITING_TOOLS = [
    create_draft,
    create_project_note,
    export_bibliography,
    summarize_document,
    compare_documents,
    # search_arxiv (read-only) lets the agent resolve a paper given by TITLE to
    # an arXiv id, so "make notes for <titles>" no longer dead-ends asking the
    # user for ids it can find itself (trace 685b2fd1). Resolve → ingest →
    # summarize/note.
    search_arxiv,
    # ingest_arxiv_papers brings a paper into the library so it can be
    # summarized/noted: used after search_arxiv resolves a title, when the user
    # supplies an arXiv id directly, or as the recovery path when
    # summarize_document / compare_documents return error_type="recoverable"
    # with suggestion="ingest_arxiv_papers". Destructive — HITL-gated.
    ingest_arxiv_papers,
]

WRITING_TOOL_NAMES_LIST = [t.name for t in WRITING_TOOLS]

# Mirrors MAX_RESEARCH_TOOL_LOOPS — a named ceiling so the forced-synthesis
# routing below and the bump in writing_force_synthesis_node stay in sync.
MAX_WRITING_TOOL_LOOPS = 8

# Destructive tools written by the writing subgraph. The main graph's
# DESTRUCTIVE_TOOLS gate only fires from the top-level interrupt_node and
# is bypassed once intent routes us into a subgraph, so the subgraph has
# to enforce HITL itself for any tool that mutates user data.
WRITING_DESTRUCTIVE_TOOLS = {
    "create_project_note",
    "create_draft",
    "ingest_arxiv_papers",
}

def _build_writing_system_prompt() -> str:
    """Construct the writing subgraph system prompt with shared rules embedded.

    Driver protocol sourced from ``AGENTS_writing.md`` — see
    ``agents_md_loader``. Inline fallback for missing-file safety.

    Imported lazily to avoid circular imports with graph.py.
    """
    from src.services.agent.graph import SHARED_AGENT_RULES
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    driver_protocol = load_agents_md("writing")
    if driver_protocol:
        return f"{driver_protocol}\n\n{SHARED_AGENT_RULES}"

    return (
        "You are a specialized Writing Agent focused on creating content, "
        "summarizing documents, and managing bibliographies.\n\n"
        f"{SHARED_AGENT_RULES}\n\n"
        "Write clearly and academically. Cite sources when available."
    )


async def writing_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Writing-specialized LLM node."""
    from langchain_core.messages import ToolMessage

    from src.core.config import get_settings
    from src.services.agent.graph import AGENT_LLM_TIMEOUT_SECONDS, _build_llm

    sanitized = _sanitize_messages(state["messages"])
    messages = [SystemMessage(content=_build_writing_system_prompt())] + sanitized

    # Post-tool synthesis turn → use the synthesis deployment. Mirrors
    # research_llm_node + main llm_node. Trace 019e191a showed gpt-5
    # spending 70s on prose synthesis after a tool result.
    settings = get_settings()
    use_synthesis = bool(
        settings.AGENT_LIGHTWEIGHT_SYNTHESIS
        and sanitized
        and isinstance(sanitized[-1], ToolMessage)
    )

    # Inject the planner's plan on the pre-tool pass so the executor follows
    # it instead of refusing. Skipped on synthesis turns — by then the tools
    # have already run and the plan would only re-trigger completed steps.
    if not use_synthesis:
        from src.services.agent.planner import render_plan_directive

        plan_directive = render_plan_directive(state.get("plan"))
        if plan_directive:
            messages.insert(1, SystemMessage(content=plan_directive))
    if use_synthesis:
        from src.services.agent.llm_factory import build_synthesis_llm

        llm = build_synthesis_llm(max_tokens=4096)
        logger.debug("writing_llm_node: using synthesis model after ToolMessage")
    else:
        llm = _build_llm()
    llm_with_tools = llm.bind_tools(WRITING_TOOLS)
    from src.services.agent.graph import _merge_run_config

    invoke_config = _merge_run_config(
        config,
        run_name="writing_llm_node",
        tags=["intent:writing", "subgraph:writing"],
    )
    try:
        response = await asyncio.wait_for(
            llm_with_tools.ainvoke(messages, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "writing_llm_node: LLM exceeded %ds; emitting fallback",
            AGENT_LLM_TIMEOUT_SECONDS,
        )
        return {
            "messages": [
                AIMessage(
                    content=(
                        "The writing model took too long to respond. Please "
                        "try again with a shorter or more specific request."
                    ),
                ),
            ],
            "last_error": "writing_llm_timeout",
            "error_count": state.get("error_count", 0) + 1,
        }

    return {
        "messages": [response],
    }


def writing_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in writing sub-graph."""
    if state.get("error_count", 0) >= 3:
        return "writing_reflection_gate"
    last = state["messages"][-1] if state["messages"] else None
    if isinstance(last, AIMessage) and last.tool_calls:
        if state.get("tool_loop_count", 0) < MAX_WRITING_TOOL_LOOPS:
            if any(tc["name"] in WRITING_DESTRUCTIVE_TOOLS for tc in last.tool_calls):
                return "writing_interrupt_node"
            return "writing_tool_node"
        # Loop ceiling tripped while the model still wants more tools.
        # Without forced synthesis the subgraph would exit with an AIMessage
        # whose tool_calls have no ToolMessages — see
        # research_should_continue (trace 019e1903) for the failure mode.
        if state.get("_force_synthesis_fired"):
            return "writing_reflection_gate"
        return "writing_force_synthesis_node"
    return "writing_reflection_gate"


async def writing_force_synthesis_node(
    state: AgentState, config: RunnableConfig
) -> dict:
    """Final-answer LLM call when the tool-loop ceiling was hit.

    Mirrors ``research_force_synthesis_node``: strip the trailing AIMessage
    with unanswered tool_calls and re-invoke the LLM with NO tools bound so
    it must produce text. See that node's docstring for the prompt-embedding
    and loop-guard rationale.
    """
    from src.services.agent.llm_factory import build_synthesis_llm

    messages = list(state["messages"])
    while messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        messages.pop()

    sanitized = _sanitize_messages(messages)
    base_prompt = _build_writing_system_prompt()
    synthesis_addendum = (
        "\n\n## Final synthesis turn\n"
        f"You ran {state.get('tool_loop_count', 0)} tool calls and reached "
        "the per-turn tool budget. Do not request any more tools. Write a "
        "final answer drawn from the tool results already in this "
        "conversation: deliver the requested content (draft, note, summary, "
        "or comparison) as far as the gathered material allows, and state "
        "plainly any step you could not complete. Do NOT repeat or quote "
        "these instructions in your reply."
    )
    full = [SystemMessage(content=base_prompt + synthesis_addendum)] + sanitized

    llm = build_synthesis_llm(max_tokens=4096)
    # No bind_tools — force a pure text response.
    from src.services.agent.graph import (
        AGENT_LLM_TIMEOUT_SECONDS,
        _merge_run_config,
    )

    invoke_config = _merge_run_config(
        config,
        run_name="writing_force_synthesis_node",
        tags=["intent:writing", "subgraph:writing", "phase:synthesis"],
    )
    try:
        response = await asyncio.wait_for(
            llm.ainvoke(full, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "writing_force_synthesis_node: LLM exceeded %ds; emitting fallback",
            AGENT_LLM_TIMEOUT_SECONDS,
        )
        response = AIMessage(
            content=(
                "I gathered material but ran out of time composing the final "
                "text. Please ask me to finish from the results above."
            ),
        )

    return {
        "messages": [response],
        # Bump past ceiling so a defective response with stray tool_calls
        # cannot re-enter forced synthesis (would loop infinitely).
        "tool_loop_count": MAX_WRITING_TOOL_LOOPS + 1,
        "_force_synthesis_fired": True,
    }


async def writing_interrupt_node(state: AgentState, config: RunnableConfig) -> dict:
    """Pause for user confirmation before executing destructive writing tools."""
    last = state["messages"][-1] if state.get("messages") else None
    if not isinstance(last, AIMessage) or not getattr(last, "tool_calls", None):
        # Defensive guard — see ``research_interrupt_node`` for rationale.
        return {"pending_confirmation": {}, "user_confirmed": False}
    destructive_calls = [
        tc for tc in last.tool_calls if tc["name"] in WRITING_DESTRUCTIVE_TOOLS
    ]
    tool_names = [tc["name"] for tc in destructive_calls]

    confirmation_details = {
        "pending_tools": tool_names,
        "tools": [
            {"name": tc["name"], "args": tc["args"]} for tc in destructive_calls
        ],
        "message": f"Confirm: {', '.join(tool_names)}?",
    }
    user_response = interrupt(confirmation_details)

    if user_response and user_response.get("confirmed"):
        return {"pending_confirmation": {}, "user_confirmed": True}

    return {
        "messages": [
            AIMessage(
                content=(
                    "Action cancelled by user. Let me know if you'd like to "
                    "proceed differently."
                ),
            ),
        ],
        "pending_confirmation": {},
        "user_confirmed": False,
    }


def writing_after_interrupt(state: AgentState) -> str:
    if state.get("user_confirmed", False):
        return "writing_tool_node"
    return "writing_reflection_gate"


def _writing_reflection_route(state: AgentState) -> str:
    """Route after reflection: revise loops back to LLM, proceed exits."""
    from src.services.agent.reflection import ReflectionResult

    result: ReflectionResult | None = state.get("_reflection_result")  # type: ignore[arg-type]
    if result is None or result.passed or result.severity == "minor":
        return END
    if result.severity == "major" and state.get("reflection_count", 0) < 2:
        return "writing_llm_node"
    return END


def build_writing_subgraph() -> StateGraph:
    """Build the writing agent sub-graph.

    Flow:
      writing_planner_node -> writing_llm_node -> writing_should_continue ->
        | writing_interrupt_node -> writing_after_interrupt -> writing_tool_node
        | writing_tool_node -> writing_compactor_node -> writing_llm_node (loop)
        | writing_reflection_gate -> END (or revise -> writing_llm_node)
    """
    from src.services.agent.graph import make_filtered_tool_node

    WRITING_TOOL_NAMES = {t.name for t in WRITING_TOOLS}
    filtered_tool = make_filtered_tool_node(WRITING_TOOL_NAMES)

    # Create v2 nodes
    planner = make_planner_node(WRITING_TOOL_NAMES_LIST)
    compactor = make_compactor_node()
    reflection_node, _reflection_route = make_reflection_gate(
        intent_filter={"writing"},
    )

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("writing_planner_node", planner)
    graph.add_node("writing_llm_node", writing_llm_node)
    graph.add_node("writing_tool_node", filtered_tool)
    graph.add_node("writing_interrupt_node", writing_interrupt_node)
    graph.add_node("writing_compactor_node", compactor)
    graph.add_node("writing_force_synthesis_node", writing_force_synthesis_node)
    graph.add_node("writing_reflection_gate", reflection_node)

    # Edges
    graph.set_entry_point("writing_planner_node")
    graph.add_edge("writing_planner_node", "writing_llm_node")

    graph.add_conditional_edges(
        "writing_llm_node",
        writing_should_continue,
        {
            "writing_tool_node": "writing_tool_node",
            "writing_interrupt_node": "writing_interrupt_node",
            "writing_force_synthesis_node": "writing_force_synthesis_node",
            "writing_reflection_gate": "writing_reflection_gate",
        },
    )

    # Forced synthesis always goes to reflection (it produced a final answer).
    graph.add_edge("writing_force_synthesis_node", "writing_reflection_gate")

    graph.add_conditional_edges(
        "writing_interrupt_node",
        writing_after_interrupt,
        {
            "writing_tool_node": "writing_tool_node",
            "writing_reflection_gate": "writing_reflection_gate",
        },
    )

    graph.add_edge("writing_tool_node", "writing_compactor_node")
    graph.add_edge("writing_compactor_node", "writing_llm_node")

    graph.add_conditional_edges(
        "writing_reflection_gate",
        _writing_reflection_route,
        {
            END: END,
            "writing_llm_node": "writing_llm_node",
        },
    )

    return graph
