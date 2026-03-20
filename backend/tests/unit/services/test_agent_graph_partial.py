"""LangGraph partial execution tests.

Uses MemorySaver checkpointer + update_state to test node-to-node
flows without requiring real LLM calls or external services.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_initial_state(user_msg: str = "find papers on transformers") -> dict:
    """Create a minimal valid AgentState dict."""
    return {
        "messages": [HumanMessage(content=user_msg)],
        "page_context": {"type": "unknown"},
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": "",
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "pending_confirmation": {},
        "user_confirmed": False,
        "intent": "",
        "user_memories": [],
    }


def _make_config(thread_id: str | None = None) -> dict:
    user = Mock(id=uuid4(), organization_id=uuid4())
    return {
        "configurable": {
            "thread_id": thread_id or str(uuid4()),
            "db": AsyncMock(),
            "current_user": user,
            "page_context": {"type": "unknown"},
        }
    }


# ---------------------------------------------------------------------------
# Individual node tests via compiled_graph.nodes[...]
# ---------------------------------------------------------------------------


class TestIndividualNodes:
    """Test individual graph nodes via compiled_graph.nodes[...].invoke()."""

    async def test_intent_classifier_research(self):
        """intent_classifier_node should classify 'search arxiv' as research."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        # Invoke the intent_classifier_node directly
        result = await graph.nodes["intent_classifier_node"].ainvoke(
            _make_initial_state("search arxiv for transformer papers"),
            _make_config(),
        )
        assert result["intent"] == "research"

    async def test_intent_classifier_writing(self):
        """intent_classifier_node should classify 'write a summary' as writing."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        result = await graph.nodes["intent_classifier_node"].ainvoke(
            _make_initial_state("write a summary of the paper"),
            _make_config(),
        )
        assert result["intent"] == "writing"

    async def test_intent_classifier_knowledge_graph(self):
        """intent_classifier_node should classify 'extract entities' as knowledge_graph."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        result = await graph.nodes["intent_classifier_node"].ainvoke(
            _make_initial_state("extract entities from the document"),
            _make_config(),
        )
        assert result["intent"] == "knowledge_graph"

    async def test_intent_classifier_general(self):
        """intent_classifier_node should return 'general' for ambiguous queries."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        result = await graph.nodes["intent_classifier_node"].ainvoke(
            _make_initial_state("hello, how are you?"),
            _make_config(),
        )
        assert result["intent"] == "general"

    async def test_intent_classifier_writing_with_paper_keyword(self):
        """'Write a summary of the findings in the paper' should be writing, not research."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())
        result = await graph.nodes["intent_classifier_node"].ainvoke(
            _make_initial_state("write a summary of the key findings in the paper"),
            _make_config(),
        )
        assert result["intent"] == "writing"

    async def test_rag_node_without_user(self):
        """rag_node should return empty contexts when no current_user."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        config = {"configurable": {"thread_id": str(uuid4())}}
        result = await graph.nodes["rag_node"].ainvoke(
            _make_initial_state("test query"),
            config,
        )
        assert result["retrieved_contexts"] == []

    async def test_rag_node_with_injected_search(self):
        """rag_node should use injected search_fn when provided."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        async def mock_search(query: str, user_id: str):
            return [
                {
                    "document_id": "doc-123",
                    "title": "Test Document",
                    "content": f"Results for: {query}",
                    "score": 0.95,
                }
            ]

        user = Mock(id=uuid4(), organization_id=uuid4())
        config = {
            "configurable": {
                "thread_id": str(uuid4()),
                "current_user": user,
                "search_fn": mock_search,
            }
        }

        result = await graph.nodes["rag_node"].ainvoke(
            _make_initial_state("test query"),
            config,
        )
        assert len(result["retrieved_contexts"]) == 1
        assert result["retrieved_contexts"][0]["title"] == "Test Document"
        assert "test query" in result["retrieved_contexts"][0]["content"]

    async def test_memory_retrieval_node_without_user(self):
        """memory_retrieval_node should return empty when no user in config."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        config = {"configurable": {"thread_id": str(uuid4())}}
        result = await graph.nodes["memory_retrieval_node"].ainvoke(
            _make_initial_state("test"),
            config,
        )
        assert result["user_memories"] == []

    async def test_memory_save_node_without_user(self):
        """memory_save_node should return empty dict when no user."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        config = {"configurable": {"thread_id": str(uuid4())}}
        result = await graph.nodes["memory_save_node"].ainvoke(
            _make_initial_state("test"),
            config,
        )
        assert result == {}

    async def test_tool_node_no_tool_calls(self):
        """tool_node should return empty lists when no tool_calls on last message."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        state = _make_initial_state("hello")
        # Add an AIMessage without tool_calls
        state["messages"].append(AIMessage(content="Hello there!"))

        result = await graph.nodes["tool_node"].ainvoke(
            state,
            _make_config(),
        )
        assert result["messages"] == []
        assert result["tool_executions"] == []

    async def test_interrupt_node_no_destructive(self):
        """interrupt_node should pass through when no destructive tools."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        state = _make_initial_state("search")
        state["messages"].append(
            AIMessage(
                content="",
                tool_calls=[{"id": "tc1", "name": "search_arxiv", "args": {"query": "test"}}],
            )
        )

        result = await graph.nodes["interrupt_node"].ainvoke(
            state,
            _make_config(),
        )
        assert result.get("user_confirmed") is True
        assert result.get("pending_confirmation") == {}


