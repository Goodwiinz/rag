"""
ResearchEvidence model for claims extracted and grounded against sources.
"""

from enum import Enum as PyEnum

from sqlalchemy import Column, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class GroundingStatus(PyEnum):
    """Status of evidence grounding verification."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class ResearchEvidence(BaseModel):
    """A claim or piece of evidence linked to a step and source."""

    __tablename__ = "research_evidence"

    step_id = Column(
        GUID(), ForeignKey("research_steps.id"), nullable=False
    )
    source_id = Column(
        GUID(), ForeignKey("research_sources.id"), nullable=False
    )
    claim_text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    grounding_status = Column(
        String(50), nullable=False, default="unverified"
    )
    page_reference = Column(String(100), nullable=True)

    def __init__(self, **kwargs):
        if "grounding_status" not in kwargs:
            kwargs["grounding_status"] = "unverified"
        super().__init__(**kwargs)

    # Relationships
    step = relationship("ResearchStep", back_populates="evidence")
    source = relationship("ResearchSource", back_populates="evidence")
