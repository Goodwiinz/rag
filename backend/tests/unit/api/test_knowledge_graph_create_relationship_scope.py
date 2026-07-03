"""create_relationship must hide scoped endpoint misses."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.database import get_db_sync
from src.core.dependencies import get_current_user
from src.services.knowledge_graph.knowledge_graph_service import RelationshipScopeError


@pytest.fixture
def mock_sync_db():
    return MagicMock()


@pytest.fixture(autouse=True)
def _override_dependencies(test_app, mock_user, mock_sync_db):
    def override_get_current_user():
        return mock_user

    def override_get_db_sync():
        yield mock_sync_db

    test_app.dependency_overrides[get_current_user] = override_get_current_user
    test_app.dependency_overrides[get_db_sync] = override_get_db_sync
    try:
        yield
    finally:
        test_app.dependency_overrides.pop(get_current_user, None)
        test_app.dependency_overrides.pop(get_db_sync, None)


def _payload():
    return {
        "source_entity_id": "a",
        "target_entity_id": "b",
        "relationship_type": "RELATED_TO",
    }


@patch("src.api.search.knowledge_graph._get_org_document_ids", return_value=["d1"])
@patch("src.api.search.knowledge_graph.knowledge_graph_service.create_relationship")
def test_scope_error_returns_404(mock_create, _mock_doc_ids, test_client):
    mock_create.side_effect = RelationshipScopeError("no in-scope pair")

    response = test_client.post(
        "/api/v1/knowledge-graph/relationships", json=_payload()
    )

    assert response.status_code == 404


@patch("src.api.search.knowledge_graph._get_org_document_ids", return_value=["d1"])
@patch("src.api.search.knowledge_graph.knowledge_graph_service.create_relationship")
def test_other_exception_returns_500(mock_create, _mock_doc_ids, test_client):
    mock_create.side_effect = RuntimeError("neo4j exploded")

    response = test_client.post(
        "/api/v1/knowledge-graph/relationships", json=_payload()
    )

    assert response.status_code == 500
