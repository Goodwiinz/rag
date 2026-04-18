"""
Search analytics model for tracking query performance and user behavior.
"""

import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import GUID, BaseModel


class SearchAnalyticsEvent(BaseModel):
    """Persisted search analytics for tracking search quality over time."""

    __tablename__ = "search_analytics"

    search_id = Column(String(64), nullable=False, index=True)
    query = Column(Text, nullable=False)
    organization_id = Column(GUID(), nullable=False, index=True)
    user_id = Column(GUID(), nullable=True, index=True)
    search_type = Column(String(32), nullable=True)  # hybrid, semantic, keyword, graph
    result_count = Column(Integer, nullable=False, default=0)
    search_time_ms = Column(Float, nullable=False, default=0.0)
    filters = Column(JSONB, nullable=True)
    # Clickthrough tracking (updated async when user clicks a result)
    clicked_document_id = Column(GUID(), nullable=True)
    clicked_position = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<SearchAnalyticsEvent query='{self.query[:30]}' results={self.result_count}>"
