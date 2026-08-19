"""R4-M5 regression: /ws/status and its websocket_v2 siblings must require auth.

``/ws/status`` (websocket.py) and ``get_websocket_status`` / ``get_available_channels``
/ ``websocket_health_check`` (websocket_v2.py) exposed connection counts, channel
metadata, and health internals to anyone, unauthenticated - the sibling endpoints
in the same router (``/connections/{user_id}``, ``/broadcast``, ``/test-connection``)
all gate on ``Depends(get_current_user)``, these four didn't. Verified statically
via the FastAPI dependency graph so no live server/DB is needed.
"""

import inspect

import pytest

from src.core.dependencies import get_current_user

pytestmark = pytest.mark.unit


def _has_current_user_dependency(fn) -> bool:
    for param in inspect.signature(fn).parameters.values():
        default = param.default
        if default is inspect._empty:
            continue
        dependency = getattr(default, "dependency", None)
        if dependency is get_current_user:
            return True
    return False


def test_ws_status_requires_auth() -> None:
    from src.api.realtime.websocket import websocket_status

    assert _has_current_user_dependency(websocket_status)


def test_websocket_v2_status_requires_auth() -> None:
    from src.api.realtime.websocket_v2 import get_websocket_status

    assert _has_current_user_dependency(get_websocket_status)


def test_websocket_v2_channels_requires_auth() -> None:
    from src.api.realtime.websocket_v2 import get_available_channels

    assert _has_current_user_dependency(get_available_channels)


def test_websocket_v2_health_requires_auth() -> None:
    from src.api.realtime.websocket_v2 import websocket_health_check

    assert _has_current_user_dependency(websocket_health_check)
