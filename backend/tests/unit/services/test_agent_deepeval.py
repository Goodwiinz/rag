"""DeepEval metrics for agent accuracy testing.

Tests agent responses for hallucination, answer relevancy,
faithfulness to retrieved context, and tool correctness.

Run with: deepeval test run tests/unit/services/test_agent_deepeval.py
Or: pytest tests/unit/services/test_agent_deepeval.py -m deepeval

Requirements:
  - deepeval installed (pip install deepeval)
  - OPENAI_API_KEY set in environment (DeepEval uses OpenAI for LLM-judge metrics)
  - AZURE_OPENAI_CHAT_ENDPOINT and AZURE_OPENAI_CHAT_API_KEY set (for agent LLM)

Note: DeepEval metrics use an LLM judge internally. By default it uses OpenAI,
so OPENAI_API_KEY must be set separately from the Azure credentials used by
the agent itself. You can configure DeepEval to use Azure via its config, but
the simplest path is to set OPENAI_API_KEY for the judge model.
"""

import os
import pytest
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

# ---------------------------------------------------------------------------
# Conditional imports — skip gracefully if deepeval is not installed
# ---------------------------------------------------------------------------

# Check for a REAL OPENAI_API_KEY. DeepEval's pytest plugin sets a
# placeholder "your-openai-key-here" during initialization, so we must
# check the value, not just its presence.
_raw_openai_key = os.environ.get("OPENAI_API_KEY", "")
_HAS_OPENAI_JUDGE = bool(_raw_openai_key) and _raw_openai_key != "your-openai-key-here" and not _raw_openai_key.startswith("your-")

_HAS_LLM = bool(
    os.environ.get("AZURE_OPENAI_CHAT_API_KEY")
    or os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT")
)

try:
    from deepeval import assert_test
    from deepeval.test_case import LLMTestCase, ToolCall
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        HallucinationMetric,
        ToolCorrectnessMetric,
    )

    _HAS_DEEPEVAL = True
except ImportError:
    _HAS_DEEPEVAL = False

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.deepeval,
    pytest.mark.skipif(
        not (_HAS_DEEPEVAL and _HAS_LLM),
        reason="Requires deepeval and Azure OpenAI credentials",
    ),
]

# The model used by DeepEval as the LLM judge for metric evaluation.
JUDGE_MODEL = "gpt-4o"

# Relevancy / faithfulness thresholds (0-1). Lowered for mocked-infra tests
# where the agent has no real retrieval context to ground answers on.
RELEVANCY_THRESHOLD = 0.5
HALLUCINATION_THRESHOLD = 0.5
FAITHFULNESS_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(user_msg: str) -> dict:
    """Build a minimal initial AgentState dict."""
    from langchain_core.messages import HumanMessage

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


def _make_config() -> dict:
    """Build a minimal RunnableConfig with mocked user/db."""
    user = Mock(id=uuid4(), organization_id=uuid4())
    return {
        "configurable": {
            "thread_id": str(uuid4()),
            "db": AsyncMock(),
            "current_user": user,
            "page_context": {"type": "unknown"},
        }
    }


@contextmanager
def _mock_infra():
    """Mock heavy infrastructure (RAG, memory, tool execution) while
    leaving the LLM real so DeepEval can evaluate actual model output."""
    with (
        patch(
            "src.services.agent.graph.rag_node",
            new=AsyncMock(return_value={"retrieved_contexts": []}),
        ),
        patch(
            "src.services.agent.graph.memory_retrieval_node",
            new=AsyncMock(return_value={"user_memories": []}),
        ),
        patch(
            "src.services.agent.graph.memory_save_node",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "src.api.agent.execute.execute_tool",
            new=AsyncMock(
                return_value={
                    "results": [
                        {
                            "title": "Mock Result",
                            "content": "Mock content for testing",
                        }
                    ],
                    "total": 1,
                    "message": "Mocked tool result",
                }
            ),
        ),
    ):
        yield


