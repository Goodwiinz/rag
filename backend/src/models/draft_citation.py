"""
DraftCitation model for linking drafts to citations (Research Assistant - User Story 5)
"""

from sqlalchemy import Column, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship

from .base import BaseModel, GUID


class DraftCitation(BaseModel):
    """
    Draft citation model - links generated drafts to their source citations.

    Each AI-generated draft contains citations to source documents.
    This model tracks which citations were used in which drafts,
    allowing for proper attribution and citation management.

    Used for Research Assistant feature (User Story 5).
    """

    __tablename__ = "draft_citations"

    # Parent relationship
    draft_id = Column(
        GUID(),
        ForeignKey("generated_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Citation reference (links to either a document or a citation)
    citation_index = Column(Integer, nullable=False)  # Order of citation in the draft (1, 2, 3, ...)
    document_id = Column(
        GUID(),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    citation_id = Column(
        GUID(),
        ForeignKey("citations.id", ondelete="SET NULL"),
        nullable=True
    )

    # Citation content (captured at time of draft generation)
    snippet = Column(Text, nullable=True)  # The cited text snippet
    context = Column(Text, nullable=True)  # Context where citation appears in the draft

    # Relationships
    draft = relationship("GeneratedDraft", back_populates="citations")
    document = relationship("Document")
    citation = relationship("Citation")

    def __repr__(self):
        ref = self.citation_id or self.document_id or "unknown"
        return f"<DraftCitation(draft_id={self.draft_id}, index={self.citation_index}, ref={ref})>"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()
        data['draft_id'] = str(self.draft_id)
        data['citation_index'] = self.citation_index
        data['document_id'] = str(self.document_id) if self.document_id else None
        data['citation_id'] = str(self.citation_id) if self.citation_id else None
        data['snippet'] = self.snippet
        data['context'] = self.context
        return data

    def to_frontend_format(self) -> dict:
        """Convert to format suitable for frontend display"""
        return {
            "id": str(self.id),
            "draft_id": str(self.draft_id),
            "citation_index": self.citation_index,
            "document_id": str(self.document_id) if self.document_id else None,
            "citation_id": str(self.citation_id) if self.citation_id else None,
            "snippet": self.snippet,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
