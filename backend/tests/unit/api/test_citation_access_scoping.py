"""Citation relationship/graph endpoints must enforce per-tenant access.

Before the fix these fetched by id with no access filter, enabling
cross-tenant enumeration (relationships, graph, node details) and IDOR
writes (linking arbitrary citations).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.research import citations as cit

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _user():
    u = Mock()
    u.id = uuid4()
    u.organization_id = uuid4()
    return u


def _db_returning(value):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = Mock(return_value=value)
    db.execute = AsyncMock(return_value=result)
    return db


async def test_load_accessible_citation_404_when_missing():
    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc:
        await cit._load_accessible_citation(uuid4(), _user(), db)
    assert exc.value.status_code == 404


async def test_load_accessible_citation_404_when_not_owned(monkeypatch):
    # Citation exists but is not accessible to the caller.
    citation = Mock()
    db = _db_returning(citation)
    monkeypatch.setattr(cit, "_citation_is_accessible", lambda c, u: False)
    with pytest.raises(HTTPException) as exc:
        await cit._load_accessible_citation(uuid4(), _user(), db)
    assert exc.value.status_code == 404


async def test_load_accessible_citation_returns_when_owned(monkeypatch):
    citation = Mock()
    db = _db_returning(citation)
    monkeypatch.setattr(cit, "_citation_is_accessible", lambda c, u: True)
    assert await cit._load_accessible_citation(uuid4(), _user(), db) is citation


async def test_list_relationships_requires_anchor():
    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc:
        await cit.list_citation_relationships(
            source_id=None,
            target_id=None,
            relationship_type=None,
            current_user=_user(),
            db=db,
        )
    assert exc.value.status_code == 400


async def test_citation_graph_requires_anchor():
    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc:
        await cit.get_citation_graph(
            project_id=None,
            document_id=None,
            depth=2,
            include_external=True,
            current_user=_user(),
            db=db,
        )
    assert exc.value.status_code == 400
