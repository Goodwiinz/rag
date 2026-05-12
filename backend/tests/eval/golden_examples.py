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
    # Optional reference answer for semantic-equivalence judging.
    # Empty string means the correctness evaluator skips this case.
    # Use for cases where a canonical answer shape is known
    # (greetings, refusals, capability questions); leave empty for
    # retrieval-driven cases whose exact wording depends on indexed
    # content.
    expected_answer: str = ""
    # Optional escape hatch for genuinely ambiguous intents. When set,
    # the evaluator accepts any of these intents in addition to
    # ``expected_intent``. Use sparingly — only for queries where two
    # subgraphs both produce correct behaviour (e.g. "Summarize arxiv X"
    # is sensible from either writing or research).
    accept_intents: tuple[str, ...] = ()
    # Tool match strategy:
    #   "subset_in_order" (default): every tool in expected_tools must
    #     appear in actual calls in the given order.
    #   "any":  pass if ANY of expected_tools appeared. For cases where
    #     the agent has multiple equally-correct paths (e.g. ingest-first
    #     vs summarize-first chain) and we only care that the dead-end
    #     refusal is gone.
    tool_match: str = "subset_in_order"


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
        expected_answer="A friendly greeting reply, offering to help. No tools, no retrieval.",
        metadata={"feature": "planner_skip_heuristic"},
    ),
    GoldenCase(
        name="thanks_skip",
        question="Thanks for your help!",
        expected_intent="general",
        expected_tools=(),
        expected_answer="A brief acknowledgement of thanks (e.g. 'You're welcome'), optionally offering further help.",
        metadata={"feature": "planner_skip_heuristic"},
    ),
    GoldenCase(
        name="capability_question_skip",
        question="What can you do?",
        expected_intent="general",
        expected_tools=(),
        expected_answer="A high-level description of capabilities: research (arXiv search/ingest), writing (drafts, notes, summaries), document Q&A, project management. Should not invoke retrieval tools for this meta-question.",
        metadata={"feature": "planner_skip_heuristic"},
    ),
)

# arXiv ID resolution coverage. Includes the writing-subgraph auto-chain
# recovery path (summarize → recoverable → ingest_arxiv_papers).
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
    GoldenCase(
        name="summarize_arxiv_auto_chain",
        question="Summarize arxiv paper 2201.00978",
        # Either writing (recovery chain via summarize_document → ingest
        # hint) or research (LLM picks ingest directly) is acceptable.
        # Two valid tool paths: ingest-first (smart) or summarize-first
        # (follows recovery prompt). Pre-fix behaviour was 0 tools +
        # refusal — any tool call proves the dead-end is gone.
        expected_intent="writing",
        accept_intents=("research",),
        expected_tools=("ingest_arxiv_papers", "summarize_document"),
        tool_match="any",
        metadata={"feature": "writing_recovery_chain"},
    ),
)


ALL_CASES: tuple[GoldenCase, ...] = DO_KB_CASES + PLANNER_SKIP_CASES + ARXIV_ID_CASES
