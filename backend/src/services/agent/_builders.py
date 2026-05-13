"""LangGraph builder + routing helpers for the agent graph.

Extracted from ``graph.py`` so the orchestration module stays under the
800-line house rule. ``graph.py`` re-exports every public name so the
LangGraph entry point in ``langgraph.json`` (``create_graph``) and all
existing callers (``compile_agent_graph``, ``build_agent_graph``,
``should_continue``, ``after_interrupt``, ``MAX_ERRORS``,
``MAX_TOOL_LOOPS``) keep resolving from ``src.services.agent.graph``
without churn.

What lives here:

* ``should_continue`` / ``after_interrupt`` — the two conditional edges
  on the general path.
* ``MAX_ERRORS`` / ``MAX_TOOL_LOOPS`` — soft circuit breakers consumed
  by ``should_continue``.
* ``build_agent_graph`` — wires every node + sub-graph into a single
  ``StateGraph``.
* ``compile_agent_graph`` — applies checkpointer + store + compiles.
* ``create_graph`` — no-arg entry for ``langgraph.json``.
"""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy

from src.services.agent._nodes_classify import (
    preprocessing_node,
    route_by_intent,
)
from src.services.agent._nodes_llm import llm_node
from src.services.agent._nodes_memory import memory_save_node
from src.services.agent._nodes_tools import (
    DESTRUCTIVE_TOOLS,
    interrupt_node,
    tool_node,
)
from src.services.agent.compactor import make_compactor_node
from src.services.agent.planner import make_planner_node
from src.services.agent.reflection import make_reflection_gate
from src.services.agent.state import AgentState
from src.services.agent.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Soft circuit breakers
# ---------------------------------------------------------------------------

# Lowered from 10 → 4. LangSmith showed slow general-intent roots (44-71s)
# burned 5+ sequential LLM hops at ~5-10s each. Four iterations covers
# plan → tool → refine → finalize; more is the agent re-running queries.
# Research subgraph runs at 5 (MAX_RESEARCH_TOOL_LOOPS).
MAX_TOOL_LOOPS = 4
MAX_ERRORS = 3


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------


def should_continue(state: AgentState) -> str:
    """Decide whether to route to tool_node, interrupt_node, or reflection_gate (then END)."""
    # Bail out if too many errors have accumulated
    if state.get("error_count", 0) >= MAX_ERRORS:
        logger.warning(
            "Agent reached max error count (%d), stopping. Last error: %s",
            MAX_ERRORS,
            state.get("last_error", ""),
        )
        return "reflection_gate"

    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < MAX_TOOL_LOOPS
    ):
        # Check if any tool call is destructive — route through interrupt
        has_destructive = any(tc["name"] in DESTRUCTIVE_TOOLS for tc in last.tool_calls)
        if has_destructive:
            return "interrupt_node"
        return "tool_node"
    return "reflection_gate"


def after_interrupt(state: AgentState) -> str:
    """Route after interrupt: proceed to tool_node if confirmed, else reflection gate and end."""
    if state.get("user_confirmed", False):
        return "tool_node"
    return "reflection_gate"


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------

_RETRY_POLICY = RetryPolicy(max_attempts=3)


