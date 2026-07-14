"""Regression tests for arxiv extraction organization-id resolution.

Production bug (2026-06-12): ``get_current_user`` returns a ``User`` ORM object,
but ``_get_organization_id`` called ``current_user.get("organization_id")`` —
dict access on an object — so every ``POST /api/v1/arxiv/extraction/extract-features``
request raised ``'User' object has no attribute 'get'`` and 500ed in <1ms.
"""

import uuid

import pytest
from fastapi import HTTPException

from src.api.arxiv.arxiv_extraction import _get_organization_id
from src.models.user import User


@pytest.mark.unit
def test_get_organization_id_reads_user_object_attribute():
    """Resolves organization_id from the User object (not via dict .get)."""
    org_id = uuid.uuid4()
    user = User(organization_id=org_id)

    assert _get_organization_id(user) == str(org_id)


@pytest.mark.unit
def test_get_organization_id_rejects_user_without_org():
    """A user with no organization must be rejected, never assigned a fabricated
    UUID — a random org id is an invalid FK and silently defeats tenant isolation
    (would let un-scoped documents/KG writes leak across tenants)."""
    user = User(organization_id=None)

    with pytest.raises(HTTPException) as exc_info:
        _get_organization_id(user)

    assert exc_info.value.status_code == 403
