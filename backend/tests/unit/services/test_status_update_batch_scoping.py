"""Batched status broadcasts must stay per-tenant.

``_broadcast_update_batch`` groups queued updates by (channel, organization).
Grouping by channel alone would bundle two orgs' updates into one batch
message with no single org to gate it by, re-opening the cross-tenant leak.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.services.infrastructure.status_update_service import StatusUpdateService
from src.services.websocket.websocket_manager import MessageType, WebSocketMessage

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _queued(org_id: str, doc_id: str) -> dict:
    msg = WebSocketMessage(
        type=MessageType.DOCUMENT_PROCESSING,
        data={"document_id": doc_id},
        timestamp=datetime.now(timezone.utc),
        target_channels=["document_processing"],
        target_organization=org_id,
    )
    return {"message": asdict(msg)}


async def test_batch_splits_by_organization():
    svc = StatusUpdateService()
    svc._batch_updates["document_processing"] = [
        _queued("org-A", "d-1"),
        _queued("org-B", "d-2"),
        _queued("org-A", "d-3"),
    ]

    sent = []

    async def _capture(channel, message):
        sent.append((channel, message.target_organization, message.data["total_updates"]))

    with patch(
        "src.services.infrastructure.status_update_service.connection_manager"
    ) as cm:
        cm.broadcast_to_channel = AsyncMock(side_effect=_capture)
        await svc._broadcast_update_batch("document_processing")

    # Two distinct (channel, org) batches — never one mixed-tenant blob.
    by_org = {org: total for _ch, org, total in sent}
    assert by_org == {"org-A": 2, "org-B": 1}
    # Every batch message carries exactly one org.
    assert all(org is not None for _ch, org, _total in sent)


async def test_document_update_without_org_skips_channel_broadcast():
    """Fail CLOSED: a document with no org must NOT fan out onto the shared
    channel (target_organization=None would otherwise = broadcast to all)."""
    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock

    import src.services.infrastructure.status_update_service as sus
    from src.models.document import ProcessingStatus

    svc = sus.StatusUpdateService()
    queued = []
    svc._queue_update = AsyncMock(side_effect=lambda *a, **k: queued.append(a))

    # org-less document (arXiv ingest mints empty-string orgs). MagicMock
    # auto-stubs the many fields update_data reads; only organization_id is
    # pinned (to the empty string that triggers the fail-closed path).
    document = MagicMock()
    document.organization_id = ""
    document.id = "d-1"
    document.uploaded_by_user_id = "u-1"

    session = MagicMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = document
    session.execute = AsyncMock(return_value=exec_result)

    @asynccontextmanager
    async def _fake_session():
        yield session

    with patch.object(sus, "get_async_session", _fake_session), patch.object(
        sus, "connection_manager"
    ) as cm, patch.object(svc, "_log_status_update", AsyncMock()):
        cm.broadcast_to_user = AsyncMock()
        await svc.broadcast_document_update("d-1", ProcessingStatus.PROCESSING)

    # No channel broadcast was queued for the org-less document.
    assert queued == []
    # The owner still got the direct per-user delivery.
    cm.broadcast_to_user.assert_awaited()


async def test_job_update_without_org_skips_channel_broadcast():
    """Same fail-closed guard as documents, on the copy-pasted job path —
    pinned separately so the two branches can't silently diverge."""
    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock

    import src.services.infrastructure.status_update_service as sus
    from src.models.processing import JobStatus

    svc = sus.StatusUpdateService()
    queued = []
    svc._queue_update = AsyncMock(side_effect=lambda *a, **k: queued.append(a))

    job = MagicMock()
    job.organization_id = ""  # org-less job
    job.id = "j-1"
    job.created_by_user_id = "u-1"
    job.job_type = MagicMock(value="ingest")
    job.document = None

    session = MagicMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = job
    session.execute = AsyncMock(return_value=exec_result)

    @asynccontextmanager
    async def _fake_session():
        yield session

    with patch.object(sus, "get_async_session", _fake_session), patch.object(
        sus, "connection_manager"
    ) as cm, patch.object(svc, "_log_status_update", AsyncMock()):
        cm.broadcast_to_user = AsyncMock()
        await svc.broadcast_job_update("j-1", JobStatus.RUNNING)

    assert queued == []  # no channel fan-out for the org-less job
    cm.broadcast_to_user.assert_awaited()  # owner still gets direct delivery
