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


@pytest.mark.unit
def test_get_all_relationships_scopes_by_org() -> None:
    """Read side: org filter on BOTH endpoints, preferred over doc-ids."""
    import contextlib

    captured: Dict[str, Any] = {}

    class _EmptyResult:
        def __iter__(self):
            return iter([])

    class _Session:
        def run(self, query: str, params: Dict[str, Any]) -> "_EmptyResult":
            captured["query"] = query
            captured["params"] = params
            return _EmptyResult()

    svc = KnowledgeGraphService()

    @contextlib.contextmanager
    def _fake_get_session(database: str = "neo4j"):
        yield _Session()

    svc.get_session = _fake_get_session  # type: ignore[method-assign]

    svc.get_all_relationships(
        organization_id="org-A", source_document_ids=["d1"]
    )

    q = captured["query"]
    assert "source.organization_id = $organization_id" in q
    assert "target.organization_id = $organization_id" in q
    # org takes precedence over the doc-id filter.
    assert "r.source_document_id IN $source_document_ids" not in q
    assert captured["params"]["organization_id"] == "org-A"


@pytest.mark.unit
def test_get_relationships_for_entities_returns_incoming_and_outgoing_edges() -> None:
    """Search calls this method for incident edges. It must include both
    source-side and target-side matches, otherwise incoming relationships are
    silently dropped from graph search results."""
    import contextlib

    captured: Dict[str, Any] = {}

    class _EmptyResult:
        def __iter__(self):
            return iter([])

    class _Session:
        def run(self, query: str, params: Dict[str, Any]) -> "_EmptyResult":
            captured["query"] = query
            captured["params"] = params
            return _EmptyResult()

    svc = KnowledgeGraphService()

    @contextlib.contextmanager
    def _fake_get_session(database: str = "neo4j"):
        yield _Session()

    svc.get_session = _fake_get_session  # type: ignore[method-assign]

    svc.get_relationships_for_entities(["entity-a"], organization_id="org-A")

    q = captured["query"]
    assert "(source.id IN $entity_ids OR target.id IN $entity_ids)" in q
    assert "source.organization_id = $organization_id" in q
    assert "target.organization_id = $organization_id" in q
    assert captured["params"]["entity_ids"] == ["entity-a"]
    assert captured["params"]["organization_id"] == "org-A"


# --- Audit D10 / D14 / D16 re-audit (2026-07-02) -----------------------------

import contextlib
from datetime import datetime


class _Neo4jDateTime:
    """Stand-in for neo4j.time.DateTime: pydantic rejects the neo4j type, so the
    service must call .to_native() before handing it to RelationshipResponse."""

    def __init__(self, dt: datetime) -> None:
        self._dt = dt

    def to_native(self) -> datetime:
        return self._dt


class _SingleResult:
    def __init__(self, record):
        self._record = record

    def single(self):
        return self._record


class _ListResult:
    def __init__(self, records):
        self._records = records

    def __iter__(self):
        return iter(self._records)


def _capture_session(captured, records, *, list_result=True):
    class _Session:
        def run(self, query: str, params: Dict[str, Any]):
            captured["query"] = query
            captured["params"] = params
            return _ListResult(records) if list_result else _SingleResult(records)

    class _Svc(KnowledgeGraphService):
        pass

    @contextlib.contextmanager
    def _fake_get_session(database: str = "neo4j"):
        yield _Session()

    svc = _Svc()
    svc.get_session = _fake_get_session  # type: ignore[method-assign]
    return svc


@pytest.mark.unit
def test_get_relationship_single_is_directed_match() -> None:
    """D10: get_relationship (single) must use a directed -[r:RELATED_TO]-> match
    so the returned source/target reflects the stored edge direction (no swap)."""
    captured: Dict[str, Any] = {}
    svc = _capture_session(
        captured,
        {
            "r": {"id": "r1", "type": "RELATED_TO", "strength": 0.5,
                  "confidence_score": 0.5},
            "source_id": "a",
            "target_id": "b",
        },
        list_result=False,
    )

    svc.get_relationship("r1", organization_id="org-A")

    q = captured["query"]
    assert ")-[r:RELATED_TO {id: $relationship_id}]->(" in q
    # undirected form must NOT be present
    assert "]-(" not in q.split("RELATED_TO", 1)[1]


@pytest.mark.unit
def test_get_relationship_single_converts_neo4j_datetime() -> None:
    """D14: neo4j DateTime must be converted to native datetime before pydantic."""
    captured: Dict[str, Any] = {}
    ts = _Neo4jDateTime(datetime(2026, 7, 2, 12, 0, 0))
    svc = _capture_session(
        captured,
        {
            "r": {"id": "r1", "type": "RELATED_TO", "strength": 0.5,
                  "confidence_score": 0.5, "created_at": ts, "updated_at": ts},
            "source_id": "a",
            "target_id": "b",
        },
        list_result=False,
    )

    rel = svc.get_relationship("r1", organization_id="org-A")
    assert isinstance(rel.created_at, datetime)
    assert not isinstance(rel.created_at, _Neo4jDateTime)
    assert rel.created_at == datetime(2026, 7, 2, 12, 0, 0)
    assert rel.updated_at == datetime(2026, 7, 2, 12, 0, 0)


@pytest.mark.unit
def test_get_relationships_converts_neo4j_datetime_and_drops_source_paper() -> None:
    """D14 + D16: list path converts neo4j DateTime and no longer falls back to a
    (dead) source_paper key that no write path ever sets."""
    captured: Dict[str, Any] = {}
    ts = _Neo4jDateTime(datetime(2026, 7, 2, 12, 0, 0))
    record = {
        "r": {
            "id": "r1",
            "type": "RELATED_TO",
            "strength": 0.5,
            "confidence_score": 0.5,
            "created_at": ts,
            # source_document_id absent; source_paper is a legacy key that the
            # write path never sets — must NOT be used as a fallback (D16).
            "source_paper": "ghost-doc",
        },
        "rel_label": "RELATED_TO",
        "source_id": "a",
        "target_id": "b",
    }
    svc = _capture_session(captured, [record], list_result=True)

    rels = svc.get_relationships("a", organization_id="org-A")
    assert len(rels) == 1
    rel = rels[0]
    # D14: native datetime
    assert isinstance(rel.created_at, datetime)
    assert not isinstance(rel.created_at, _Neo4jDateTime)
    # D16: dead fallback removed — absent source_document_id yields None, not the ghost
    assert rel.source_document_id is None