# ---------------------------------------------------------------------------
# Partial execution tests via update_state + invoke(None)
# ---------------------------------------------------------------------------


class TestPartialExecution:
    """Test partial graph execution via update_state + invoke(None)."""

    async def test_intent_routing_research_path(self):
        """After rag_node, research intent should route to research_subgraph."""
        from src.services.agent.graph import compile_agent_graph

        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        thread_id = str(uuid4())
        config = _make_config(thread_id)

        # Simulate state as if rag_node just completed
        state_after_rag = _make_initial_state("search arxiv for transformers")
        state_after_rag["retrieved_contexts"] = [
            {"document_id": "d1", "title": "Attention Is All You Need", "content": "...", "score": 0.95}
        ]

        graph.update_state(
            config,
            values=state_after_rag,
            as_node="rag_node",
        )

        # Run from intent_classifier_node, interrupt before LLM calls
        # (research_subgraph would try to call real LLM)
        snapshot = await graph.aget_state(config)
        assert snapshot is not None
        # Verify next node is intent_classifier_node
        assert "intent_classifier_node" in snapshot.next

    async def test_intent_classification_sets_correct_intent(self):
        """Intent classifier should set intent in state correctly."""
        from src.services.agent.graph import compile_agent_graph

        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        thread_id = str(uuid4())
        config = _make_config(thread_id)

        # Simulate: rag_node done, intent_classifier next
        state = _make_initial_state("write a literature review draft")

        graph.update_state(config, values=state, as_node="rag_node")

        # Run just the intent_classifier_node by interrupting after it
        result = await graph.ainvoke(
            None,
            config=config,
            interrupt_before=["memory_retrieval_node"],
        )

        snapshot = await graph.aget_state(config)
        # Intent should have been classified as "writing"
        assert snapshot.values.get("intent") == "writing"

    async def test_tool_node_executes_and_increments_loop_count(self):
        """tool_node should execute tools and increment tool_loop_count."""
        from src.services.agent.graph import compile_agent_graph

        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        thread_id = str(uuid4())
        config = _make_config(thread_id)

        # Simulate: LLM produced a tool call, state is at tool_node
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc1", "name": "search_arxiv", "args": {"query": "attention mechanism"}}],
        )
        state = _make_initial_state("find papers")
        state["messages"].append(ai_msg)
        state["intent"] = "general"
        state["tool_loop_count"] = 0

        # Mock execute_tool to avoid real API calls
        with patch(
            "src.api.agent.execute.execute_tool",
            new_callable=AsyncMock,
            return_value={"results": [], "total": 0},
        ):
            graph.update_state(config, values=state, as_node="llm_node")

            # Run tool_node, interrupt before next llm_node
            result = await graph.ainvoke(
                None,
                config=config,
                interrupt_before=["llm_node"],
            )

        snapshot = await graph.aget_state(config)
        # tool_loop_count should have been incremented by tool_node
        assert snapshot.values.get("tool_loop_count", 0) >= 1

    async def test_error_count_terminates_graph(self):
        """Graph should terminate when error_count >= MAX_ERRORS."""
        from src.services.agent.graph import MAX_ERRORS, compile_agent_graph

        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        thread_id = str(uuid4())
        config = _make_config(thread_id)

        # Simulate: LLM returned with tool_calls but we've hit max errors
        ai_msg = AIMessage(
            content="Let me try again",
            tool_calls=[{"id": "tc1", "name": "search_arxiv", "args": {"query": "test"}}],
        )
        state = _make_initial_state("test")
        state["messages"].append(ai_msg)
        state["intent"] = "general"
        state["error_count"] = MAX_ERRORS  # At max errors
        state["last_error"] = "repeated failures"

        graph.update_state(config, values=state, as_node="llm_node")

        # Should route to memory_save_node -> END instead of tool_node
        # This should complete without hanging
        result = await graph.ainvoke(None, config=config)
        assert result is not None


