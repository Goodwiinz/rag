"""API tests for deterministic hybrid search response fields."""

import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.models.search_schemas import DeterministicTrace, SearchResponse, SearchType


def _load_search_module():
    module_path = (
        Path(__file__).resolve().parents[3] / "src" / "api" / "search" / "search.py"
    )
    spec = importlib.util.spec_from_file_location("search_router_module", module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_app() -> FastAPI:
    search_module = _load_search_module()
    app = FastAPI()
    app.include_router(search_module.router, prefix="/api/v1")
    return app, search_module


def test_hybrid_search_returns_deterministic_fields() -> None:
    app, search_module = _build_app()

    mock_user = Mock()
    mock_user.id = "test-user-id"
    mock_user.organization_id = "test-org-id"

    app.dependency_overrides[search_module.get_current_user] = lambda: mock_user
    app.dependency_overrides[search_module.get_db_sync] = lambda: Mock()

    hybrid_response = SearchResponse(
        query="deterministic test query",
        search_id="search-123",
        search_type=SearchType.HYBRID,
        results=[],
        total_results=0,
        returned_results=0,
        search_time_ms=12.3,
        limit=20,
        offset=0,
        has_more=False,
        answer_type="extractive",
        claims=["Claim A", "Claim B"],
        confidence=0.91,
        coverage=0.82,
        decision_trace_id="trace-top-level-should-be-overridden",
        trace=DeterministicTrace(decision_trace_id="trace-abc-123"),
    )

    @asynccontextmanager
    async def _no_lifespan(_app: FastAPI):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _no_lifespan

    try:
        with patch.object(
            search_module.hybrid_search_service,
            "search",
            return_value=hybrid_response,
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/search/hybrid",
                    json={"query": "deterministic test query"},
                )

        assert response.status_code == 200
        payload = response.json()

        assert payload["answer_type"] == "extractive"
        assert payload["claims"] == ["Claim A", "Claim B"]
        assert payload["confidence"] == 0.91
        assert payload["coverage"] == 0.82
        assert payload["decision_trace_id"] == "trace-abc-123"
        assert payload["trace"] == {"decision_trace_id": "trace-abc-123"}
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()


def test_hybrid_search_backfills_missing_deterministic_fields() -> None:
    app, search_module = _build_app()

    mock_user = Mock()
    mock_user.id = "test-user-id"
    mock_user.organization_id = "test-org-id"

    app.dependency_overrides[search_module.get_current_user] = lambda: mock_user
    app.dependency_overrides[search_module.get_db_sync] = lambda: Mock()

    hybrid_response = SearchResponse(
        query="deterministic defaults query",
        search_id="search-999",
        search_type=SearchType.HYBRID,
        results=[],
        total_results=0,
        returned_results=0,
        search_time_ms=7.2,
        limit=20,
        offset=0,
        has_more=False,
    )

    @asynccontextmanager
    async def _no_lifespan(_app: FastAPI):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _no_lifespan

    try:
        with patch.object(
            search_module.hybrid_search_service,
            "search",
            return_value=hybrid_response,
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/search/hybrid",
                    json={"query": "deterministic defaults query"},
                )

        assert response.status_code == 200
        payload = response.json()

        assert payload["answer_type"] == "extractive"
        assert payload["confidence"] == 0.0
        assert payload["coverage"] == 0.0
        assert payload["decision_trace_id"] == "trace-search-999"
        assert payload["trace"] == {"decision_trace_id": "trace-search-999"}
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()
