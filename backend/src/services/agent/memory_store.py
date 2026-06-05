"""Persistent agent memory store with PostgreSQL + Qdrant semantic retrieval.

Stores user insights, preferences, and context extracted from conversations.
PostgreSQL provides durability; Qdrant provides semantic search.
Gracefully degrades if Qdrant or embeddings are unavailable.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings

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

# Qdrant collection name for agent memories
QDRANT_COLLECTION = "agent_memories"
EMBEDDING_DIMENSION = 384  # sentence-transformers default


# ---------------------------------------------------------------------------
# Service helpers (patchable for testing)
# ---------------------------------------------------------------------------


def _get_embedding_service():
    """Get or create the embedding service. Returns None if unavailable."""
    try:
        from src.services.embedding.embedding_service import EmbeddingService
        return EmbeddingService(lazy=True)
    except Exception as e:
        logger.warning("Embedding service unavailable: %s", e)
        return None


_QDRANT_CLIENT = None


def _get_qdrant_client():
    """Get a Qdrant client. Returns None if unavailable.

    Cached at module level to avoid HTTP-client setup on every call.
    """
    global _QDRANT_CLIENT
    if _QDRANT_CLIENT is not None:
        return _QDRANT_CLIENT
    try:
        from qdrant_client import QdrantClient
        settings = get_settings()
        url = getattr(settings, "QDRANT_URL", None) or "http://localhost:6333"
        api_key = getattr(settings, "QDRANT_API_KEY", None)
        client = QdrantClient(url=url, api_key=api_key, timeout=10)
        _QDRANT_CLIENT = client
        return client
    except Exception as e:
        logger.warning("Qdrant client unavailable: %s", e)
        return None


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
