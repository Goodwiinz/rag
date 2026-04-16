
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.core.api_key_auth import get_api_key_data, APIKey, generate_api_key

@pytest.mark.asyncio
async def test_get_api_key_data_success():
    # Setup
    raw_key, key_hash = generate_api_key()
    key_prefix = raw_key[:8]

    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "127.0.0.1"
    mock_request.url.path = "/test"

    mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = raw_key

    # Mock DB
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock APIKey record
    api_key_record = APIKey(
        id="test-id",
        name="Test Key",
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=True,
        rate_limit_per_hour=100,
        usage_count=0,
        organization_id="org-1"
    )

    # Mock db.execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = api_key_record
    mock_db.execute.return_value = mock_result

    # Mock rate limiter
    with patch("src.core.api_key_auth.api_key_auth") as mock_auth_service:
        mock_auth_service.check_rate_limit = AsyncMock(return_value=True)
        mock_auth_service.track_usage = AsyncMock()
        mock_auth_service.get_current_usage = AsyncMock(return_value=0)

        # Execute
        result, endpoint = await get_api_key_data(mock_request, mock_credentials, mock_db)

        # Verify
        assert result.id == "test-id"
        assert endpoint == "/test"

        # Verify DB calls
        assert mock_db.execute.called
        assert mock_db.commit.called # It should be awaited now

@pytest.mark.asyncio
async def test_get_api_key_data_invalid_key():
    # Setup
    raw_key, key_hash = generate_api_key()
    # Use a different key for request
    wrong_key = "rag_" + "a"*32

    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "127.0.0.1"

    mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = wrong_key

    mock_db = AsyncMock(spec=AsyncSession)

    # Scenario 1: No key with prefix
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as excinfo:
        await get_api_key_data(mock_request, mock_credentials, mock_db)

    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Invalid API key"

@pytest.mark.asyncio
async def test_get_api_key_data_hash_mismatch():
    # Setup: Key with same prefix but different secret
    raw_key, key_hash = generate_api_key()
    key_prefix = raw_key[:8]

    # Create a "fake" key that has same prefix but different tail
    fake_key = key_prefix + "x" * (len(raw_key) - 8)

    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "127.0.0.1"

    mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = fake_key

    mock_db = AsyncMock(spec=AsyncSession)

    # DB returns the valid key record because prefix matches
    api_key_record = APIKey(
        id="test-id",
        name="Test Key",
        key_hash=key_hash, # Valid hash for raw_key, NOT fake_key
        key_prefix=key_prefix,
        is_active=True,
        organization_id="org-1"
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = api_key_record
    mock_db.execute.return_value = mock_result

    # Execute
    with pytest.raises(HTTPException) as excinfo:
        await get_api_key_data(mock_request, mock_credentials, mock_db)

    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
