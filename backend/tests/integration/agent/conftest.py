"""Agent integration test fixtures.

Provides mock LLM, tool executor, compiled graph, and config fixtures
that build on the existing integration conftest (test_db, test_user, etc.).
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Mock user (lightweight, no DB required)
# ---------------------------------------------------------------------------


def make_mock_user(user_id: str | None = None) -> Mock:
    """Create a lightweight mock user for graph config."""
    user = Mock()
    user.id = user_id or str(uuid.uuid4())
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.role = Mock(value="user")
    user.organization_id = str(uuid.uuid4())
    user.is_active = True
    return user


@pytest.fixture
def mock_user():
    return make_mock_user()


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class MockChatModel:
    """Controllable mock LLM for graph testing.

    Responses are consumed in order from the ``responses`` list.
    Each response can be an AIMessage or a dict with ``content`` / ``tool_calls``.
    """

    def __init__(self, responses: list | None = None):
        self._responses = list(responses or [])
        self._call_count = 0
        self.bind_tools_called_with: list | None = None

    def bind_tools(self, tools, **_kwargs):
        """Record which tools were bound (for subgraph routing assertions)."""
        self.bind_tools_called_with = tools
        return self  # chainable

    async def ainvoke(self, _messages, **_kwargs):
        """Return the next queued response."""
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = AIMessage(content="I can help with that.")
        self._call_count += 1

        if isinstance(resp, AIMessage):
            return resp
        if isinstance(resp, dict):
            return AIMessage(
                content=resp.get("content", ""),
                tool_calls=resp.get("tool_calls", []),
            )
        return resp

    @property
    def call_count(self) -> int:
        return self._call_count


def make_ai_response(content: str = "Here is the answer.") -> AIMessage:
    """Create a simple AIMessage response."""
    return AIMessage(content=content)


def make_tool_call_response(
    tool_name: str,
    tool_args: dict | None = None,
    call_id: str | None = None,
) -> AIMessage:
    """Create an AIMessage with a tool call."""
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": call_id or f"call_{uuid.uuid4().hex[:8]}",
                "name": tool_name,
                "args": tool_args or {},
            }
        ],
    )


@pytest.fixture
def mock_llm():
    """Default mock LLM that returns a simple response."""
    return MockChatModel([make_ai_response()])


# ---------------------------------------------------------------------------
# Mock tool executor
# ---------------------------------------------------------------------------


def make_mock_execute_tool(results: dict | None = None):
    """Create a mock execute_tool function.

    ``results`` maps tool_name -> return value (dict).
    Unknown tools return ``{"result": "ok"}``.
    """
    default_results = results or {}

    async def _execute(
        *, tool_name, args, user_id=None, db=None, current_user=None, **_kw
    ):
        del args, user_id, db, current_user, _kw  # unused — captured for signature parity
        return default_results.get(tool_name, {"result": "ok"})

    return _execute


@pytest.fixture
def mock_execute_tool():
    return make_mock_execute_tool()


# ---------------------------------------------------------------------------
# Graph compilation helper
# ---------------------------------------------------------------------------


# Patches started by compile_graph_with_mocks; torn down by the autouse
# _cleanup_graph_patchers fixture so they outlive the helper's return and
# remain active during `await graph.ainvoke(...)`.
_active_graph_patchers: list = []


@pytest.fixture(autouse=True)
def _cleanup_graph_patchers():
    yield
    while _active_graph_patchers:
        _active_graph_patchers.pop().stop()


def compile_graph_with_mocks(mock_llm_instance, mock_tool_fn):
    """Compile the agent graph with all external deps patched."""
    from langgraph.checkpoint.memory import MemorySaver

    patchers = [
        patch("src.services.agent.graph._build_llm", return_value=mock_llm_instance),
        patch("src.services.agent.graph.execute_tool", new=mock_tool_fn),
        patch("src.services.agent.graph._get_execute_tool", return_value=mock_tool_fn),
        patch(
            "src.services.agent.graph.memory_retrieval_node",
            new=AsyncMock(return_value={"user_memories": []}),
        ),
        patch(
            "src.services.agent.graph.memory_save_node",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "src.services.agent.graph.rag_node",
            new=AsyncMock(return_value={"retrieved_contexts": []}),
        ),
    ]
    for p in patchers:
        p.start()
        _active_graph_patchers.append(p)

    from src.services.agent.graph import compile_agent_graph

    return compile_agent_graph(checkpointer=MemorySaver())


@pytest_asyncio.fixture
async def compiled_graph(mock_llm, mock_execute_tool):
    """Compiled agent graph with mocked LLM, tools, RAG, memory."""
    return compile_graph_with_mocks(mock_llm, mock_execute_tool)


# ---------------------------------------------------------------------------
# Graph config
# ---------------------------------------------------------------------------


def make_graph_config(
    user: Mock | None = None,
    thread_id: str | None = None,
    page_context: dict | None = None,
) -> dict:
    """Build a RunnableConfig for graph invocation."""
    return {
        "configurable": {
            "thread_id": thread_id or str(uuid.uuid4()),
            "current_user": user or make_mock_user(),
            "page_context": page_context or {},
            "search_fn": AsyncMock(return_value=[]),
        }
    }


@pytest.fixture
def graph_config(mock_user):
    return make_graph_config(user=mock_user)


# ---------------------------------------------------------------------------
# Initial state helper
# ---------------------------------------------------------------------------


def make_initial_state(
    message: str = "Hello",
    **overrides,
) -> dict:
    """Build a valid initial AgentState dict."""
    state = {
        "messages": [HumanMessage(content=message)],
        "page_context": {},
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": str(uuid.uuid4()),
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "pending_confirmation": {},
        "user_confirmed": False,
        "intent": "",
        "user_memories": [],
        # v2 fields
        "plan": [],
        "reflection_count": 0,
        "compaction_count": 0,
        "intent_confidence": 0.0,
        "last_error_info": {},
    }
    state.update(overrides)
    return state
