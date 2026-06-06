"""Project-memory recall for the agent.

A thin, defensive read path used when a chat turn is bound to a project: it
loads the project's saved memories so they can be injected into the agent
system prompt. Kept separate from the CRUD endpoints so the agent hot path has
no dependency on the API layer.
"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Cap injected memories so a runaway project can never bloat the prompt.
MAX_AGENT_MEMORIES = 25


async def load_project_memories(
    db: AsyncSession,
    project_id: str,
    limit: int = MAX_AGENT_MEMORIES,
) -> List[str]:
    """Return up to ``limit`` memory strings for a project (newest first).

    Best-effort: never raises. A failure here must not break a chat turn, so
    any error returns an empty list.
    """
    if not db or not project_id:
        return []
    try:
        from src.models import ProjectMemory

        query = (
            select(ProjectMemory.content)
            .where(ProjectMemory.project_id == project_id)
            .order_by(ProjectMemory.created_at.desc())
            .limit(max(1, min(limit, MAX_AGENT_MEMORIES)))
        )
        result = await db.execute(query)
        rows = result.scalars().all()
        return [c.strip() for c in rows if c and c.strip()]
    except Exception as exc:  # noqa: BLE001 - recall is best-effort
        logger.warning("Project-memory recall failed: %s", exc)
        return []
