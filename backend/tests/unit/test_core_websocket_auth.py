from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.core.security import TokenData
from src.core.websocket_auth import WebSocketAuthenticator, WebSocketAuthError


class DummyWebSocket:
    def __init__(self, *, headers=None, cookies=None):
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.accepted_with_subprotocol = None

    async def accept(self, subprotocol=None):
        self.accepted_with_subprotocol = subprotocol


def make_token_data(**overrides):
    data = {
        "user_id": "user-123",
        "email": "user@example.com",
        "organization_id": "org-456",
        "role": "admin",
        "exp": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return TokenData(**data)


@pytest.mark.asyncio
async def test_authenticate_accepts_tokens_via_shared_verifier_without_hs256_secret():
    websocket = DummyWebSocket(
        headers={"authorization": "Bearer es256-token"},
    )
    token_data = make_token_data()

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
        with pytest.raises(WebSocketAuthError, match="Invalid authentication token") as exc:
            await WebSocketAuthenticator.authenticate(websocket)

    assert exc.value.code == 4003


@pytest.mark.asyncio
async def test_authenticate_accepts_browser_subprotocol_token():
    websocket = DummyWebSocket(
        headers={"sec-websocket-protocol": "auth, browser-token"},
    )

    with patch(
        "src.core.websocket_auth.verify_token",
        return_value=make_token_data(role=None),
        create=True,
    ) as verify_token:
        payload = await WebSocketAuthenticator.authenticate(websocket)

    verify_token.assert_called_once_with("browser-token")
    assert payload["sub"] == "user-123"
    assert payload["role"] == "USER"
    assert payload["_auth_method"] == "subprotocol"


@pytest.mark.asyncio
async def test_authenticate_accepts_cookie_token_fallback():
    websocket = DummyWebSocket(cookies={"access_token": "cookie-token"})

    with patch(
        "src.core.websocket_auth.verify_token",
        return_value=make_token_data(user_id="cookie-user"),
        create=True,
    ) as verify_token:
        payload = await WebSocketAuthenticator.authenticate(websocket)

    verify_token.assert_called_once_with("cookie-token")
    assert payload["sub"] == "cookie-user"
    assert payload["_auth_method"] == "cookie"


@pytest.mark.asyncio
async def test_authenticate_rejects_missing_token_with_4001():
    websocket = DummyWebSocket()

    with pytest.raises(WebSocketAuthError, match="No authentication token") as exc:
        await WebSocketAuthenticator.authenticate(websocket)

    assert exc.value.code == 4001


@pytest.mark.asyncio
async def test_authenticate_rejects_expired_token_with_4002():
    websocket = DummyWebSocket(
        headers={"authorization": "Bearer expired-token"},
    )
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    with (
        patch("src.core.websocket_auth.verify_token", return_value=None, create=True),
        patch(
            "src.core.websocket_auth.jwt.get_unverified_claims",
            return_value={"exp": int(expired_at.timestamp())},
        ),
    ):
        with pytest.raises(WebSocketAuthError, match="token has expired") as exc:
            await WebSocketAuthenticator.authenticate(websocket)

    assert exc.value.code == 4002


def test_get_subprotocol_response_returns_auth_for_subprotocol_handshake():
    websocket = DummyWebSocket(
        headers={"sec-websocket-protocol": "auth, browser-token"},
    )

    subprotocol = WebSocketAuthenticator.get_subprotocol_response(websocket)

    assert subprotocol == "auth"


@pytest.mark.asyncio
async def test_authenticate_and_accept_echoes_auth_subprotocol():
    websocket = DummyWebSocket(
        headers={"sec-websocket-protocol": "auth, browser-token"},
    )

    with patch(
        "src.core.websocket_auth.verify_token",
        return_value=make_token_data(),
        create=True,
    ):
        payload, accepted = await WebSocketAuthenticator.authenticate_and_accept(
            websocket
        )

    assert accepted is True
    assert payload["_auth_method"] == "subprotocol"
    assert websocket.accepted_with_subprotocol == "auth"
