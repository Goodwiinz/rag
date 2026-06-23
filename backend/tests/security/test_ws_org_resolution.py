"""Regression: WebSocket v2 resolves the REAL org and never uses "default".

Every Supabase JWT carried no org claim, so websocket_v2 bucketed every user
into a shared "default" organization → cross-tenant message exposure. The
connection's org is now resolved from the DB and the connection is refused
(fail-closed) when no real org resolves — never "default".
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.realtime.websocket_v2 import _resolve_ws_organization_id


class _Result:
    def __init__(self, obj):
        self._obj = obj

    def scalars(self):
        return self

    def first(self):
        return self._obj


def _factory(db):
    def make():
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=db)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    return make


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolves_real_org_for_existing_user() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_Result(SimpleNamespace(organization_id="org-REAL"))
    )

    org = await _resolve_ws_organization_id(
        "user-1", {"role": "USER"}, session_factory=_factory(db)
    )

    assert org == "org-REAL"  # real org, never "default"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_none_when_no_user_and_no_provision() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(None))

    with patch(
        "src.api.realtime.websocket_v2.ensure_user_and_org",
        new=AsyncMock(return_value=False),
    ):
        org = await _resolve_ws_organization_id(
            "user-1", {"role": "USER"}, session_factory=_factory(db)
        )

    assert org is None  # fail-closed, not "default"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_none_when_user_has_null_org() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_Result(SimpleNamespace(organization_id=None))
    )

    org = await _resolve_ws_organization_id(
        "user-1", {"role": "USER"}, session_factory=_factory(db)
    )

    assert org is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_error_fails_closed() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    org = await _resolve_ws_organization_id(
        "user-1", {"role": "USER"}, session_factory=_factory(db)
    )

    assert org is None  # DB failure must not grant shared access