def build_agent_graph() -> StateGraph:
    """Build the uncompiled agent state graph.

    Flow:
      START -> preprocessing_node (RAG + classify + memory in parallel)
        -> [route_by_intent]
        -> research_subgraph | writing_subgraph | data_subgraph | general path

      General path:
        planner_node -> llm_node -> [should_continue]
          -> tool_node -> compactor_node -> llm_node (loop)
          -> interrupt_node -> [after_interrupt] -> tool_node | reflection_gate
          -> reflection_gate -> [reflection_route] -> memory_save_node | llm_node (revise)

      Sub-graphs (internal planner + compactor + reflection) -> memory_save_node -> END
    """
    from src.services.agent.subgraphs.data_agent import build_data_subgraph
    from src.services.agent.subgraphs.research_agent import build_research_subgraph
    from src.services.agent.subgraphs.writing_agent import build_writing_subgraph

    # General-path v2 nodes
    tool_names = [t.name for t in ALL_TOOLS]
    planner_node_fn = make_planner_node(tool_names)
    compactor_node_fn = make_compactor_node()
    reflection_node_fn, reflection_route_fn = make_reflection_gate()

    graph = StateGraph(AgentState)

    graph.add_node("preprocessing_node", preprocessing_node)
    graph.add_node("planner_node", planner_node_fn)
    graph.add_node("llm_node", llm_node, retry=_RETRY_POLICY)
    graph.add_node("tool_node", tool_node)
    graph.add_node("compactor_node", compactor_node_fn)
    graph.add_node("interrupt_node", interrupt_node)
    graph.add_node("reflection_gate", reflection_node_fn)
    graph.add_node("memory_save_node", memory_save_node, retry=_RETRY_POLICY)

    # Sub-graphs compiled as nodes (they have internal planner/compactor/reflection)
    graph.add_node("research_subgraph", build_research_subgraph().compile())
    graph.add_node("writing_subgraph", build_writing_subgraph().compile())
    graph.add_node("data_subgraph", build_data_subgraph().compile())

    graph.set_entry_point("preprocessing_node")

    # Route by intent after parallel preprocessing
    graph.add_conditional_edges(
        "preprocessing_node",
        route_by_intent,
        {
            "research_subgraph": "research_subgraph",
            "writing_subgraph": "writing_subgraph",
            "data_subgraph": "data_subgraph",
            "llm_node": "planner_node",
        },
    )

    # Sub-graphs (with internal reflection) -> memory_save_node -> END
    graph.add_edge("research_subgraph", "memory_save_node")
    graph.add_edge("writing_subgraph", "memory_save_node")
    graph.add_edge("data_subgraph", "memory_save_node")

    # General path: planner -> llm
    graph.add_edge("planner_node", "llm_node")

    # General path: llm_node -> conditional
    graph.add_conditional_edges(
        "llm_node",
        should_continue,
        {
            "tool_node": "tool_node",
            "interrupt_node": "interrupt_node",
            "reflection_gate": "reflection_gate",
        },
    )
    graph.add_conditional_edges(
        "interrupt_node",
        after_interrupt,
        {"tool_node": "tool_node", "reflection_gate": "reflection_gate"},
    )

    # General path: tool_node -> compactor_node -> llm_node (loop)
    graph.add_edge("tool_node", "compactor_node")
    graph.add_edge("compactor_node", "llm_node")

    # Reflection gate routes: proceed -> memory_save, revise -> llm_node
    graph.add_conditional_edges(
        "reflection_gate",
        reflection_route_fn,
        {"proceed": "memory_save_node", "revise": "llm_node"},
    )
    graph.add_edge("memory_save_node", END)

    return graph


def compile_agent_graph(checkpointer=None, store=None, **kwargs):
    """Compile the agent graph, optionally with a checkpointer and store.

    ``checkpointer`` may be ``None`` (no checkpointing), an instance of
    ``BaseCheckpointSaver``, or ``True`` to opt into the default in-memory
    saver. Anything else is rejected with a clear error rather than
    silently passing a bool to ``graph.compile()`` (which would crash with
    ``AttributeError`` deep inside LangGraph at runtime).

    ``store`` is an optional ``BaseStore`` for long-term, cross-thread
    memory (user preferences, facts).  When provided, LangGraph injects it
    into nodes that accept a ``Runtime`` parameter so they can use
    ``runtime.store`` instead of importing the singleton directly.
    """
    graph = build_agent_graph()
    from langgraph.checkpoint.base import BaseCheckpointSaver

    compile_kwargs: dict = {}
    if store is not None:
        compile_kwargs["store"] = store

    if checkpointer is None or checkpointer is False:
        return graph.compile(**compile_kwargs)

    if checkpointer is True:
        # Convenience: ``True`` opts into the in-memory default so callers
        # don't have to import MemorySaver themselves.
        from langgraph.checkpoint.memory import MemorySaver

        return graph.compile(checkpointer=MemorySaver(), **compile_kwargs)

    if isinstance(checkpointer, BaseCheckpointSaver):
        return graph.compile(checkpointer=checkpointer, **compile_kwargs)

    raise TypeError(
        "compile_agent_graph(checkpointer=...) must be None, True, False, "
        f"or a BaseCheckpointSaver instance — got {type(checkpointer).__name__}"
    )


def create_graph():
    """No-arg entry point for langgraph dev (langgraph.json)."""
    return compile_agent_graph(checkpointer=True)


__all__ = [
    "MAX_ERRORS",
    "MAX_TOOL_LOOPS",
    "should_continue",
    "after_interrupt",
    "build_agent_graph",
    "compile_agent_graph",
    "create_graph",
]
