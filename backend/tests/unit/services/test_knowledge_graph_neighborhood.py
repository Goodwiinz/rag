from unittest.mock import MagicMock, patch


def test_get_neighborhood_preserves_logical_relationship_type():
    from src.models.graph import RelationshipType
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    session = MagicMock()
    session.__enter__.return_value = session
    session.run.return_value = [
        {
            "related": {"id": "company-1", "name": "Acme", "type": "ORGANIZATION"},
            "path_rels": [{"label": "WORKS_FOR", "strength": 0.9, "confidence": 0.8}],
            "path_node_ids": ["person-1", "company-1"],
        }
    ]

    with patch.object(KnowledgeGraphService, "get_session", return_value=session):
        response = KnowledgeGraphService().get_neighborhood(
            "person-1", organization_id="org-1"
        )

    query = session.run.call_args.args[0]
    assert "coalesce(rel.type, type(rel))" in query
    assert response["relationships"][0].relationship_type is RelationshipType.WORKS_FOR
