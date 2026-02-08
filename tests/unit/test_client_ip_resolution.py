import pytest

from src.core.config import settings
from src.core.security import get_client_ip


def test_get_client_ip_multi_proxy_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "10.0.0.1,10.0.0.2")
    headers = {
        "X-Forwarded-For": "203.0.113.5, 10.0.0.1, 198.51.100.7, 10.0.0.2"
    }

    assert get_client_ip(headers, "192.0.2.10") == "198.51.100.7"
