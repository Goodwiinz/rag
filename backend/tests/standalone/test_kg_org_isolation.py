"""Integration: entity MERGE is org-isolated (KG Phase 2 / #842).

Requires a live Neo4j (skipped otherwise). Verifies the real behavior the
unit tests can only assert at the Cypher-string level:
  - two orgs ingesting the same name+type get SEPARATE nodes (tenant isolation),
  - re-ingesting the same (name, type, org) dedups onto the existing node.
"""

import uuid

import pytest

from src.models.graph import CreateEntityRequest, EntityType
from src.services.knowledge_graph.knowledge_graph_service import (
    KnowledgeGraphService,
)


def _neo4j_or_skip() -> KnowledgeGraphService:
    svc = KnowledgeGraphService()
    # Only a connection failure should skip. Run the probe OUTSIDE the skip
    # guard so a connected-but-broken Neo4j surfaces as a real test failure
    # instead of a false-green skip.
    try:
        svc._connect()
    except Exception:  # noqa: BLE001 - connection error -> skip, not fail
        pytest.skip("Neo4j unavailable")
    if not svc.driver:
        pytest.skip("Neo4j unavailable")
    with svc.get_session() as session:
        session.run("RETURN 1")
    return svc


@pytest.mark.integration
def test_two_orgs_get_separate_nodes_and_same_org_dedups() -> None:
    svc = _neo4j_or_skip()
    name = f"KGIso {uuid.uuid4().hex[:10]}"
    canonical_key = name.strip().lower()
    org_a = "iso-a-" + uuid.uuid4().hex[:8]
    org_b = "iso-b-" + uuid.uuid4().hex[:8]

    try:
        a1 = svc.create_entity(
            CreateEntityRequest(
                name=name, entity_type=EntityType.CONCEPT, organization_id=org_a
            )
        )
        b1 = svc.create_entity(
            CreateEntityRequest(
                name=name, entity_type=EntityType.CONCEPT, organization_id=org_b
            )
        )
        # Two orgs, same name+type -> two distinct nodes (tenant isolation).
        assert a1.id != b1.id

        # Re-ingest for org A dedups onto the existing node.
        a2 = svc.create_entity(
            CreateEntityRequest(
                name=name, entity_type=EntityType.CONCEPT, organization_id=org_a
            )
        )
        assert a2.id == a1.id

        with svc.get_session() as session:
            count = session.run(
                "MATCH (e:Entity {canonical_key: $ck, type: $t}) RETURN count(e) AS c",
                {"ck": canonical_key, "t": EntityType.CONCEPT.value},
            ).single()["c"]
        assert count == 2
    finally:
        with svc.get_session() as session:
            session.run(
                "MATCH (e:Entity {canonical_key: $ck}) DETACH DELETE e",
                {"ck": canonical_key},
            )
