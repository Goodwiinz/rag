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
