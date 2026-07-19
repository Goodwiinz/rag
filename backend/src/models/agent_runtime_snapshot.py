"""Durable frozen tool and project-skill metadata for an agent run."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class AgentRuntimeSnapshot(BaseModel):
    """Transport-neutral, immutable input snapshot for streaming and queued runs."""

    __tablename__ = "agent_runtime_snapshots"
    __table_args__ = (
        Index(
            "idx_agent_runtime_snapshots_project_created", "project_id", "created_at"
        ),
        Index("idx_agent_runtime_snapshots_expires_at", "expires_at"),
    )

    project_id = Column(
        GUID(),
        ForeignKey("collections.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    thread_id = Column(
        GUID(), ForeignKey("threads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id = Column(
        String(36),
        ForeignKey("agent_runs.job_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_registry_hash = Column(String(64), nullable=False)
    tool_registry_version = Column(String(64), nullable=False)
    tool_metadata = Column(JSONB, nullable=False, default=dict, server_default="{}")
    skill_catalog = Column(JSONB, nullable=False, default=list, server_default="[]")
    loaded_skill_versions = Column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    project = relationship("Collection", foreign_keys=[project_id])
    user = relationship("User", foreign_keys=[user_id])
    thread = relationship("Thread", foreign_keys=[thread_id])
    agent_run = relationship("AgentRun", foreign_keys=[job_id])
