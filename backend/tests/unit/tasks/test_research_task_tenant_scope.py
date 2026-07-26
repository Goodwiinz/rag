"""The Celery research workflow must scope its local-index search to one tenant.

``_search_rag_store`` feeds the ``rag_store`` connector, whose results are
copied wholesale into the run (including ``metadata["full_text"]``). It called
``hybrid_search_service.search(SearchQuery(...))`` with no tenant, and
``fulltext_search_service`` applies its filter only ``if organization_id:`` —
so "no argument" meant "every organization", not "none".

The HTTP path (``api/research_engine/runs.py``) already bound the run owner's
org into the connector; only the Celery path did not. Per CLAUDE.md, tenant
scope on document queries is mandatory and the org must come from the
authenticated owner, never from client input.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


class _Recorder:
    """Stands in for hybrid_search_service, capturing the kwargs it receives."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def search(self, search_request: Any, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(results=[])


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()
    from src.services.search import hybrid_search_service as mod

    monkeypatch.setattr(mod, "hybrid_search_service", rec)
    return rec


async def test_search_is_scoped_to_the_runs_organization(recorder: _Recorder) -> None:
    from src.tasks.research_tasks import _search_rag_store

    org = str(uuid4())
    await _search_rag_store("transformers", organization_id=org)

    assert recorder.calls, "search should have been called"
    assert recorder.calls[0].get("organization_id") == org, (
        "an unscoped search returns every tenant's documents and copies their "
        "full_text into the run"
    )


async def test_unresolved_organization_searches_nothing(recorder: _Recorder) -> None:
    """Fail closed: no org resolved must not degrade to an unfiltered search."""
    from src.tasks.research_tasks import _search_rag_store

    out = await _search_rag_store("transformers", organization_id=None)

    assert out == {"results": []}
    assert not recorder.calls, "no tenant means no search, not a global search"


def test_connectors_bind_the_org_into_rag_store() -> None:
    """The connector must carry the scope; the engine never passes one."""
    from src.tasks.research_tasks import _build_connectors

    org = str(uuid4())
    connectors = _build_connectors(organization_id=org)
    search_fn = connectors["rag_store"].search_fn

    assert getattr(search_fn, "keywords", {}).get("organization_id") == org


def test_org_resolves_through_blueprint_project_owner() -> None:
    """ResearchRun has no tenant column; the owner is reached via the project."""
    from src.tasks.research_tasks import _resolve_run_organization_id

    org = uuid4()

    class _Query:
        def join(self, *_a: Any, **_k: Any) -> "_Query":
            return self

        def filter(self, *_a: Any, **_k: Any) -> "_Query":
            return self

        def scalar(self) -> Any:
            return org

    db = SimpleNamespace(query=lambda *_a, **_k: _Query())
    blueprint = SimpleNamespace(project_id=uuid4())

    assert _resolve_run_organization_id(db, blueprint) == str(org)


def test_missing_owner_org_resolves_to_none_not_a_wildcard() -> None:
    from src.tasks.research_tasks import _resolve_run_organization_id

    class _Query:
        def join(self, *_a: Any, **_k: Any) -> "_Query":
            return self

        def filter(self, *_a: Any, **_k: Any) -> "_Query":
            return self

        def scalar(self) -> Any:
            return None

    db = SimpleNamespace(query=lambda *_a, **_k: _Query())
    blueprint = SimpleNamespace(project_id=uuid4())

    assert _resolve_run_organization_id(db, blueprint) is None
