"""Persistent agent memory store (PostgreSQL).

Stores user insights, preferences, and context extracted from conversations.
Durable rows live in the ``agent_memories`` table. Semantic recall is served
by the LangGraph ``AsyncPostgresStore`` (pgvector) in ``memory.py`` — the
former Qdrant client here was orphaned after Qdrant was dropped and has been
removed. See [[project_rag_dropped_qdrant]].
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# agent_memories table definition (mirrors Alembic migration)
# ---------------------------------------------------------------------------

agent_memories = sa.Table(
    "agent_memories",
    sa.MetaData(),
    sa.Column("id", postgresql.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("user_id", postgresql.UUID(), nullable=False),
    sa.Column("organization_id", postgresql.UUID(), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("memory_type", sa.String(50), server_default="insight"),
    sa.Column("embedding_id", sa.String(255)),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("last_accessed_at", sa.DateTime(timezone=True)),
    sa.Column("access_count", sa.Integer(), server_default="0"),
    sa.Column("metadata_", postgresql.JSONB(), server_default="{}"),
    sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false")),
)

# ---------------------------------------------------------------------------
# Service helpers (patchable for testing)
# ---------------------------------------------------------------------------


def _build_insights_llm():
    """Build a lightweight LLM for insight extraction."""
    from src.services.agent.llm_factory import build_lightweight_llm

    return build_lightweight_llm(max_tokens=512)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


async def update_access(db: AsyncSession, memory_id: UUID) -> None:
    """Bump last_accessed_at and access_count for a memory."""
    stmt = (
        sa.update(agent_memories)
        .where(agent_memories.c.id == memory_id)
        .values(
            last_accessed_at=datetime.now(timezone.utc),
            access_count=agent_memories.c.access_count + 1,
        )
    )
    await db.execute(stmt)
    await db.commit()


async def cleanup_stale_memories(db: AsyncSession, days: int = 90) -> int:
    """Soft-delete memories not accessed in the given number of days.

    Returns the count of deleted memories.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        sa.update(agent_memories)
        .where(
            sa.or_(
                agent_memories.c.last_accessed_at < cutoff,
                sa.and_(
                    agent_memories.c.last_accessed_at.is_(None),
                    agent_memories.c.created_at < cutoff,
                ),
            ),
            agent_memories.c.is_deleted == False,  # noqa: E712
        )
        .values(is_deleted=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def extract_insights(
    messages: list[dict],
    config: dict,
) -> list[str]:
    """Extract key insights from conversation messages using a lightweight LLM.

    Returns a list of insight strings, or empty list on failure.
    """
    if not messages:
        return []

    try:
        llm = _build_insights_llm()
        from langchain_core.messages import SystemMessage, HumanMessage

        conversation = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in messages
        )

        result = await llm.ainvoke([
            SystemMessage(content=(
                "Extract key insights from this conversation that would be useful to remember "
                "for future interactions. Focus on:\n"
                "- User preferences and working style\n"
                "- Research interests and topics\n"
                "- Important context about their work\n\n"
                "Return each insight as a numbered line (e.g., '1. User prefers concise summaries').\n"
                "Return only the insights, nothing else."
            )),
            HumanMessage(content=conversation),
        ])

        # Parse numbered lines into a list
        raw = result.content if isinstance(result.content, str) else str(result.content)
        insights = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip leading number and punctuation (e.g., "1. " or "- ")
            cleaned = line.lstrip("0123456789.-) ").strip()
            if cleaned:
                insights.append(cleaned)

        return insights

    except Exception as e:
        logger.error("Failed to extract insights: %s", e)
        return []
