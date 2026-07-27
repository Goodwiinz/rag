"""Soft-deleted projects must not be listed or fetched.

Live on dev, 2026-07-27. The writing agent called ``list_projects``, took an
id straight from the result, and ``create_project_note`` refused it::

    {"projects": [{"id": "96012179-65b7-428e-a744-2207e3fddb3d",
                   "name": "synthtraffic-20260726T184029", ...}]}
    {"error": "Project not found or access denied", "error_type": "recoverable"}

That project is soft-deleted, and so were **6 of the 12** projects the service
returned for that user. ``ProjectService`` never mentioned ``is_deleted`` at
all, while every write path filters it (``_verify_project_ownership``,
``project_skills.access``, the RAG node). So the service handed out ids that
the rest of the system then rejected, and the agent burned its retry budget
on them.

Asserted against compiled SQL rather than mocked rows: the bug was a missing
predicate, and only the statement itself proves a predicate is present.
"""

from __future__ import annotations

from typing import Any, List
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


class _Result:
    def __init__(self, value: Any = None, rows: List[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def all(self) -> List[Any]:
        return self._rows

    def scalars(self) -> "_Result":
        return self

    def unique(self) -> "_Result":
        return self

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._rows)


class _DB:
    """Captures every statement so the emitted SQL can be inspected."""

    def __init__(self, workspace_id: Any) -> None:
        self.statements: List[Any] = []
        self._workspace_id = workspace_id
        self._calls = 0

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> _Result:
        self.statements.append(stmt)
        self._calls += 1
        if self._calls == 1:
            # _get_workspace_ids_for_user
            return _Result(rows=[(self._workspace_id,)])
        return _Result(value=0, rows=[])

    def where(self, index: int) -> str:
        """The WHERE clause only.

        ``select(Collection)`` renders every column, so ``is_deleted`` appears
        in the SELECT list of an unfiltered query too — asserting against the
        full statement passes without the predicate. Only the whereclause
        proves the filter is applied.
        """
        clause = getattr(self.statements[index], "whereclause", None)
        return str(clause).lower() if clause is not None else ""

    def sql(self, index: int) -> str:
        return str(self.statements[index]).lower()


async def _run_list() -> _DB:
    from src.services.research.project_service import ProjectService

    db = _DB(workspace_id=uuid4())
    await ProjectService(db).list_projects(user_id=uuid4())
    return db


class TestListProjects:
    async def test_list_filters_out_soft_deleted(self) -> None:
        db = await _run_list()

        # statements[0] is the workspace lookup; the rest are count + page.
        clauses = [db.where(i) for i in range(1, len(db.statements))]
        assert clauses, "no project query was issued"
        for clause in clauses:
            assert "is_deleted" in clause, (
                "list_projects returned soft-deleted projects, which every "
                "write path then rejects as 'not found or access denied'"
            )

    async def test_count_and_page_share_the_filter(self) -> None:
        """A count that ignores the filter over-reports total and has_more."""
        db = await _run_list()

        indexes = range(1, len(db.statements))
        count = [db.where(i) for i in indexes if "count" in db.sql(i)]
        page = [db.where(i) for i in indexes if "count" not in db.sql(i)]

        assert count and page, "expected both a count query and a page query"
        assert all("is_deleted" in c for c in count)
        assert all("is_deleted" in c for c in page)


class TestGetProjectForUser:
    async def test_fetch_excludes_soft_deleted(self) -> None:
        """update_project and delete_project both route through this."""
        from fastapi import HTTPException

        from src.services.research.project_service import ProjectService

        db = _DB(workspace_id=uuid4())
        db._calls = 1  # skip the workspace-lookup branch

        with pytest.raises(HTTPException):
            await ProjectService(db).get_project_for_user(
                project_id=uuid4(), user_id=uuid4()
            )

        assert "is_deleted" in db.where(0)
