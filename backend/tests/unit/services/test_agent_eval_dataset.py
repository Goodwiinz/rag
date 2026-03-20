"""LangSmith dataset evaluation suite for the RAG agent.

Defines a curated evaluation dataset, custom evaluators, and an
aggregate benchmark test that runs the agent against every example
and asserts minimum accuracy thresholds.

Results are uploaded to LangSmith under the ``rag-agent-evals`` project
so they can be compared across runs in the dashboard.

Requirements:
  - LANGCHAIN_API_KEY set in environment
  - AZURE_OPENAI_CHAT_ENDPOINT and AZURE_OPENAI_CHAT_API_KEY set
  - Run with: pytest tests/unit/services/test_agent_eval_dataset.py -m langsmith -v

These tests are skipped by default unless credentials are present.
"""

import os
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

# ---------------------------------------------------------------------------
# Credential checks
# ---------------------------------------------------------------------------

_HAS_LANGSMITH = bool(os.environ.get("LANGCHAIN_API_KEY"))
_HAS_LLM = bool(
    os.environ.get("AZURE_OPENAI_CHAT_API_KEY")
    or os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT")
)

if _HAS_LANGSMITH:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "rag-agent-evals")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.langsmith,
    pytest.mark.skipif(
        not (_HAS_LANGSMITH and _HAS_LLM),
        reason="Requires LANGCHAIN_API_KEY and Azure OpenAI credentials",
    ),
]


# ---------------------------------------------------------------------------
# Evaluation dataset
# ---------------------------------------------------------------------------

EVAL_EXAMPLES: list[dict[str, Any]] = [
    # Research intent - should use search tools
    {
        "input": {"question": "Find recent papers on transformer architectures"},
        "expected": {"intent": "research", "tool": "search_arxiv"},
    },
    {
        "input": {"question": "Search arxiv for retrieval augmented generation"},
        "expected": {"intent": "research", "tool": "search_arxiv"},
    },
    {
        "input": {"question": "Look up papers about attention mechanisms"},
        "expected": {"intent": "research", "tool": "search_arxiv"},
    },
    {
        "input": {"question": "Import this arxiv paper 2401.12345"},
        "expected": {"intent": "research", "tool": "ingest_arxiv_papers"},
    },
    {
        "input": {"question": "Find documents about neural networks in my library"},
        "expected": {"intent": "research", "tool": "search_documents"},
    },
    # Writing intent - should use writing tools
    {
        "input": {"question": "Write a literature review draft about machine learning"},
        "expected": {"intent": "writing", "tool": "create_draft"},
    },
    {
        "input": {"question": "Summarize this document for me"},
        "expected": {"intent": "writing", "tool": "summarize_document"},
    },
    {
        "input": {"question": "Compare these two papers on NLP"},
        "expected": {"intent": "writing", "tool": "compare_documents"},
    },
    {
        "input": {"question": "Export bibliography in bibtex format"},
        "expected": {"intent": "writing", "tool": "export_bibliography"},
    },
    {
        "input": {"question": "Create a note about key findings"},
        "expected": {"intent": "writing", "tool": "create_project_note"},
    },
    # Knowledge graph intent
    {
        "input": {"question": "Extract entities from this document"},
        "expected": {"intent": "knowledge_graph", "tool": "extract_entities"},
    },
    {
        "input": {"question": "Search the knowledge graph for relationships between concepts"},
        "expected": {"intent": "knowledge_graph", "tool": "search_knowledge_graph"},
    },
    # General - no tools expected
    {
        "input": {"question": "Hello, how are you?"},
        "expected": {"intent": "general", "tool": None},
    },
    {
        "input": {"question": "What can you help me with?"},
        "expected": {"intent": "general", "tool": None},
    },
    {
        "input": {"question": "Thanks for your help!"},
        "expected": {"intent": "general", "tool": None},
    },
]


# ---------------------------------------------------------------------------
# Helpers (aligned with test_agent_langsmith.py patterns)
# ---------------------------------------------------------------------------


def _make_state(user_msg: str) -> dict:
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


def _extract_tool_calls(state: dict) -> list[str]:
    """Extract tool names from all AIMessages in state."""
    return [
        tc["name"]
        for msg in state.get("messages", [])
        if isinstance(msg, AIMessage)
        for tc in getattr(msg, "tool_calls", [])
    ]


def _extract_final_answer(state: dict) -> str:
    """Extract the last AI text message."""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return ""


@contextmanager
def _mock_infra():
    """Mock heavy infrastructure (RAG, memory, tools) while leaving the LLM real."""
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
                return_value={"results": [], "total": 0, "message": "Mocked tool result"}
            ),
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Target function for LangSmith evaluation
# ---------------------------------------------------------------------------


async def run_graph(inputs: dict) -> dict:
    """Target function that the LangSmith evaluator invokes per example.

    Accepts ``inputs`` with a ``"question"`` key, runs the full agent
    graph with mocked infrastructure, and returns structured outputs
    for the evaluators to score.
    """
    from src.services.agent.graph import compile_agent_graph

    question = inputs["question"]

    with _mock_infra():
        checkpointer = MemorySaver()
        graph = compile_agent_graph(checkpointer=checkpointer)
        config = _make_config()
        result = await graph.ainvoke(_make_state(question), config=config)

        # Read the intent from the checkpointed state
        snapshot = await graph.aget_state(config)
        intent = snapshot.values.get("intent", "")

    tool_calls = _extract_tool_calls(result)
    response = _extract_final_answer(result)

    return {
        "response": response,
        "intent": intent,
        "tool_calls": tool_calls,
        "messages": [
            {"type": type(m).__name__, "content": getattr(m, "content", "")}
            for m in result["messages"]
        ],
        "num_steps": len(result["messages"]),
    }


