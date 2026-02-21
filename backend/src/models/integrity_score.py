"""IntegrityScore model for AI authorship detection."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class IntegrityScore(BaseModel):
    __tablename__ = "integrity_scores"

    document_id = Column(
        GUID(),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_probability = Column(Float, nullable=False)
    human_probability = Column(Float, nullable=False)
    method = Column(String(100), nullable=False, default="roberta-base-openai-detector")
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    segment_scores = Column(JSONB, nullable=False, server_default="[]")

    document = relationship("Document", backref="integrity_scores")

    def __repr__(self):
        return f"<IntegrityScore(doc={self.document_id}, ai={self.ai_probability})>"
