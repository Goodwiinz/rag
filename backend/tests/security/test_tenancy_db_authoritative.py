"""Regression: tenancy context comes from the DB user, not the JWT claim.

_extract_tenant_info previously read role from token_data.role and never
checked is_active/is_deleted, so a since-demoted or since-deactivated user kept
their elevated role / tenant access for the life of a (up to 30-day) token. The
live DB User row is now the source of truth.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.middleware.multi_tenancy import MultiTenancyMiddleware, _role_to_str
from src.models.user import UserRole


class _Result:
    def __init__(self, obj):
        self._obj = obj

    def scalars(self):
        return self

    def first(self):
        return self._obj


def _mw() -> MultiTenancyMiddleware:
    return MultiTenancyMiddleware(app=MagicMock())


def _request():
    return SimpleNamespace(headers={"Authorization": "Bearer tok"})


def _token(role: str = "admin"):
    # organization_id=None -> exercises the DB fallback path (not the CLI
    # fast-path, which needs a real AsyncSessionLocal).
    return SimpleNamespace(user_id="user-1", organization_id=None, role=role)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_comes_from_db_not_token() -> None:
    mw = _mw()
    db = AsyncMock()
    db_user = SimpleNamespace(
        id="user-1", organization_id="org-1", role=UserRole.USER
    )
    db.execute = AsyncMock(return_value=_Result(db_user))

    with patch(
        "src.middleware.multi_tenancy.verify_token",
        return_value=_token(role="admin"),
    ):
        ctx = await mw._extract_tenant_info(_request(), db)

    assert ctx is not None
    assert ctx["role"] == "user"  # DB role, NOT the token's "admin"
    assert ctx["organization_id"] == "org-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_inactive_or_deleted_user_gets_no_context() -> None:
    mw = _mw()
    db = AsyncMock()
    # The is_active/is_deleted WHERE filter excludes the row -> query returns
    # None on both the initial select and the post-JIT re-query.
    db.execute = AsyncMock(return_value=_Result(None))

    with patch(
        "src.middleware.multi_tenancy.verify_token",
        return_value=_token(role="admin"),
    ), patch(
        "src.middleware.multi_tenancy.ensure_user_and_org",
        new=AsyncMock(return_value=None),
    ):
        ctx = await mw._extract_tenant_info(_request(), db)

    assert ctx is None  # no tenant context for a deactivated/deleted user


@pytest.mark.unit
def test_role_to_str_maps_enum_and_defaults() -> None:
    assert _role_to_str(UserRole.ADMIN) == "admin"
    assert _role_to_str(UserRole.USER) == "user"
    assert _role_to_str(None) == "user"
