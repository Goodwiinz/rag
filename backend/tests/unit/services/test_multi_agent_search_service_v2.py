"""Regression tests for enhanced multi-agent search tenant scoping."""

import json
from types import SimpleNamespace

import pytest

from src.services.search import multi_agent_search_service_v2 as service_v2


@pytest.mark.unit
def test_enhanced_search_tool_uses_request_tenant_context(monkeypatch):
    """The CrewAI tool must not search or cache under a shared tenant."""
    calls = []

    def fake_search(search_request, user_id, organization_id):
        calls.append(
            {
                "query": search_request.query,
                "user_id": user_id,
                "organization_id": organization_id,
            }
        )
        return SimpleNamespace(results=[], query_time=0, search_strategy="hybrid")

    monkeypatch.setattr(service_v2.hybrid_search_service, "search", fake_search)

    tool = service_v2.EnhancedSearchTool()

    user_token = service_v2._current_search_user_id.set("user-a")
    organization_token = service_v2._current_search_organization_id.set("org-a")
    try:
        first_response = json.loads(tool._run("shared query"))
    finally:
        service_v2._current_search_user_id.reset(user_token)
        service_v2._current_search_organization_id.reset(organization_token)

    user_token = service_v2._current_search_user_id.set("user-b")
    organization_token = service_v2._current_search_organization_id.set("org-b")
    try:
        second_response = json.loads(tool._run("shared query"))
    finally:
        service_v2._current_search_user_id.reset(user_token)
        service_v2._current_search_organization_id.reset(organization_token)

    assert first_response["results"] == []
    assert second_response["results"] == []
    assert calls == [
        {"query": "shared query", "user_id": "user-a", "organization_id": "org-a"},
        {"query": "shared query", "user_id": "user-b", "organization_id": "org-b"},
    ]


@pytest.mark.unit
def test_enhanced_search_tool_fails_closed_without_tenant_context(monkeypatch):
    """A missing request context must not fall back to a global/default org."""

    def fail_if_called(*args, **kwargs):
        raise AssertionError("search should not run without tenant context")

    monkeypatch.setattr(service_v2.hybrid_search_service, "search", fail_if_called)

    tool = service_v2.EnhancedSearchTool()
    response = json.loads(tool._run("query without context"))

    assert response == {
        "error": "Search request context unavailable",
        "results": [],
    }
