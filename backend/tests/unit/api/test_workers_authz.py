"""R4-M14: every /workers/* route must be admin-gated.

``GET /workers/status`` and ``GET /workers/health`` used ``get_current_user``
(any authenticated user) while the other four routes on this router
(``/workers/queues``, ``/workers/ping``, ``/workers/registered-tasks``,
``/workers/shutdown/{worker_name}``) used ``require_admin``. All six now
depend on ``require_admin`` for consistency — worker infrastructure detail
(queue depth, registered task names, hostnames) shouldn't be exposed to a
plain USER.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

pytestmark = pytest.mark.unit


def _routes():
    from src.api.infrastructure.workers import router

    return {r.path: r for r in router.routes if isinstance(r, APIRoute)}


def test_all_worker_routes_require_admin() -> None:
    """Router-level introspection — survives a future route being added
    without re-guarding, and catches a guard silently downgraded back to
    get_current_user."""
    from src.core.dependencies import require_admin

    routes = _routes()
    assert routes, "workers router has no routes — path likely changed"

    ungated = []
    for path, route in routes.items():
        calls = [d.call for d in route.dependant.dependencies]
        if require_admin not in calls:
            ungated.append(path)

    assert ungated == [], f"routes missing require_admin: {ungated}"


def test_get_current_user_no_longer_used_on_worker_routes() -> None:
    """Regression pin for R4-M14: /status and /health specifically must not
    fall back to the weaker get_current_user dependency."""
    from src.core.dependencies import get_current_user

    routes = _routes()
    for path in ("/workers/status", "/workers/health"):
        assert path in routes, f"expected route {path} not found"
        calls = [d.call for d in routes[path].dependant.dependencies]
        assert get_current_user not in calls, f"{path} still uses get_current_user"


def test_require_admin_rejects_non_admin_caller() -> None:
    """Sanity: the require_admin dependency itself 403s a non-admin — the
    piece the router-introspection tests above assume is wired correctly."""
    from src.core.dependencies import require_role
    from src.models.user import UserRole

    checker = require_role(UserRole.ADMIN)
    non_admin = Mock()
    non_admin.has_permission = Mock(return_value=False)

    with pytest.raises(HTTPException) as exc:
        checker(current_user=non_admin)

    assert exc.value.status_code == 403
