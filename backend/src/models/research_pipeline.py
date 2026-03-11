"""ResearchPipeline model for step-by-step research workflow tracking."""

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class ResearchPipeline(BaseModel):
    """Tracks pipeline state for a research project's wizard workflow."""

    __tablename__ = "research_pipelines"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_pipeline_project"),
    )

    project_id = Column(
        GUID(),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_step = Column(Integer, nullable=False, server_default="0")
    completed_steps = Column(ARRAY(Integer), nullable=False, server_default="{}")
    skipped_steps = Column(ARRAY(Integer), nullable=False, server_default="{}")
    step_data = Column(JSONB, nullable=False, server_default="{}")
    invalidated_steps = Column(ARRAY(Integer), nullable=False, server_default="{}")

    project = relationship("Collection", backref="research_pipeline")

    def __repr__(self):
        return f"<ResearchPipeline(id={self.id}, project={self.project_id}, step={self.current_step})>"
