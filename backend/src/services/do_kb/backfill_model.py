"""ORM model for do_kb_backfill_progress.

Kept inside services/do_kb to avoid bloating the global models registry —
this is operational state, not a domain entity.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from src.models.base import GUID, Base


class DOKBBackfillProgress(Base):
    """One row per organization tracking backfill cursor + state."""

    __tablename__ = "do_kb_backfill_progress"

    organization_id = Column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_document_id = Column(GUID(), nullable=True)
    completed_count = Column(Integer, nullable=False, default=0, server_default="0")
    failed_count = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
