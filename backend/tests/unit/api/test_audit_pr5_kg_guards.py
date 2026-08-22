"""Audit PR5 regression guards — KG integrity cluster.

Covers:
- R5-M1: circuit breaker failure-count reset on success in CLOSED
- R2-M5: sync Neo4j driver calls offloaded from the event loop
- R5-M3: paper-title entity ensured before edge creation; loud skip on
  unresolvable endpoints (no silent all-edge drops)
- R5-M5: exact-name endpoint resolution; ambiguous prefix hits are skipped
- R2-M6: papers correlated to documents by arXiv id, not positional zip
- R5-L1/L2/L4: deterministic pagination ORDER BY, start entity excluded from
  LIMIT accounting, no private session._database access
- R5-L5: located_in requires word boundaries + location-like target;
  direction follows textual order
"""

from __future__ import annotations

import inspect
import logging
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.circuit_breaker import CircuitState, ServiceCircuitBreaker
from src.services.arxiv import arxiv_kg_integration as kg_module
from src.services.arxiv.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
from src.services.knowledge_graph.knowledge_graph_service import KnowledgeGraphService

pytestmark = pytest.mark.unit


def _paper(title: str = "A Study of Attention", pid: str = "2401.00001v1") -> dict:
    return {
        "id": pid,
        "title": title,
        "abstract": "Abstract text.",
        "authors": ["Ada Lovelace"],
        "categories": ["cs.AI"],
        "primary_category": "cs.AI",
    }


def _node(id: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=id, name=name)


# ---------------------------------------------------------------------------
# R5-M1: circuit breaker reset
# ---------------------------------------------------------------------------


def test_breaker_success_in_closed_resets_failure_count() -> None:
    breaker = ServiceCircuitBreaker("svc", failure_threshold=5)
    for _ in range(4):
        breaker.record_failure(Exception("blip"))
    assert breaker.get_stats().failure_count == 4

    breaker.record_success()

    assert breaker.get_stats().failure_count == 0

    # Historical blips must not accumulate into a spurious OPEN.
    for _ in range(4):
        breaker.record_failure(Exception("another day, another blip"))
    assert breaker.state is CircuitState.CLOSED


def test_breaker_half_open_recovery_still_resets_on_close() -> None:
    breaker = ServiceCircuitBreaker("svc", failure_threshold=1, half_open_max_calls=1)
    breaker.record_failure(Exception("down"))
    assert breaker.state is CircuitState.OPEN
    breaker._transition_to_half_open()
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.get_stats().failure_count == 0


