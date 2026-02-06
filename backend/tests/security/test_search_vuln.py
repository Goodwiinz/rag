import sys
from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

@pytest.fixture(scope="module")
def mock_dependencies():
    """
    Mock heavy dependencies and services to isolate the search router.
    This uses patch.dict to safely mock sys.modules without polluting other tests.
    """
    # Create mocks
    mock_spacy = MagicMock()
    mock_en_core = MagicMock()
    mock_hybrid = MagicMock()
    mock_fulltext = MagicMock()
    mock_kg = MagicMock()
    mock_vector = MagicMock()
    mock_sentence_transformers = MagicMock()
    mock_transformers = MagicMock()
    mock_db = MagicMock()
    mock_processing = MagicMock()

    # Mock numpy to be safe
    mock_numpy = MagicMock()

    # Setup specific mocks
    mock_db.get_db = MagicMock()

    # Create a dictionary of modules to patch
    # We aggressively mock everything that might trigger complex imports
    modules_to_patch = {
        "spacy": mock_spacy,
        "en_core_web_sm": mock_en_core,
        "numpy": mock_numpy,
        "sentence_transformers": mock_sentence_transformers,
        "transformers": mock_transformers,

        # Services
        "src.services.search.hybrid_search_service": mock_hybrid,
        "src.services.search.fulltext_search_service": mock_fulltext,
        "src.services.knowledge_graph.knowledge_graph_service": mock_kg,
        "src.services.search.vector_search_service": mock_vector,
        "src.services.search.vector_service": MagicMock(),
        "src.services.search.multi_agent_search_service": MagicMock(),

        # Knowledge Graph Package (prevents layout_algorithms -> numpy import)
        "src.services.knowledge_graph": MagicMock(),
        "src.services.knowledge_graph.layout_algorithms": MagicMock(),

        # API sub-modules that might be imported by __init__
        "src.api.search.multi_agent_search": MagicMock(),
        "src.api.search.knowledge_graph": MagicMock(),
        "src.api.search.vectors": MagicMock(),

        # Core & Infra
        "src.core.database": mock_db,
        "src.services.processing": mock_processing,
        "src.services.processing.processing_service": MagicMock(),
        "src.services.processing.entity_extraction_service": MagicMock(),
        "src.services.processing.multimodal_processing_service": MagicMock(),
    }

    # Use patch.dict context manager
    with patch.dict(sys.modules, modules_to_patch):
        # We must remove the module from sys.modules if it was already loaded
        # so that it gets re-imported using our mocks
        if "src.api.search.search" in sys.modules:
            del sys.modules["src.api.search.search"]

        yield

        # Cleanup: remove the module again so subsequent tests re-import the real one
        if "src.api.search.search" in sys.modules:
            del sys.modules["src.api.search.search"]

@pytest.fixture(scope="module")
def isolated_client(mock_dependencies):
    """
    Create a TestClient with the search router, ensuring dependencies are mocked.
    """
    # Import inside the fixture where mocks are active
    from src.api.search.search import router

    app = FastAPI()
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
    Verify that normal search endpoints still exist.
    """
    response = isolated_client.post(
        "/api/v1/search/",
        json={
            "query": "test",
            "limit": 10,
            "search_type": "hybrid"
        }
    )

    # It should not be 404
    assert response.status_code != status.HTTP_404_NOT_FOUND
