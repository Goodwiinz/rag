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
from langchain_core.messages import HumanMessage, SystemMessage

from src.core.circuit_breaker import circuit_breakers
from src.services.agent.llm_factory import build_lightweight_llm

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


ENTITY_TYPES = [
    "PERSON", "ORGANIZATION", "CONCEPT", "METHOD", "MODEL",
    "DATASET", "TECHNOLOGY", "METRIC", "LOCATION", "RESEARCH",
]

EXTRACTION_SYSTEM_PROMPT = """\
Extract named entities from the following text. Return a JSON object with an "entities" array.

For each entity include:
- "name": exact name as it appears in the text
- "type": one of {entity_types}
- "canonical_name": lowercase normalized form (e.g. "gpt-4" for "GPT-4")
- "description": one-sentence description of what this entity is (from context)
- "confidence": 0.0-1.0 how confident you are this is a real entity
- "aliases": array of alternate names/abbreviations seen in the text

Focus on entities that carry domain meaning. Skip generic words, stopwords, and formatting artifacts.
Return ONLY the JSON object, no other text."""

EXTRACTION_USER_TEMPLATE = "Extract entities from this text:\n\n{text}"


def _build_system_prompt(entity_types: list[str] | None = None) -> str:
    types = entity_types or ENTITY_TYPES
    return EXTRACTION_SYSTEM_PROMPT.format(entity_types=", ".join(types))


def parse_llm_response(raw: str) -> list[ExtractedEntity]:
    """Parse LLM JSON response into ExtractedEntity list. Returns empty on failure."""
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM entity response as JSON")
        return []

    if not isinstance(data, dict) or "entities" not in data:
        logger.warning("LLM response missing 'entities' key")
        return []

    entities: list[ExtractedEntity] = []
    for raw_ent in data["entities"]:
        if not isinstance(raw_ent, dict):
            continue
        name = raw_ent.get("name", "").strip()
        ent_type = raw_ent.get("type", "").strip().upper()
        if not name or not ent_type:
            continue
        entities.append(
            ExtractedEntity(
                name=name,
                type=ent_type,
                canonical_name=raw_ent.get("canonical_name", ""),
                description=raw_ent.get("description", ""),
                confidence=float(raw_ent.get("confidence", 0.8)),
                aliases=raw_ent.get("aliases", []),
            )
        )

    return entities


from src.models.entity import EntityType

_LLM_TYPE_TO_ENTITY_TYPE: dict[str, EntityType] = {
    "PERSON": EntityType.PERSON,
    "ORGANIZATION": EntityType.ORGANIZATION,
    "LOCATION": EntityType.LOCATION,
    "CONCEPT": EntityType.CONCEPT,
    "TECHNOLOGY": EntityType.TECHNOLOGY,
    "RESEARCH": EntityType.RESEARCH,
    "MODEL": EntityType.PRODUCT,
    "DATASET": EntityType.PRODUCT,
    "METHOD": EntityType.CONCEPT,
    "METRIC": EntityType.NUMBER,
}


def map_to_entity_type(llm_type: str) -> EntityType:
    """Map LLM extraction type string to EntityType enum."""
    return _LLM_TYPE_TO_ENTITY_TYPE.get(llm_type.strip().upper(), EntityType.CUSTOM)


_MAX_CONCURRENT_CHUNKS = 3
_AGENT_TIMEOUT_SECONDS = 90.0
_BACKGROUND_TIMEOUT_SECONDS = 300.0


@dataclass
class ExtractionResult:
    """Result of entity extraction over a full document."""

    entities: list[ExtractedEntity]
    chunks_processed: int
    chunks_failed: int
    processing_time_ms: float
    error: str | None = None


class LLMEntityExtractionService:
    """Extracts entities from text using Azure OpenAI (gpt-5-nano)."""

    def __init__(self) -> None:
        self._llm = build_lightweight_llm(max_tokens=2048)
        self._breaker = circuit_breakers["llm_entity_extraction"]

    async def _extract_chunk(
        self,
        chunk: str,
        system_prompt: str,
        semaphore: asyncio.Semaphore,
    ) -> list[ExtractedEntity]:
        """Extract entities from a single text chunk."""
        async with semaphore:
            if not self._breaker.can_execute():
                raise RuntimeError("Circuit breaker open")

            try:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=EXTRACTION_USER_TEMPLATE.format(text=chunk)
                    ),
                ]
                response = await self._llm.ainvoke(messages)
                self._breaker.record_success()
                return parse_llm_response(response.content)
            except Exception:
                self._breaker.record_failure()
                raise

    async def extract_entities(
        self,
        text: str,
        entity_types: list[str] | None = None,
        timeout_seconds: float = _AGENT_TIMEOUT_SECONDS,
        max_tokens_per_chunk: int = 4000,
    ) -> ExtractionResult:
        """Extract entities from full document text."""
        start = time.monotonic()

        chunks = chunk_text(text, max_tokens=max_tokens_per_chunk, overlap_tokens=200)
        if not chunks:
            return ExtractionResult(
                entities=[], chunks_processed=0, chunks_failed=0,
                processing_time_ms=0.0,
            )

        system_prompt = _build_system_prompt(entity_types)
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_CHUNKS)

        all_entities: list[ExtractedEntity] = []
        chunks_failed = 0

        batch_size = 10
        for batch_start in range(0, len(chunks), batch_size):
            elapsed = time.monotonic() - start
            if elapsed >= timeout_seconds:
                logger.warning(
                    "Entity extraction timeout after %d/%d chunks",
                    batch_start, len(chunks),
                )
                break

            batch = chunks[batch_start : batch_start + batch_size]
            tasks = [
                self._extract_chunk(chunk, system_prompt, semaphore)
                for chunk in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            from src.core.async_utils import reraise_if_cancelled

            for result in results:
                reraise_if_cancelled(result)
                if isinstance(result, Exception):
                    chunks_failed += 1
                    logger.warning("Chunk extraction failed: %s", result)
                else:
                    all_entities.extend(result)

        merged = merge_entities(all_entities)
        elapsed_ms = (time.monotonic() - start) * 1000

        error = None
        if chunks_failed == len(chunks):
            error = "All chunks failed during entity extraction"

        return ExtractionResult(
            entities=merged,
            chunks_processed=len(chunks) - chunks_failed,
            chunks_failed=chunks_failed,
            processing_time_ms=elapsed_ms,
            error=error,
        )
