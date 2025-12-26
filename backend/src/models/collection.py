"""
Collection model for Terminal Observatory document organization
"""

from sqlalchemy import Column, String, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship

from .base import BaseModel, GUID


class Collection(BaseModel):
    """
    Collection model - groups of documents within a workspace.

    Collections allow users to organize documents by topic, project,
    or any other logical grouping within a workspace.
    """

    __tablename__ = "collections"

    # Parent relationship
    workspace_id = Column(GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Basic information
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Settings
    color = Column(String(7), nullable=True)  # Hex color for UI
    icon = Column(String(50), nullable=True)  # Icon name for UI

    # Relationships
    workspace = relationship("Workspace", back_populates="collections")
    documents = relationship("CollectionDocument", back_populates="collection", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Collection(name={self.name}, workspace_id={self.workspace_id})>"

    @property
    def document_count(self) -> int:
        """Get number of documents in collection"""
        return len(self.documents) if self.documents else 0

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()
        data['document_count'] = self.document_count
        return data


class CollectionDocument(BaseModel):
    """
    Association table for Collection-Document many-to-many relationship.

    A document can belong to multiple collections, and each collection
    can contain multiple documents.
    """

    __tablename__ = "collection_documents"

    collection_id = Column(GUID(), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)

    # Optional ordering within collection
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    collection = relationship("Collection", back_populates="documents")
    document = relationship("Document")

    def __repr__(self):
        return f"<CollectionDocument(collection_id={self.collection_id}, document_id={self.document_id})>"

    class Meta:
        unique_together = [('collection_id', 'document_id')]
