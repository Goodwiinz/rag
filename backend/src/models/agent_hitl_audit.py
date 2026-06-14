"""Durable audit record for agent human-in-the-loop (HITL) decisions.

Every time a destructive agent tool (ingest, create_note, create_draft,
create_project, …) is approved or rejected at the ``interrupt_node`` gate, one
immutable row is written here. This is the durable complement to the
``hitl_interrupt_raised`` / ``hitl_decision`` structlog events: logs answer
"what happened recently" via the log pipeline; this table answers "who approved
which destructive action, when" for compliance/audit queries that outlive log
retention.

Args are stored already PII-scrubbed (``_scrub_tool_args`` in ``_nodes_tools``)
— free-text bodies are dropped, remaining strings PII-redacted and capped. Never
write raw tool args here.
"""

import uuid

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from .base import Base


class AgentHitlAudit(Base):
    """One row per destructive-tool approve/reject decision."""

    __tablename__ = "agent_hitl_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Actor — who made the decision. No standalone index: the composite
    # (organization_id, created_at) / (user_id, created_at) indexes below
    # cover equality lookups via their leftmost column.
    user_id = Column(UUID(as_uuid=True), nullable=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True)

    # Correlation — which conversation turn.
    thread_id = Column(String(255), nullable=True, index=True)

    # What was decided.
    tool_names = Column(JSON, nullable=False)  # list[str] of destructive tools
    tool_args = Column(JSON, nullable=True)  # PII-scrubbed args, never raw bodies
    decision = Column(String(20), nullable=False, index=True)  # "approve" | "reject"

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Tenant-scoped and per-user audit lookups ("everything org X approved").
    __table_args__ = (
        Index("idx_agent_hitl_audit_org_created", "organization_id", "created_at"),
        Index("idx_agent_hitl_audit_user_created", "user_id", "created_at"),
        # Constrain decision to its two-value domain so a typo/ad-hoc insert
        # can't poison the audit trail or break exact-match audit queries.
        CheckConstraint(
            "decision IN ('approve', 'reject')",
            name="ck_agent_hitl_audit_decision",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentHitlAudit(decision={self.decision!r}, "
            f"tools={self.tool_names!r}, org={self.organization_id})>"
        )
