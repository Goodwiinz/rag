"""POST /alerts/{alert_id}/acknowledge must scope to the caller's organization.

quality_metrics_service.acknowledge_alert looked up QualityAlert by
client-supplied alert_id with no org filter, then mutated + committed it — a
cross-tenant write (any user could acknowledge/dismiss another org's quality
alert). It was masked by the get_db() 500; fixing that un-masks it. The endpoint
now passes the caller's organization_id, and the service filters on it. These
tests pin the endpoint contract.

asyncio_mode=AUTO -> plain async def.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit

from src.api.quality import quality_metrics as qm


def _caller(org="org-A"):
    return SimpleNamespace(id="u1", organization_id=org)


async def test_acknowledge_passes_caller_org(monkeypatch):
    svc = MagicMock(return_value=True)
    monkeypatch.setattr(qm.quality_metrics_service, "acknowledge_alert", svc)
    await qm.acknowledge_alert(
        alert_id="alert-x",
        request=SimpleNamespace(),
        current_user=_caller("org-A"),
        db=MagicMock(),
    )
    kw = svc.call_args.kwargs
    assert kw["organization_id"] == "org-A"
    assert kw["alert_id"] == "alert-x"
    assert kw["acknowledged_by"] == "u1"


async def test_acknowledge_not_found_returns_404(monkeypatch):
    # service returns False when the alert isn't in the caller's org
    monkeypatch.setattr(
        qm.quality_metrics_service, "acknowledge_alert", MagicMock(return_value=False)
    )
    with pytest.raises(HTTPException) as ei:
        await qm.acknowledge_alert(
            alert_id="foreign-alert",
            request=SimpleNamespace(),
            current_user=_caller("org-A"),
            db=MagicMock(),
        )
    assert ei.value.status_code == 404
