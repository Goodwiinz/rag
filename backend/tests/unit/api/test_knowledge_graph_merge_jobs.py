"""Unit tests for knowledge-graph merge job tenant validation."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.database import get_db_sync
from src.core.dependencies import get_current_user


@pytest.fixture
def mock_sync_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db


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


def _set_doc_query_results(db, doc_ids):
    query = MagicMock()
    filtered = MagicMock()
    filtered.all.return_value = [MagicMock(id=doc_id) for doc_id in doc_ids]
    query.filter.return_value = filtered
    db.query.return_value = query


@patch("src.api.search.knowledge_graph.kg_merge_entities_job.apply_async")
@patch("src.api.search.knowledge_graph.knowledge_graph_service.get_entity")
def test_create_merge_job_rejects_cross_tenant_entities(
    mock_get_entity,
    mock_apply_async,
    test_client,
    mock_sync_db,
):
    payload = {
        "groups": [
            {
                "entities": [
                    {"id": "entity-1", "name": "A"},
                    {"id": "entity-2", "name": "B"},
                ],
                "suggested_primary": "entity-1",
            }
        ]
    }
    mock_get_entity.side_effect = [
        MagicMock(source_document_id="doc-org"),
        MagicMock(source_document_id="doc-foreign"),
    ]
    _set_doc_query_results(mock_sync_db, ["doc-org"])

    response = test_client.post("/api/v1/knowledge-graph/merge-jobs", json=payload)

    assert response.status_code == 403
    mock_apply_async.assert_not_called()


@patch("src.api.search.knowledge_graph.kg_merge_entities_job.apply_async")
@patch("src.api.search.knowledge_graph.knowledge_graph_service.get_entity")
def test_create_merge_job_accepts_entities_from_same_tenant(
    mock_get_entity,
    mock_apply_async,
    test_client,
    mock_sync_db,
):
    payload = {
        "groups": [
            {
                "entities": [
                    {"id": "entity-1", "name": "A"},
                    {"id": "entity-2", "name": "B"},
                ],
                "suggested_primary": "entity-1",
            }
        ]
    }
    mock_get_entity.side_effect = [
        MagicMock(source_document_id="doc-1"),
        MagicMock(source_document_id="doc-2"),
    ]
    _set_doc_query_results(mock_sync_db, ["doc-1", "doc-2"])
    mock_apply_async.return_value = MagicMock(id="task-123")

    response = test_client.post("/api/v1/knowledge-graph/merge-jobs", json=payload)

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    mock_apply_async.assert_called_once()
