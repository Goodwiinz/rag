"""Regression: require_permission_dep actually enforces as a FastAPI dependency.

require_permission is a decorator; using it in Depends() never ran the check
(and broke the endpoint with 422/500). require_permission_dep is the
dependency-style enforcer used by the compliance + RBAC-management routers.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.middleware import rbac as rbac_mod


def _run(dep):
    # The dependency takes db via Depends(get_db_sync); call it directly.
    return dep(db=MagicMock())


@pytest.mark.unit
def test_unauthenticated_raises_401():
    dep = rbac_mod.require_permission_dep("audit_read")
    with (
        patch.object(rbac_mod, "get_current_user_id", return_value=None),
        patch.object(rbac_mod, "get_current_tenant_id", return_value=None),
    ):
        with pytest.raises(HTTPException) as ei:
            _run(dep)
    assert ei.value.status_code == 401


@pytest.mark.unit
def test_missing_permission_raises_403():
    dep = rbac_mod.require_permission_dep("audit_read")
    svc = MagicMock()
    svc.user_has_permission.return_value = False
    with (
        patch.object(rbac_mod, "get_current_user_id", return_value="u1"),
        patch.object(rbac_mod, "get_current_tenant_id", return_value="org1"),
        patch.object(rbac_mod, "RBACService", return_value=svc),
    ):
        with pytest.raises(HTTPException) as ei:
            _run(dep)
    assert ei.value.status_code == 403
    svc.user_has_permission.assert_called_once_with("u1", "audit_read", "org1")


@pytest.mark.unit
def test_granted_permission_passes():
    dep = rbac_mod.require_permission_dep("audit_read")
    svc = MagicMock()
    svc.user_has_permission.return_value = True
    with (
        patch.object(rbac_mod, "get_current_user_id", return_value="u1"),
        patch.object(rbac_mod, "get_current_tenant_id", return_value="org1"),
        patch.object(rbac_mod, "RBACService", return_value=svc),
    ):
        assert _run(dep) is None  # no raise


@pytest.mark.unit
def test_fastapi_actually_invokes_the_dependency():
    """The bug was FastAPI never running the check (decorator-in-Depends). Prove
    the dependency is resolved on a real route: no-permission → 403, not 200/422."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from src.core.database import get_db_sync

    app = FastAPI()

    @app.get(
        "/guarded",
        dependencies=[Depends(rbac_mod.require_permission_dep("audit_read"))],
    )
    def guarded():
        return {"ok": True}

    app.dependency_overrides[get_db_sync] = lambda: MagicMock()

    svc = MagicMock()
    svc.user_has_permission.return_value = False
    with (
        patch.object(rbac_mod, "get_current_user_id", return_value="u1"),
        patch.object(rbac_mod, "get_current_tenant_id", return_value="org1"),
        patch.object(rbac_mod, "RBACService", return_value=svc),
    ):
        resp = TestClient(app).get("/guarded")
    assert resp.status_code == 403

    svc.user_has_permission.return_value = True
    with (
        patch.object(rbac_mod, "get_current_user_id", return_value="u1"),
        patch.object(rbac_mod, "get_current_tenant_id", return_value="org1"),
        patch.object(rbac_mod, "RBACService", return_value=svc),
    ):
        resp_ok = TestClient(app).get("/guarded")
    assert resp_ok.status_code == 200
