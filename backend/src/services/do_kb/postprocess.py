"""Pure model-boundary sanitation for DigitalOcean KB retrieval chunks."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from src.services.agent._pii_redact import redact_nested_pii, redact_pii
from src.services.do_kb.models import Chunk

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ChunkPostprocessResult:
    """Sanitized chunks and content-free counters for observability."""

    chunks: list[Chunk]
    input_count: int
    output_count: int
    duplicate_count: int
    redacted_count: int


def _normalize_for_deduplication(text: str) -> str:
    """Canonicalize sanitized chunk text before computing its fingerprint."""
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", text)).strip().casefold()


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


__all__ = ["ChunkPostprocessResult", "sanitize_and_deduplicate_chunks"]
