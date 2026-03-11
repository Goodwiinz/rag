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
def mock_rate_limiter():
    # Make sure module is imported before patching
    import src.api.auth.auth
    with patch("src.api.auth.auth.auth_rate_limiter") as mock:
        mock.is_allowed = AsyncMock(return_value=False)
        yield mock

def test_rate_limiting_refresh_token(mock_rate_limiter):
    client, _ = get_client()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "some_token"})
    assert response.status_code == 429
    # The middleware wraps the response in {'error': {'message': ...}}
    assert response.json()["error"]["message"] == "Too many refresh attempts. Please try again later."
    mock_rate_limiter.is_allowed.assert_called_once()

def test_rate_limiting_change_password(mock_rate_limiter):
    # To verify both the IP and email guards are reachable, return True for IP, False for email
    mock_rate_limiter.is_allowed.side_effect = [True, False]

    client, app = get_client()
    from src.models.user import User
    from src.core.dependencies import get_current_user

    mock_user = MagicMock(spec=User)
    mock_user.email = "test@example.com"

    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = client.post("/api/v1/auth/change-password", json={"current_password": "old", "new_password": "new"})

    assert response.status_code == 429
    assert "Too many password change attempts" in response.json()["error"]["message"]
    assert mock_rate_limiter.is_allowed.call_count == 2

    app.dependency_overrides.clear()
