"""Phase 2: organization_id is part of the entity MERGE identity.

create_entity, _create_entity_in_transaction and _batch_merge_entities now MERGE
on (canonical_key, type, organization_id), backed by the
entity_canonical_org_unique constraint, so two orgs' same name+type entities are
separate nodes. org is coalesced to "" because Cypher cannot MERGE on a null key.
"""

import contextlib
from typing import Any, Dict, Iterator, List

import pytest

from src.models.graph import CreateEntityRequest, EntityType
from src.services.knowledge_graph.knowledge_graph_service import (
    KnowledgeGraphService,
)


class _Result:
    def __init__(self, record: Dict[str, Any]) -> None:
        self._record = record

    def single(self) -> Dict[str, Any]:
        return self._record

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter([self._record])


class _Session:
    def __init__(self, captured: Dict[str, Any]) -> None:
        self._captured = captured

    def run(self, query: str, params: Dict[str, Any]) -> _Result:
        self._captured["query"] = query
        self._captured["params"] = params
        return _Result({"resolved_id": "e1", "created_at": 1, "updated_at": 1})


def _svc_with_session(captured: Dict[str, Any]) -> KnowledgeGraphService:
    svc = KnowledgeGraphService()

    @contextlib.contextmanager
    def _fake_get_session(database: str = "neo4j") -> Iterator[_Session]:
        yield _Session(captured)

    svc.get_session = _fake_get_session  # type: ignore[method-assign]
    return svc


@pytest.mark.unit
def test_create_entity_merges_on_org_key() -> None:
    captured: Dict[str, Any] = {}
    svc = _svc_with_session(captured)
    svc.create_entity(
        CreateEntityRequest(
            name="RAG", entity_type=EntityType.CONCEPT, organization_id="org-A"
        )
    )
    assert "organization_id: $org_key" in captured["query"]
    assert captured["params"]["org_key"] == "org-A"
    # org must not be re-set as a property (would desync key vs property).
    assert "e.organization_id =" not in captured["query"]


@pytest.mark.unit
def test_create_entity_null_org_coalesced_to_sentinel() -> None:
    captured: Dict[str, Any] = {}
    svc = _svc_with_session(captured)
    svc.create_entity(CreateEntityRequest(name="RAG", entity_type=EntityType.CONCEPT))
    # None would make Cypher reject the MERGE key; must be "".
    assert captured["params"]["org_key"] == ""


@pytest.mark.unit
def test_batch_merge_identity_map_includes_org() -> None:
    captured: Dict[str, Any] = {}

    class _Tx:
        def run(self, query: str, params: Dict[str, Any]) -> _Result:
            captured["query"] = query
            captured["params"] = params
            return _Result({"idx": 0, "id": "e1"})

    svc = KnowledgeGraphService()
    entities: List[CreateEntityRequest] = [
        CreateEntityRequest(
            name="RAG", entity_type=EntityType.CONCEPT, organization_id="org-A"
        )
    ]
    svc._batch_merge_entities(_Tx(), entities)

    assert "organization_id: row.org_key" in captured["query"]
    assert captured["params"]["rows"][0]["org_key"] == "org-A"
    # identity-map org and stored prop are the same value (no desync).
    assert captured["params"]["rows"][0]["props"]["organization_id"] == "org-A"
