"""Agent state schema for LangGraph."""
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    page_context: dict
    retrieved_contexts: list
    tool_executions: list
    thread_id: str
    tool_loop_count: int
