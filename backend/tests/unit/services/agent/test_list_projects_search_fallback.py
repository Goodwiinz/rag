"""A search that matches nothing must not read as "you have no projects".

Observed on dev, 2026-07-27, synthetic ``writing_draft`` (thread
``synthetic-writing_draft-1785130836600``)::

    list_projects(search='library', limit=10) -> {"projects": [], "total": 0}
    create_project_note(...)                  -> "project_id is required"
    list_projects(limit=50)                   -> [1 project]
    create_project_note(...)                  -> success

Asked to "save it to my **library**", the model used that word as a project
name filter. Nothing is named "library", so it got an empty list, concluded
there was nowhere to save, and called ``create_project_note`` without a
project_id. That call is destructive, so the failure cost a human
confirmation round trip and surfaced a red tool card, before the model
retried unfiltered and succeeded.

The user's phrasing is rarely a project name. Falling back to the unfiltered
list — and saying the filter was dropped — removes the wasted round trip
without hiding anything.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


def _project(name: str) -> MagicMock:
    proj = MagicMock()
    proj.id = uuid4()
    proj.name = name
    proj.description = None
    proj.research_status = "active"
    proj.tags = []
    proj.updated_at = None
    return proj


class _Service:
    """Stands in for ProjectService, recording each call's search term."""

    def __init__(self, by_search: Dict[Any, List[MagicMock]]) -> None:
        self._by_search = by_search
        self.searches: List[Any] = []

    async def list_projects(self, **kwargs: Any) -> Dict[str, Any]:
        search = kwargs.get("search")
        self.searches.append(search)
        found = self._by_search.get(search, [])
        return {"projects": found, "total": len(found)}


async def _run(monkeypatch: pytest.MonkeyPatch, service: _Service, args: dict) -> dict:
    import src.services.research.project_service as ps
    from src.services.agent.tools_impl import _tool_list_projects

    monkeypatch.setattr(ps, "ProjectService", lambda _db: service)

    user = MagicMock()
    user.id = uuid4()
    user.organization_id = uuid4()
    return await _tool_list_projects(args, MagicMock(), user)


class TestSearchFallback:
    async def test_unmatched_search_falls_back_to_the_full_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = _Service({None: [_project("synthtraffic-2026")], "library": []})

        result = await _run(monkeypatch, service, {"search": "library"})

        assert service.searches == ["library", None], "should retry unfiltered"
        assert len(result["projects"]) == 1
        assert result["search_ignored"] == "library"
        assert "library" in result["note"]

    async def test_a_matching_search_is_not_second_guessed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The filter is honoured whenever it actually matches."""
        service = _Service(
            {"thesis": [_project("thesis")], None: [_project("a"), _project("b")]}
        )

        result = await _run(monkeypatch, service, {"search": "thesis"})

        assert service.searches == ["thesis"], "no fallback query when the search hit"
        assert len(result["projects"]) == 1
        assert "search_ignored" not in result
        assert "note" not in result

    async def test_a_genuinely_empty_library_stays_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No projects at all must not be dressed up as a filter problem."""
        service = _Service({"library": [], None: []})

        result = await _run(monkeypatch, service, {"search": "library"})

        assert result["projects"] == []
        assert result["total"] == 0
        assert "search_ignored" not in result, (
            "there is nothing to fall back to — saying the filter was dropped "
            "would imply projects exist"
        )

    async def test_no_search_means_no_extra_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = _Service({None: []})

        await _run(monkeypatch, service, {})

        assert service.searches == [None]