def _extract_tool_calls(state: dict) -> list[str]:
    """Extract tool names from all AIMessages in state."""
    from langchain_core.messages import AIMessage

    return [
        tc["name"]
        for msg in state.get("messages", [])
        if isinstance(msg, AIMessage)
        for tc in getattr(msg, "tool_calls", [])
    ]


def _extract_final_answer(state: dict) -> str:
    """Extract the last AI text message from state."""
    from langchain_core.messages import AIMessage

    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return ""


def _extract_retrieval_context(state: dict) -> list[str]:
    """Extract retrieval context strings from state."""
    return [
        ctx.get("content", "")
        for ctx in state.get("retrieved_contexts", [])
        if ctx.get("content")
    ]


async def _run_agent(query: str) -> dict:
    """Run the agent graph with mocked infrastructure, return structured results.

    Returns a dict with keys:
      - response: final AI text answer
      - tool_calls: list of tool name strings
      - retrieval_context: list of context content strings
      - messages: full message list from state
    """
    from langgraph.checkpoint.memory import MemorySaver

    from src.services.agent.graph import compile_agent_graph

    with _mock_infra():
        graph = compile_agent_graph(checkpointer=MemorySaver())
        result = await graph.ainvoke(_make_state(query), config=_make_config())

    return {
        "response": _extract_final_answer(result),
        "tool_calls": _extract_tool_calls(result),
        "retrieval_context": _extract_retrieval_context(result),
        "messages": result.get("messages", []),
    }


# ---------------------------------------------------------------------------
# Test: Answer Relevancy
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_OPENAI_JUDGE, reason="Requires real OPENAI_API_KEY for DeepEval LLM judge")
class TestAgentAnswerRelevancy:
    """Test that agent answers are relevant to the user query.

    AnswerRelevancyMetric uses an LLM judge to score how well the
    actual_output addresses the input query.
    """

    async def test_research_query_relevancy(self):
        """Agent response to a research query should be relevant."""
        query = "Find papers about attention mechanisms in deep learning"
        result = await _run_agent(query)

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
        )
        metric = AnswerRelevancyMetric(
            threshold=RELEVANCY_THRESHOLD,
            model=JUDGE_MODEL,
        )
        assert_test(test_case, [metric])

    async def test_greeting_relevancy(self):
        """Agent response to a greeting should be relevant."""
        query = "Hello! What can you help me with?"
        result = await _run_agent(query)

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
        )
        metric = AnswerRelevancyMetric(
            threshold=RELEVANCY_THRESHOLD,
            model=JUDGE_MODEL,
        )
        assert_test(test_case, [metric])

    async def test_writing_query_relevancy(self):
        """Agent response to a writing request should be relevant."""
        query = "Summarize the key findings from my uploaded documents"
        result = await _run_agent(query)

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
        )
        metric = AnswerRelevancyMetric(
            threshold=RELEVANCY_THRESHOLD,
            model=JUDGE_MODEL,
        )
        assert_test(test_case, [metric])


# ---------------------------------------------------------------------------
# Test: Hallucination
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_OPENAI_JUDGE, reason="Requires real OPENAI_API_KEY for DeepEval LLM judge")
class TestAgentHallucination:
    """Test that agent does not hallucinate beyond tool/context data.

    HallucinationMetric checks whether the actual_output contains
    information not grounded in the provided context.
    """

    async def test_no_hallucination_on_search(self):
        """Agent should not fabricate search results."""
        query = "Search for papers on quantum computing"
        result = await _run_agent(query)

        # Build context from what the (mocked) tools returned
        context = (
            ["Mock content for testing"]
            if result["tool_calls"]
            else ["No tools were used. The agent responded from general knowledge."]
        )

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
            context=context,
        )
        metric = HallucinationMetric(
            threshold=HALLUCINATION_THRESHOLD,
            model=JUDGE_MODEL,
        )
        assert_test(test_case, [metric])

    async def test_no_hallucination_on_greeting(self):
        """Agent should not hallucinate when responding to a greeting."""
        query = "Hi there! Tell me about yourself."
        result = await _run_agent(query)

        context = [
            "You are an AI research agent for a RAG-powered academic "
            "research system. You help users search documents, manage "
            "research projects, find ArXiv papers, create notes, and "
            "analyze research."
        ]

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
            context=context,
        )
        metric = HallucinationMetric(
            threshold=HALLUCINATION_THRESHOLD,
            model=JUDGE_MODEL,
        )
        assert_test(test_case, [metric])


