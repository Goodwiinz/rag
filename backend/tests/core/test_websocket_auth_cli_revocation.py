"""R4-M7 regression: WebSocket auth never checked CLI-token revocation.

``src/core/dependencies.get_current_user`` (the HTTP auth chokepoint) rejects
a revoked CLI token via ``is_cli_token_revoked``; ``WebSocketAuthenticator.
authenticate`` (the WS chokepoint) skipped that check entirely, so a revoked
CLI token could still open a WebSocket connection. Mocked verify_token +
revocation store, no real Redis/DB.
"""

from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from src.core.security import TokenData
from src.core.websocket_auth import WebSocketAuthenticator, WebSocketAuthError

pytestmark = pytest.mark.unit


class DummyWebSocket:
    def __init__(self, *, headers: dict | None = None) -> None:
        self.headers = headers or {}


def make_cli_token_data(**overrides: Any) -> TokenData:
    data: dict[str, Any] = {
        "user_id": "user-123",
        "email": "user@example.com",
        "organization_id": "org-456",
        "role": "admin",
        "exp": datetime.now(timezone.utc),
        "is_cli": True,
        "issued_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return TokenData(**data)


@pytest.mark.asyncio
async def test_authenticate_rejects_revoked_cli_token() -> None:
    websocket = DummyWebSocket(headers={"authorization": "Bearer cli-token"})
    token_data = make_cli_token_data()

    with (
        patch(
            "src.core.websocket_auth.verify_token", return_value=token_data, create=True
        ),
        patch(
            "src.core.cli_token_revocation.is_cli_token_revoked",
            new=AsyncMock(return_value=True),
        ),
    ):
        with pytest.raises(WebSocketAuthError):
            await WebSocketAuthenticator.authenticate(cast(Any, websocket))


@pytest.mark.asyncio
async def test_authenticate_allows_non_revoked_cli_token() -> None:
    websocket = DummyWebSocket(headers={"authorization": "Bearer cli-token"})
    token_data = make_cli_token_data()

    with (
        patch(
            "src.core.websocket_auth.verify_token", return_value=token_data, create=True
        ),
        patch(
            "src.core.cli_token_revocation.is_cli_token_revoked",
            new=AsyncMock(return_value=False),
        ),
    ):
        payload = await WebSocketAuthenticator.authenticate(cast(Any, websocket))

    assert payload["sub"] == "user-123"


@pytest.mark.asyncio
async def test_authenticate_skips_revocation_check_for_non_cli_token() -> None:
    websocket = DummyWebSocket(headers={"authorization": "Bearer regular-token"})
    token_data = make_cli_token_data(is_cli=False)

    with (
        patch(
            "src.core.websocket_auth.verify_token", return_value=token_data, create=True
        ),
        patch(
            "src.core.cli_token_revocation.is_cli_token_revoked",
            new=AsyncMock(return_value=True),
        ) as mock_revoked,
    ):
        payload = await WebSocketAuthenticator.authenticate(cast(Any, websocket))

    mock_revoked.assert_not_called()
    assert payload["sub"] == "user-123"
