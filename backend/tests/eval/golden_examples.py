"""Golden Q&A regression cases for the agent.

Each case captures user input + expected intent + expected tool sequence.
Used by ``test_agent_regression.py`` and ``upload_golden.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GoldenCase:
    name: str
    question: str
    expected_intent: str
    expected_tools: tuple[str, ...] = ()
    page_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# do-kb activation coverage — verifies do_kb_retrieve tool selection
DO_KB_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="do_kb_semantic_search_in_project",
        question="What does our knowledge base say about transformer attention?",
        expected_intent="research",
        expected_tools=("do_kb_retrieve",),
        page_context={"type": "project", "project_id": "42e805e9-7a8d-4117-86ff-b0f1169bc05a"},
        metadata={"feature": "do_kb_activation"},
    ),
    GoldenCase(
        name="do_kb_org_wide_search",
        question="Search the org knowledge base for retrieval-augmented generation papers",
        expected_intent="research",
        expected_tools=("do_kb_retrieve",),
        metadata={"feature": "do_kb_activation"},
    ),
)

# Planner skip-heuristic coverage — pure conversational, no tools, no rag_node
PLANNER_SKIP_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="greeting_skip",
        question="Hello!",
        expected_intent="general",
        expected_tools=(),
        metadata={"feature": "planner_skip_heuristic"},
    ),
    GoldenCase(
        name="thanks_skip",
        question="Thanks for your help!",
        expected_intent="general",
        expected_tools=(),
        metadata={"feature": "planner_skip_heuristic"},
    ),
    GoldenCase(
        name="capability_question_skip",
        question="What can you do?",
        expected_intent="general",
        expected_tools=(),
        metadata={"feature": "planner_skip_heuristic"},
    ),
)

# arXiv ID resolution coverage. Note: writing-subgraph auto-chain
# (ingest → summarize) is currently a separate gap and not covered here;
# the dedicated test is in test_summarize_document_arxiv_hint.py.
ARXIV_ID_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="ingest_arxiv_id_only",
        question="Add arxiv 1706.03762 to my library",
        expected_intent="research",
        expected_tools=("ingest_arxiv_papers",),
        metadata={"feature": "arxiv_id_resolution"},
    ),
    GoldenCase(
        name="ingest_arxiv_imperative",
        question="Ingest arxiv paper 2201.00978",
        expected_intent="research",
        expected_tools=("ingest_arxiv_papers",),
        metadata={"feature": "arxiv_id_resolution"},
    ),
)


ALL_CASES: tuple[GoldenCase, ...] = DO_KB_CASES + PLANNER_SKIP_CASES + ARXIV_ID_CASES
