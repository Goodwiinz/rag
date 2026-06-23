"""Phase 3a: relationships are org-scoped + edge stamped (#842 follow-up).

create_relationship / _create_relationship_in_transaction now constrain BOTH
endpoints to the caller's organization_id (when provided) so a relationship can
never bind a cross-tenant entity, and stamp organization_id on the edge. The
MERGE key is unchanged ((type, source_document_id)) to avoid the duplicate-edge
regression fixed in #828.
"""

from typing import Any, Dict

import pytest

from src.models.graph import CreateRelationshipRequest, RelationshipType
from src.services.knowledge_graph.knowledge_graph_service import (
    KnowledgeGraphService,
)


class _FakeResult:
    def __init__(self, record: Dict[str, Any]) -> None:
        self._record = record

    def single(self) -> Dict[str, Any]:
        return self._record


class _FakeSession:
    def __init__(self, record: Dict[str, Any], captured: Dict[str, Any]) -> None:
        self._record = record
        self._captured = captured

    def run(self, query: str, params: Dict[str, Any]) -> _FakeResult:
        self._captured["query"] = query
        self._captured["params"] = params
        return _FakeResult(self._record)


def _svc(record: Dict[str, Any], captured: Dict[str, Any]) -> KnowledgeGraphService:
    import contextlib

    svc = KnowledgeGraphService()

    @contextlib.contextmanager
    def _fake_get_session(database: str = "neo4j"):
        yield _FakeSession(record, captured)

    svc.get_session = _fake_get_session  # type: ignore[method-assign]
    return svc


def _req(**kw: Any) -> CreateRelationshipRequest:
    base: Dict[str, Any] = dict(
        source_entity_id="a",
        target_entity_id="b",
        relationship_type=RelationshipType.RELATED_TO,
    )
    base.update(kw)
    return CreateRelationshipRequest(**base)


@pytest.mark.unit
def test_create_relationship_scopes_both_endpoints_to_org() -> None:
    captured: Dict[str, Any] = {}
    record = {"r": {"id": "r1"}, "source": {}, "target": {}}
    svc = _svc(record, captured)

    svc.create_relationship(_req(organization_id="org-A"))

    q = captured["query"]
    assert "source.organization_id = $organization_id" in q
    assert "target.organization_id = $organization_id" in q
    assert "r.organization_id = $organization_id" in q  # ON CREATE stamp
    assert captured["params"]["organization_id"] == "org-A"
    # org must NOT be in the MERGE key (avoids the #828 dup-edge regression).
    merge_line = q.split("MERGE", 1)[1].split("]->", 1)[0]
    assert "organization_id" not in merge_line


@pytest.mark.unit
def test_create_relationship_falls_back_to_doc_ids_without_org() -> None:
    captured: Dict[str, Any] = {}
    record = {"r": {"id": "r1"}, "source": {}, "target": {}}
    svc = _svc(record, captured)

    svc.create_relationship(_req(), source_document_ids=["d1", "d2"])

    q = captured["query"]
    assert "source.organization_id" not in q  # no org → no org filter
    assert "source.source_document_id IN $source_document_ids" in q


@pytest.mark.unit
def test_tx_relationship_scopes_endpoints_to_org() -> None:
    captured: Dict[str, Any] = {}

    class _Tx:
        def run(self, query: str, params: Dict[str, Any]) -> _FakeResult:
            captured["query"] = query
            captured["params"] = params
            return _FakeResult({"r": {"id": "r1"}})

    svc = KnowledgeGraphService()
    svc._create_relationship_in_transaction(_Tx(), _req(organization_id="org-A"))

    q = captured["query"]
    assert "source.organization_id = $organization_id" in q
    assert "target.organization_id = $organization_id" in q
    assert "r.organization_id = $organization_id" in q
    assert captured["params"]["organization_id"] == "org-A"


@pytest.mark.unit
def test_tx_relationship_falls_back_to_source_document_id() -> None:
    """Batch path: no org -> scope both endpoints by the edge's source doc
    rather than leaving it fully unscoped."""
    captured: Dict[str, Any] = {}

    class _Tx:
        def run(self, query: str, params: Dict[str, Any]) -> _FakeResult:
            captured["query"] = query
            captured["params"] = params
            return _FakeResult({"r": {"id": "r1"}})

    svc = KnowledgeGraphService()
    svc._create_relationship_in_transaction(_Tx(), _req(source_document_id="doc-1"))

    q = captured["query"]
    assert "source.organization_id" not in q  # no org
    assert "source.source_document_id = $source_document_id" in q
    assert "target.source_document_id = $source_document_id" in q


@pytest.mark.unit
def test_blank_org_rejected_at_request_boundary() -> None:
    with pytest.raises(Exception):
        _req(organization_id="   ")
    # None stays allowed (genuinely org-less).
    assert _req().organization_id is None
