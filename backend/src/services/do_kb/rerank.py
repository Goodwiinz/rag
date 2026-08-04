"""Cohere re-scoring of DO KB chunks.

DO KB Public Preview returns no relevance scores; Chunk synthesizes
1.0 - 0.05*rank (models.py:from_do_payload). This replaces synthetic
scores with calibrated cross-encoder relevance via the live Azure
Cohere service. Tenant filtering stays upstream in
resolve_and_filter_chunks — never here.
"""

import asyncio
import logging

from src.services.do_kb.models import Chunk

logger = logging.getLogger(__name__)

# ponytail: constant, not a setting — promote to config if ops ever need to tune
_RERANK_TIMEOUT_SECONDS = 2.0


async def cohere_rescore_chunks(query: str, chunks: list[Chunk]) -> list[Chunk]:
    """Reorder + re-score chunks via cohere_rerank_service.

    Passthrough (input returned unchanged) when: <2 chunks, service
    disabled, circuit open, timeout, or any failure. Never raises,
    never drops chunks (top_n = len(chunks)).
    """
    if len(chunks) < 2:
        return chunks

    from src.services.search.cohere_rerank_service import cohere_rerank_service

    if not cohere_rerank_service.is_enabled:
        logger.debug("cohere_rescore_chunks: service disabled, passthrough")
        return chunks

    docs = [
        {"content": c.text, "id": str(i), "score": c.score}
        for i, c in enumerate(chunks)
    ]

    try:
        outcome = await asyncio.wait_for(
            cohere_rerank_service.rerank_with_outcome(query, docs, top_n=len(docs)),
            timeout=_RERANK_TIMEOUT_SECONDS,
        )
    except (asyncio.TimeoutError, Exception):
        logger.warning("cohere_rescore_chunks: rerank call failed, passthrough")
        return chunks

    try:
        if not outcome.succeeded:
            return chunks

        reranked = []
        covered: set[int] = set()
        for result in outcome.results:
            index = result.index
            if index < 0 or index >= len(chunks) or index in covered:
                raise ValueError("invalid Cohere rerank result index")
            chunk = chunks[index]
            metadata = {**chunk.metadata, "score_source": "cohere"}
            reranked.append(
                chunk.model_copy(
                    update={
                        "score": float(result.relevance_score),
                        "metadata": metadata,
                    }
                )
            )
            covered.add(index)
    except Exception:
        logger.warning("cohere_rescore_chunks: invalid rerank result, passthrough")
        return chunks

    reranked.extend(c for i, c in enumerate(chunks) if i not in covered)
    return reranked
