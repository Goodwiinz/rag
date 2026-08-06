"""Agent graph visualization utilities.

Exports graph structure and execution traces as Mermaid diagrams.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Mermaid label escaping: ``"`` and ``:`` break the parser inside
# ``A->>B: <label>`` style sequence-diagram lines, ``[`` and ``]`` confuse
# node-shape parsing in ``graph TD``, and Unicode arrows render
# inconsistently across renderers. Replace with safe ASCII equivalents.
_MERMAID_LABEL_REPLACEMENTS = {
    '"': "'",
    ":": "-",
    "[": "(",
    "]": ")",
    "{": "(",
    "}": ")",
    "\n": " ",
    "\r": " ",
    "→": "-->",
}


def _escape_mermaid_label(value: object) -> str:
    """Make ``value`` safe to interpolate into a Mermaid label.

    Strips control characters, replaces the small set of metacharacters
    that break the parser, and caps the length so a runaway tool
    response cannot bloat the diagram beyond what most renderers can
    display.
    """
    text = str(value)
    for needle, replacement in _MERMAID_LABEL_REPLACEMENTS.items():
        text = text.replace(needle, replacement)
    # Drop ASCII control characters except tab (which Mermaid tolerates).
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", " ", text)
    if len(text) > 120:
        text = text[:117] + "..."
    return text


def get_graph_mermaid() -> str:
    """Generate a Mermaid diagram of the current agent graph structure."""
    from src.services.agent.graph import build_agent_graph

    try:
        graph = build_agent_graph()
        compiled = graph.compile()
        return compiled.get_graph().draw_mermaid()
    except Exception as e:
        logger.error("Failed to generate graph mermaid: %s", e)
        return f"graph TD\n  error[\"Failed to generate graph: {_escape_mermaid_label(e)}\"]"


async def get_execution_trace_mermaid(
    thread_id: str,
) -> Optional[str]:
    """Generate a Mermaid sequence diagram for a specific execution trace.

    Uses the checkpointer to retrieve state history for the given thread.
    Returns a sequence diagram annotated with a clear note when no
    history is available (e.g. when the in-memory MemorySaver fallback
    is in use, which produces an empty trace for any real thread —
    making debugging silently impossible).
    """
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph

    try:
        checkpointer = await get_checkpointer()
        graph = compile_agent_graph(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": thread_id}}

        # Build sequence diagram from state history
        lines = ["sequenceDiagram"]
        lines.append("    participant U as User")
        lines.append("    participant G as Agent Graph")
        lines.append("    participant T as Tools")

        states = []
        async for state in graph.aget_state_history(config):
            states.append(state)

        # Reverse to get chronological order
        states.reverse()

        for state_snapshot in states:
            values = state_snapshot.values or {}
            next_nodes = state_snapshot.next or ()

            # Show tool executions
            tool_execs = values.get("tool_executions", [])
            for te in tool_execs:
                tool_name = _escape_mermaid_label(te.get("tool_name", "unknown"))
                status = _escape_mermaid_label(te.get("status", "unknown"))
                lines.append(f"    G->>T: {tool_name}")
                lines.append(f"    T-->>G: {status}")

            # Show next routing — use ASCII arrow so renderers without
            # Unicode-arrow support don't drop the label.
            for node in next_nodes:
                if node != "__end__":
                    lines.append(f"    G->>G: -> {_escape_mermaid_label(node)}")

        if len(lines) <= 4:
            checkpointer_kind = type(checkpointer).__name__
            logger.warning(
                "Trace request for thread_id=%s returned no state history "
                "(checkpointer=%s). The in-memory MemorySaver fallback does "
                "not persist across requests — wire up the Postgres "
                "checkpointer for real traces.",
                thread_id,
                checkpointer_kind,
            )
            lines.append(
                f"    Note over G: No execution history for this thread "
                f"(checkpointer={_escape_mermaid_label(checkpointer_kind)})."
            )

        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to generate trace mermaid: %s", e)
        return None
