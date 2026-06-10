"""Data Agent sub-graph.

Specialized for entity extraction, knowledge graph exploration, and data analysis.
Tools: extract_entities, search_knowledge_graph, search_documents,
       list_project_documents
"""

import asyncio
import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.services.agent.compactor import make_compactor_node
from src.services.agent.graph import _sanitize_messages
from src.services.agent.planner import make_planner_node
from src.services.agent.reflection import make_reflection_gate
from src.services.agent.state import AgentState
from src.services.agent.tools import (
    explore_entity_neighborhood,
    extract_entities,
    find_entity_paths,
    get_graph_stats,
    list_project_documents,
    search_documents,
    search_knowledge_graph,
)

logger = logging.getLogger(__name__)

DATA_TOOLS = [
    extract_entities,
    search_knowledge_graph,
    explore_entity_neighborhood,
    find_entity_paths,
    get_graph_stats,
    search_documents,
    list_project_documents,
]

DATA_TOOL_NAMES_LIST = [t.name for t in DATA_TOOLS]

# Named ceiling (preserves the previous hardcoded ``< 8``) so the
# forced-synthesis routing below and the bump in data_force_synthesis_node
# stay in sync. Same pattern as research's MAX_RESEARCH_TOOL_LOOPS but an
# independent value — research deliberately lowered theirs to 5 after a
# runaway-fanout trace; this one has no such justification yet.
MAX_DATA_TOOL_LOOPS = 8

def _build_data_system_prompt() -> str:
    """Construct the data subgraph system prompt with shared rules embedded.

    Driver protocol sourced from ``AGENTS_data.md`` — see ``agents_md_loader``.
    Inline fallback for missing-file safety.

    Imported lazily to avoid circular imports with graph.py.
    """
    from src.services.agent.graph import SHARED_AGENT_RULES
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    driver_protocol = load_agents_md("data")
    if driver_protocol:
        return f"{driver_protocol}\n\n{SHARED_AGENT_RULES}"

    return (
        "You are a specialized Data Agent focused on extracting entities, "
        "exploring knowledge graphs, and analyzing structured data from documents.\n\n"
        f"{SHARED_AGENT_RULES}\n\n"
        "Be analytical and thorough. Present findings in structured formats."
    )


async def data_llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Data-specialized LLM node."""
    from langchain_core.messages import ToolMessage

    from src.core.config import get_settings
    from src.services.agent.graph import AGENT_LLM_TIMEOUT_SECONDS, _build_llm

    sanitized = _sanitize_messages(state["messages"])
    messages = [SystemMessage(content=_build_data_system_prompt())] + sanitized

    settings = get_settings()
    use_synthesis = bool(
        settings.AGENT_LIGHTWEIGHT_SYNTHESIS
        and sanitized
        and isinstance(sanitized[-1], ToolMessage)
    )

    # Close the plan→execute handoff (see planner.render_plan_directive).
    if not use_synthesis:
        from src.services.agent.planner import render_plan_directive

        plan_directive = render_plan_directive(state.get("plan"))
        if plan_directive:
            messages.insert(1, SystemMessage(content=plan_directive))

    if use_synthesis:
        from src.services.agent.llm_factory import build_synthesis_llm

        llm = build_synthesis_llm(max_tokens=4096)
        logger.debug("data_llm_node: using synthesis model after ToolMessage")
    else:
        llm = _build_llm()
    llm_with_tools = llm.bind_tools(DATA_TOOLS)
    from src.services.agent.graph import _merge_run_config

    invoke_config = _merge_run_config(
        config,
        run_name="data_llm_node",
        tags=["intent:knowledge_graph", "subgraph:data"],
    )
    try:
        response = await asyncio.wait_for(
            llm_with_tools.ainvoke(messages, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "data_llm_node: LLM exceeded %ds; emitting fallback",
            AGENT_LLM_TIMEOUT_SECONDS,
        )
        return {
            "messages": [
                AIMessage(
                    content=(
                        "The data model took too long to respond. Please "
                        "try again with a narrower query."
                    ),
                ),
            ],
            "last_error": "data_llm_timeout",
            "error_count": state.get("error_count", 0) + 1,
        }

    return {
        "messages": [response],
    }


def data_should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution in data sub-graph."""
    if state.get("error_count", 0) >= 3:
        return "data_reflection_gate"
    last = state["messages"][-1] if state["messages"] else None
    if isinstance(last, AIMessage) and last.tool_calls:
        if state.get("tool_loop_count", 0) < MAX_DATA_TOOL_LOOPS:
            return "data_tool_node"
        # Loop ceiling tripped while the model still wants more tools.
        # Without forced synthesis the subgraph would exit with an AIMessage
        # whose tool_calls have no ToolMessages — see
        # research_should_continue (trace 019e1903) for the failure mode.
        if state.get("_force_synthesis_fired"):
            return "data_reflection_gate"
        return "data_force_synthesis_node"
    return "data_reflection_gate"


