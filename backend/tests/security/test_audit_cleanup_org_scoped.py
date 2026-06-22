"""Regression: audit cleanup is org-scoped (no cross-tenant wipe).

cleanup_old_audit_events deleted ALL orgs' events (only a created_at filter),
exposed via a per-org system_admin endpoint → one tenant's admin could wipe
every tenant's audit trail. With organization_id it must add an org filter to
both the count and delete queries.
"""

from unittest.mock import MagicMock

import pytest

from src.services.security.audit_service import AuditService


class _FakeQuery:
    def __init__(self, recorder):
        self.recorder = recorder
        self.filters = 0

    def filter(self, *args):
        self.filters += 1
        return self

    def scalar(self):
        return 0

    def delete(self):
        self.recorder["delete_filter_count"] = self.filters
        return 0


def _svc_with_recorder():
    rec = {}
    db = MagicMock()
    db.query.side_effect = lambda *a, **k: _FakeQuery(rec)
    return AuditService(db), rec


@pytest.mark.unit
def test_cleanup_scoped_to_org_adds_org_filter():
    svc, rec = _svc_with_recorder()
    svc.cleanup_old_audit_events(retention_days=365, organization_id="org-1")
    # created_at filter + organization_id filter on the delete query.
    assert rec["delete_filter_count"] == 2


@pytest.mark.unit
def test_cleanup_without_org_only_time_filter():
    svc, rec = _svc_with_recorder()
    svc.cleanup_old_audit_events(retention_days=365)
    assert rec["delete_filter_count"] == 1
