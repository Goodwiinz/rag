"""
ResearchBlueprint model for defining research workflow templates.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class ResearchBlueprint(BaseModel):
    """A blueprint defining the steps and parameters for a research run."""

    __tablename__ = "research_blueprints"

    project_id = Column(GUID(), ForeignKey("research_projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    template_source = Column(String(100), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    steps = Column(JSONB, nullable=True, default=list)
    parameters = Column(JSONB, nullable=True, default=dict)
    is_immutable = Column(Boolean, nullable=False, default=False)

    def __init__(self, **kwargs):
        if "version" not in kwargs:
            kwargs["version"] = 1
        if "is_immutable" not in kwargs:
            kwargs["is_immutable"] = False
        if "steps" not in kwargs:
            kwargs["steps"] = []
        if "parameters" not in kwargs:
            kwargs["parameters"] = {}
        super().__init__(**kwargs)

    # Relationships
    project = relationship("ResearchProject", back_populates="blueprints")
    runs = relationship(
        "ResearchRun",
        back_populates="blueprint",
        cascade="all, delete-orphan",
    )
