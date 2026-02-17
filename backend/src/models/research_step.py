"""
ResearchStep model for individual steps within a research run.
"""

from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class StepType(PyEnum):
    """Types of research steps."""

    SEARCH = "search"
    SCREEN = "screen"
    EXTRACT = "extract"
    SYNTHESIZE = "synthesize"
    VERIFY = "verify"
    EXPORT = "export"


class ExecutionMode(PyEnum):
    """Execution mode for a research step."""

    DETERMINISTIC = "deterministic"
    EXPLORATORY = "exploratory"


class ResearchStep(BaseModel):
    """A single step executed within a research run."""

    __tablename__ = "research_steps"

    run_id = Column(
        GUID(), ForeignKey("research_runs.id"), nullable=False
    )
    step_index = Column(Integer, nullable=False)
    step_type = Column(String(50), nullable=False)
    mode = Column(String(50), nullable=False, default="deterministic")
    inputs_hash = Column(String(64), nullable=True)
    outputs_hash = Column(String(64), nullable=True)
    full_prompt = Column(Text, nullable=True)
    model_id = Column(String(100), nullable=True)
    model_version = Column(String(100), nullable=True)
    temperature = Column(Float, nullable=False, default=0.0)
    seed = Column(Integer, nullable=True)
    output = Column(JSONB, nullable=True)
    quality_marks = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    token_count = Column(Integer, nullable=False, default=0)

    def __init__(self, **kwargs):
        if "mode" not in kwargs:
            kwargs["mode"] = "deterministic"
        if "temperature" not in kwargs:
            kwargs["temperature"] = 0.0
        if "token_count" not in kwargs:
            kwargs["token_count"] = 0
        super().__init__(**kwargs)

    # Relationships
    run = relationship("ResearchRun", back_populates="steps")
    evidence = relationship(
        "ResearchEvidence",
        back_populates="step",
        cascade="all, delete-orphan",
    )
