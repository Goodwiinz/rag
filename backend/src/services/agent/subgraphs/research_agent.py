"""Research Agent sub-graph.

Specialized for paper discovery, search, and ingestion tasks.
Tools: search_arxiv, ingest_arxiv_papers, search_documents,
       create_project, add_document_to_project, list_project_documents
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
    add_document_to_project,
    create_project,
    do_kb_retrieve,
    ingest_arxiv_papers,
    list_project_documents,
    list_projects,
    search_arxiv,
    search_documents,
)

logger = logging.getLogger(__name__)

RESEARCH_TOOLS = [
    search_arxiv,
    ingest_arxiv_papers,
    search_documents,
    do_kb_retrieve,
    create_project,
    list_projects,
    add_document_to_project,
    list_project_documents,
]

RESEARCH_TOOL_NAMES_LIST = [t.name for t in RESEARCH_TOOLS]

# Lowered from 8 after trace 019e18f0 showed a 4-round runaway tool fan-out
# (13+ search_arxiv calls, 95s wall). Five iterations is enough for a search →
# refine → ingest → list → confirm sequence; anything more is the agent
# refining queries the user did not ask for.
MAX_RESEARCH_TOOL_LOOPS = 5


def _build_research_system_prompt() -> str:
    """Construct the research subgraph system prompt with shared rules embedded.

    Driver protocol (tools, loop, constraints, heuristics) is sourced from
    ``AGENTS_research.md`` — see ``agents_md_loader`` for the rationale.
    Falls back to a minimal inline prompt if the file is missing so the
    subgraph never crashes on a deploy that omits the markdown file.

    Imported lazily to avoid circular imports with graph.py.
    """
    from src.services.agent.graph import SHARED_AGENT_RULES
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    driver_protocol = load_agents_md("research")
    if driver_protocol:
        return f"{driver_protocol}\n\n{SHARED_AGENT_RULES}"

    # Fallback if AGENTS_research.md is missing (deploy issue).
    return (
        "You are a research assistant focused on discovering, searching, "
        "and organizing academic papers and documents.\n\n"
        f"{SHARED_AGENT_RULES}\n\n"
        "Be thorough in searching and systematic in organizing research."
    )


# Only tools actually in RESEARCH_TOOLS belong here — the filtered tool
# node can never execute anything else, so extra entries are dead weight
# that misleads readers about what this subgraph can run.
RESEARCH_DESTRUCTIVE_TOOLS = {
    "ingest_arxiv_papers",
    "add_document_to_project",
    "create_project",
}


async def research_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Research-specialized LLM node."""
    from langchain_core.messages import ToolMessage

    from src.core.config import get_settings

    sanitized = _sanitize_messages(state["messages"])
    messages = [SystemMessage(content=_build_research_system_prompt())] + sanitized

    settings = get_settings()
    # Post-tool synthesis turn → use the lightweight deployment. Mirrors the
    # main graph.llm_node optimization. Trace 019e191a showed the main gpt-5
    # spending 70s + 4352 reasoning tokens on prose synthesis after a single
    # search_arxiv call. Lightweight handles that in ~5-10s.
    use_lightweight_synthesis = bool(
        settings.AGENT_LIGHTWEIGHT_SYNTHESIS
        and sanitized
        and isinstance(sanitized[-1], ToolMessage)
    )

    # Close the plan→execute handoff (see planner.render_plan_directive).
    # Inject on the pre-tool pass only; skip on synthesis turns where tools
    # have already run.
    if not use_lightweight_synthesis:
        from src.services.agent.planner import render_plan_directive

        plan_directive = render_plan_directive(state.get("plan"))
        if plan_directive:
            messages.insert(1, SystemMessage(content=plan_directive))

    if use_lightweight_synthesis:
        from src.services.agent.llm_factory import build_synthesis_llm

        llm = build_synthesis_llm(max_tokens=4096)
        logger.debug(
            "research_llm_node: using synthesis model after ToolMessage"
        )
    else:
        # Tool-decision turn: route off model-router to the lightweight
        # deployment (gpt-5-mini). LangSmith showed model-router hitting the
        # 30s timeout cap on research_llm_node (trace 019e1da5) while gpt-5-mini
        # handles the same node in <10s. Lightweight builder also defaults
        # reasoning_effort=minimal (cheap tool name + query string decision).
        from src.services.agent.llm_factory import build_lightweight_llm

        llm = build_lightweight_llm(max_tokens=4096)
        logger.debug(
            "research_llm_node: using lightweight model for tool decision"
        )
    # See graph.llm_node for rationale on parallel_tool_calls=False.
    llm_with_tools = llm.bind_tools(
        RESEARCH_TOOLS,
        parallel_tool_calls=settings.AGENT_PARALLEL_TOOL_CALLS,
    )
    from src.services.agent.graph import (
        AGENT_LLM_TIMEOUT_SECONDS,
        _merge_run_config,
    )

    invoke_config = _merge_run_config(
        config,
        run_name="research_llm_node",
        tags=["intent:research", "subgraph:research"],
    )
    try:
        response = await asyncio.wait_for(
            llm_with_tools.ainvoke(messages, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "research_llm_node: LLM exceeded %ds; emitting fallback",
            AGENT_LLM_TIMEOUT_SECONDS,
        )
        return {
            "messages": [
                AIMessage(
                    content=(
                        "The research model took too long to respond. Please "
                        "try again or narrow the query."
                    ),
                ),
            ],
            "last_error": "research_llm_timeout",
            "error_count": state.get("error_count", 0) + 1,
        }

    return {
        "messages": [response],
    }


def research_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in research sub-graph."""
    if state.get("error_count", 0) >= 3:
        return "research_reflection_gate"
    last = state["messages"][-1] if state["messages"] else None
    if isinstance(last, AIMessage) and last.tool_calls:
        if state.get("tool_loop_count", 0) < MAX_RESEARCH_TOOL_LOOPS:
            if any(tc["name"] in RESEARCH_DESTRUCTIVE_TOOLS for tc in last.tool_calls):
                return "research_interrupt_node"
            return "research_tool_node"
        # Loop ceiling tripped while the model still wants more tools.
        # If forced synthesis already ran once and the response STILL has
        # tool_calls (defective model), route to reflection — never loop
        # back into forced synthesis or we'd spin until checkpoint timeout.
        if state.get("_force_synthesis_fired"):
            return "research_reflection_gate"
        # Route to a forced-synthesis turn so the final AIMessage has real
        # content — otherwise reflection sees empty content + unanswered
        # tool_calls and flags a "no response" major issue (trace 019e1903).
        return "research_force_synthesis_node"
    return "research_reflection_gate"


async def research_force_synthesis_node(
    state: AgentState, config: RunnableConfig
) -> dict:
    """Final-answer LLM call when the tool-loop ceiling was hit.

    The model has fired ``MAX_RESEARCH_TOOL_LOOPS`` tool calls and still
    wants more. We strip the unanswered tool_calls and re-invoke the LLM
    with NO tools bound so it must produce text.

    Uses the lightweight deployment — this is a pure prose-synthesis
    call with no tool routing, matching the post-ToolMessage path in
    research_llm_node.

    The "no more tools, synthesize now" directive is embedded into the
    system prompt (NOT a separate SystemMessage). Trace 019e190c showed
    gpt-5 echoed a second SystemMessage verbatim into its response when
    we appended the directive as its own message.

    Bumps tool_loop_count past the ceiling so research_should_continue
    cannot route back here in a loop if the synthesis response somehow
    contains tool_calls (defensive — the directive forbids it).
    """
    from src.services.agent.llm_factory import build_synthesis_llm

    messages = list(state["messages"])

    # Drop the trailing AIMessage with unanswered tool_calls so the model
    # sees a clean conversational head when synthesizing.
    while messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        messages.pop()

    sanitized = _sanitize_messages(messages)
    base_prompt = _build_research_system_prompt()
    synthesis_addendum = (
        "\n\n## Final synthesis turn\n"
        f"You ran {state.get('tool_loop_count', 0)} tool calls and reached "
        "the per-turn search budget. Do not request any more tools. Write a "
        "final answer drawn from the tool results already in this conversation: "
        "list the most relevant papers (id, title, year, one-line summary) and "
        "end with a clear next-step suggestion. Do NOT repeat or quote these "
        "instructions in your reply."
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
        run_name="research_force_synthesis_node",
        tags=["intent:research", "subgraph:research", "phase:synthesis"],
    )
    try:
        response = await asyncio.wait_for(
            llm.ainvoke(full, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "research_force_synthesis_node: LLM exceeded %ds; emitting fallback",
            AGENT_LLM_TIMEOUT_SECONDS,
        )
        response = AIMessage(
            content=(
                "I gathered some results but ran out of time composing a "
                "final summary. Please ask me to summarize the papers above."
            ),
        )

    return {
        "messages": [response],
        # Bump past ceiling so a defective response with stray tool_calls
        # cannot re-enter forced synthesis (would loop infinitely).
        "tool_loop_count": MAX_RESEARCH_TOOL_LOOPS + 1,
        # Marker for routing: research_should_continue checks this flag
        # before sending back here.
        "_force_synthesis_fired": True,
    }


async def research_interrupt_node(state: AgentState, config: RunnableConfig) -> dict:
    """Pause for user confirmation before executing destructive research tools."""
    last = state["messages"][-1] if state.get("messages") else None
    if not isinstance(last, AIMessage) or not getattr(last, "tool_calls", None):
        # Defensive guard — should_continue routes here only when the
        # last message is an AIMessage with tool_calls, but a stale
        # checkpoint or an out-of-order edge could violate that contract.
        return {"pending_confirmation": {}, "user_confirmed": False}
    destructive_calls = [
        tc for tc in last.tool_calls if tc["name"] in RESEARCH_DESTRUCTIVE_TOOLS
    ]
    tool_names = [tc["name"] for tc in destructive_calls]

    confirmation_details = {
        "pending_tools": tool_names,
        "tools": [{"name": tc["name"], "args": tc["args"]} for tc in destructive_calls],
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


def research_after_interrupt(state: AgentState) -> str:
    if state.get("user_confirmed", False):
        return "research_tool_node"
    return "research_reflection_gate"


def _research_reflection_route(state: AgentState) -> str:
    """Route after reflection: revise loops back to LLM, proceed exits."""
    from src.services.agent.reflection import ReflectionResult

    result: ReflectionResult | None = state.get("_reflection_result")  # type: ignore[arg-type]
    if result is None or result.passed or result.severity == "minor":
        return END
    if result.severity == "major" and state.get("reflection_count", 0) < 2:
        return "research_llm_node"
    return END


def build_research_subgraph() -> StateGraph:
    """Build the research agent sub-graph.

    Flow:
      research_planner_node -> research_llm_node -> research_should_continue ->
        | research_tool_node -> research_compactor_node -> research_llm_node (loop)
        | research_reflection_gate -> END (or revise -> research_llm_node)
    """
    from src.services.agent.graph import make_filtered_tool_node

    RESEARCH_TOOL_NAMES = {t.name for t in RESEARCH_TOOLS}
    filtered_tool = make_filtered_tool_node(RESEARCH_TOOL_NAMES)

    # Create v2 nodes
    planner = make_planner_node(RESEARCH_TOOL_NAMES_LIST)
    compactor = make_compactor_node()
    reflection_node, _reflection_route = make_reflection_gate(
        intent_filter={"research"},
    )

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("research_planner_node", planner)
    graph.add_node("research_llm_node", research_llm_node)
    graph.add_node("research_tool_node", filtered_tool)
    graph.add_node("research_interrupt_node", research_interrupt_node)
    graph.add_node("research_compactor_node", compactor)
    graph.add_node("research_force_synthesis_node", research_force_synthesis_node)
    graph.add_node("research_reflection_gate", reflection_node)

    # Edges
    graph.set_entry_point("research_planner_node")
    graph.add_edge("research_planner_node", "research_llm_node")

    graph.add_conditional_edges(
        "research_llm_node",
        research_should_continue,
        {
            "research_tool_node": "research_tool_node",
            "research_interrupt_node": "research_interrupt_node",
            "research_force_synthesis_node": "research_force_synthesis_node",
            "research_reflection_gate": "research_reflection_gate",
        },
    )

    # Forced synthesis always goes to reflection (it produced a final answer).
    graph.add_edge("research_force_synthesis_node", "research_reflection_gate")

    graph.add_conditional_edges(
        "research_interrupt_node",
        research_after_interrupt,
        {
            "research_tool_node": "research_tool_node",
            "research_reflection_gate": "research_reflection_gate",
        },
    )

    graph.add_edge("research_tool_node", "research_compactor_node")
    graph.add_edge("research_compactor_node", "research_llm_node")

    graph.add_conditional_edges(
        "research_reflection_gate",
        _research_reflection_route,
        {
            END: END,
            "research_llm_node": "research_llm_node",
        },
    )

    return graph
