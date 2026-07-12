"""Durable Postgres projection of agent execution jobs (``agent_runs``).

The agent job store is Redis-first (``src/services/agent/job_store.py``,
TTL 1h). That alone is a single point of failure: a Redis failover 404s every
poller and orphans HITL confirm state (audit findings X1/D7). This table is a
write-through projection of every job-status transition so the *status* of a
run survives Redis loss and a future sweeper can reap runs stuck ``running``.

Redis stays authoritative during rollout: writes here are log-and-continue
(never fail the turn), and the poll endpoint only reads this table when Redis
misses. Full result payloads / confirmation details are NOT projected — only
the lifecycle status and error, which is what a failed-over poller needs to
stop spinning.

All access goes through ``src/services/agent/agent_run_service.py`` — do not
query this table directly. Tenant rule: user-facing reads MUST filter
``organization_id`` (and ``user_id``); only the system sweeper may scan
cross-tenant.
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Index, String, Text, text
from sqlalchemy.sql import func

from src.shared.enums import JobStatus

from .base import GUID, Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Rendered into a CHECK constraint so the column domain cannot drift from
# JobStatus without a migration. "error" is intentionally absent: the service
# normalizes the legacy alias to "failed" before any write (see JobStatus).
# Shared with the Alembic migration so the constraint text has one source.
AGENT_RUN_STATUS_CHECK = (
    "status IN (" + ", ".join(f"'{s.value}'" for s in JobStatus) + ")"
)


class AgentRun(Base):
    """One row per agent execution job (job_id from ``POST /agent/execute``)."""

    __tablename__ = "agent_runs"

    # The job id handed to pollers — a server-generated uuid4 string.
    job_id = Column(String(36), primary_key=True)

    # Tenancy — who owns the run. Nullable to mirror User.organization_id
    # (SET NULL FK); reads filter on both, so an org-less row is only visible
    # to an org-less owner.
    organization_id = Column(GUID(), nullable=True)
    user_id = Column(GUID(), nullable=True)

    # Correlation — which conversation the run belongs to (uuid string or the
    # job-id fallback the graph uses for thread-less runs).
    thread_id = Column(String(255), nullable=True)

    # Lifecycle status; values constrained to the JobStatus domain.
    status = Column(String(32), nullable=False)

    # Client idempotency key for a future dedupe of /execute retries.
    # Unique where not null (partial index) — nothing writes it yet.
    idempotency_key = Column(String(255), nullable=True)

    # Lease fields for the next-PR sweeper: a worker claims a stuck run by
    # writing its identity + expiry atomically (see claim_lease in the service).
    lease_owner = Column(String(255), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Client-safe error message for failed/cancelled runs.
    error = Column(Text, nullable=True)

    # Client-side defaults keep ORM-written timestamps timezone-aware on every
    # backend (sqlite tests included); server_default covers raw SQL inserts.
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        # Tenant-scoped listing ("org X's recent runs").
        Index("idx_agent_runs_org_updated", "organization_id", "updated_at"),
        # Sweeper scan: non-terminal runs ordered by staleness.
        Index("idx_agent_runs_status_updated", "status", "updated_at"),
        Index(
            "uq_agent_runs_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
        CheckConstraint(AGENT_RUN_STATUS_CHECK, name="ck_agent_runs_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentRun(job_id={self.job_id!r}, status={self.status!r}, "
            f"org={self.organization_id})>"
        )