async def data_force_synthesis_node(
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
    base_prompt = _build_data_system_prompt()
    synthesis_addendum = (
        "\n\n## Final synthesis turn\n"
        f"You ran {state.get('tool_loop_count', 0)} tool calls and reached "
        "the per-turn tool budget. Do not request any more tools. Write a "
        "final answer drawn from the tool results already in this "
        "conversation: present the entities, relationships, or graph "
        "findings gathered so far in a structured format, and state plainly "
        "any query you could not complete. Do NOT repeat or quote these "
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
        run_name="data_force_synthesis_node",
        tags=["intent:knowledge_graph", "subgraph:data", "phase:synthesis"],
    )
    try:
        response = await asyncio.wait_for(
            llm.ainvoke(full, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        # Error, not warning: the turn still completes "successfully" with
        # the canned fallback below, so this log line is the only
        # machine-visible signal that synthesis was degraded.
        logger.error(
            "data_force_synthesis_node: LLM exceeded %ds; emitting fallback "
            "(thread_id=%s, tool_loop_count=%s)",
            AGENT_LLM_TIMEOUT_SECONDS,
            state.get("thread_id", ""),
            state.get("tool_loop_count", 0),
        )
        response = AIMessage(
            content=(
                "I gathered results but ran out of time composing a final "
                "summary. Please ask me to summarize the findings above."
            ),
        )

    return {
        "messages": [response],
        # Bump past ceiling so a defective response with stray tool_calls
        # cannot re-enter forced synthesis (would loop infinitely).
        "tool_loop_count": MAX_DATA_TOOL_LOOPS + 1,
        "_force_synthesis_fired": True,
    }


def _data_reflection_route(state: AgentState) -> str:
    """Route after reflection: revise loops back to LLM, proceed exits.

    The data subgraph uses ``intent_filter={"research", "writing"}`` which
    means knowledge_graph intent is *excluded* from reflection evaluation
    (the reflection node passes through for KG queries).
    """
    from src.services.agent.reflection import ReflectionResult

    result: ReflectionResult | None = state.get("_reflection_result")  # type: ignore[arg-type]
    if result is None or result.passed or result.severity == "minor":
        return END
    if result.severity == "major" and state.get("reflection_count", 0) < 2:
        return "data_llm_node"
    return END


def build_data_subgraph() -> StateGraph:
    """Build the data agent sub-graph.

    Flow:
      data_planner_node -> data_llm_node -> data_should_continue ->
        | data_tool_node -> data_compactor_node -> data_llm_node (loop)
        | data_reflection_gate -> END (or revise -> data_llm_node)

    Note: Reflection gate skips for knowledge_graph intent (excluded from
    intent_filter) since KG queries are deterministic lookups.
    """
    from src.services.agent.graph import make_filtered_tool_node

    DATA_TOOL_NAMES = {t.name for t in DATA_TOOLS}
    filtered_tool = make_filtered_tool_node(DATA_TOOL_NAMES)

    # Create v2 nodes
    planner = make_planner_node(DATA_TOOL_NAMES_LIST)
    compactor = make_compactor_node()
    # Exclude knowledge_graph from reflection — KG queries are deterministic
    reflection_node, _reflection_route = make_reflection_gate(
        intent_filter={"research", "writing"},
    )

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("data_planner_node", planner)
    graph.add_node("data_llm_node", data_llm_node)
    graph.add_node("data_tool_node", filtered_tool)
    graph.add_node("data_compactor_node", compactor)
    graph.add_node("data_force_synthesis_node", data_force_synthesis_node)
    graph.add_node("data_reflection_gate", reflection_node)

    # Edges
    graph.set_entry_point("data_planner_node")
    graph.add_edge("data_planner_node", "data_llm_node")

    graph.add_conditional_edges(
        "data_llm_node",
        data_should_continue,
        {
            "data_tool_node": "data_tool_node",
            "data_force_synthesis_node": "data_force_synthesis_node",
            "data_reflection_gate": "data_reflection_gate",
        },
    )

    # Forced synthesis always goes to reflection (it produced a final answer).
    graph.add_edge("data_force_synthesis_node", "data_reflection_gate")

    graph.add_edge("data_tool_node", "data_compactor_node")
    graph.add_edge("data_compactor_node", "data_llm_node")

    graph.add_conditional_edges(
        "data_reflection_gate",
        _data_reflection_route,
        {
            END: END,
            "data_llm_node": "data_llm_node",
        },
    )

    return graph
