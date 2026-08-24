"""Persisted search-quality feedback.

R6-L5 / R2-M16: record_user_feedback used to answer "Feedback recorded
successfully" while only writing a log line, and analytics returned
hardcoded mock numbers. This table is the real store.
"""

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class SearchFeedback(Base):
    """A user's 1-5 rating of a single search interaction."""

    __tablename__ = "search_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    query_id = Column(String(128), nullable=False)
    query_text = Column(Text, nullable=True)
    # R6-F3d: analytics accepts a search_type filter; without this column the
    # filter was silently ignored and every row was counted.
    search_type = Column(String(32), nullable=True, index=True)
    rating = Column(Integer, nullable=False)  # 1-5
    feedback_text = Column(Text, nullable=True)
    document_id = Column(String(36), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_search_feedback_org_created", "organization_id", "created_at"),
    )
