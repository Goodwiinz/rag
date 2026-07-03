"""cleanup_old_audit_events must reject a null tenant context.

AuditService.cleanup_old_audit_events(organization_id=None) deletes audit
events across EVERY org (documented platform-only path). The endpoint derives
org from get_current_tenant_id(), which can be None. Without a guard, a caller
with the system_admin permission but no tenant context (e.g. a user whose org
was deleted -> SET NULL) would trigger a GLOBAL cross-tenant wipe of audit
trails. These tests pin: None org -> 401 + service never invoked; real org ->
scoped call.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit

from src.api.security import compliance as comp


async def test_null_org_rejected_and_no_delete(monkeypatch):
    monkeypatch.setattr(comp, "get_current_tenant_id", lambda: None)
    svc = MagicMock()
    svc.cleanup_old_audit_events = MagicMock(
        side_effect=AssertionError("global delete must never run for null org")
    )
    with pytest.raises(HTTPException) as ei:
        await comp.cleanup_old_audit_events(
            retention_days=365, audit_service=svc, _="ok"
        )
    assert ei.value.status_code == 401
    svc.cleanup_old_audit_events.assert_not_called()


async def test_real_org_scopes_delete(monkeypatch):
    monkeypatch.setattr(comp, "get_current_tenant_id", lambda: "org-A")
    svc = MagicMock()
    svc.cleanup_old_audit_events = MagicMock(return_value=7)
    result = await comp.cleanup_old_audit_events(
        retention_days=365, audit_service=svc, _="ok"
    )
    assert result["deleted_events"] == 7
    # service called scoped to the caller's org, never None
    _, kwargs = svc.cleanup_old_audit_events.call_args
    assert kwargs["organization_id"] == "org-A"
