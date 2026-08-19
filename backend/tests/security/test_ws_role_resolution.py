"""R4-M8: WS admin-channel gating must trust the DB role, not the JWT claim.

Before this fix, the connect-time and mid-session admin-channel checks both
read ``user_payload.get("role")`` — sourced entirely from the JWT (Supabase
``app_metadata.role``, or a copy baked into a long-lived CLI token at mint
time). A CLI token defaults to ``CLI_TOKEN_EXPIRE_DAYS`` (30d) and is never
re-minted on demotion, so a demoted admin kept working admin-channel access
for up to 30 days after losing the role in the DB. Both call sites now
resolve the role from the DB (mirroring ``_resolve_ws_organization_id``).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.realtime.websocket_v2 import _resolve_ws_role
from src.models.user import UserRole
from src.services.websocket.websocket_manager import _resolve_current_db_role


class _Result:
    def __init__(self, obj):
        self._obj = obj

    def scalars(self):
        return self

    def first(self):
        return self._obj


def _session_factory(db):
    def make():
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=db)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    return make


# --- _resolve_ws_role (connect-time, websocket_v2.py) -----------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_ws_role_returns_db_role_even_when_jwt_would_say_admin() -> None:
    """DB says 'user' — the demoted-admin case a stale JWT/CLI token can't see."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(UserRole.USER))

    role = await _resolve_ws_role("user-1", session_factory=_session_factory(db))

    assert role == "user"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_ws_role_returns_admin_when_db_says_admin() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(UserRole.ADMIN))

    role = await _resolve_ws_role("user-1", session_factory=_session_factory(db))

    assert role == "admin"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_ws_role_fails_closed_to_user_when_no_row() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(None))

    role = await _resolve_ws_role("user-1", session_factory=_session_factory(db))

    assert role == "user"  # never a shared/elevated default


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_ws_role_fails_closed_to_user_on_db_error() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    role = await _resolve_ws_role("user-1", session_factory=_session_factory(db))

    assert role == "user"  # DB failure must NOT grant admin access


# --- connect-time full flow: JWT says admin, DB says user → denied ----------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connect_time_gate_denies_admin_channel_when_jwt_admin_db_user() -> None:
    """The core R4-M8 regression: a stale/forged JWT role claim of 'admin'
    must not grant the admin channel once the DB-resolved role is checked."""
    from src.api.realtime.websocket_v2 import _can_subscribe_to_channel

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(UserRole.USER))

    jwt_role = "ADMIN"  # what a stale/forged JWT claims
    db_role = await _resolve_ws_role("user-1", session_factory=_session_factory(db))

    assert db_role == "user"
    # Gate must be evaluated against db_role, not jwt_role.
    assert (
        _can_subscribe_to_channel("admin_alerts", jwt_role) is True
    )  # JWT alone would wrongly allow
    assert (
        _can_subscribe_to_channel("admin_alerts", db_role) is False
    )  # DB-sourced role correctly denies


# --- _resolve_current_db_role (mid-session, websocket_manager.py) -----------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_current_db_role_reflects_demotion() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(UserRole.USER))

    with patch(
        "src.services.websocket.websocket_manager.get_async_session",
        new=lambda: _session_factory(db)(),
    ):
        role = await _resolve_current_db_role("user-1")

    assert role == "user"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_current_db_role_fails_closed_on_error() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    with patch(
        "src.services.websocket.websocket_manager.get_async_session",
        new=lambda: _session_factory(db)(),
    ):
        role = await _resolve_current_db_role("user-1")

    assert role == "user"
