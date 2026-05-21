"""SQLAlchemy ORM model for the ``kg_sync_runs`` audit table.

Mirrors Alembic migration ``w1b2c3d4e5f6_add_kg_sync_runs``. The ``metadata``
JSONB column is mapped as ``run_metadata`` to avoid collision with
``Base.metadata`` on the declarative base.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class KGSyncRun(Base):
    __tablename__ = "kg_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','success','failed')",
            name="kg_sync_runs_status_check",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    orphan_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    drift_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    fixed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    run_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