# ---------------------------------------------------------------------------
# Evaluator functions
# ---------------------------------------------------------------------------


def correct_intent(inputs: dict, outputs: dict, reference_outputs: dict) -> bool:
    """Check if the classified intent matches the expected intent."""
    expected = reference_outputs.get("intent", "")
    actual = outputs.get("intent", "")
    return actual == expected


def correct_tool(inputs: dict, outputs: dict, reference_outputs: dict) -> bool:
    """Check if the first tool call matches the expected tool.

    For examples where no tool is expected (``tool`` is None), passes
    if the agent made zero tool calls.
    """
    expected_tool = reference_outputs.get("tool")
    actual_tools = outputs.get("tool_calls", [])

    if expected_tool is None:
        return len(actual_tools) == 0

    return expected_tool in actual_tools


def has_response(inputs: dict, outputs: dict) -> bool:
    """Check that the agent produced a non-empty text response."""
    response = outputs.get("response", "")
    return bool(response and response.strip())


def trajectory_efficiency(inputs: dict, outputs: dict) -> float:
    """Score 0-1 based on number of steps (fewer = better).

    Normalised against a maximum of 20 messages. An agent that
    finishes in 2 messages scores 0.9, one that uses all 20 scores 0.0.
    """
    max_steps = 20
    num_steps = outputs.get("num_steps", max_steps)
    score = max(0.0, 1.0 - (num_steps / max_steps))
    return round(score, 3)


# ---------------------------------------------------------------------------
# LLM-as-judge evaluator
# ---------------------------------------------------------------------------


async def answer_groundedness(inputs: dict, outputs: dict) -> bool:
    """LLM judge: is the answer grounded in tool outputs?

    Uses the same Azure LLM that powers the agent to evaluate whether
    the final response is grounded in the tool results it received.
    Returns True (grounded) or False (not grounded).

    If no tools were used there is nothing to ground against, so the
    evaluator returns True by default.
    """
    from src.services.agent.graph import _build_llm

    response_text = outputs.get("response", "")
    tool_calls = outputs.get("tool_calls", [])

    if not response_text or not tool_calls:
        return True  # No tools used, nothing to ground against

    judge = _build_llm()

    grade = await judge.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "You are evaluating whether an AI assistant's response is "
                    "grounded in the tool results it received. Return ONLY "
                    "'GROUNDED' or 'NOT_GROUNDED'."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"RESPONSE: {response_text[:1000]}\n\n"
                    f"TOOL CALLS: {tool_calls}\n\n"
                    "Is the response grounded in the tool results?"
                ),
            },
        ]
    )
    return "GROUNDED" in grade.content.upper()


# ---------------------------------------------------------------------------
# Dataset management helpers
# ---------------------------------------------------------------------------

DATASET_NAME = "agent-accuracy-benchmark"


def _ensure_dataset(client: "langsmith.Client") -> str:  # noqa: F821
    """Create the LangSmith dataset if it does not already exist.

    Returns the dataset name.
    """
    try:
        client.read_dataset(dataset_name=DATASET_NAME)
    except Exception:
        # Dataset does not exist yet — create it
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Agent intent classification and tool routing benchmark",
        )
        for ex in EVAL_EXAMPLES:
            client.create_example(
                inputs=ex["input"],
                outputs=ex["expected"],
                dataset_id=dataset.id,
            )
    return DATASET_NAME


# ---------------------------------------------------------------------------
# Benchmark test
# ---------------------------------------------------------------------------


@pytest.mark.langsmith
@pytest.mark.eval
async def test_agent_accuracy_benchmark():
    """Run the agent against the full eval dataset and assert aggregate scores.

    This test:
    1. Creates (or reuses) a LangSmith dataset from EVAL_EXAMPLES.
    2. Evaluates the agent graph on every example using ``client.aevaluate``.
    3. Asserts minimum thresholds for intent accuracy, tool accuracy, and
       response rate.

    Results are visible in the LangSmith dashboard under the
    ``rag-agent-evals`` project.
    """
    from langsmith import Client

    client = Client()

    # Ensure the dataset exists
    dataset_name = _ensure_dataset(client)

    # Run evaluation
    results = await client.aevaluate(
        run_graph,
        data=dataset_name,
        evaluators=[
            correct_intent,
            correct_tool,
            has_response,
            trajectory_efficiency,
            answer_groundedness,
        ],
        experiment_prefix="agent-accuracy",
        max_concurrency=1,  # Sequential to avoid Azure rate limits
    )

    # Aggregate scores
    df = results.to_pandas()

    intent_accuracy = df["feedback.correct_intent"].mean()
    tool_accuracy = df["feedback.correct_tool"].mean()
    response_rate = df["feedback.has_response"].mean()

    assert intent_accuracy >= 0.8, (
        f"Intent accuracy {intent_accuracy:.0%} below 80% threshold"
    )
    assert tool_accuracy >= 0.5, (
        f"Tool accuracy {tool_accuracy:.0%} below 50% threshold"
    )
    assert response_rate >= 0.9, (
        f"Response rate {response_rate:.0%} below 90% threshold"
    )
