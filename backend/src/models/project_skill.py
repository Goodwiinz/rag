"""Immutable, project-scoped instruction-only skills and approval history."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel

SKILL_ACTIONS = ("activate", "archive", "restore", "rollback")
SKILL_CHANGE_STATUSES = ("pending", "approved", "rejected", "superseded")
SKILL_SCAN_STATES = ("pending", "passed", "blocked", "error")


class ProjectSkill(BaseModel):
    """A stable project-local skill identity with a movable active-version pointer."""

    __tablename__ = "project_skills"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "normalized_name",
            name="uq_project_skills_project_normalized_name",
        ),
        Index("idx_project_skills_project_archived", "project_id", "is_archived"),
    )

    project_id = Column(
        GUID(),
        ForeignKey("collections.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    normalized_name = Column(String(128), nullable=False)
    active_version_id = Column(
        GUID(),
        ForeignKey(
            "project_skill_versions.id",
            name="fk_project_skills_active_version",
            use_alter=True,
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    is_archived = Column(Boolean, nullable=False, default=False, server_default="false")
    created_by_id = Column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    project = relationship("Collection", foreign_keys=[project_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    versions = relationship(
        "ProjectSkillVersion",
        back_populates="skill",
        foreign_keys="ProjectSkillVersion.skill_id",
    )
    active_version = relationship(
        "ProjectSkillVersion", foreign_keys=[active_version_id], post_update=True
    )
    change_requests = relationship(
        "ProjectSkillChangeRequest",
        back_populates="skill",
        foreign_keys="ProjectSkillChangeRequest.skill_id",
    )


class ProjectSkillVersion(BaseModel):
    """An append-only canonical ``SKILL.md`` document revision."""

    __tablename__ = "project_skill_versions"
    __table_args__ = (
        UniqueConstraint(
            "skill_id", "version", name="uq_project_skill_versions_skill_version"
        ),
        CheckConstraint(
            "scan_state IN ('pending', 'passed', 'blocked', 'error')",
            name="ck_project_skill_versions_scan_state",
        ),
        CheckConstraint(
            "version > 0", name="ck_project_skill_versions_positive_version"
        ),
    )

    skill_id = Column(
        GUID(),
        ForeignKey("project_skills.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False)
    instructions = Column(Text, nullable=False)
    parsed_name = Column(String(128), nullable=False)
    description = Column(String(240), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    scan_state = Column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    scan_findings = Column(JSONB, nullable=False, default=list, server_default="[]")
    scanner_version = Column(String(64), nullable=False)
    author_id = Column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    skill = relationship(
        "ProjectSkill", back_populates="versions", foreign_keys=[skill_id]
    )
    author = relationship("User", foreign_keys=[author_id])


class ProjectSkillChangeRequest(BaseModel):
    """An audited, staged request to alter one skill's active state."""

    __tablename__ = "project_skill_change_requests"
    __table_args__ = (
        CheckConstraint(
            "action IN ('activate', 'archive', 'restore', 'rollback')",
            name="ck_project_skill_change_requests_action",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_project_skill_change_requests_status",
        ),
        Index("idx_project_skill_change_requests_skill_status", "skill_id", "status"),
    )

    skill_id = Column(
        GUID(),
        ForeignKey("project_skills.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action = Column(String(16), nullable=False)
    proposed_version_id = Column(
        GUID(),
        ForeignKey("project_skill_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    prior_version_id = Column(
        GUID(),
        ForeignKey("project_skill_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    expected_active_version_id = Column(
        GUID(),
        ForeignKey("project_skill_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    requester_id = Column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reviewer_id = Column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status = Column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    warning_acknowledged = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    audit_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    skill = relationship(
        "ProjectSkill", back_populates="change_requests", foreign_keys=[skill_id]
    )
    proposed_version = relationship(
        "ProjectSkillVersion", foreign_keys=[proposed_version_id]
    )
    prior_version = relationship("ProjectSkillVersion", foreign_keys=[prior_version_id])
    expected_active_version = relationship(
        "ProjectSkillVersion", foreign_keys=[expected_active_version_id]
    )
    requester = relationship("User", foreign_keys=[requester_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
