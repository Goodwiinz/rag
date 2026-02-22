import pytest
from unittest.mock import patch, MagicMock
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from src.core.api_key_auth import get_api_key_data, APIKey
import secrets
import hashlib
import sys
import os

# Ensure src can be imported if running from backend root
sys.path.append(os.getcwd())

@pytest.mark.asyncio
async def test_get_api_key_data_uses_compare_digest():
    """
    Test that get_api_key_data uses secrets.compare_digest for timing-safe comparison.
    """
    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "127.0.0.1"
    mock_request.url.path = "/test/endpoint"

    # Use a key that matches the prefix logic (rag_ + chars)
    raw_key = "rag_" + "a" * 32
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw_key)

    mock_db = MagicMock()
    mock_api_key = APIKey(
        id="test_id",
        name="test_key",
        key_prefix=raw_key[:8],
        key_hash=key_hash,
        is_active=True,
        rate_limit_per_hour=1000,
        usage_count=0,
        expires_at=None
    )

    # Mock DB query
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    # Support both .first() (current) and .all() (future)
    mock_filter.first.return_value = mock_api_key
    mock_filter.all.return_value = [mock_api_key]

    # Patch secrets.compare_digest to verify it is called
    with patch("secrets.compare_digest", wraps=secrets.compare_digest) as mock_compare_digest:
        # Patch rate limiter to avoid redis interaction
        with patch("src.core.api_key_auth.api_key_auth.check_rate_limit", return_value=True), \
             patch("src.core.api_key_auth.api_key_auth.track_usage"), \
             patch("src.core.api_key_auth.api_key_auth.get_current_usage", return_value=0):

            await get_api_key_data(mock_request, credentials, mock_db)

            # Assert compare_digest was called
            # This is expected to FAIL on the current insecure implementation
            mock_compare_digest.assert_called()
