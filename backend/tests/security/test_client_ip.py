import pytest
from unittest.mock import Mock, patch
from fastapi import Request
from src.core.security import get_client_ip
from src.core.config import settings

def create_mock_request(client_ip, headers=None):
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = client_ip
    request.headers = headers or {}
    return request

def test_get_client_ip_no_headers():
    request = create_mock_request("1.2.3.4")
    assert get_client_ip(request) == "1.2.3.4"

def test_get_client_ip_with_x_forwarded_for_untrusted_source():
    # If source is not trusted, we ignore headers
    with patch.object(settings, 'TRUSTED_PROXIES', ""):
        request = create_mock_request("1.2.3.4", {"X-Forwarded-For": "5.6.7.8"})
        assert get_client_ip(request) == "1.2.3.4"

def test_get_client_ip_with_x_forwarded_for_trusted_source():
    # If source is trusted, we use headers
    with patch.object(settings, 'TRUSTED_PROXIES', "1.2.3.4"):
        request = create_mock_request("1.2.3.4", {"X-Forwarded-For": "5.6.7.8"})
        assert get_client_ip(request) == "5.6.7.8"

def test_get_client_ip_chain_all_untrusted():
    # Source trusted, header has chain. Last proxy in header is untrusted.
    with patch.object(settings, 'TRUSTED_PROXIES', "1.2.3.4"):
        # Header: client, untrusted_proxy
        # We received from 1.2.3.4 (trusted)
        request = create_mock_request("1.2.3.4", {"X-Forwarded-For": "9.9.9.9, 5.6.7.8"})
        # 5.6.7.8 is not trusted. So it is the client (from our perspective).
        assert get_client_ip(request) == "5.6.7.8"

def test_get_client_ip_chain_with_trusted_proxies():
    # Source trusted, header has chain with some trusted proxies.
    with patch.object(settings, 'TRUSTED_PROXIES', "1.2.3.4, 5.6.7.8"):
        # Header: client, trusted_proxy
        # We received from 1.2.3.4 (trusted)
        request = create_mock_request("1.2.3.4", {"X-Forwarded-For": "9.9.9.9, 5.6.7.8"})
        # 5.6.7.8 is trusted. Look at next.
        # 9.9.9.9 is not trusted. It is the client.
        assert get_client_ip(request) == "9.9.9.9"

def test_get_client_ip_multiple_trusted_proxies_chain():
    # Longer chain
    with patch.object(settings, 'TRUSTED_PROXIES', "10.0.0.1, 10.0.0.2, 10.0.0.3"):
        # Header: client, proxy1, proxy2
        # Received from 10.0.0.3
        request = create_mock_request("10.0.0.3", {"X-Forwarded-For": "1.2.3.4, 10.0.0.1, 10.0.0.2"})
        # 10.0.0.2 is trusted.
        # 10.0.0.1 is trusted.
        # 1.2.3.4 is untrusted -> client.
        assert get_client_ip(request) == "1.2.3.4"

def test_get_client_ip_all_trusted():
    # All IPs are trusted (internal traffic?)
    with patch.object(settings, 'TRUSTED_PROXIES', "10.0.0.1, 10.0.0.2"):
        request = create_mock_request("10.0.0.2", {"X-Forwarded-For": "10.0.0.1"})
        # 10.0.0.1 is trusted.
        # No more IPs. Return 10.0.0.1.
        assert get_client_ip(request) == "10.0.0.1"

def test_get_client_ip_empty_header():
    with patch.object(settings, 'TRUSTED_PROXIES', "1.2.3.4"):
        request = create_mock_request("1.2.3.4", {"X-Forwarded-For": ""})
        assert get_client_ip(request) == "1.2.3.4"

def test_get_client_ip_no_client_host():
    request = Mock(spec=Request)
    request.client = None
    assert get_client_ip(request) == "0.0.0.0"