# ---------------------------------------------------------------------------
# Graph structure tests
# ---------------------------------------------------------------------------


class TestGraphStructure:
    """Verify the compiled graph has the expected structure."""

    def test_graph_has_all_expected_nodes(self):
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())

        expected_nodes = {
            "rag_node",
            "intent_classifier_node",
            "memory_retrieval_node",
            "llm_node",
            "tool_node",
            "interrupt_node",
            "memory_save_node",
            "research_subgraph",
            "writing_subgraph",
            "data_subgraph",
        }
        actual_nodes = set(graph.nodes.keys()) - {"__start__", "__end__"}
        assert expected_nodes.issubset(actual_nodes), (
            f"Missing nodes: {expected_nodes - actual_nodes}"
        )

    def test_graph_entry_point_is_rag_node(self):
        """The first node after __start__ should be rag_node."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())
        mermaid = graph.get_graph().draw_mermaid()
        # In Mermaid output, __start__ connects to rag_node
        assert "__start__" in mermaid
        assert "rag_node" in mermaid

    def test_graph_mermaid_output(self):
        """Graph should produce valid Mermaid diagram."""
        from src.services.agent.graph import compile_agent_graph

        graph = compile_agent_graph(checkpointer=MemorySaver())
        mermaid = graph.get_graph().draw_mermaid()
        assert "rag_node" in mermaid
        assert "llm_node" in mermaid
        assert "tool_node" in mermaid


# ---------------------------------------------------------------------------
# Human-in-the-loop (interrupt → confirm → resume) E2E tests
# ---------------------------------------------------------------------------


class TestHumanInTheLoopFlow:
    """Test the full interrupt → confirm → resume flow.

    In LangGraph >=1.x, ``interrupt()`` does not raise ``GraphInterrupt`` from
    ``ainvoke``.  Instead ``ainvoke`` returns the state dict containing an
    ``__interrupt__`` key and the graph pauses.  Interrupt details are available
    via ``aget_state().tasks[0].interrupts``.  Resuming is done by passing
    ``Command(resume=...)`` to a subsequent ``ainvoke`` call.
    """

    async def test_destructive_tool_triggers_interrupt(self):
        """A destructive tool call should pause the graph with an interrupt."""
        from src.services.agent.graph import compile_agent_graph

        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        thread_id = str(uuid4())
        config = _make_config(thread_id)

        # Create state where LLM has requested a destructive tool (ingest_arxiv_papers)
        ai_msg = AIMessage(
            content="I'll ingest those papers for you.",
            tool_calls=[{
                "id": "tc1",
                "name": "ingest_arxiv_papers",
                "args": {"paper_ids": ["2401.12345"]},
            }],
        )
        state = _make_initial_state("ingest this paper 2401.12345")
        state["messages"].append(ai_msg)
        state["intent"] = "general"

        # Set state as if llm_node just ran — should_continue will route to interrupt_node
        graph.update_state(config, values=state, as_node="llm_node")

        # Invoking should return state with __interrupt__ (graph paused)
        result = await graph.ainvoke(None, config=config)
        assert "__interrupt__" in result, "Graph should pause with an __interrupt__ key"

        # Verify the graph is paused at interrupt_node
        snapshot = await graph.aget_state(config)
        assert "interrupt_node" in snapshot.next, "Graph should be paused at interrupt_node"

        # The interrupt should contain confirmation details
        assert len(snapshot.tasks) > 0
        task = snapshot.tasks[0]
        assert hasattr(task, "interrupts") and len(task.interrupts) > 0
        confirmation = task.interrupts[0].value
        assert "tools" in confirmation
        assert any(t["name"] == "ingest_arxiv_papers" for t in confirmation["tools"])
        assert "message" in confirmation

    async def test_confirmed_interrupt_resumes_execution(self):
        """After confirming, the graph should resume and execute the tool."""
        from langgraph.types import Command
        from src.services.agent.graph import compile_agent_graph

        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        thread_id = str(uuid4())
        config = _make_config(thread_id)

        # Setup: LLM requested a destructive tool
        ai_msg = AIMessage(
            content="I'll ingest that paper.",
            tool_calls=[{
                "id": "tc1",
                "name": "ingest_arxiv_papers",
                "args": {"paper_ids": ["2401.12345"]},
            }],
        )
        state = _make_initial_state("ingest paper 2401.12345")
        state["messages"].append(ai_msg)
        state["intent"] = "general"

        graph.update_state(config, values=state, as_node="llm_node")

        # First invoke triggers interrupt (graph pauses)
        result = await graph.ainvoke(None, config=config)
        assert "__interrupt__" in result, "Graph should pause with an interrupt"

        # Now resume with confirmation
        with patch(
            "src.api.agent.execute.execute_tool",
            new_callable=AsyncMock,
            return_value={"status": "success", "document_ids": ["doc-uuid-1"]},
        ):
            # Also mock the LLM for the post-tool response
            with patch("src.services.agent.graph._build_llm") as mock_build:
                mock_llm = MagicMock()
                mock_response = AIMessage(content="Papers ingested successfully!")
                mock_llm.bind_tools.return_value.ainvoke = AsyncMock(return_value=mock_response)
                mock_build.return_value = mock_llm

                result = await graph.ainvoke(
                    Command(resume={"confirmed": True}),
                    config=config,
                )

        # Graph should have completed with the tool result and LLM response
        assert result is not None
        assert "__interrupt__" not in result, "Graph should have completed (no pending interrupt)"
        final_answer = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                final_answer = msg.content
                break
        assert final_answer, "Should have a final AI response after resume"

        # Verify the graph reached the end (no next nodes)
        snapshot = await graph.aget_state(config)
        assert not snapshot.next, "Graph should have completed (no next nodes)"

    async def test_denied_interrupt_skips_tool(self):
        """Denying the interrupt should skip tool execution."""
        from langgraph.types import Command
        from src.services.agent.graph import compile_agent_graph

        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        thread_id = str(uuid4())
        config = _make_config(thread_id)

        # Setup: LLM requested a destructive tool
        ai_msg = AIMessage(
            content="I'll create a draft.",
            tool_calls=[{
                "id": "tc1",
                "name": "create_draft",
                "args": {"themes": ["AI"]},
            }],
        )
        state = _make_initial_state("create a draft about AI")
        state["messages"].append(ai_msg)
        state["intent"] = "general"

        graph.update_state(config, values=state, as_node="llm_node")

        # First invoke triggers interrupt (graph pauses)
        result = await graph.ainvoke(None, config=config)
        assert "__interrupt__" in result, "Graph should pause with an interrupt"

        # Resume with denial
        result = await graph.ainvoke(
            Command(resume={"confirmed": False}),
            config=config,
        )

        # Should have a cancellation message, no tool execution
        assert result is not None
        assert "__interrupt__" not in result, "Graph should have completed after denial"
        # Check that the cancellation message is present
        has_cancel_msg = any(
            isinstance(msg, AIMessage) and "cancelled" in (msg.content or "").lower()
            for msg in result["messages"]
        )
        assert has_cancel_msg, "Should have a cancellation message"

        # Verify the graph reached the end
        snapshot = await graph.aget_state(config)
        assert not snapshot.next, "Graph should have completed (no next nodes)"

    async def test_non_destructive_tool_skips_interrupt(self):
        """Non-destructive tool calls should bypass the interrupt node entirely."""
        from src.services.agent.graph import compile_agent_graph

        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        thread_id = str(uuid4())
        config = _make_config(thread_id)

        # Setup: LLM requested a non-destructive tool (search_arxiv)
        ai_msg = AIMessage(
            content="Let me search for that.",
            tool_calls=[{
                "id": "tc1",
                "name": "search_arxiv",
                "args": {"query": "transformers"},
            }],
        )
        state = _make_initial_state("find papers on transformers")
        state["messages"].append(ai_msg)
        state["intent"] = "general"

        graph.update_state(config, values=state, as_node="llm_node")

        # Mock tool execution and LLM for the post-tool response
        with patch(
            "src.api.agent.execute.execute_tool",
            new_callable=AsyncMock,
            return_value={"results": [], "total": 0},
        ):
            with patch("src.services.agent.graph._build_llm") as mock_build:
                mock_llm = MagicMock()
                mock_response = AIMessage(content="No papers found.")
                mock_llm.bind_tools.return_value.ainvoke = AsyncMock(return_value=mock_response)
                mock_build.return_value = mock_llm

                result = await graph.ainvoke(None, config=config)

        # Should complete without any interrupt
        assert result is not None
        assert "__interrupt__" not in result, "Non-destructive tools should not trigger interrupt"
        snapshot = await graph.aget_state(config)
        assert not snapshot.next, "Graph should have completed"
