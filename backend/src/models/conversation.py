"""
Conversation model for Terminal Observatory thread-centric chat schema
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import BaseModel, GUID


class Conversation(BaseModel):
    """
    Conversation model - high-level container for related threads.

    A conversation represents a project or topic area (e.g., "Q3 Financial Analysis",
    "Project Typhoon") that contains multiple threads of inquiry.
    """

    __tablename__ = "conversations"

    # Basic information
    workspace_id = Column(GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # State
    is_archived = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)

    # Metadata
    last_activity_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Creator tracking
    created_by_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="conversations")
    created_by = relationship("User", foreign_keys=[created_by_id])
    threads = relationship("Thread", back_populates="conversation", cascade="all, delete-orphan", order_by="Thread.created_at.desc()")

    def __repr__(self):
        return f"<Conversation(title={self.title}, workspace_id={self.workspace_id})>"

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity_at = datetime.utcnow()

    @property
    def thread_count(self) -> int:
        """Get number of threads"""
        return len(self.threads) if self.threads else 0

    @property
    def active_thread_count(self) -> int:
        """Get number of active threads"""
        if not self.threads:
            return 0
        from .thread import ThreadStatus
        return sum(1 for t in self.threads if t.status == ThreadStatus.ACTIVE)

    def to_dict(self, include_threads: bool = False) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()
        data['thread_count'] = self.thread_count
        data['active_thread_count'] = self.active_thread_count

        if include_threads and self.threads:
            data['threads'] = [t.to_dict() for t in self.threads[:10]]  # Limit to first 10

        return data

    def archive(self):
        """Archive the conversation"""
        self.is_archived = True

    def unarchive(self):
        """Unarchive the conversation"""
        self.is_archived = False
