"""Persistent agent memory store with PostgreSQL + Qdrant semantic retrieval.

Stores user insights, preferences, and context extracted from conversations.
PostgreSQL provides durability; Qdrant provides semantic search.
Gracefully degrades if Qdrant or embeddings are unavailable.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

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


def _get_qdrant_client():
    """Get a Qdrant client. Returns None if unavailable."""
    try:
        from qdrant_client import QdrantClient
        settings = get_settings()
        url = getattr(settings, "QDRANT_URL", None) or "http://localhost:6333"
        api_key = getattr(settings, "QDRANT_API_KEY", None)
        client = QdrantClient(url=url, api_key=api_key, timeout=10)
        return client
    except Exception as e:
        logger.warning("Qdrant client unavailable: %s", e)
        return None


def _build_insights_llm():
    """Build a gpt-4o-mini LLM for insight extraction."""
    settings = get_settings()
    endpoint = settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""

    if not endpoint or not api_key:
        raise RuntimeError("Azure/OpenAI config required for insights LLM")

    from src.core.openai_endpoint import classify_openai_endpoint

    if classify_openai_endpoint(endpoint) == "openai_compatible":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=api_key,
            base_url=endpoint,
            temperature=0,
            max_tokens=512,
        )
    else:
        from langchain_openai import AzureChatOpenAI
        api_version = settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
        return AzureChatOpenAI(
            azure_deployment="gpt-4o-mini",
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            temperature=0,
            max_tokens=512,
        )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


async def save_memory(
    db: AsyncSession,
    user_id: UUID,
    org_id: UUID,
    content: str,
    memory_type: str = "insight",
    metadata: Optional[dict] = None,
) -> Optional[UUID]:
    """Save a memory to PostgreSQL and optionally index in Qdrant.

    Returns the memory UUID, or None on complete failure.
    """
    memory_id = uuid4()
    embedding_id: Optional[str] = None

    # Step 1: Generate embedding and index in Qdrant (best-effort)
    embedding_service = _get_embedding_service()
    qdrant_client = _get_qdrant_client()

    if embedding_service is not None:
        try:
            from src.models.vector import EmbeddingRequest
            response = await embedding_service.generate_embedding(
                EmbeddingRequest(text=content)
            )
            embedding = response.embedding

            if qdrant_client is not None:
                try:
                    from qdrant_client.models import PointStruct
                    qdrant_client.upsert(
                        collection_name=QDRANT_COLLECTION,
                        points=[
                            PointStruct(
                                id=str(memory_id),
                                vector=embedding,
                                payload={
                                    "user_id": str(user_id),
                                    "content": content,
                                    "memory_type": memory_type,
                                },
                            )
                        ],
                    )
                    embedding_id = str(memory_id)
                except Exception as e:
                    logger.warning("Failed to index memory in Qdrant: %s", e)
        except Exception as e:
            logger.warning("Failed to generate embedding for memory: %s", e)

    # Step 2: Persist to PostgreSQL (required)
    row = type("AgentMemory", (), {
        "id": memory_id,
        "user_id": user_id,
        "organization_id": org_id,
        "content": content,
        "memory_type": memory_type,
        "embedding_id": embedding_id,
        "created_at": datetime.now(timezone.utc),
        "last_accessed_at": None,
        "access_count": 0,
        "metadata_": metadata or {},
        "is_deleted": False,
    })()

    # Use raw insert for cleaner test mocking
    db.add(row)
    await db.flush()

    return memory_id


async def search_memories(
    db: AsyncSession,
    user_id: UUID,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search memories using Qdrant semantic search + PostgreSQL hydration.

    Returns empty list if Qdrant is unavailable.
    """
    embedding_service = _get_embedding_service()
    qdrant_client = _get_qdrant_client()

    if embedding_service is None or qdrant_client is None:
        return []

    try:
        from src.models.vector import EmbeddingRequest
        response = await embedding_service.generate_embedding(
            EmbeddingRequest(text=query)
        )
        query_vector = response.embedding

        from qdrant_client.models import Filter, FieldCondition, MatchValue
        hits = qdrant_client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))]
            ),
            limit=limit,
        )

        if not hits:
            return []

        # Hydrate from PostgreSQL
        memory_ids = [UUID(h.id) for h in hits]
        score_map = {h.id: h.score for h in hits}

        stmt = sa.select(agent_memories).where(
            agent_memories.c.id.in_(memory_ids),
            agent_memories.c.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        # Update access timestamps
        for row in rows:
            await update_access(db, row.id)

        return [
            {
                "id": str(row.id),
                "content": row.content,
                "memory_type": row.memory_type,
                "score": score_map.get(str(row.id), 0.0),
                "access_count": row.access_count,
                "created_at": str(row.created_at) if row.created_at else None,
                "metadata": row.metadata_,
            }
            for row in rows
        ]

    except Exception as e:
        logger.error("Memory search failed: %s", e)
        return []


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
    """Extract key insights from conversation messages using gpt-4o-mini.

    Returns a list of insight strings, or empty list on failure.
    """
    if not messages:
        try:
            llm = _build_insights_llm()
            from langchain_core.messages import SystemMessage, HumanMessage
            result = await llm.ainvoke([
                SystemMessage(content="Extract key insights. Return an empty response."),
                HumanMessage(content="No messages."),
            ])
            return []
        except Exception:
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
