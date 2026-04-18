"""Agent state schema for LangGraph."""
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """Full agent state passed through the graph.

    All fields must be provided in the initial state dict passed to
    ``graph.ainvoke()`` / ``graph.astream_events()``.  See
    ``_run_agent_graph`` and ``event_generator`` in ``execute.py``
    for the canonical initial-state construction.
    """

    messages: Annotated[list, add_messages]
    page_context: dict
    retrieved_contexts: list
    tool_executions: list
    thread_id: str
    tool_loop_count: int
    error_count: int
    last_error: str
    pending_confirmation: dict
    user_confirmed: bool
    intent: str
    user_memories: list
