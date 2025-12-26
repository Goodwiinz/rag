"""
Citation model for Terminal Observatory RAG references
"""

from sqlalchemy import Column, String, ForeignKey, Text, Integer, Float
from sqlalchemy.orm import relationship

from .base import BaseModel, GUID


class Citation(BaseModel):
    """
    Citation model - links document chunks to generated messages.

    When the RAG system generates a response using retrieved context,
    each source chunk is recorded as a citation for transparency and
    verification.
    """

    __tablename__ = "citations"

    # Parent relationships
    message_id = Column(GUID(), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)

    # Chunk information
    chunk_index = Column(Integer, nullable=True)  # Index of the vector chunk
    chunk_id = Column(String(255), nullable=True)  # Qdrant chunk ID

    # Content
    snippet = Column(Text, nullable=True)  # The text snippet used
    page_number = Column(Integer, nullable=True)  # Page number if applicable

    # Relevance scores
    score = Column(Float, nullable=True)  # Retrieval score (cosine similarity or RRF)
    rerank_score = Column(Float, nullable=True)  # Reranking score (e.g., Cohere)

    # Highlight positions (for UI highlighting)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)

    # Relationships
    message = relationship("ChatMessage", back_populates="citations")
    document = relationship("Document")

    def __repr__(self):
        return f"<Citation(message_id={self.message_id}, document_id={self.document_id}, score={self.score})>"

    @property
    def snippet_preview(self) -> str:
        """Get a preview of the snippet"""
        if not self.snippet:
            return ""
        if len(self.snippet) <= 100:
            return self.snippet
        return self.snippet[:100] + "..."

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()
        data['snippet_preview'] = self.snippet_preview
        return data

    def to_frontend_format(self) -> dict:
        """Convert to format suitable for frontend display"""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "snippet": self.snippet,
            "snippet_preview": self.snippet_preview,
            "page_number": self.page_number,
            "score": self.score,
            "chunk_index": self.chunk_index
        }
