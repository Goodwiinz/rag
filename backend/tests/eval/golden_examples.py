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


# Knowledge-graph routing coverage — verifies KG-subgraph tool selection.
KG_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="kg_search_concept",
        question="Search the knowledge graph for relationships involving transformer architectures",
        expected_intent="knowledge_graph",
        accept_intents=("data", "research"),
        expected_tools=("search_knowledge_graph",),
        metadata={"feature": "kg_routing"},
    ),
    GoldenCase(
        name="kg_explore_neighborhood",
        question="Show me entities connected to BERT in the knowledge graph",
        expected_intent="knowledge_graph",
        accept_intents=("data", "research"),
        expected_tools=("search_knowledge_graph", "explore_entity_neighborhood"),
        tool_match="any",
        metadata={"feature": "kg_routing"},
    ),
    GoldenCase(
        name="kg_extract_entities",
        question="Extract entities from my latest indexed document",
        expected_intent="knowledge_graph",
        accept_intents=("data",),
        # Without fixture data the agent often lists documents first to
        # identify "latest" before extracting.
        expected_tools=("extract_entities", "list_project_documents", "search_documents"),
        tool_match="any",
        metadata={"feature": "kg_routing"},
    ),
)

# Draft / writing-tool coverage — verifies writing-subgraph routing.
# create_draft is destructive → triggers HITL interrupt; tool name still
# shows up in interrupted_tool_calls. Without fixture data the agent may
# fall back to lookup tools, so we use tool_match="any" with permissive
# tool lists that include reasonable recovery paths.
DRAFT_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="create_literature_review_draft",
        question="Write a literature review draft about retrieval-augmented generation",
        expected_intent="writing",
        expected_tools=("create_draft",),
        tool_match="any",
        metadata={"feature": "draft_generation"},
    ),
    # NOTE: export_bibliography case removed — without project_id fixture,
    # agent correctly asks "which project?" instead of guessing. Re-add
    # when test fixtures provide a seeded project with documents.
    GoldenCase(
        name="compare_two_documents",
        question="Compare the two most recently indexed papers on attention mechanisms",
        expected_intent="writing",
        accept_intents=("research",),
        # Agent may search/list documents first to identify "two most recent".
        expected_tools=("compare_documents", "search_documents", "list_project_documents"),
        tool_match="any",
        metadata={"feature": "document_comparison"},
    ),
)


ALL_CASES: tuple[GoldenCase, ...] = (
    DO_KB_CASES
    + PLANNER_SKIP_CASES
    + ARXIV_ID_CASES
    + KG_CASES
    + DRAFT_CASES
)
