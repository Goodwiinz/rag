import sys
from unittest.mock import MagicMock

# Mock spacy and other heavy dependencies before any imports
# These are safe to mock globally as they are external libraries often missing or slow
sys.modules["spacy"] = MagicMock()
sys.modules["en_core_web_sm"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["transformers"] = MagicMock()
sys.modules["torch"] = MagicMock()

# Mock services that might cause side effects or import errors
# We mock these specific services but NOT core config
mock_hybrid_service = MagicMock()
mock_fulltext_service = MagicMock()
mock_kg_service = MagicMock()
mock_vector_service = MagicMock()

# Assign the global instances that search.py expects
mock_hybrid_service.hybrid_search_service = MagicMock()
mock_fulltext_service.fulltext_search_service = MagicMock()
mock_kg_service.knowledge_graph_service = MagicMock()
mock_vector_service.vector_search_service = MagicMock()

sys.modules["src.services.search.hybrid_search_service"] = mock_hybrid_service
sys.modules["src.services.search.fulltext_search_service"] = mock_fulltext_service
sys.modules["src.services.knowledge_graph.knowledge_graph_service"] = mock_kg_service
sys.modules["src.services.search.vector_search_service"] = mock_vector_service

# Mock vector service (used by vectors router)
sys.modules["src.services.search.vector_service"] = MagicMock()

# DO NOT mock src.core.config here - let it use the real config logic (with env vars from conftest)
# mock_config = MagicMock() ... sys.modules["src.core.config"] = mock_config  <-- REMOVED

# Mock database to avoid connection attempts during import if any
# But be careful not to break things that expect specific DB types
# We only mock the module if it's not already loaded or if we really need to intercept get_db
# In this case, we'll mock it but ensure get_db exists
mock_db_module = MagicMock()
mock_db_module.get_db = MagicMock()
sys.modules["src.core.database"] = mock_db_module

# Mock processing service to break circular imports
sys.modules["src.services.processing"] = MagicMock()
sys.modules["src.services.processing.processing_service"] = MagicMock()
sys.modules["src.services.processing.entity_extraction_service"] = MagicMock()
sys.modules["src.services.processing.multimodal_processing_service"] = MagicMock()

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

# Import the router under test
from src.api.search.search import router

@pytest.fixture
def isolated_client():
    app = FastAPI()
    # The router prefix in search.py is "/search"
    # So if we include it with prefix "/api/v1", the result is "/api/v1/search"
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)

@pytest.mark.search
def test_public_hybrid_search_removed(isolated_client):
    """
    Test that the vulnerable public hybrid search endpoint is removed.
    It should return 404 Not Found.
    """
    response = isolated_client.post(
        "/api/v1/search/public/hybrid",
        json={
            "query": "secret",
            "limit": 10,
            "search_type": "hybrid"
        }
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.search
def test_public_health_check_removed(isolated_client):
    """
    Test that the public health check endpoint is removed.
    It should return 404 Not Found.
    """
    response = isolated_client.get("/api/v1/search/public/health")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.search
def test_other_search_endpoint_exists(isolated_client):
    """
    Verify that normal search endpoints still exist (but might fail due to mocks, which is fine)
    """
    # The normal endpoint is POST /
    # Mocks will be returned
    response = isolated_client.post(
        "/api/v1/search/",
        json={
            "query": "test",
            "limit": 10,
            "search_type": "hybrid"
        }
    )

    # It should not be 404.
    # It might be 401 (Unauthorized) because dependencies are not mocked for auth
    # or 422 (Validation Error)
    # or 500 (Internal Server Error) if something breaks in the handler
    # But definitely NOT 404.
    assert response.status_code != status.HTTP_404_NOT_FOUND
