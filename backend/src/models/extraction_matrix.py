"""ExtractionMatrix and ExtractionCell models for Literature Review Matrix."""

from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class ExtractionMatrix(BaseModel):
    """A structured extraction matrix for comparing documents in a project."""

    __tablename__ = "extraction_matrices"

    project_id = Column(
        GUID(),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    columns = Column(JSONB, nullable=False, server_default="[]")

    project = relationship("Collection", backref="extraction_matrices")
    cells = relationship(
        "ExtractionCell", back_populates="matrix", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ExtractionMatrix(id={self.id}, name={self.name})>"


class ExtractionCell(BaseModel):
    """A single extracted value in the matrix grid."""

    __tablename__ = "extraction_cells"
    __table_args__ = (
        UniqueConstraint(
            "matrix_id", "document_id", "column_name",
            name="uq_cell_matrix_doc_col",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_cell_confidence_range",
        ),
    )

    matrix_id = Column(
        GUID(),
        ForeignKey("extraction_matrices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        GUID(),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name = Column(String(100), nullable=False)
    value = Column(Text, nullable=True)
    citation_snippet = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    matrix = relationship("ExtractionMatrix", back_populates="cells")
    document = relationship("Document")

    def __repr__(self):
        return f"<ExtractionCell(matrix={self.matrix_id}, col={self.column_name})>"
