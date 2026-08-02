"""Append-only ordered event history for durable agent runs.

One row per fact about a run (``run.created``, ``assistant.delta``,
``tool.started``, terminal events, ...). PostgreSQL is authoritative: replay
and reconnect read this table; Redis only wakes subscribers. Rows are
immutable — ``services/agent/run_event_store.py`` owns every write, allocates
``seq`` server-side, and never updates or deletes. ``(run_id, seq)`` is the
ordering contract clients resume from (SSE ``id`` == ``seq``).

Payloads are bounded and display-safe: IDs, summaries, status, capped text
fragments — never full tool results, prompts, or secrets (those stay in their
canonical stores). See docs/plans/2026-07-20-hermes-event-runtime-design.md.
"""

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from .base import GUID, BaseModel

# Terminal event types, spelled as SQL so the partial unique index below and
# the Alembic revision (f2a3b4c5d6e7) share one literal. The vocabulary itself
# lives in services/agent/run_event_types.TERMINAL_RUN_EVENTS — models must not
# import services, so a contract test asserts the two never drift.
_TERMINAL_EVENT_PREDICATE = (
    "event_type IN ('run.completed', 'run.failed', 'run.cancelled')"
)


class AgentRunEvent(BaseModel):
    """One immutable ordered fact about an agent run."""

    __tablename__ = "agent_run_events"

    run_id = Column(
        String(36),
        ForeignKey("agent_runs.job_id", ondelete="CASCADE"),
        nullable=False,
    )
    # Tenancy. Nullable, mirroring ``agent_runs.organization_id`` (org-less
    # users exist), so reads MUST compare null-safely: ``== None`` compiles to
    # ``IS NULL`` and an org-less caller sees only org-less rows. Never part of
    # the (run_id, seq) unique key — NULLs are distinct in PostgreSQL unique
    # constraints, so an org in the key would permit duplicate seqs.
    organization_id = Column(GUID(), nullable=True)
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
        # Tenant-scoped replay read (organization_id + run_id).
        Index("idx_agent_run_events_org_run", "organization_id", "run_id"),
        # One terminal event per run, ever — enforced by the database, not by
        # the append path's read-then-write check (which alone races).
        Index(
            "uq_agent_run_events_one_terminal",
            "run_id",
            unique=True,
            postgresql_where=text(_TERMINAL_EVENT_PREDICATE),
            sqlite_where=text(_TERMINAL_EVENT_PREDICATE),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentRunEvent(run_id={self.run_id!r}, seq={self.seq}, "
            f"type={self.event_type!r})>"
        )
