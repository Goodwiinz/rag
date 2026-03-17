"""Agent graph visualization utilities.

Exports graph structure and execution traces as Mermaid diagrams.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_graph_mermaid() -> str:
    """Generate a Mermaid diagram of the current agent graph structure."""
    from src.services.agent.graph import build_agent_graph

    try:
        graph = build_agent_graph()
        compiled = graph.compile()
        return compiled.get_graph().draw_mermaid()
    except Exception as e:
        logger.error("Failed to generate graph mermaid: %s", e)
        return f"graph TD\n  error[\"Failed to generate graph: {e}\"]"


async def get_execution_trace_mermaid(
    thread_id: str,
) -> Optional[str]:
    """Generate a Mermaid sequence diagram for a specific execution trace.

    Uses the checkpointer to retrieve state history for the given thread.
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
                tool_name = te.get("tool_name", "unknown")
                status = te.get("status", "unknown")
                lines.append(f"    G->>T: {tool_name}")
                lines.append(f"    T-->>G: {status}")

            # Show next routing
            for node in next_nodes:
                if node != "__end__":
                    lines.append(f"    G->>G: → {node}")

        if len(lines) <= 3:
            lines.append("    Note over G: No execution history found")

        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to generate trace mermaid: %s", e)
        return None
