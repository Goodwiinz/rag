"""extract_entities_from_document must stamp extracted entities with the caller's org.

The endpoint builds CreateEntityRequest objects server-side and calls
create_entities_batch directly (bypassing the batch endpoint's org-forcing loop).
The relationship requests already set organization_id; the entity requests did
not, so entities were persisted with an empty org_key and never appeared in the
caller's own org-scoped entity list / search. This test pins that every entity
request now carries the caller's org.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from src.api.search import knowledge_graph as kg


def test_extracted_entities_stamped_with_caller_org(monkeypatch):
    # document owned by caller's org
    doc = SimpleNamespace(id="doc1", content_text="Alice knows Bob.", content="")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = doc

    # extractor returns one entity, no relationships
    ent = SimpleNamespace(
        name="Alice", entity_type="PERSON", confidence=0.9, properties={}
    )
    extractor = MagicMock()
    extractor.extract_entities_and_relationships_from_text.return_value = ([ent], [])
    monkeypatch.setattr(
        kg, "EntityExtractionService", MagicMock(return_value=extractor)
    )
    monkeypatch.setattr(
        kg, "_map_processing_entity_type_to_graph", lambda t: kg.EntityType.PERSON
    )

    captured = {}

    def _batch(req, *a, **k):
        captured["req"] = req
        return SimpleNamespace(
            created_entities=[], errors=[], processing_time=0.0, entities=[]
        )

    monkeypatch.setattr(kg.knowledge_graph_service, "create_entities_batch", _batch)

    caller = SimpleNamespace(id="u1", organization_id="org-A")
    kg.extract_entities_from_document(document_id="doc1", current_user=caller, db=db)

    ents = captured["req"].entities
    assert ents, "no entity requests built"
    assert all(e.organization_id == "org-A" for e in ents)
