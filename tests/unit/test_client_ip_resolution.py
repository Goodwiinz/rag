import pytest

from src.core.config import settings
from src.core.security import get_client_ip


def test_get_client_ip_multi_proxy_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "10.0.0.1,10.0.0.2")
    headers = {
        "X-Forwarded-For": "203.0.113.5, 10.0.0.1, 198.51.100.7, 10.0.0.2"
    }

    assert get_client_ip(headers, "192.0.2.10") == "198.51.100.7"


def test_get_client_ip_no_trusted_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "")
    headers = {"X-Forwarded-For": "203.0.113.5", "X-Real-IP": "198.51.100.7"}

    assert get_client_ip(headers, "192.0.2.10") == "192.0.2.10"


def test_get_client_ip_untrusted_client_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "10.0.0.1")
    headers = {"X-Forwarded-For": "203.0.113.5", "X-Real-IP": "198.51.100.7"}

    assert get_client_ip(headers, "192.0.2.10") == "192.0.2.10"


def test_get_client_ip_skips_malformed_ips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "10.0.0.2")
    headers = {
        "X-Forwarded-For": "bad-ip, 203.0.113.5, 10.0.0.2, 999.999.999.999"
    }

    assert get_client_ip(headers, "10.0.0.2") == "203.0.113.5"


def test_get_client_ip_ipv6(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "2001:db8::1")
    headers = {"X-Forwarded-For": "2001:db8::2, 2001:db8::1"}

    assert get_client_ip(headers, "2001:db8::1") == "2001:db8::2"
