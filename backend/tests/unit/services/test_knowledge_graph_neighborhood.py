from unittest.mock import MagicMock, patch


def test_get_neighborhood_preserves_relationship_type_and_direction() -> None:
    from src.models.graph import RelationshipType
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    session = MagicMock()
    session.__enter__.return_value = session
    session.run.return_value = [
        {
            "related": {
                "id": "marcus-chen",
                "name": "Marcus Chen",
                "type": "PERSON",
            },
            "path_rels": [
                {
                    "label": "WORKS_FOR",
                    "source_entity_id": "marcus-chen",
                    "target_entity_id": "nova-research-institute",
                    "strength": 0.9,
                    "confidence": 0.8,
                }
            ],
            "path_node_ids": ["nova-research-institute", "marcus-chen"],
        },
        {
            "related": {
                "id": "fault-tolerant-survey",
                "name": "Fault-Tolerant Quantum Computing Survey",
                "type": "RESEARCH",
            },
            "path_rels": [
                {
                    "label": "CITED",
                    "source_entity_id": "fault-tolerant-survey",
                    "target_entity_id": "quantum-error-correction",
                    "strength": 0.9,
                    "confidence": 0.8,
                }
            ],
            "path_node_ids": [
                "quantum-error-correction",
                "fault-tolerant-survey",
            ],
        },
    ]

    with patch.object(KnowledgeGraphService, "get_session", return_value=session):
        response = KnowledgeGraphService().get_neighborhood(
            "nova-research-institute", organization_id="org-1"
        )

    query = session.run.call_args.args[0]
    assert "coalesce(rel.type, type(rel))" in query
    assert "startNode(rel).id" in query
    assert "endNode(rel).id" in query
    assert "all(n IN nodes(path) WHERE n.organization_id = $organization_id)" in query
    relationships = {
        (
            relationship.source_entity_id,
            relationship.relationship_type,
            relationship.target_entity_id,
        )
        for relationship in response["relationships"]
    }
    assert (
        "marcus-chen",
        RelationshipType.WORKS_FOR,
        "nova-research-institute",
    ) in relationships
    assert (
        "fault-tolerant-survey",
        RelationshipType.CITED,
        "quantum-error-correction",
    ) in relationships


def test_get_neighborhood_scopes_source_document_intermediates() -> None:
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    session = MagicMock()
    session.__enter__.return_value = session
    session.run.side_effect = [
        [
            {
                "related": {
                    "id": "target",
                    "name": "Target",
                    "type": "PERSON",
                },
                "path_rels": [],
                "path_node_ids": ["start", "intermediate", "target"],
            }
        ],
        [
            {
                "n": {
                    "id": "intermediate",
                    "name": "Intermediate",
                    "type": "CONCEPT",
                }
            }
        ],
    ]

    with patch.object(KnowledgeGraphService, "get_session", return_value=session):
        response = KnowledgeGraphService().get_neighborhood(
            "start", source_document_ids=["doc-1"]
        )

    traversal_query, traversal_params = session.run.call_args_list[0].args
    assert (
        "all(n IN nodes(path) "
        "WHERE n.source_document_id IN $source_document_ids)" in traversal_query
    )
    assert traversal_params["source_document_ids"] == ["doc-1"]

    refetch_query, refetch_params = session.run.call_args_list[1].args
    assert "n.source_document_id IN $source_document_ids" in refetch_query
    assert refetch_params == {
        "ids": ["intermediate"],
        "source_document_ids": ["doc-1"],
    }
    assert {entity.id for entity in response["entities"]} == {"target", "intermediate"}


def test_get_neighborhood_combines_scopes_for_intermediate_refetch() -> None:
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    session = MagicMock()
    session.__enter__.return_value = session
    session.run.side_effect = [
        [
            {
                "related": {"id": "target", "name": "Target", "type": "PERSON"},
                "path_rels": [],
                "path_node_ids": ["start", "intermediate", "target"],
            }
        ],
        [],
    ]

    with patch.object(KnowledgeGraphService, "get_session", return_value=session):
        KnowledgeGraphService().get_neighborhood(
            "start",
            source_document_ids=["doc-legacy"],
            organization_id="org-1",
        )

    # Both scopes supplied → OR them (matching _two_endpoint_scope) so legacy
    # NULL-org nodes reachable via source_document_ids stay traversable.
    combined = (
        "(n.organization_id = $organization_id"
        " OR n.source_document_id IN $source_document_ids)"
    )
    traversal_query, traversal_params = session.run.call_args_list[0].args
    assert f"all(n IN nodes(path) WHERE {combined})" in traversal_query
    assert traversal_params["organization_id"] == "org-1"
    assert traversal_params["source_document_ids"] == ["doc-legacy"]

    refetch_query, refetch_params = session.run.call_args_list[1].args
    assert combined in refetch_query
    assert refetch_params == {
        "ids": ["intermediate"],
        "organization_id": "org-1",
        "source_document_ids": ["doc-legacy"],
    }
