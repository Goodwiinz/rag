"""
ProjectThread model for linking research projects to chat threads.

This model enables the integration between Research Projects (Collection)
and Chat systems (Thread/Conversation) by tracking which threads are
associated with which projects.
"""

from sqlalchemy import Column, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from datetime import datetime

from .base import BaseModel, GUID


class ProjectThreadLinkType(PyEnum):
    """Type of link between project and thread"""
    AUTO = "auto"  # Automatically created when starting chat from project
    MANUAL = "manual"  # Manually linked by user
    FROM_CHAT = "from_chat"  # Linked from chat interface


class ProjectThread(BaseModel):
    """
    Junction table linking research projects to chat threads.

    Enables users to:
    - Start a chat from a project with project documents as RAG context
    - Link existing threads to projects for organization
    - View project-related conversations in one place
    - Save chat insights back to project notes
    """

    __tablename__ = "project_threads"

    # Foreign keys
    project_id = Column(
        GUID(),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id = Column(
        GUID(),
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Link metadata
    link_type = Column(
        String(50),
        nullable=False,
        default=ProjectThreadLinkType.MANUAL.value,
    )
    linked_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    linked_by_id = Column(
        GUID(),
        ForeignKey("users.id"),
        nullable=True,
    )
    context_note = Column(
        Text,
        nullable=True,
        comment="Optional note about why this thread was linked to this project",
    )

    # Relationships
    project = relationship("Collection", backref="project_threads")
    thread = relationship("Thread", backref="project_threads")
    linked_by = relationship("User", foreign_keys=[linked_by_id])

    def __repr__(self):
        return f"<ProjectThread(project_id={self.project_id}, thread_id={self.thread_id}, link_type={self.link_type})>"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()
        data["link_type"] = self.link_type
        data["linked_at"] = self.linked_at.isoformat() if self.linked_at else None
        return data
