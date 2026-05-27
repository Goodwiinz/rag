"""LLM-based entity extraction service.

Replaces spaCy NER with gpt-5-nano structured extraction via Azure OpenAI.
Chunks document text, extracts entities per chunk, merges and deduplicates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import tiktoken

logger = logging.getLogger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def chunk_text(
    text: str,
    max_tokens: int = 4000,
    overlap_tokens: int = 200,
) -> list[str]:
    """Split text into chunks on paragraph boundaries with token-based sizing.

    Returns empty list for empty/whitespace-only input.
    """
    stripped = text.strip()
    if not stripped:
        return []

    if _count_tokens(stripped) <= max_tokens:
        return [stripped]

    paragraphs = re.split(r"\n\n+", stripped)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks: list[str] = []
    current_paragraphs: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _count_tokens(para)

        if current_tokens + para_tokens > max_tokens and current_paragraphs:
            chunks.append("\n\n".join(current_paragraphs))

            overlap_paras: list[str] = []
            overlap_count = 0
            for prev in reversed(current_paragraphs):
                prev_tokens = _count_tokens(prev)
                if overlap_count + prev_tokens > overlap_tokens:
                    break
                overlap_paras.insert(0, prev)
                overlap_count += prev_tokens

            current_paragraphs = overlap_paras
            current_tokens = overlap_count

        current_paragraphs.append(para)
        current_tokens += para_tokens

    if current_paragraphs:
        chunks.append("\n\n".join(current_paragraphs))

    return chunks


@dataclass
class ExtractedEntity:
    """Entity extracted by LLM from a text chunk."""

    name: str
    type: str
    canonical_name: str = ""
    description: str = ""
    confidence: float = 0.8
    aliases: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.canonical_name:
            self.canonical_name = self.name.strip().lower()


def merge_entities(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    """Merge duplicate entities by canonical_name, combining aliases and keeping best metadata."""
    if not entities:
        return []

    groups: dict[str, list[ExtractedEntity]] = {}
    for ent in entities:
        key = ent.canonical_name.strip().lower()
        groups.setdefault(key, []).append(ent)

    merged: list[ExtractedEntity] = []
    for key, group in groups.items():
        best = max(group, key=lambda e: e.confidence)
        all_aliases: set[str] = set()
        for e in group:
            all_aliases.update(e.aliases)
            if e.name != best.name:
                all_aliases.add(e.name)
        all_aliases.discard(best.name)

        description = best.description
        if not description:
            for e in group:
                if e.description:
                    description = e.description
                    break

        merged.append(
            ExtractedEntity(
                name=best.name,
                type=best.type,
                canonical_name=best.canonical_name,
                description=description,
                confidence=best.confidence,
                aliases=sorted(all_aliases),
            )
        )

    return merged