# ---------------------------------------------------------------------------
# Test: Faithfulness
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_OPENAI_JUDGE, reason="Requires real OPENAI_API_KEY for DeepEval LLM judge")
class TestAgentFaithfulness:
    """Test that agent responses are faithful to retrieved context.

    FaithfulnessMetric checks whether claims in actual_output can be
    attributed to the retrieval_context.
    """

    async def test_faithfulness_with_context(self):
        """Agent claims should be traceable to retrieval context."""
        query = "What do my documents say about neural networks?"
        result = await _run_agent(query)

        # Use retrieval context if available, otherwise provide minimal context
        retrieval_context = result["retrieval_context"] or [
            "No documents were retrieved for this query."
        ]

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
            retrieval_context=retrieval_context,
        )
        metric = FaithfulnessMetric(
            threshold=FAITHFULNESS_THRESHOLD,
            model=JUDGE_MODEL,
        )
        assert_test(test_case, [metric])


# ---------------------------------------------------------------------------
# Test: Tool Correctness
# ---------------------------------------------------------------------------


class TestAgentToolCorrectness:
    """Test that the agent selects the right tools for given queries.

    ToolCorrectnessMetric compares tools_called against expected_tools.
    """

    async def test_search_uses_arxiv_tool(self):
        """Agent should call search_arxiv for an arXiv search request."""
        query = "Search arxiv for transformer papers"
        result = await _run_agent(query)

        actual_tools = [ToolCall(name=tc) for tc in result["tool_calls"]]
        expected_tools = [ToolCall(name="search_arxiv")]

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
            tools_called=actual_tools,
            expected_tools=expected_tools,
        )
        metric = ToolCorrectnessMetric()
        assert_test(test_case, [metric])

    async def test_greeting_uses_no_tools(self):
        """Agent should NOT invoke tools for a simple greeting."""
        query = "Hi there!"
        result = await _run_agent(query)

        actual_tools = [ToolCall(name=tc) for tc in result["tool_calls"]]

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
            tools_called=actual_tools,
            expected_tools=[],  # No tools expected for greetings
        )
        metric = ToolCorrectnessMetric()
        assert_test(test_case, [metric])

    async def test_document_search_uses_search_documents(self):
        """Agent should call search_documents for local document queries."""
        query = "Search my documents for papers about climate change"
        result = await _run_agent(query)

        actual_tools = [ToolCall(name=tc) for tc in result["tool_calls"]]
        expected_tools = [ToolCall(name="search_documents")]

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
            tools_called=actual_tools,
            expected_tools=expected_tools,
        )
        metric = ToolCorrectnessMetric()
        assert_test(test_case, [metric])

    async def test_knowledge_graph_uses_extract_entities(self):
        """Agent should call extract_entities for entity extraction requests."""
        query = "Extract entities from document abc-123"
        result = await _run_agent(query)

        actual_tools = [ToolCall(name=tc) for tc in result["tool_calls"]]
        # At minimum, extract_entities should be among the called tools
        expected_tools = [ToolCall(name="extract_entities")]

        test_case = LLMTestCase(
            input=query,
            actual_output=result["response"],
            tools_called=actual_tools,
            expected_tools=expected_tools,
        )
        metric = ToolCorrectnessMetric()
        assert_test(test_case, [metric])
