"""Extracted Neo4j repair core (audit D1 / P2.3).

``repair_document_graph`` is the idempotent per-document re-index shared by
the ``scripts/repair_kg.py`` CLI and the satellite reconciler. Contract:

- no content -> skipped outcome (ok False), no graph calls;
- extraction failure -> error outcome (ok False), never raises;
- happy path -> entities upserted (``BatchEntityRequest(upsert=True)``) with
  the document's organization_id on every request (tenancy), relationships
  resolved by created-node name;
- batch errors -> ok False (document stays reconcilable);
- vacuous extraction (nothing found, no errors) -> ok True.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from src.models.graph import EntityType as GraphEntityType
from src.models.graph import RelationshipType as GraphRelationshipType
from src.services.knowledge_graph.repair import (
    GraphRepairOutcome,
    repair_document_graph,
    safe_enum_value,
)


def _document(content="Ada works at Analytical Engines."):
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        content_text=content,
    )


def _extracted_entity(name, etype="person", confidence=0.9):
    return SimpleNamespace(
        name=name,
        entity_type=SimpleNamespace(value=etype),
        confidence=confidence,
        extraction_method=SimpleNamespace(value="spacy"),
        properties={"context_window": "ctx"},
    )


def _extraction(entities, relationships):
    service = MagicMock()
    service.extract_entities_and_relationships_from_text.return_value = (
        entities,
        relationships,
    )
    return service


def _kg(created_names_to_ids, errors=(), created_relationships=()):
    kg = MagicMock()
    kg.create_entities_batch.side_effect = [
        SimpleNamespace(
            created_entities=[
                SimpleNamespace(id=node_id, name=name)
                for name, node_id in created_names_to_ids.items()
            ],
            created_relationships=[],
            errors=list(errors),
        ),
        SimpleNamespace(
            created_entities=[],
            created_relationships=list(created_relationships),
            errors=[],
        ),
    ]
    return kg


def test_no_content_is_skipped_not_ok():
    doc = _document(content="   ")
    kg = MagicMock()
    outcome = repair_document_graph(doc, extraction_service=MagicMock(), kg_service=kg)
    assert outcome.skipped_reason == "no_content"
    assert outcome.ok is False
    kg.create_entities_batch.assert_not_called()


def test_extraction_failure_reports_error_never_raises():
    doc = _document()
    service = MagicMock()
    service.extract_entities_and_relationships_from_text.side_effect = RuntimeError(
        "spacy exploded"
    )
    kg = MagicMock()
    outcome = repair_document_graph(doc, extraction_service=service, kg_service=kg)
    assert outcome.error_message == "spacy exploded"
    assert outcome.ok is False
    kg.create_entities_batch.assert_not_called()


def test_happy_path_upserts_org_scoped_entities_and_relationships():
    doc = _document()
    ada = _extracted_entity("Ada Lovelace")
    org = _extracted_entity("Analytical Engines", etype="organization")
    rel = {
        "source_entity": ada,
        "target_entity": org,
        "relationship_type": "works_for",
        "confidence": 0.7,
        "evidence": "Ada works at Analytical Engines.",
        "pattern_matched": "works at",
    }
    kg = _kg(
        {"Ada Lovelace": "n1", "Analytical Engines": "n2"},
        created_relationships=["r1"],
    )

    outcome = repair_document_graph(
        doc, extraction_service=_extraction([ada, org], [rel]), kg_service=kg
    )

    assert outcome.ok is True
    assert outcome.entities_created == 2
    assert outcome.relationships_created == 1
    assert outcome.errors == 0

    entity_batch = kg.create_entities_batch.call_args_list[0].args[0]
    assert entity_batch.upsert is True
    assert entity_batch.document_id == str(doc.id)
    assert [e.name for e in entity_batch.entities] == [
        "Ada Lovelace",
        "Analytical Engines",
    ]
    # Tenancy: every request carries the document's org (the old script wrote
    # unscoped nodes).
    assert {e.organization_id for e in entity_batch.entities} == {
        str(doc.organization_id)
    }
    assert entity_batch.entities[0].entity_type == GraphEntityType.PERSON

    rel_batch = kg.create_entities_batch.call_args_list[1].args[0]
    assert rel_batch.upsert is True
    (rel_req,) = rel_batch.relationships
    assert rel_req.source_entity_id == "n1"
    assert rel_req.target_entity_id == "n2"
    assert rel_req.relationship_type == GraphRelationshipType.WORKS_FOR
    assert rel_req.organization_id == str(doc.organization_id)


def test_batch_errors_keep_document_reconcilable():
    doc = _document()
    ada = _extracted_entity("Ada Lovelace")
    kg = _kg({"Ada Lovelace": "n1"}, errors=["boom"])
    outcome = repair_document_graph(
        doc, extraction_service=_extraction([ada], []), kg_service=kg
    )
    assert outcome.errors == 1
    assert outcome.ok is False


def test_unresolvable_relationship_endpoints_are_skipped():
    doc = _document()
    ada = _extracted_entity("Ada Lovelace")
    ghost = _extracted_entity("Ghost")
    rel = {
        "source_entity": ada,
        "target_entity": ghost,  # not in created map -> unresolvable
        "relationship_type": "works_for",
        "confidence": 0.7,
        "evidence": "e",
        "pattern_matched": "p",
    }
    kg = _kg({"Ada Lovelace": "n1"})
    outcome = repair_document_graph(
        doc, extraction_service=_extraction([ada, ghost], [rel]), kg_service=kg
    )
    # Only the entity batch ran; no relationship batch for an empty list.
    assert kg.create_entities_batch.call_count == 1
    assert outcome.relationships_created == 0
    assert outcome.ok is True


def test_vacuous_extraction_is_ok():
    doc = _document()
    kg = MagicMock()
    outcome = repair_document_graph(
        doc, extraction_service=_extraction([], []), kg_service=kg
    )
    assert outcome.ok is True
    assert outcome.entities_created == 0
    kg.create_entities_batch.assert_not_called()


def test_kg_exception_reports_error_never_raises():
    doc = _document()
    ada = _extracted_entity("Ada Lovelace")
    kg = MagicMock()
    kg.create_entities_batch.side_effect = ConnectionError("neo4j down")
    outcome = repair_document_graph(
        doc, extraction_service=_extraction([ada], []), kg_service=kg
    )
    assert outcome.ok is False
    assert "neo4j down" in outcome.error_message


def test_safe_enum_value_case_insensitive_with_fallback():
    assert (
        safe_enum_value(GraphEntityType, "person", GraphEntityType.OTHER)
        == GraphEntityType.PERSON
    )
    assert (
        safe_enum_value(GraphEntityType, "no-such-type", GraphEntityType.OTHER)
        == GraphEntityType.OTHER
    )
    assert (
        safe_enum_value(
            GraphRelationshipType, "WORKS_FOR", GraphRelationshipType.RELATED_TO
        )
        == GraphRelationshipType.WORKS_FOR
    )


def test_outcome_ok_semantics():
    ok = GraphRepairOutcome(document_id="d", entities_found=1, entities_created=1)
    assert ok.ok is True
    assert GraphRepairOutcome(document_id="d", errors=1).ok is False
    assert GraphRepairOutcome(document_id="d", skipped_reason="no_content").ok is False
    assert GraphRepairOutcome(document_id="d", error_message="x").ok is False
