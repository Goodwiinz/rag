"""require_org_access must reject a path organization_id != caller's tenant.

The /tenants/organizations/{organization_id}/... routes take a client-supplied
org id; the old require_tenant_permission guard only checked the caller's role,
so any authenticated user with the (universally-granted) organization_read
permission could read/update another tenant's org by id — a cross-tenant IDOR.
require_org_access adds the ownership binding. These tests pin it without an app
server by driving the dependency directly with the tenant context patched.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit

from src.api.auth import tenant_management as tm


@pytest.fixture
def _ctx(monkeypatch):
    """Patch the tenant/role context helpers used inside the guard."""
    state = {"tenant": "org-CALLER", "role": "user", "perm": True}
    monkeypatch.setattr(tm, "get_current_tenant_id", lambda: state["tenant"])
    monkeypatch.setattr(tm, "get_current_user_role", lambda: state["role"])
    monkeypatch.setattr(tm, "check_tenant_permission", lambda perm: state["perm"])
    return state


def test_same_org_allowed(_ctx):
    dep = tm.require_org_access("organization_read")
    assert dep(organization_id="org-CALLER") == "org-CALLER"


def test_cross_tenant_org_rejected_403(_ctx):
    dep = tm.require_org_access("organization_read")
    with pytest.raises(HTTPException) as ei:
        dep(organization_id="org-VICTIM")
    assert ei.value.status_code == 403


def test_unauthenticated_rejected_401(_ctx):
    _ctx["tenant"] = None
    dep = tm.require_org_access("organization_read")
    with pytest.raises(HTTPException) as ei:
        dep(organization_id="org-VICTIM")
    assert ei.value.status_code == 401


def test_missing_permission_rejected(_ctx):
    # role check fails -> permission-denied (not 403-ownership); ownership never reached
    _ctx["perm"] = False
    dep = tm.require_org_access("organization_update")
    with pytest.raises(HTTPException):
        dep(organization_id="org-CALLER")


def test_create_organization_still_uses_plain_permission_guard():
    # create has no path org -> must NOT be swapped to the ownership guard
    import inspect

    src = inspect.getsource(tm.create_organization)
    assert 'require_tenant_permission("organization_create")' in src
