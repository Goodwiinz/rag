"""
ProjectMemory model — project-scoped persistent memory.

Short, durable facts the user saves for a research project (e.g. "always cite
in APA", "focus on post-2020 work", "the client is a hospital"). Unlike
``ProjectNote`` (long markdown the user reads), memories are terse instructions
the agent honors, and every thread bound to the project recalls them — they are
injected into the agent system prompt.
"""

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class ProjectMemory(BaseModel):
    """A single durable fact attached to a project."""

    __tablename__ = "project_memories"

    project_id = Column(
        GUID(),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    content = Column(Text, nullable=False)
    # How the memory was created: "manual" (UI / API) or "remember" (chat command).
    source = Column(String(32), nullable=False, default="manual", server_default="manual")

    project = relationship("Collection", backref="memories")
    user = relationship("User", backref="project_memories")

    def __repr__(self):
        return f"<ProjectMemory(project_id={self.project_id}, content={self.content[:40]!r})>"

    def to_frontend_format(self) -> dict:
        """Convert to a frontend-friendly dict."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "user_id": str(self.user_id),
            "content": self.content,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
