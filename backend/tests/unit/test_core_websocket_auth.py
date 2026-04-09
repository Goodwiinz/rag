from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.core.security import TokenData
from src.core.websocket_auth import WebSocketAuthenticator, WebSocketAuthError


class DummyWebSocket:
    def __init__(self, *, headers=None, cookies=None):
        self.headers = headers or {}
        self.cookies = cookies or {}


@pytest.mark.asyncio
async def test_authenticate_accepts_tokens_via_shared_verifier_without_hs256_secret():
    websocket = DummyWebSocket(
        headers={"authorization": "Bearer es256-token"},
    )
    token_data = TokenData(
        user_id="user-123",
        email="user@example.com",
        organization_id="org-456",
        role="admin",
        exp=datetime.now(timezone.utc),
    )

    with patch(
        "src.core.websocket_auth.verify_token",
        return_value=token_data,
        create=True,
    ):
        payload = await WebSocketAuthenticator.authenticate(websocket)

    assert payload["sub"] == "user-123"
    assert payload["email"] == "user@example.com"
    assert payload["organization_id"] == "org-456"
    assert payload["role"] == "admin"
    assert payload["_auth_method"] == "bearer_header"
    assert "_authenticated_at" in payload


@pytest.mark.asyncio
async def test_authenticate_rejects_invalid_token_from_shared_verifier():
    websocket = DummyWebSocket(
        headers={"authorization": "Bearer invalid-token"},
    )

    with patch("src.core.websocket_auth.verify_token", return_value=None, create=True):
        with pytest.raises(WebSocketAuthError, match="Invalid authentication token"):
            await WebSocketAuthenticator.authenticate(websocket)
