"""
ProjectNote model for research project notes (Research Assistant - User Story 4)
"""

from sqlalchemy import Column, String, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import BaseModel, GUID


class ProjectNote(BaseModel):
    """
    Project note model - markdown notes within research projects.

    Users can create markdown notes within their research projects to document
    insights, observations, and analysis. Notes can be linked to specific
    documents and organized with tags.

    Used for Research Assistant feature (User Story 4).
    """

    __tablename__ = "project_notes"

    # Parent relationships
    project_id = Column(
        GUID(),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Note content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)  # Markdown content

    # Organization and linking
    linked_document_ids = Column(JSONB, nullable=False, default=list, server_default="[]")  # Array of document UUIDs
    tags = Column(JSONB, nullable=False, default=list, server_default="[]")  # Array of tag strings

    # UI settings
    is_pinned = Column(Boolean, nullable=False, default=False, server_default="false", index=True)

    # Relationships
    project = relationship("Collection", backref="notes")
    user = relationship("User", backref="project_notes")

    def __repr__(self):
        return f"<ProjectNote(title={self.title}, project_id={self.project_id}, user_id={self.user_id})>"

    @property
    def content_preview(self) -> str:
        """Get a preview of the note content"""
        if not self.content:
            return ""
        if len(self.content) <= 200:
            return self.content
        return self.content[:200] + "..."

    @property
    def linked_document_count(self) -> int:
        """Get number of linked documents"""
        if not self.linked_document_ids:
            return 0
        return len(self.linked_document_ids)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()
        data['project_id'] = str(self.project_id)
        data['user_id'] = str(self.user_id)
        data['title'] = self.title
        data['content'] = self.content
        data['content_preview'] = self.content_preview
        data['linked_document_ids'] = self.linked_document_ids
        data['linked_document_count'] = self.linked_document_count
        data['tags'] = self.tags
        data['is_pinned'] = self.is_pinned
        return data

    def to_frontend_format(self) -> dict:
        """Convert to format suitable for frontend display"""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "user_id": str(self.user_id),
            "title": self.title,
            "content": self.content,
            "content_preview": self.content_preview,
            "linked_document_ids": [str(doc_id) for doc_id in (self.linked_document_ids or [])],
            "linked_document_count": self.linked_document_count,
            "tags": self.tags or [],
            "is_pinned": self.is_pinned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
