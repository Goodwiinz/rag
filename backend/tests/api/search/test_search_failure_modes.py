"""API tests for deterministic gate failure modes on hybrid search."""

import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.models.search_schemas import SearchResponse, SearchResult, SearchType


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


def _make_result(
    document_id: str,
    content_preview: str,
    source_count: int,
    relevance_score: float = 0.8,
) -> SearchResult:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return SearchResult(
        document_id=document_id,
        title=f"Doc {document_id}",
        document_type="text",
        content_preview=content_preview,
        snippets=[],
        relevance_score=relevance_score,
        file_size_bytes=1,
        created_at=now,
        updated_at=now,
        processing_status="completed",
        tags=[],
        is_public=False,
        uploaded_by_user_id="user-1",
        organization_id="org-1",
        metadata={"source_count": source_count},
    )


def test_hybrid_search_returns_insufficient_evidence_when_coverage_is_low() -> None:
    app, search_module = _build_app()

    mock_user = Mock()
    mock_user.id = "test-user-id"
    mock_user.organization_id = "test-org-id"

    app.dependency_overrides[search_module.get_current_user] = lambda: mock_user
    app.dependency_overrides[search_module.get_db_sync] = lambda: Mock()

    hybrid_response = SearchResponse(
        query="rag hallucination mitigation",
        search_id="search-low-coverage",
        search_type=SearchType.HYBRID,
        results=[
            _make_result("doc-1", "single source evidence one", source_count=1),
            _make_result("doc-2", "single source evidence two", source_count=1),
        ],
        total_results=2,
        returned_results=2,
        search_time_ms=10.1,
        limit=20,
        offset=0,
        has_more=False,
        confidence=0.76,
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
                    json={"query": "rag hallucination mitigation"},
                )

        assert response.status_code == 200
        payload = response.json()
        assert payload["deterministic_status"] == "INSUFFICIENT_EVIDENCE"
        assert "Insufficient cross-source evidence" in payload["deterministic_message"]
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()


def test_hybrid_search_returns_conflicting_evidence_when_top_hits_disagree() -> None:
    app, search_module = _build_app()

    mock_user = Mock()
    mock_user.id = "test-user-id"
    mock_user.organization_id = "test-org-id"

    app.dependency_overrides[search_module.get_current_user] = lambda: mock_user
    app.dependency_overrides[search_module.get_db_sync] = lambda: Mock()

    hybrid_response = SearchResponse(
        query="is technique X effective",
        search_id="search-conflict",
        search_type=SearchType.HYBRID,
        results=[
            _make_result(
                "doc-1",
                "A controlled study confirms the method is effective for this use case.",
                source_count=2,
            ),
            _make_result(
                "doc-2",
                "A replication study reports the method is ineffective and fails under noise.",
                source_count=2,
            ),
        ],
        total_results=2,
        returned_results=2,
        search_time_ms=11.4,
        limit=20,
        offset=0,
        has_more=False,
        confidence=0.81,
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
                    json={"query": "is technique X effective"},
                )

        assert response.status_code == 200
        payload = response.json()
        assert payload["deterministic_status"] == "CONFLICTING_EVIDENCE"
        assert "conflicting conclusions" in payload["deterministic_message"]
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()


def test_hybrid_search_returns_no_match_when_confidence_is_too_low() -> None:
    app, search_module = _build_app()

    mock_user = Mock()
    mock_user.id = "test-user-id"
    mock_user.organization_id = "test-org-id"

    app.dependency_overrides[search_module.get_current_user] = lambda: mock_user
    app.dependency_overrides[search_module.get_db_sync] = lambda: Mock()

    hybrid_response = SearchResponse(
        query="rare out-of-domain query",
        search_id="search-low-confidence",
        search_type=SearchType.HYBRID,
        results=[
            _make_result(
                "doc-1",
                "weak semantic neighbor with little relevance",
                source_count=2,
                relevance_score=0.09,
            ),
            _make_result(
                "doc-2",
                "another weak hit from broad corpus",
                source_count=2,
                relevance_score=0.1,
            ),
        ],
        total_results=2,
        returned_results=2,
        search_time_ms=10.9,
        limit=20,
        offset=0,
        has_more=False,
        confidence=0.1,
        coverage=1.0,
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
                    json={"query": "rare out-of-domain query"},
                )

        assert response.status_code == 200
        payload = response.json()
        assert payload["deterministic_status"] == "NO_MATCH"
        assert "confidence" in payload["deterministic_message"].lower()
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()
