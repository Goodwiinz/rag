"""Versioned wire envelope for durable run events.

Every event served by ``GET /api/v1/agent/runs/{run_id}/events`` uses this
envelope. ``type`` is a plain string on purpose: an older client must parse
a newer server's event, keep its ``seq`` for sequence accounting, and ignore
the payload (forward compatibility). Producers validate payloads through
``run_event_types.validate_payload`` before persistence; this schema is the
read-side contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RUN_EVENT_CONTRACT_VERSION = 1


class AgentRunEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = RUN_EVENT_CONTRACT_VERSION
    event_id: UUID
    run_id: UUID
    conversation_id: UUID | None = None
    thread_id: UUID | None = None
    message_id: UUID | None = None
    seq: int = Field(gt=0)
    timestamp: datetime
    # Deliberately not RunEventType: unknown types must parse (see module doc).
    type: str = Field(max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


__all__ = ["RUN_EVENT_CONTRACT_VERSION", "AgentRunEventEnvelope"]
