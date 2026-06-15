"""Golden Q&A regression cases for the agent.

Each case captures user input + expected intent + expected tool sequence.
Used by ``test_agent_regression.py`` and ``upload_golden.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


@dataclass(frozen=True)
class GoldenCase:
    name: str
    question: str
    expected_intent: str
    expected_tools: tuple[str, ...] = ()
    page_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional multi-turn prior history. When set, the harness seeds the agent
    # with these messages instead of a single ``question`` (see
    # _build_initial_state). Carries LangChain message objects, so cases using
    # it are LOCAL-ONLY — they are not JSON-serialised into the LangSmith
    # dataset by upload_golden.
    messages: tuple[Any, ...] = ()


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
        metadata={"feature": "greeting_template"},
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

# Greeting fast-path coverage (PR #619) — bare greetings route to general,
# bind ZERO tools, and (post-#619) get a templated zero-LLM reply. One per
# greeting family so a regression of _is_greeting / _greeting_reply is caught.
GREETING_CASES: tuple[GoldenCase, ...] = (
    GoldenCase("greeting_hi", "Hi", "general", (), metadata={"feature": "greeting_fast_path"}),
    GoldenCase("greeting_hey_there", "Hey there", "general", (), metadata={"feature": "greeting_fast_path"}),
    GoldenCase("greeting_good_morning", "Good morning", "general", (), metadata={"feature": "greeting_fast_path"}),
    GoldenCase("greeting_yo", "Yo", "general", (), metadata={"feature": "greeting_fast_path"}),
    GoldenCase("greeting_greetings", "Greetings", "general", (), metadata={"feature": "greeting_fast_path"}),
    GoldenCase(
        name="greeting_in_project",
        question="Hello!",
        expected_intent="general",
        expected_tools=(),
        page_context={"type": "project", "project_id": "42e805e9-7a8d-4117-86ff-b0f1169bc05a", "project_name": "Transformer Papers"},
        metadata={"feature": "greeting_fast_path"},
    ),
)

# Ack discriminators — "yes"/"no"/"thanks"/"ok" classify as general and bind
# no tools, but must NOT be swallowed by the greeting template (they often
# answer a prior question / HITL confirmation). Pins _is_greeting's exclusion.
ACK_CASES: tuple[GoldenCase, ...] = (
    GoldenCase("ack_yes", "Yes", "general", (), metadata={"feature": "ack_discriminator"}),
    GoldenCase("ack_no", "No", "general", (), metadata={"feature": "ack_discriminator"}),
    GoldenCase("ack_thanks", "Thanks", "general", (), metadata={"feature": "ack_discriminator"}),
    GoldenCase("ack_ok", "Ok", "general", (), metadata={"feature": "ack_discriminator"}),
)

# Intent-routing coverage for the two previously-untested subgraphs. These
# assert INTENT only (expected_tools=()): the specific tool call is LLM-
# dependent and would make the regression flaky, but the routing decision
# (writing vs knowledge_graph vs research) is the high-value signal.
WRITING_CASES: tuple[GoldenCase, ...] = (
    GoldenCase("writing_summarize", "Summarize the latest paper in my library", "writing", (), metadata={"feature": "writing_intent"}),
    GoldenCase("writing_draft", "Draft a related-work section on attention mechanisms", "writing", (), metadata={"feature": "writing_intent"}),
    GoldenCase("writing_bibliography", "Export my project bibliography as BibTeX", "writing", (), metadata={"feature": "writing_intent"}),
)

KG_CASES: tuple[GoldenCase, ...] = (
    GoldenCase("kg_extract_entities", "Extract the key entities from this document", "knowledge_graph", (), metadata={"feature": "kg_intent"}),
    GoldenCase("kg_search_graph", "What is connected to BERT in our knowledge graph?", "knowledge_graph", (), metadata={"feature": "kg_intent"}),
    GoldenCase("kg_neighborhood", "Explore the entity neighborhood around transformers", "knowledge_graph", (), metadata={"feature": "kg_intent"}),
)

# Project-scoped multi-step query — exists to make the planner emit a
# NON-EMPTY plan so the online `plan_adherence` evaluator has something to
# score (it is vacuously 1 on the empty plans every other case produces).
# Asserts intent only; the plan itself is judged online, not here.
PLAN_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="plan_multistep_research",
        question="Find recent transformer papers, add the top three to this project, and summarize them",
        expected_intent="research",
        expected_tools=(),
        page_context={"type": "project", "project_id": "42e805e9-7a8d-4117-86ff-b0f1169bc05a", "project_name": "Transformer Papers"},
        metadata={"feature": "plan_adherence_fixture"},
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


# Multi-turn retry follow-up — pins _extract_prior_tool + the "Handling retry
# follow-ups" rule (_nodes_classify.py / _prompts.py): a bare "try again" after
# a failed tool call must route back to the prior tool's intent. LOCAL-ONLY
# (LangChain message objects do not serialise into the LangSmith dataset), so
# kept out of ALL_CASES and excluded from upload_golden.
RETRY_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="retry_after_failed_search",
        question="",
        expected_intent="research",
        expected_tools=(),
        messages=(
            AIMessage(
                content="",
                tool_calls=[
                    {"type": "tool_call", "id": "c1", "name": "search_arxiv", "args": {"query": "transformers"}}
                ],
            ),
            ToolMessage(content="error: rate limited", tool_call_id="c1"),
            HumanMessage(content="try again"),
        ),
        metadata={"feature": "retry_followup"},
    ),
)


# Uploaded to the remote LangSmith dataset (question-based rows only).
ALL_CASES: tuple[GoldenCase, ...] = (
    DO_KB_CASES
    + PLANNER_SKIP_CASES
    + GREETING_CASES
    + ACK_CASES
    + WRITING_CASES
    + KG_CASES
    + ARXIV_ID_CASES
    + PLAN_CASES
)

# Full set the LOCAL golden test runs — adds message-based cases that cannot
# be serialised into the remote dataset. Use this for test parametrization;
# use ALL_CASES for upload.
LOCAL_CASES: tuple[GoldenCase, ...] = ALL_CASES + RETRY_CASES
