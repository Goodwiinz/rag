"""Regression tests for ObservabilityMiddleware HTTP tracing."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.observability.instrumentation import ObservabilityMiddleware
from src.observability.metrics import configure_metrics


@pytest.fixture
def observability_app():
    configure_metrics()
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.mark.unit
def test_observability_middleware_handles_requests(observability_app):
    """Middleware must use async_trace_span correctly (async with, not with)."""
    with TestClient(observability_app, raise_server_exceptions=False) as client:
        response = client.get("/health")

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
    assert response.headers.get("x-correlation-id")
