import pytest
from unittest.mock import Mock, patch
from fastapi import Request
from src.core.config import settings
from src.core.security import get_client_ip

class TestGetClientIP:

    @pytest.fixture
    def mock_request(self):
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.1"
        request.headers = {}
        return request

    def test_default_untrusted(self, mock_request):
        """Test default behavior (no trusted proxies configured)"""
        with patch.object(settings, 'TRUSTED_PROXIES', ""):
            # Should return direct IP
            mock_request.headers = {"X-Forwarded-For": "1.2.3.4"}
            assert get_client_ip(mock_request) == "10.0.0.1"

    def test_trusted_proxy_exact_match(self, mock_request):
        """Test with specific trusted proxy"""
        with patch.object(settings, 'TRUSTED_PROXIES', "10.0.0.1"):
            mock_request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            # Should return last IP from header (most recent hop)
            assert get_client_ip(mock_request) == "5.6.7.8"

    def test_trusted_proxy_wildcard(self, mock_request):
        """Test with wildcard trusted proxy"""
        with patch.object(settings, 'TRUSTED_PROXIES', "*"):
            mock_request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            # Should return last IP from header
            assert get_client_ip(mock_request) == "5.6.7.8"

    def test_untrusted_proxy_with_config(self, mock_request):
        """Test when proxy is configured but request comes from untrusted source"""
        with patch.object(settings, 'TRUSTED_PROXIES', "192.168.1.1"):
            mock_request.client.host = "10.0.0.1" # Untrusted

            mock_request.headers = {"X-Forwarded-For": "1.2.3.4"}
            # Should ignore header and return direct IP
            assert get_client_ip(mock_request) == "10.0.0.1"

    def test_trusted_proxy_no_header(self, mock_request):
        """Test trusted proxy but missing header"""
        with patch.object(settings, 'TRUSTED_PROXIES', "*"):
            mock_request.headers = {}

            # Should fallback to direct IP
            assert get_client_ip(mock_request) == "10.0.0.1"

    def test_no_client_host(self, mock_request):
        """Test when request.client is None"""
        mock_request.client = None
        assert get_client_ip(mock_request) == "unknown"

    def test_spoofed_header(self, mock_request):
        """Test preventing spoofing by taking the last IP"""
        with patch.object(settings, 'TRUSTED_PROXIES', "*"):
            # Attacker sends "spoofed_ip", proxy appends "real_ip"
            # So the header received by app is "spoofed_ip, real_ip"
            mock_request.headers = {"X-Forwarded-For": "spoofed_ip, real_ip"}
            # We expect real_ip (the one appended by the trusted proxy)
            assert get_client_ip(mock_request) == "real_ip"
