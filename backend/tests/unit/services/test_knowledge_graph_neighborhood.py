from unittest.mock import MagicMock, patch


def test_get_neighborhood_preserves_relationship_type_and_direction():
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
