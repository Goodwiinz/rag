"""R4-M13: gate the process-wide X-Forwarded-For trust behind a settings flag.

``core.security._install_proxy_aware_client_patch`` monkeypatches
``starlette.requests.HTTPConnection.client`` process-wide so
``request.client.host`` reflects X-Forwarded-For. That's only safe behind a
proxy that itself sets/overwrites the header (our ingress does) — a
deployment not behind a trusted proxy would let a client spoof its own IP for
rate-limiting / audit-log / abuse-detection. The install is now gated behind
``settings.TRUSTED_PROXY_ENABLED`` (default True, preserving deployed-dev
behavior).

The gate itself runs once at module import time (a process-wide monkeypatch
can't be un-installed mid-process for a behavioral toggle test without
re-importing the module in isolation), so this pins: the config default, the
source-level wiring of the gate, and that the underlying patch function
still behaves correctly when invoked directly.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from starlette.datastructures import Address
from starlette.requests import HTTPConnection

from src.core.config import settings

pytestmark = pytest.mark.unit


def test_trusted_proxy_enabled_defaults_true() -> None:
    """Default True preserves current deployed-dev behavior (behind ingress)."""
    assert settings.TRUSTED_PROXY_ENABLED is True


def test_install_is_gated_behind_the_settings_flag_in_source() -> None:
    """Pin the source-level wiring: the process-wide install call must be
    conditional on the flag, not unconditional at import time."""
    backend = pathlib.Path(__file__).parents[2]
    src = (backend / "src/core/security.py").read_text()

    assert re.search(
        r"if\s+settings\.TRUSTED_PROXY_ENABLED\s*:\s*\n\s*_install_proxy_aware_client_patch\(\)",
        src,
    ), "expected the install call gated behind `if settings.TRUSTED_PROXY_ENABLED:`"


def test_proxy_aware_patch_prefers_forwarded_ip_when_installed() -> None:
    """The underlying patch function's behavior is unchanged by the gate —
    once installed (as it is by default), request.client.host reflects XFF."""
    from src.core.security import _install_proxy_aware_client_patch

    # Idempotent: a no-op if already installed by the module import (the
    # default-True case), otherwise installs it fresh.
    _install_proxy_aware_client_patch()

    conn = HTTPConnection.__new__(HTTPConnection)
    conn.scope = {
        "client": ("127.0.0.1", 12345),
        "type": "http",
        "headers": [(b"x-forwarded-for", b"10.0.0.1, 10.0.0.2")],
    }

    client = conn.client
    assert isinstance(client, Address)
    assert client.host == "10.0.0.2"  # rightmost — see api_security.py comment
