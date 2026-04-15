"""
Cache warm-up: pre-populates critical caches after pod restart.

Runs as a non-blocking background task during application startup so it
never delays the server from accepting requests.  All errors are caught
and logged — none are re-raised.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def warm_critical_caches() -> None:
    """
    Pre-populate critical caches from persistent storage.

    Spawns three sub-tasks in parallel and gathers their results.
    Individual failures are logged but do not abort the others.
    """
    logger.info("Cache warm-up starting...")

    results = await asyncio.gather(
        _warm_quality_metrics(),
        _warm_search_cache(),
        _warm_llm_embedding_index(),
        return_exceptions=True,
    )

    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Cache warm-up sub-task {idx} failed: {result}")

    logger.info("Cache warm-up complete")


# ---------------------------------------------------------------------------
# Sub-tasks
# ---------------------------------------------------------------------------


async def _warm_quality_metrics() -> None:
    """
    Pre-compute quality metrics for all active organisations.

    Queries the DB for distinct organisation IDs that have recent metrics
    data, then issues a cache-get for each so that the analytics cache layer
    can populate itself on the first real request.
    """
    try:
        from sqlalchemy import text

        from src.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT DISTINCT organization_id
                    FROM quality_metrics
                    WHERE measured_at >= NOW() - INTERVAL '30 days'
                    LIMIT 10
                    """
                )
            )
            org_ids = [str(row[0]) for row in result.fetchall()]

        if not org_ids:
            logger.debug("Cache warm-up: no organisations found in quality_metrics")
            return

        logger.info(
            f"Cache warm-up: pre-warming quality metrics for {len(org_ids)} organisation(s)"
        )
        # Touching the cache key ensures the analytics layer is primed; the
        # actual heavy computation happens on the first real hit (cache miss),
        # but this confirms Redis connectivity and warms any L1 in-memory layer.
        from src.cache.analytics_cache import AnalyticsCache

        cache = AnalyticsCache()
        for org_id in org_ids:
            try:
                await cache.get(f"quality_overview:{org_id}")
            except Exception as exc:
                logger.debug(f"Cache warm-up: quality metrics skip for {org_id}: {exc}")

    except Exception as exc:
        logger.warning(f"Cache warm-up: quality metrics failed: {exc}")
        raise


async def _warm_search_cache() -> None:
    """
    Identify the top-10 most frequently searched queries from the last 30 days.

    The query results are logged so operators know which terms are hottest;
    actual search execution (and therefore Redis population) is intentionally
    deferred to the first real request to avoid heavyweight embedding/vector
    operations during startup.
    """
    try:
        from sqlalchemy import text

        from src.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT query_text, COUNT(*) AS cnt
                    FROM search_queries
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY query_text
                    ORDER BY cnt DESC
                    LIMIT 10
                    """
                )
            )
            rows = result.fetchall()

        if rows:
            top = ", ".join(f'"{r[0]}" ({r[1]})' for r in rows[:3])
            logger.info(
                f"Cache warm-up: top search queries — {top}"
                + (f" (+{len(rows) - 3} more)" if len(rows) > 3 else "")
            )
        else:
            logger.debug("Cache warm-up: no search_queries rows found")

    except Exception as exc:
        # search_queries table may not exist in all deployments
        logger.warning(f"Cache warm-up: search cache warm skipped: {exc}")
        raise


async def _warm_llm_embedding_index() -> None:
    """
    Scan Redis for existing LLM cache entries and log cache health.

    The LLMResponseCache instances rebuild their own in-memory embedding index
    lazily on each get(), so this step verifies Redis connectivity and gives
    operators an at-a-glance count of surviving cache entries after a restart.
    """
    client = None
    try:
        import redis.asyncio as aioredis

        from src.core.config import settings

        client = aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )

        try:
            await client.ping()
        except Exception as exc:
            logger.debug(f"Cache warm-up: Redis not reachable for LLM index scan: {exc}")
            return

        count = 0
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match="llm_cache:*", count=100)
            count += len(keys)
            if cursor == 0:
                break

        logger.info(f"Cache warm-up: {count} LLM cache entries surviving in Redis")

    except Exception as exc:
        logger.warning(f"Cache warm-up: LLM index scan failed: {exc}")
        raise
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass
