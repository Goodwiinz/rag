"""Regression: relationship creation MERGEs (idempotent) instead of CREATE.

create_relationship / _create_relationship_in_transaction used CREATE with a
fresh uuid every call, so re-ingesting the same paper piled up duplicate
RELATED_TO edges between the same two entities. They now MERGE on
(source, target, type) and refresh mutable fields, returning the edge's actual
id (which, on an existing edge, is NOT the freshly minted uuid).
"""

import contextlib

import pytest

from src.models.graph import CreateRelationshipRequest, RelationshipType
from src.services.knowledge_graph.knowledge_graph_service import (
    KnowledgeGraphService,
)


class _FakeResult:
    def __init__(self, record):
        self._record = record

    def single(self):
        return self._record


class _FakeSession:
    """Captures the Cypher and returns a record whose edge id differs from the
    generated uuid, so the test can prove the id is read back from the result."""

    def __init__(self, record, captured):
        self._record = record
        self._captured = captured

    def run(self, query, params):
        self._captured["query"] = query
        self._captured["params"] = params
        return _FakeResult(self._record)


def _service_with_session(record, captured):
    svc = KnowledgeGraphService()

    @contextlib.contextmanager
    def _fake_get_session(database: str = "neo4j"):
        yield _FakeSession(record, captured)

    svc.get_session = _fake_get_session
    return svc


def _request():
    return CreateRelationshipRequest(
        source_entity_id="entity-a",
        target_entity_id="entity-b",
        relationship_type=RelationshipType.RELATED_TO,
        strength=0.7,
    )


@pytest.mark.unit
def test_create_relationship_merges_not_creates():
    captured = {}
    record = {"r": {"id": "pre-existing-edge"}, "source": {}, "target": {}}
    svc = _service_with_session(record, captured)

    resp = svc.create_relationship(_request())

    query = captured["query"]
    # Idempotent upsert, not a blind CREATE that duplicates edges.
    assert "MERGE (source)-[r:RELATED_TO {type: $relationship_type}]->(target)" in query
    assert "ON CREATE SET" in query
    assert "ON MATCH SET" in query
    assert "CREATE (source)-[r:RELATED_TO" not in query
    # The existing edge's id is read back, not the freshly generated uuid.
    assert resp.id == "pre-existing-edge"


@pytest.mark.unit
def test_create_relationship_in_transaction_merges_not_creates():
    captured = {}
    record = {"r": {"id": "pre-existing-edge"}}

    class _Tx:
        def run(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return _FakeResult(record)

    svc = KnowledgeGraphService()
    resp = svc._create_relationship_in_transaction(_Tx(), _request())

    query = captured["query"]
    assert "MERGE (source)-[r:RELATED_TO {type: $relationship_type}]->(target)" in query
    assert "CREATE (source)-[r:RELATED_TO" not in query
    assert resp.id == "pre-existing-edge"
