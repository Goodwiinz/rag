import pytest
import sys
from unittest.mock import MagicMock, AsyncMock, patch


# Safe spacy mocking using fixture
@pytest.fixture(autouse=True)
def mock_spacy():
    original_spacy = sys.modules.get('spacy')
    sys.modules['spacy'] = MagicMock()
    yield
    if original_spacy is None:
        del sys.modules['spacy']
    else:
        sys.modules['spacy'] = original_spacy


def get_client():
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app), app


@pytest.fixture
def mock_rate_limiter_blocked():
    import src.api.auth.auth
    with patch("src.api.auth.auth.auth_rate_limiter") as mock:
        mock.check_rate_limit = AsyncMock(return_value=(False, 120))
        mock.record_attempt = AsyncMock()
        mock.is_allowed = AsyncMock(return_value=False)
        yield mock


@pytest.fixture
def mock_rate_limiter_allowed():
    import src.api.auth.auth
    with patch("src.api.auth.auth.auth_rate_limiter") as mock:
        mock.check_rate_limit = AsyncMock(return_value=(True, 0))
        mock.record_attempt = AsyncMock()
        mock.is_allowed = AsyncMock(return_value=True)
        yield mock


def test_refresh_ip_blocked_returns_429_with_retry_after(mock_rate_limiter_blocked):
    """IP-layer block on /refresh returns 429 with Retry-After header."""
    client, _ = get_client()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "some_token"})
    assert response.status_code == 429
    assert response.json()["error"]["message"] == "Too many refresh attempts. Please try again later."
    assert response.headers.get("retry-after") == "120"
    # check_rate_limit called once for IP layer (blocked before user layer)
    mock_rate_limiter_blocked.check_rate_limit.assert_called_once()


def test_refresh_success_does_not_record(mock_rate_limiter_allowed):
    """Successful refresh should NOT call record_attempt."""
    client, app = get_client()

    from src.services.security.auth_service import AuthService, get_auth_service
    mock_auth = AsyncMock(spec=AuthService)
    mock_auth.refresh_access_token = AsyncMock(return_value={
        "access_token": "new_token",
        "refresh_token": "new_refresh",
        "token_type": "bearer",
        "expires_in": 3600,
    })
    app.dependency_overrides[get_auth_service] = lambda: mock_auth

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "valid_token"})
    assert response.status_code == 200
    mock_rate_limiter_allowed.record_attempt.assert_not_called()

    app.dependency_overrides.clear()


def test_refresh_failure_records_attempt(mock_rate_limiter_allowed):
    """Failed refresh should call record_attempt for IP layer."""
    client, app = get_client()

    from src.services.security.auth_service import AuthService, get_auth_service
    mock_auth = AsyncMock(spec=AuthService)
    mock_auth.refresh_access_token = AsyncMock(side_effect=Exception("Invalid token"))
    app.dependency_overrides[get_auth_service] = lambda: mock_auth

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "bad_token"})
    assert response.status_code == 401
    # At minimum, IP-layer attempt was recorded
    mock_rate_limiter_allowed.record_attempt.assert_called()

    app.dependency_overrides.clear()


def test_change_password_ip_blocked_returns_429(mock_rate_limiter_blocked):
    """IP-layer block on change-password returns 429 with Retry-After."""
    client, app = get_client()

    from src.core.security import get_current_user_token

    mock_token = MagicMock()
    mock_token.user_id = "00000000-0000-0000-0000-000000000001"
    app.dependency_overrides[get_current_user_token] = lambda: mock_token

    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "old", "new_password": "new"},
        headers={"Authorization": "Bearer fake_token"},
    )

    assert response.status_code == 429
    assert "Too many password change attempts" in response.json()["error"]["message"]
    assert response.headers.get("retry-after") == "120"

    app.dependency_overrides.clear()


def test_change_password_email_blocked_returns_429():
    """Email-layer block on change-password returns 429 (IP passes, email blocked)."""
    import src.api.auth.auth

    from src.core.security import get_current_user_token
    from src.models.user import User

    mock_user = MagicMock(spec=User)
    mock_user.email = "test@example.com"
    mock_user.id = "00000000-0000-0000-0000-000000000001"

    with patch("src.api.auth.auth.auth_rate_limiter") as mock_rl, \
         patch("src.api.auth.auth.get_current_user", new_callable=AsyncMock, return_value=mock_user):
        # IP check passes, email check fails
        mock_rl.check_rate_limit = AsyncMock(side_effect=[
            (True, 0),     # IP layer
            (False, 60),   # Email layer
        ])
        mock_rl.record_attempt = AsyncMock()

        client, app = get_client()

        mock_token = MagicMock()
        mock_token.user_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_current_user_token] = lambda: mock_token

        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "old", "new_password": "new"},
            headers={"Authorization": "Bearer fake_token"},
        )

        assert response.status_code == 429
        assert "Too many password change attempts for this account" in response.json()["error"]["message"]
        assert response.headers.get("retry-after") == "60"
        # check_rate_limit called twice (IP + email)
        assert mock_rl.check_rate_limit.call_count == 2

        app.dependency_overrides.clear()
