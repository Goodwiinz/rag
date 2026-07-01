"""delete_file must commit the soft-delete BEFORE removing the storage object.

Deleting the physical object first meant a commit failure rolled the DB row back
while the object was already irreversibly gone — a live row pointing at a missing
file. Now the DB is the source of truth: commit first, then best-effort physical
delete (a storage-delete failure must NOT roll back the committed soft-delete).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.services.documents.file_service import FileService

pytestmark = pytest.mark.unit


def _svc():
    svc = object.__new__(FileService)  # skip heavy __init__
    svc.db = AsyncMock()
    return svc


def _doc(owner_id="u1"):
    doc = MagicMock()
    doc.uploaded_by_user_id = owner_id
    doc.file_size_bytes = 100
    doc.organization = MagicMock()
    return doc


def _owner():
    user = MagicMock()
    user.id = "u1"
    user.has_permission = MagicMock(return_value=False)
    return user


@pytest.mark.asyncio
async def test_commits_before_physical_delete():
    svc = _svc()
    order = []
    svc.db.commit = AsyncMock(side_effect=lambda: order.append("commit"))
    svc.delete_physical_file = MagicMock(side_effect=lambda d: order.append("physical"))

    doc, user = _doc(), _owner()
    assert await svc.delete_file(doc, user) is True
    # commit (DB source of truth) happens BEFORE the irreversible object delete.
    assert order == ["commit", "physical"]
    doc.soft_delete.assert_called_once()


@pytest.mark.asyncio
async def test_physical_delete_failure_does_not_rollback():
    svc = _svc()
    svc.db.commit = AsyncMock()
    svc.db.rollback = AsyncMock()
    svc.delete_physical_file = MagicMock(side_effect=RuntimeError("s3 down"))

    doc, user = _doc(), _owner()
    # A storage-delete failure after the commit leaves an orphan, not a data-loss
    # rollback: the call still succeeds and the committed soft-delete stands.
    assert await svc.delete_file(doc, user) is True
    svc.db.commit.assert_awaited_once()
    svc.db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_permission_denied_propagates_403():
    svc = _svc()
    svc.delete_physical_file = MagicMock()
    doc = _doc(owner_id="someone-else")
    user = _owner()  # not owner, not admin
    with pytest.raises(HTTPException) as exc:
        await svc.delete_file(doc, user)
    assert exc.value.status_code == 403
    svc.delete_physical_file.assert_not_called()
    svc.db.commit.assert_not_awaited()