# ---------------------------------------------------------------------------
# R2-M5: blocking Neo4j IO off the event loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_entity_runs_off_event_loop() -> None:
    integration = ArXivKnowledgeGraphIntegration()
    kg_service = MagicMock()
    seen_threads = []

    def slow_create(request):
        seen_threads.append(threading.get_ident())
        return SimpleNamespace(id="e1")

    kg_service.create_entity = MagicMock(side_effect=slow_create)
    integration.kg_service = kg_service

    ok = await integration._add_entity_to_kg(
        {
            "text": "Concept X",
            "type": "concept",
            "confidence": 0.9,
            "source": "test",
            "extraction_method": "manual",
        },
        _paper(),
        organization_id="org-1",
    )

    assert ok is True
    assert seen_threads and seen_threads[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_relationship_creation_runs_off_event_loop() -> None:
    integration = ArXivKnowledgeGraphIntegration()
    kg_service = MagicMock()
    seen_threads = []
    node = _node("n1", "Ada Lovelace")

    def search(query, limit=None, organization_id=None):
        return [node]

    def create_rel(request):
        seen_threads.append(threading.get_ident())
        return SimpleNamespace(id="r1")

    kg_service.search_entities = MagicMock(side_effect=search)
    kg_service.create_relationship = MagicMock(side_effect=create_rel)
    integration.kg_service = kg_service

    ok = await integration._add_relationship_to_kg(
        {
            "source": {"text": "Ada Lovelace", "type": "author"},
            "target": {"text": "Ada Lovelace", "type": "author"},
            "relation": "author_of",
            "confidence": 1.0,
        },
        _paper(),
        organization_id="org-1",
    )

    assert ok is True
    assert seen_threads and seen_threads[0] != threading.get_ident()


# ---------------------------------------------------------------------------
# R5-M3: paper-title entity + loud skips
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_paper_title_entity_is_created_before_edge(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    title = _paper()["title"]
    integration = ArXivKnowledgeGraphIntegration()
    kg_service = MagicMock()

    created_names = []
    ada = _node("ada-1", "Ada Lovelace")

    def fake_search(query, limit=None, organization_id=None):
        if query == "Ada Lovelace":
            return [ada]
        if created_names:
            return [_node("title-1", title)]
        return []

    def fake_create(request):
        created_names.append(request.name)
        return SimpleNamespace(id="title-1")

    kg_service.search_entities = MagicMock(side_effect=fake_search)
    kg_service.create_entity = MagicMock(side_effect=fake_create)
    kg_service.create_relationship = MagicMock(return_value=SimpleNamespace(id="r1"))
    integration.kg_service = kg_service

    with caplog.at_level(logging.WARNING):
        ok = await integration._add_relationship_to_kg(
            {
                "source": {"text": "Ada Lovelace", "type": "author"},
                "target": {"text": title, "type": "paper"},
                "relation": "author_of",
                "confidence": 1.0,
            },
            _paper(),
            organization_id="org-1",
        )

    assert ok is True
    assert title in created_names
    request = kg_service.create_relationship.call_args[0][0]
    assert request.source_entity_id == "ada-1"
    assert request.target_entity_id == "title-1"


@pytest.mark.asyncio
async def test_unresolvable_endpoint_skips_edge_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    integration = ArXivKnowledgeGraphIntegration()
    kg_service = MagicMock()
    kg_service.search_entities = MagicMock(return_value=[])
    integration.kg_service = kg_service

    with caplog.at_level(logging.WARNING):
        ok = await integration._add_relationship_to_kg(
            {
                "source": {"text": "Ghost Author", "type": "author"},
                "target": {"text": _paper()["title"], "type": "paper"},
                "relation": "author_of",
                "confidence": 1.0,
            },
            _paper(),
            organization_id="org-1",
        )

    assert ok is False
    kg_service.create_relationship.assert_not_called()
    assert any("could not be resolved" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# R5-M5: exact-name resolution beats prefix search
# ---------------------------------------------------------------------------


def _relationship(source: str, target: str) -> dict:
    return {
        "source": {"text": source, "type": "model"},
        "target": {"text": target, "type": "mechanism"},
        "relation": "USES",
        "confidence": 0.9,
        "extraction_source": "test",
    }


@pytest.mark.asyncio
async def test_exact_name_beats_prefix_hit() -> None:
    integration = ArXivKnowledgeGraphIntegration()
    kg_service = MagicMock()
    attention = _node("att-exact", "Attention")
    mechanism = _node("att-prefix", "Attention Mechanism")

    def fake_search(query, limit=None, organization_id=None):
        if query == "Attention":
            return [mechanism, attention]
        return [_node("bert-1", "BERT")]

    kg_service.search_entities = MagicMock(side_effect=fake_search)
    kg_service.create_relationship = MagicMock(return_value=SimpleNamespace(id="r1"))
    integration.kg_service = kg_service

    ok = await integration._add_relationship_to_kg(
        _relationship("BERT", "Attention"), _paper(), organization_id="org-1"
    )

    assert ok is True
    request = kg_service.create_relationship.call_args[0][0]
    assert request.target_entity_id == "att-exact"


@pytest.mark.asyncio
async def test_ambiguous_prefix_without_exact_skips_edge(
    caplog: pytest.LogCaptureFixture,
) -> None:
    integration = ArXivKnowledgeGraphIntegration()
    kg_service = MagicMock()

    def fake_search(query, limit=None, organization_id=None):
        if query == "Atten":
            return [
                _node("p1", "Attention Mechanism"),
                _node("p2", "Attention Is All You Need"),
            ]
        return [_node("bert-1", "BERT")]

    kg_service.search_entities = MagicMock(side_effect=fake_search)
    kg_service.create_relationship = MagicMock()
    integration.kg_service = kg_service

    with caplog.at_level(logging.WARNING):
        ok = await integration._add_relationship_to_kg(
            _relationship("BERT", "Atten"), _paper(), organization_id="org-1"
        )

    assert ok is False
    kg_service.create_relationship.assert_not_called()
    assert any("ambiguous" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_unambiguous_single_prefix_candidate_is_accepted() -> None:
    integration = ArXivKnowledgeGraphIntegration()
    kg_service = MagicMock()
    only = _node("only-1", "Attention Mechanism")

    def fake_search(query, limit=None, organization_id=None):
        if query == "Attenti":
            return [only]
        return [_node("bert-1", "BERT")]

    kg_service.search_entities = MagicMock(side_effect=fake_search)
    kg_service.create_relationship = MagicMock(return_value=SimpleNamespace(id="r1"))
    integration.kg_service = kg_service

    ok = await integration._add_relationship_to_kg(
        _relationship("BERT", "Attenti"), _paper(), organization_id="org-1"
    )

    assert ok is True
    request = kg_service.create_relationship.call_args[0][0]
    assert request.target_entity_id == "only-1"


# ---------------------------------------------------------------------------
# R2-M6: correlate documents by arXiv id, not position
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_correlates_documents_by_arxiv_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p1 = _paper(title="Paper One", pid="2401.11111v1")
    p2 = _paper(title="Paper Two", pid="2401.22222v1")
    doc2 = SimpleNamespace(metadata={"arxiv_id": "2401.22222v1"}, organization_id=None)

    integration = ArXivKnowledgeGraphIntegration()
    integration.arxiv_service = MagicMock()
    integration.arxiv_service.ingest_papers = AsyncMock(return_value=[doc2])
    integration.kg_service = MagicMock()

    extract_entities = AsyncMock(return_value=[])
    extract_relationships = AsyncMock(return_value=[])
    ensure_title = AsyncMock(return_value=None)
    add_entity = AsyncMock(return_value=True)
    monkeypatch.setattr(integration, "_extract_entities_from_paper", extract_entities)
    monkeypatch.setattr(
        integration, "_extract_relationships_from_paper", extract_relationships
    )
    monkeypatch.setattr(integration, "_ensure_paper_title_entity", ensure_title)
    monkeypatch.setattr(integration, "_add_entity_to_kg", add_entity)

    # p1's ingest failed => only [doc2] came back. The old zip(papers, docs)
    # would have processed p1 against doc2 and skipped p2 entirely.
    await integration.ingest_papers_with_kg(
        papers=[p1, p2],
        extract_entities=True,
        create_relationships=True,
        organization_id="org-9",
    )

    assert extract_entities.await_count == 1
    assert extract_entities.await_args[0][0] is p2
    assert add_entity.await_count == 0  # p2 has no extracted entities here
    assert ensure_title.await_count == 1
    assert ensure_title.await_args.kwargs["organization_id"] == "org-9"


@pytest.mark.asyncio
async def test_ingest_skips_document_without_arxiv_id(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    p1 = _paper(title="Paper One")
    mystery_doc = SimpleNamespace(metadata={}, organization_id=None)

    integration = ArXivKnowledgeGraphIntegration()
    integration.arxiv_service = MagicMock()
    integration.arxiv_service.ingest_papers = AsyncMock(return_value=[mystery_doc])
    integration.kg_service = MagicMock()

    extract_entities = AsyncMock(return_value=[])
    monkeypatch.setattr(integration, "_extract_entities_from_paper", extract_entities)

    with caplog.at_level(logging.WARNING):
        result = await integration.ingest_papers_with_kg(
            papers=[p1], extract_entities=True, create_relationships=False
        )

    assert result == [mystery_doc]
    assert extract_entities.await_count == 0
    assert any("arxiv_id" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# R5-L1 / R5-L2 / R5-L4: query-shape guards
# ---------------------------------------------------------------------------


def test_pagination_queries_order_by_stable_keys() -> None:
    entities_src = inspect.getsource(KnowledgeGraphService.get_all_entities)
    relationships_src = inspect.getsource(KnowledgeGraphService.get_all_relationships)
    related_src = inspect.getsource(KnowledgeGraphService.find_related_entities)
    neighborhood_src = inspect.getsource(KnowledgeGraphService.get_neighborhood)

    assert "ORDER BY e.created_at DESC, e.id" in entities_src
    assert "ORDER BY r.created_at DESC, rid" in relationships_src
    assert "ORDER BY length(shortest_path), related.id" in neighborhood_src
    assert neighborhood_src.index("ORDER BY") < neighborhood_src.index("LIMIT $limit")

    # R5-L2: start entity excluded inside Cypher so it cannot eat a LIMIT slot.
    assert "related.id <> $entity_id" in related_src
    assert "ORDER BY related.id" in related_src


def test_database_name_is_explicit_not_private_session_attr() -> None:
    service_src = inspect.getsource(KnowledgeGraphService)
    assert "session._database" not in service_src

    service = KnowledgeGraphService()
    assert service.database == "neo4j"


# ---------------------------------------------------------------------------
# R5-L5: located_in word boundaries, location-like target, direction
# ---------------------------------------------------------------------------


def _extraction_service():
    from src.services.processing.entity_extraction_service import (
        EntityExtractionService,
    )

    # Skip __init__: it eagerly loads spaCy; relationship analysis needs none.
    return object.__new__(EntityExtractionService)


def _sent_entity(name: str, text: str, *, etype=None, label=None):
    start = text.index(name)
    return SimpleNamespace(
        name=name,
        properties={
            "start_char": start,
            "end_char": start + len(name),
            **({"spacy_label": label} if label else {}),
        },
        entity_type=etype,
    )


def _sentence(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, start_char=0)


def test_bare_in_inside_word_does_not_create_located_in() -> None:
    service = _extraction_service()
    text = "Acme working in data centers."
    e1 = _sent_entity("Acme", text)
    e2 = _sent_entity("data centers", text)

    result = service._analyze_entity_relationship(_sentence(text), e1, e2)

    # Substring matching used to fire on the "in" inside "working".
    assert result is None


def test_bare_in_with_location_target_creates_located_in() -> None:
    from src.models.entity import EntityType

    service = _extraction_service()
    text = "OpenAI training in Paris."
    e1 = _sent_entity("OpenAI", text)
    e2 = _sent_entity("Paris", text, etype=EntityType.LOCATION, label="GPE")

    result = service._analyze_entity_relationship(_sentence(text), e1, e2)

    assert result is not None
    assert result["relationship_type"] == "located_in"
    assert result["source_entity"] is e1
    assert result["target_entity"] is e2


def test_bare_at_with_nonlocation_target_is_rejected() -> None:
    from src.models.entity import EntityType

    service = _extraction_service()
    text = "Signals sampled at dawn by sensors."
    e1 = _sent_entity("Signals", text)
    e2 = _sent_entity("dawn", text, etype=EntityType.CONCEPT)

    result = service._analyze_entity_relationship(_sentence(text), e1, e2)

    assert result is None


def test_direction_follows_sentence_order_not_argument_order() -> None:
    service = _extraction_service()
    text = "Sundar works for Google."
    sundar = _sent_entity("Sundar", text)
    google = _sent_entity("Google", text)

    # Argument order flipped relative to sentence order.
    result = service._analyze_entity_relationship(_sentence(text), google, sundar)

    assert result is not None
    assert result["relationship_type"] == "works_for"
    assert result["source_entity"] is sundar
    assert result["target_entity"] is google
