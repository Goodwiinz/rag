"""Pure model-boundary sanitation for DigitalOcean KB retrieval chunks."""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Union

from src.services.agent._pii_redact import redact_nested_pii, redact_pii
from src.services.do_kb.models import Chunk

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")
_COHERE_RELEVANCE_FLOOR = 0.1
_ChunkLike = Union[Chunk, dict[str, Any]]


@dataclass(frozen=True)
class ChunkPostprocessResult:
    """Sanitized chunks and content-free counters for observability."""

    chunks: list[Chunk]
    input_count: int
    output_count: int
    duplicate_count: int
    redacted_count: int


def drop_low_relevance_chunks(chunks: list[_ChunkLike]) -> list[_ChunkLike]:
    """Drop only calibrated Cohere scores below the shared relevance floor."""
    kept = [
        chunk
        for chunk in chunks
        if (
            (
                chunk.get("score_source")
                if isinstance(chunk, dict)
                else (chunk.metadata or {}).get("score_source")
            )
            != "cohere"
            or ((chunk.get("score") if isinstance(chunk, dict) else chunk.score) or 0.0)
            >= _COHERE_RELEVANCE_FLOOR
        )
    ]
    dropped = len(chunks) - len(kept)
    if dropped:
        logger.info(
            "do_kb: dropped %d low-relevance chunk(s) below cohere floor %.2f",
            dropped,
            _COHERE_RELEVANCE_FLOOR,
        )
    return kept


def _normalize_for_deduplication(text: str) -> str:
    """Canonicalize sanitized chunk text before computing its fingerprint."""
    return (
        _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", text)).strip().casefold()
    )


def sanitize_and_deduplicate_chunks(chunks: list[Chunk]) -> ChunkPostprocessResult:
    """Return redacted model copies, retaining the first chunk per content hash.

    Incoming order is deliberately retained: upstream retrieval or reranking
    establishes rank, so the first matching sanitized chunk is the winner.
    """
    output: list[Chunk] = []
    seen_fingerprints: set[str] = set()
    duplicate_count = 0
    redacted_count = 0

    for chunk in chunks:
        sanitized_text = redact_pii(chunk.text)
        sanitized_metadata = redact_nested_pii(chunk.metadata)
        if sanitized_text != chunk.text or sanitized_metadata != chunk.metadata:
            redacted_count += 1

        normalized_text = _normalize_for_deduplication(sanitized_text)
        if not normalized_text:
            continue

        fingerprint = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
        if fingerprint in seen_fingerprints:
            duplicate_count += 1
            continue

        seen_fingerprints.add(fingerprint)
        output.append(
            chunk.model_copy(
                update={"text": sanitized_text, "metadata": sanitized_metadata},
                deep=True,
            )
        )

    return ChunkPostprocessResult(
        chunks=output,
        input_count=len(chunks),
        output_count=len(output),
        duplicate_count=duplicate_count,
        redacted_count=redacted_count,
    )


__all__ = [
    "ChunkPostprocessResult",
    "drop_low_relevance_chunks",
    "sanitize_and_deduplicate_chunks",
]
