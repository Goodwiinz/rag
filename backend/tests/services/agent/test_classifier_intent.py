"""Regression tests for classifier intent routing.

Covers the disambiguation between the indexed document corpus
("knowledge base", "our docs") — which routes to the ``research`` intent
and the ``do_kb_retrieve`` tool — and the Neo4j entity graph
("knowledge graph", "extract entities") — which routes to the
``knowledge_graph`` intent and the data subgraph.
"""

from __future__ import annotations

import pytest

from src.services.agent.classifier import classify_intent_keywords


@pytest.mark.unit
def test_kb_query_classified_research() -> None:
    """KB queries route to research so do_kb_retrieve becomes available."""
    result = classify_intent_keywords(
        "What does our knowledge base say about transformer attention?"
    )
    assert result.intent == "research"
    assert result.source == "keyword"
    assert result.confidence > 0


@pytest.mark.unit
def test_our_docs_classified_research() -> None:
    """'our docs' phrasing routes to research."""
    result = classify_intent_keywords("Search our docs for RLHF")
    assert result.intent == "research"


@pytest.mark.unit
def test_our_library_classified_research() -> None:
    """'our library' phrasing routes to research."""
    result = classify_intent_keywords("Look up our library for diffusion papers")
    assert result.intent == "research"


@pytest.mark.unit
def test_kg_query_classified_knowledge_graph() -> None:
    """Regression guard: 'knowledge graph' still routes to knowledge_graph."""
    result = classify_intent_keywords(
        "Search the knowledge graph for entities related to BERT"
    )
    assert result.intent == "knowledge_graph"


@pytest.mark.unit
def test_extract_entities_classified_knowledge_graph() -> None:
    """Regression guard: explicit entity-extraction intent unchanged."""
    result = classify_intent_keywords("Extract entities from this paper")
    assert result.intent == "knowledge_graph"


@pytest.mark.unit
def test_kb_phrase_does_not_substring_match_skbio() -> None:
    """Sanity check: 'kb' was deliberately omitted from keyword list to avoid
    matching tokens like 'skbio'. A query about scikit-bio must not be
    classified as research on the basis of 'kb' alone."""
    result = classify_intent_keywords("Tell me about skbio versions")
    assert result.intent == "general"
