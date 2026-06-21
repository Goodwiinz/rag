"""Regression: compliance/audit endpoints no longer crash.

S4: audit_service.create_security_incident used uuid without `import uuid` →
NameError on every call (incidents never recorded).
S5: compliance.get_audit_service() built AuditService(db=None) → every
audit_service.db.query(...) raised AttributeError (compliance reads 500).
"""

from unittest.mock import MagicMock

import pytest

from src.services.security.audit_service import AuditService


@pytest.mark.unit
def test_create_security_incident_does_not_nameerror_on_uuid():
    svc = AuditService(MagicMock())
    incident = svc.create_security_incident(
        organization_id="org-1",
        title="t",
        description="d",
        severity="high",
        category="intrusion",
    )
    # uuid resolved (no NameError) and an id was generated.
    assert incident.incident_id.startswith("INC-")


@pytest.mark.unit
def test_get_audit_service_injects_session():
    from src.api.security.compliance import get_audit_service

    sentinel = MagicMock()
    svc = get_audit_service(db=sentinel)
    assert svc.db is sentinel  # not None → no AttributeError on .db.query
