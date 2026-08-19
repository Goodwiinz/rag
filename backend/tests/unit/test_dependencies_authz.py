"""R4-L12 / R4-L18: dead-branch cleanup in core/dependencies.py.

R4-L18: ``can_access_document``'s private-document gate used to read
``not document.is_public and not current_user.has_permission(UserRole.USER)``.
``UserRole.USER`` is rank 0 in the role hierarchy (models/user.py
``has_permission``), so ``has_permission(UserRole.USER)`` is ``True`` for
every authenticated user and the branch could never fire. The org-membership
check earlier in the function already restricts access to same-org users, so
a private document's evident additional intent — restrict further to its
uploader or an admin — is now the actual enforced check.

R4-L12: ``get_current_user_optional`` had an unreachable ``if not token_data:
return None`` branch, since its dependency chain always either returns a
``TokenData`` or raises (see ``core/security.py``'s module-level
``HTTPBearer()``, ``auto_error=True``). Confirmed zero callers repo-wide, so
the branch was deleted rather than reworked into genuine optional auth.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.core.dependencies import can_access_document, get_current_user_optional
from src.models.user import UserRole

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _db_with_document(document) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = document
    db.execute = AsyncMock(return_value=result)
    return db


def _user(user_id=None, org_id=None, is_admin=False):
    u = Mock()
    u.id = user_id or uuid4()
    u.organization_id = org_id or uuid4()
    u.has_permission = Mock(return_value=is_admin)
    return u


def _document(org_id, uploader_id, is_public):
    doc = Mock()
    doc.organization_id = org_id
    doc.uploaded_by_user_id = uploader_id
    doc.is_public = is_public
    return doc


# --- R4-L18: can_access_document private-document gate ----------------------


async def test_private_document_accessible_by_uploader():
    org = uuid4()
    user = _user(org_id=org)
    doc = _document(org_id=org, uploader_id=user.id, is_public=False)
    db = _db_with_document(doc)

    result_user, result_doc = await can_access_document("doc-1", user, db)

    assert result_user is user
    assert result_doc is doc


async def test_private_document_denied_for_non_uploader_non_admin():
    org = uuid4()
    user = _user(org_id=org, is_admin=False)
    doc = _document(
        org_id=org, uploader_id=uuid4(), is_public=False
    )  # different uploader
    db = _db_with_document(doc)

    with pytest.raises(HTTPException) as exc:
        await can_access_document("doc-1", user, db)

    assert exc.value.status_code == 403


async def test_private_document_accessible_by_admin_non_uploader():
    org = uuid4()
    user = _user(org_id=org, is_admin=True)
    doc = _document(org_id=org, uploader_id=uuid4(), is_public=False)
    db = _db_with_document(doc)

    result_user, result_doc = await can_access_document("doc-1", user, db)

    assert result_user is user
    assert result_doc is doc
    user.has_permission.assert_any_call(UserRole.ADMIN)


async def test_public_document_accessible_by_any_org_member():
    org = uuid4()
    user = _user(org_id=org, is_admin=False)
    doc = _document(org_id=org, uploader_id=uuid4(), is_public=True)
    db = _db_with_document(doc)

    result_user, result_doc = await can_access_document("doc-1", user, db)

    assert result_user is user
    assert result_doc is doc


async def test_cross_org_document_still_denied_before_private_check():
    user = _user(org_id=uuid4())
    doc = _document(
        org_id=uuid4(), uploader_id=user.id, is_public=True
    )  # different org
    db = _db_with_document(doc)

    with pytest.raises(HTTPException) as exc:
        await can_access_document("doc-1", user, db)

    assert exc.value.status_code == 403


# --- R4-L12: get_current_user_optional dead-branch removal ------------------


async def test_get_current_user_optional_returns_user_for_valid_token():
    from types import SimpleNamespace

    token_data = SimpleNamespace(user_id=str(uuid4()))
    fake_user = Mock()
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = fake_user
    db.execute = AsyncMock(return_value=result)

    out = await get_current_user_optional(token_data=token_data, db=db)

    assert out is fake_user


async def test_get_current_user_optional_returns_none_on_db_error():
    from types import SimpleNamespace

    token_data = SimpleNamespace(user_id=str(uuid4()))
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    out = await get_current_user_optional(token_data=token_data, db=db)

    assert out is None
