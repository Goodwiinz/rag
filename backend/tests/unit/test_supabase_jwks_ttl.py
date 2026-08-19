"""R4-M11 regression: _get_supabase_jwks cached the JWKS forever.

Once fetched successfully, the module-level cache was never invalidated, so
a Supabase key rotation would never be picked up without a full process
restart. Now cached for _SUPABASE_JWKS_TTL_SECONDS; a refetch failure after
expiry must fall back to the stale (but still valid) cache rather than
dropping working keys.
"""

from unittest.mock import MagicMock, patch

import pytest

import src.core.security as security_module


@pytest.fixture(autouse=True)
def _reset_jwks_cache():
    security_module._supabase_jwks_cache = None
    security_module._supabase_jwks_cache_fetched_at = None
    yield
    security_module._supabase_jwks_cache = None
    security_module._supabase_jwks_cache_fetched_at = None


def _mock_response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


@pytest.mark.unit
def test_first_call_fetches_and_caches():
    with (
        patch("src.core.security.httpx.get") as mock_get,
        patch("src.core.security.time.time", return_value=1000.0),
    ):
        mock_get.return_value = _mock_response({"keys": ["a"]})
        result = security_module._get_supabase_jwks()

    assert result == {"keys": ["a"]}
    assert mock_get.call_count == 1


@pytest.mark.unit
def test_within_ttl_does_not_refetch():
    with (
        patch("src.core.security.httpx.get") as mock_get,
        patch("src.core.security.time.time", return_value=1000.0),
    ):
        mock_get.return_value = _mock_response({"keys": ["a"]})
        security_module._get_supabase_jwks()

    with (
        patch("src.core.security.httpx.get") as mock_get2,
        patch("src.core.security.time.time", return_value=1000.0 + 3599),
    ):
        result = security_module._get_supabase_jwks()

    mock_get2.assert_not_called()
    assert result == {"keys": ["a"]}


@pytest.mark.unit
def test_after_ttl_refetches():
    with (
        patch("src.core.security.httpx.get") as mock_get,
        patch("src.core.security.time.time", return_value=1000.0),
    ):
        mock_get.return_value = _mock_response({"keys": ["a"]})
        security_module._get_supabase_jwks()

    with (
        patch("src.core.security.httpx.get") as mock_get2,
        patch("src.core.security.time.time", return_value=1000.0 + 3601),
    ):
        mock_get2.return_value = _mock_response({"keys": ["b"]})
        result = security_module._get_supabase_jwks()

    mock_get2.assert_called_once()
    assert result == {"keys": ["b"]}


@pytest.mark.unit
def test_refetch_failure_after_ttl_returns_stale_cache():
    with (
        patch("src.core.security.httpx.get") as mock_get,
        patch("src.core.security.time.time", return_value=1000.0),
    ):
        mock_get.return_value = _mock_response({"keys": ["a"]})
        security_module._get_supabase_jwks()

    with (
        patch("src.core.security.httpx.get", side_effect=Exception("network down")),
        patch("src.core.security.time.time", return_value=1000.0 + 3601),
    ):
        result = security_module._get_supabase_jwks()

    assert result == {"keys": ["a"]}
