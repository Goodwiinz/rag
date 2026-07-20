"""Append-only ordered event history for durable agent runs.

One row per fact about a run (``run.created``, ``assistant.delta``,
``tool.started``, terminal events, ...). PostgreSQL is authoritative: replay
and reconnect read this table; Redis only wakes subscribers. Rows are
immutable — the service layer (``run_event_store``, next PR) appends under the
run-row lock and never updates or deletes. ``(run_id, seq)`` is the ordering
contract clients resume from (SSE ``id`` == ``seq``).

Payloads are bounded and display-safe: IDs, summaries, status, capped text
fragments — never full tool results, prompts, or secrets (those stay in their
canonical stores). See docs/plans/2026-07-20-hermes-event-runtime-design.md.
"""

from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from .base import BaseModel


class AgentRunEvent(BaseModel):
    """One immutable ordered fact about an agent run."""

    __tablename__ = "agent_run_events"

    run_id = Column(
        String(36),
        ForeignKey("agent_runs.job_id", ondelete="CASCADE"),
        nullable=False,
    )
    # Server-allocated, strictly monotonic per run (1-based). Clients never
    # supply it; the store computes it under the run-row lock.
    seq = Column(Integer, nullable=False)
    # Versioned public vocabulary (e.g. "assistant.delta"), never raw
    # LangGraph callback names.
    event_type = Column(String(64), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict, server_default="{}")

    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_agent_run_events_run_seq"),
        Index("idx_agent_run_events_run_seq", "run_id", "seq"),
        # Operational retention scans ("delete events older than N days").
        Index("idx_agent_run_events_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentRunEvent(run_id={self.run_id!r}, seq={self.seq}, "
            f"type={self.event_type!r})>"
        )
