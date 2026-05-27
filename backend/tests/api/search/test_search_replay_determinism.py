"""API replay test for deterministic hybrid search payload stability."""

import importlib.util
import json
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


def test_hybrid_search_replay_returns_identical_deterministic_payload() -> None:
    app, search_module = _build_app()

    mock_user = Mock()
    mock_user.id = "test-user-id"
    mock_user.organization_id = "test-org-id"

    app.dependency_overrides[search_module.get_current_user] = lambda: mock_user
    app.dependency_overrides[search_module.get_db] = lambda: Mock()

    deterministic_response = SearchResponse(
        query="determinism replay",
        search_id="search-replay-fixed",
        search_type=SearchType.HYBRID,
        results=[],
        total_results=0,
        returned_results=0,
        search_time_ms=9.0,
        limit=20,
        offset=0,
        has_more=False,
        answer_type="extractive",
        confidence=0.0,
        coverage=0.0,
        decision_trace_id="trace-search-replay-fixed",
        trace=DeterministicTrace(decision_trace_id="trace-search-replay-fixed"),
        deterministic_status="NO_MATCH",
        deterministic_message="No matching evidence found for this query.",
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
            return_value=deterministic_response,
        ):
            with TestClient(app) as client:
                first = client.post(
                    "/api/v1/search/hybrid", json={"query": "determinism replay"}
                )
                second = client.post(
                    "/api/v1/search/hybrid", json={"query": "determinism replay"}
                )

        assert first.status_code == 200
        assert second.status_code == 200

        first_payload = first.json()
        second_payload = second.json()

        assert first_payload == second_payload
        assert json.dumps(first_payload, sort_keys=True) == json.dumps(
            second_payload, sort_keys=True
        )
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()
