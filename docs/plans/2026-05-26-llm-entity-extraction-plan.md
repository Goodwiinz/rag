# LLM Entity Extraction — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace broken spaCy entity extraction with gpt-5-nano LLM extraction so Neo4j knowledge graph gets populated with useful entities from academic papers.

**Architecture:** New `LLMEntityExtractionService` chunks document text, sends each chunk to gpt-5-nano for structured entity extraction, merges/deduplicates results across chunks. Replaces both `EntityExtractor` and `EntityExtractionService`. Wired into agent tool (on-demand) and Celery background job (at ingest).

**Tech Stack:** Azure OpenAI (gpt-5-nano via `llm_factory`), tiktoken, asyncio, LangChain `with_structured_output`, existing Neo4j integration.

**Design doc:** `docs/plans/2026-05-26-llm-entity-extraction-design.md`

---

### Task 1: Text Chunker — Tests

**Files:**

- Create: `backend/tests/services/processing/test_llm_entity_extraction.py`

**Step 1: Write failing tests for text chunker**

```python
"""Tests for LLM entity extraction service."""

import pytest

from src.services.processing.llm_entity_extraction import chunk_text


class TestChunkText:
    def test_small_doc_single_chunk(self):
        """Document under token limit returns single chunk."""
        text = "This is a short document about transformers."
        chunks = chunk_text(text, max_tokens=4000, overlap_tokens=200)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_on_paragraph_boundaries(self):
        """Chunks split at double-newline paragraph breaks."""
        para1 = "First paragraph. " * 200  # ~400 tokens
        para2 = "Second paragraph. " * 200
        para3 = "Third paragraph. " * 200
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = chunk_text(text, max_tokens=500, overlap_tokens=50)
        assert len(chunks) >= 2
        # Each chunk should start/end at paragraph boundary (no mid-word splits)
        for chunk in chunks:
            assert not chunk.startswith(" ")

    def test_overlap_between_chunks(self):
        """Adjacent chunks share overlapping text."""
        paragraphs = [f"Paragraph {i} content. " * 100 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, max_tokens=300, overlap_tokens=100)
        assert len(chunks) >= 3
        # Check some overlap exists between consecutive chunks
        for i in range(len(chunks) - 1):
            # Last part of chunk i should appear in start of chunk i+1
            tail = chunks[i][-50:]
            assert tail in chunks[i + 1] or chunks[i + 1][:100] in chunks[i]

    def test_empty_text_returns_empty(self):
        chunks = chunk_text("", max_tokens=4000, overlap_tokens=200)
        assert chunks == []

    def test_whitespace_only_returns_empty(self):
        chunks = chunk_text("   \n\n  ", max_tokens=4000, overlap_tokens=200)
        assert chunks == []
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py::TestChunkText -v`
Expected: FAIL with `ImportError: cannot import name 'chunk_text'`

**Step 3: Commit test file**

```bash
git add backend/tests/services/processing/test_llm_entity_extraction.py
git commit -m "test: add text chunker tests for LLM entity extraction"
```

---

### Task 2: Text Chunker — Implementation

**Files:**

- Create: `backend/src/services/processing/llm_entity_extraction.py`

**Step 1: Implement chunk_text**

```python
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

            # Build overlap from tail paragraphs
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
```

**Step 2: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py::TestChunkText -v`
Expected: All 5 tests PASS

**Step 3: Commit**

```bash
git add backend/src/services/processing/llm_entity_extraction.py
git commit -m "feat: add text chunker for LLM entity extraction"
```

---

### Task 3: Entity Merge/Dedup — Tests

**Files:**

- Modify: `backend/tests/services/processing/test_llm_entity_extraction.py`

**Step 1: Add merge tests**

```python
from src.services.processing.llm_entity_extraction import (
    ExtractedEntity,
    merge_entities,
)


class TestMergeEntities:
    def test_deduplicates_by_canonical_name(self):
        """Same canonical name from different chunks merges into one."""
        e1 = ExtractedEntity(name="LoopMDM", type="MODEL", canonical_name="loopmdm", confidence=0.9)
        e2 = ExtractedEntity(name="Loop MDM", type="MODEL", canonical_name="loopmdm", confidence=0.95)
        result = merge_entities([e1, e2])
        assert len(result) == 1
        assert result[0].confidence == 0.95  # highest wins

    def test_combines_aliases(self):
        """Aliases from duplicate entities are merged."""
        e1 = ExtractedEntity(name="GPT-4", type="MODEL", canonical_name="gpt-4", aliases=["GPT4"])
        e2 = ExtractedEntity(name="GPT-4", type="MODEL", canonical_name="gpt-4", aliases=["gpt-4o"])
        result = merge_entities([e1, e2])
        assert len(result) == 1
        assert set(result[0].aliases) >= {"GPT4", "gpt-4o"}

    def test_first_nonempty_description_wins(self):
        e1 = ExtractedEntity(name="BERT", type="MODEL", canonical_name="bert", description="")
        e2 = ExtractedEntity(name="BERT", type="MODEL", canonical_name="bert", description="Bidirectional encoder")
        result = merge_entities([e1, e2])
        assert result[0].description == "Bidirectional encoder"

    def test_different_entities_not_merged(self):
        e1 = ExtractedEntity(name="BERT", type="MODEL", canonical_name="bert")
        e2 = ExtractedEntity(name="Berkeley", type="ORGANIZATION", canonical_name="berkeley")
        result = merge_entities([e1, e2])
        assert len(result) == 2

    def test_empty_input(self):
        assert merge_entities([]) == []
```

**Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py::TestMergeEntities -v`
Expected: FAIL with `ImportError: cannot import name 'ExtractedEntity'`

**Step 3: Commit tests**

```bash
git add backend/tests/services/processing/test_llm_entity_extraction.py
git commit -m "test: add entity merge/dedup tests"
```

---

### Task 4: Entity Merge/Dedup — Implementation

**Files:**

- Modify: `backend/src/services/processing/llm_entity_extraction.py`

**Step 1: Add dataclass and merge function**

Add after the `chunk_text` function:

```python
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
```

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py::TestMergeEntities -v`
Expected: All 5 tests PASS

**Step 3: Commit**

```bash
git add backend/src/services/processing/llm_entity_extraction.py
git commit -m "feat: add entity merge/dedup logic"
```

---

### Task 5: LLM Extraction Core — Tests

**Files:**

- Modify: `backend/tests/services/processing/test_llm_entity_extraction.py`

**Step 1: Add LLM response parsing tests**

````python
from src.services.processing.llm_entity_extraction import parse_llm_response


class TestParseLLMResponse:
    def test_valid_json(self):
        raw = json.dumps({
            "entities": [
                {
                    "name": "LoopMDM",
                    "type": "MODEL",
                    "canonical_name": "loopmdm",
                    "description": "Looped Masked Diffusion Model",
                    "confidence": 0.95,
                    "aliases": ["Loop MDM"],
                }
            ]
        })
        entities = parse_llm_response(raw)
        assert len(entities) == 1
        assert entities[0].name == "LoopMDM"
        assert entities[0].type == "MODEL"
        assert entities[0].confidence == 0.95

    def test_malformed_json_returns_empty(self):
        entities = parse_llm_response("not json {{{")
        assert entities == []

    def test_json_wrapped_in_markdown_code_block(self):
        raw = '```json\n{"entities": [{"name": "BERT", "type": "MODEL"}]}\n```'
        entities = parse_llm_response(raw)
        assert len(entities) == 1
        assert entities[0].name == "BERT"

    def test_missing_fields_use_defaults(self):
        raw = json.dumps({"entities": [{"name": "GPT-4", "type": "MODEL"}]})
        entities = parse_llm_response(raw)
        assert len(entities) == 1
        assert entities[0].confidence == 0.8
        assert entities[0].aliases == []
        assert entities[0].canonical_name == "gpt-4"

    def test_empty_entities_array(self):
        raw = json.dumps({"entities": []})
        entities = parse_llm_response(raw)
        assert entities == []
````

**Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py::TestParseLLMResponse -v`
Expected: FAIL with `ImportError: cannot import name 'parse_llm_response'`

**Step 3: Commit tests**

```bash
git add backend/tests/services/processing/test_llm_entity_extraction.py
git commit -m "test: add LLM response parsing tests"
```

---

### Task 6: LLM Extraction Core — Implementation

**Files:**

- Modify: `backend/src/services/processing/llm_entity_extraction.py`

**Step 1: Add parse_llm_response and entity type constants**

````python
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
````

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py::TestParseLLMResponse -v`
Expected: All 5 tests PASS

**Step 3: Also run all previous tests to check no regressions**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add backend/src/services/processing/llm_entity_extraction.py
git commit -m "feat: add LLM response parsing and extraction prompt"
```

---

### Task 7: LLMEntityExtractionService Class — Tests

**Files:**

- Modify: `backend/tests/services/processing/test_llm_entity_extraction.py`

**Step 1: Add service-level tests with mocked LLM**

```python
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.processing.llm_entity_extraction import LLMEntityExtractionService


def _mock_llm_response(entities: list[dict]) -> MagicMock:
    """Build a mock LLM response with .content containing JSON."""
    mock = MagicMock()
    mock.content = json.dumps({"entities": entities})
    return mock


class TestLLMEntityExtractionService:
    @pytest.fixture
    def service(self):
        with patch(
            "src.services.processing.llm_entity_extraction.build_lightweight_llm"
        ) as mock_build:
            mock_llm = AsyncMock()
            mock_build.return_value = mock_llm
            svc = LLMEntityExtractionService()
            svc._llm = mock_llm
            yield svc, mock_llm

    @pytest.mark.asyncio
    async def test_extract_entities_full_pipeline(self, service):
        svc, mock_llm = service
        mock_llm.ainvoke.return_value = _mock_llm_response([
            {"name": "LoopMDM", "type": "MODEL", "confidence": 0.95},
            {"name": "Berkeley", "type": "ORGANIZATION", "confidence": 0.9},
        ])

        result = await svc.extract_entities("Short document about LoopMDM at Berkeley.")
        assert len(result.entities) == 2
        assert result.entities[0].name == "LoopMDM"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_partial_results_on_chunk_failure(self, service):
        svc, mock_llm = service
        good_response = _mock_llm_response([
            {"name": "BERT", "type": "MODEL", "confidence": 0.9}
        ])
        mock_llm.ainvoke.side_effect = [
            good_response,
            Exception("API timeout"),
            good_response,
        ]

        # Build text large enough for 3 chunks
        text = "\n\n".join([f"Paragraph {i}. " * 200 for i in range(30)])
        result = await svc.extract_entities(text, max_tokens_per_chunk=300)
        assert len(result.entities) >= 1  # at least partial results
        assert result.error is None  # partial success is not an error

    @pytest.mark.asyncio
    async def test_entity_types_filter(self, service):
        svc, mock_llm = service
        mock_llm.ainvoke.return_value = _mock_llm_response([
            {"name": "BERT", "type": "MODEL", "confidence": 0.9}
        ])
        result = await svc.extract_entities(
            "BERT is a model.",
            entity_types=["MODEL", "METHOD"],
        )
        # Verify the system prompt only contains requested types
        call_args = mock_llm.ainvoke.call_args
        messages = call_args[0][0]
        system_msg = messages[0].content
        assert "MODEL" in system_msg
        assert "METHOD" in system_msg
        assert "PERSON" not in system_msg

    @pytest.mark.asyncio
    async def test_all_chunks_fail_returns_empty(self, service):
        svc, mock_llm = service
        mock_llm.ainvoke.side_effect = Exception("All calls fail")
        result = await svc.extract_entities("Some text.")
        assert result.entities == []
        assert result.error is not None
```

**Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py::TestLLMEntityExtractionService -v`
Expected: FAIL with `ImportError: cannot import name 'LLMEntityExtractionService'`

**Step 3: Commit tests**

```bash
git add backend/tests/services/processing/test_llm_entity_extraction.py
git commit -m "test: add LLMEntityExtractionService integration tests"
```

---

### Task 8: LLMEntityExtractionService Class — Implementation

**Files:**

- Modify: `backend/src/services/processing/llm_entity_extraction.py`

**Step 1: Add circuit breaker registration**

In `backend/src/core/circuit_breaker.py`, add to the `circuit_breakers` dict:

```python
    "llm_entity_extraction": ServiceCircuitBreaker(
        "llm_entity_extraction",
        failure_threshold=5,
        recovery_timeout=60.0,
        half_open_max_calls=2,
    ),
```

**Step 2: Implement the service class**

Add to `llm_entity_extraction.py`:

```python
from langchain_core.messages import HumanMessage, SystemMessage

from src.core.circuit_breaker import circuit_breakers
from src.services.agent.llm_factory import build_lightweight_llm

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
            except Exception as exc:
                self._breaker.record_failure()
                raise

    async def extract_entities(
        self,
        text: str,
        entity_types: list[str] | None = None,
        timeout_seconds: float = _AGENT_TIMEOUT_SECONDS,
        max_tokens_per_chunk: int = 4000,
    ) -> ExtractionResult:
        """Extract entities from full document text.

        Chunks text, runs LLM extraction per chunk in parallel,
        merges and deduplicates results.
        """
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

        # Process in batches of 10 for large documents
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

            remaining = timeout_seconds - (time.monotonic() - start)
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
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
```

**Step 3: Run all tests**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add backend/src/services/processing/llm_entity_extraction.py backend/src/core/circuit_breaker.py
git commit -m "feat: add LLMEntityExtractionService with circuit breaker"
```

---

### Task 9: Entity Type Mapping

**Files:**

- Modify: `backend/src/services/processing/llm_entity_extraction.py`
- Modify: `backend/tests/services/processing/test_llm_entity_extraction.py`

**Step 1: Write tests for type mapping**

```python
from src.services.processing.llm_entity_extraction import map_to_entity_type
from src.models.entity import EntityType


class TestEntityTypeMapping:
    def test_direct_mappings(self):
        assert map_to_entity_type("PERSON") == EntityType.PERSON
        assert map_to_entity_type("ORGANIZATION") == EntityType.ORGANIZATION
        assert map_to_entity_type("CONCEPT") == EntityType.CONCEPT
        assert map_to_entity_type("TECHNOLOGY") == EntityType.TECHNOLOGY
        assert map_to_entity_type("RESEARCH") == EntityType.RESEARCH

    def test_alias_mappings(self):
        assert map_to_entity_type("MODEL") == EntityType.PRODUCT
        assert map_to_entity_type("DATASET") == EntityType.PRODUCT
        assert map_to_entity_type("METRIC") == EntityType.NUMBER
        assert map_to_entity_type("METHOD") == EntityType.CONCEPT

    def test_unknown_type_returns_custom(self):
        assert map_to_entity_type("UNKNOWN_THING") == EntityType.CUSTOM

    def test_case_insensitive(self):
        assert map_to_entity_type("person") == EntityType.PERSON
        assert map_to_entity_type("Model") == EntityType.PRODUCT
```

**Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py::TestEntityTypeMapping -v`
Expected: FAIL

**Step 3: Implement mapping function**

Add to `llm_entity_extraction.py`:

```python
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
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/src/services/processing/llm_entity_extraction.py backend/tests/services/processing/test_llm_entity_extraction.py
git commit -m "feat: add LLM entity type to EntityType enum mapping"
```

---

### Task 10: Wire Into Agent Tool

**Files:**

- Modify: `backend/src/api/agent/tools_impl.py:358-373` (tool schema)
- Modify: `backend/src/api/agent/tools_impl.py:1717-1773` (tool impl)

**Step 1: Update tool schema** (lines 358-373)

Replace the existing `extract_entities` tool definition:

```python
    {
        "type": "function",
        "function": {
            "name": "extract_entities",
            "description": "Extract named entities from a document using LLM analysis. Finds people, organizations, concepts, methods, models, datasets, and more.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The UUID of the document to extract entities from",
                    },
                    "entity_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional filter. Allowed types: PERSON, ORGANIZATION, CONCEPT, METHOD, MODEL, DATASET, TECHNOLOGY, METRIC, LOCATION, RESEARCH. Omit for all types.",
                    },
                },
                "required": ["document_id"],
            },
        },
    },
```

**Step 2: Replace tool implementation** (lines 1717-1773)

```python
async def _tool_extract_entities(
    args: Dict[str, Any],
    db: Any,
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Extract named entities from a document using LLM."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    document_id = args.get("document_id", "")
    if not document_id:
        return {"error": "document_id is required"}

    entity_types = args.get("entity_types")

    try:
        doc = await _resolve_document_id(document_id, db, current_user)
        if not doc:
            return {"error": "Document not found or access denied"}

        text = doc.content_text or ""
        if not text:
            from src.services.documents.file_service import FileService

            file_service = FileService(db)
            text = file_service.extract_text_content(doc)

        if not text or text.startswith("Error"):
            return {"error": "Could not extract text from document"}

        from src.services.processing.llm_entity_extraction import (
            LLMEntityExtractionService,
            map_to_entity_type,
        )

        service = LLMEntityExtractionService()
        result = await service.extract_entities(text, entity_types=entity_types)

        if result.entities:
            return {
                "entities": [
                    {
                        "name": e.name,
                        "type": e.type,
                        "description": e.description,
                        "confidence": e.confidence,
                        "aliases": e.aliases,
                    }
                    for e in result.entities[:50]
                ],
                "total": len(result.entities),
                "chunks_processed": result.chunks_processed,
                "document_id": document_id,
                "title": doc.title or "Untitled",
            }

        return {
            "entities": [],
            "total": 0,
            "document_id": document_id,
            "error": result.error,
        }
    except Exception as e:
        logger.error("extract_entities tool failed", exc_info=e)
        return {"error": f"Entity extraction failed: {str(e)}"}
```

**Step 3: Run type check**

Run: `cd backend && python -m pyright src/api/agent/tools_impl.py --pythonversion 3.12 2>&1 | tail -5` (or mypy equivalent)

**Step 4: Commit**

```bash
git add backend/src/api/agent/tools_impl.py
git commit -m "feat: wire LLM entity extraction into agent tool"
```

---

### Task 11: Wire Into Background Ingest Job

**Files:**

- Modify: `backend/src/tasks/processing_tasks.py:29-32` (imports)
- Modify: `backend/src/tasks/processing_tasks.py:531-694` (kg_extract_entities_job)
- Modify: `backend/src/tasks/processing_tasks.py:346-407` (extract_entities task)

**Step 1: Update imports** (lines 29-32)

Replace:

```python
from src.services.processing.entity_extraction_service import (
    EntityExtractionService,
    EntityType as ProcessingEntityType,
)
```

With:

```python
from src.services.processing.llm_entity_extraction import (
    LLMEntityExtractionService,
    map_to_entity_type,
)
```

**Step 2: Update `_map_processing_entity_type_to_graph`** (lines 66-82)

Replace entire function:

```python
def _map_llm_entity_type_to_graph(llm_type: str) -> GraphEntityType:
    """Map LLM extraction type string to graph EntityType."""
    mapping = {
        "PERSON": GraphEntityType.PERSON,
        "ORGANIZATION": GraphEntityType.ORGANIZATION,
        "LOCATION": GraphEntityType.LOCATION,
        "CONCEPT": GraphEntityType.CONCEPT,
        "TECHNOLOGY": GraphEntityType.TECHNOLOGY,
        "RESEARCH": GraphEntityType.RESEARCH,
        "MODEL": GraphEntityType.PRODUCT,
        "DATASET": GraphEntityType.PRODUCT,
        "METHOD": GraphEntityType.CONCEPT,
        "METRIC": GraphEntityType.OTHER,
    }
    return mapping.get(llm_type.strip().upper(), GraphEntityType.OTHER)
```

**Step 3: Update `kg_extract_entities_job`** (lines 531-694)

Replace the inner extraction loop (lines 543 and 577-579). Change:

```python
        extractor = EntityExtractionService()
```

to:

```python
        loop = asyncio.get_event_loop()
```

Replace lines 577-579:

```python
            extracted_entities, extracted_relationships = extractor.extract_entities_and_relationships_from_text(
                document, content
            )
```

with:

```python
            service = LLMEntityExtractionService()
            extraction_result = loop.run_until_complete(
                service.extract_entities(
                    content,
                    timeout_seconds=300.0,
                )
            )
            extracted_entities = extraction_result.entities
            extracted_relationships = []  # LLM extraction handles relationships separately
```

Update the `create_requests` loop (lines 583-599). Replace:

```python
            for ent in extracted_entities:
                create_requests.append(
                    CreateEntityRequest(
                        name=ent.name,
                        entity_type=_map_processing_entity_type_to_graph(ent.entity_type),
                        confidence_score=min(1.0, max(0.0, ent.confidence or 0.8)),
                        extraction_method=GraphExtractionMethod.MANUAL,
                        position=None,
                        context=ent.description,
                        metadata={
                            "source": "background_extraction_job",
                            "document_id": str(document.id),
                        },
                        source_document_id=str(document.id),
                    )
                )
```

with:

```python
            for ent in extracted_entities:
                create_requests.append(
                    CreateEntityRequest(
                        name=ent.name,
                        entity_type=_map_llm_entity_type_to_graph(ent.type),
                        confidence_score=min(1.0, max(0.0, ent.confidence)),
                        extraction_method=GraphExtractionMethod.LLM_EXTRACTION,
                        position=None,
                        context=ent.description,
                        metadata={
                            "source": "background_extraction_job",
                            "document_id": str(document.id),
                            "aliases": ent.aliases,
                        },
                        source_document_id=str(document.id),
                    )
                )
```

**Step 4: Update `extract_entities` task** (lines 346-407)

Replace lines 372-376:

```python
        processing_service = ProcessingPipeline(db)
        entities = processing_service.process_entity_extraction(
            document, document.content_text
        )
```

with:

```python
        loop = asyncio.get_event_loop()
        service = LLMEntityExtractionService()
        result = loop.run_until_complete(
            service.extract_entities(document.content_text)
        )
```

And update the save loop (lines 379-383) to create Entity objects from `result.entities`, setting `extraction_method=ExtractionMethod.OPENAI`.

**Step 5: Run affected tests**

Run: `cd backend && python -m pytest tests/tasks/ -v -k "entity" --no-header 2>&1 | tail -20`

**Step 6: Commit**

```bash
git add backend/src/tasks/processing_tasks.py
git commit -m "feat: wire LLM entity extraction into background ingest jobs"
```

---

### Task 12: Update Graph Type Mapping

**Files:**

- Modify: `backend/src/tasks/processing_tasks.py:66-82`

The `_map_processing_entity_type_to_graph` mapping (line 66-82) is missing entries for TOPIC, TECHNOLOGY, RESEARCH, EVENT. These types exist in both the `EntityType` and `GraphEntityType` enums but were never mapped because spaCy never produced them.

**Step 1: Verify the old mapping is already replaced in Task 11**

If Task 11 already replaced the function with `_map_llm_entity_type_to_graph`, verify it handles all LLM output types. If not, ensure full mapping coverage.

**Step 2: Commit if any changes needed**

```bash
git add backend/src/tasks/processing_tasks.py
git commit -m "fix: ensure full entity type mapping coverage for LLM extraction"
```

---

### Task 13: Remove spaCy Dead Code

**Files:**

- Modify: `backend/src/services/processing/entity_extraction_service.py` — mark as deprecated or delete
- Modify: `backend/src/services/documents/enhanced_document_processing_service.py:380-500` — remove `EntityExtractor` class

**Step 1: Check for other callers of spaCy classes**

Run: `grep -rn "EntityExtractionService\|EntityExtractor" backend/src/ --include="*.py" | grep -v __pycache__ | grep -v test`

If only `processing_tasks.py` (already updated) and `tools_impl.py` (already updated) reference them, safe to remove.

**Step 2: Remove `EntityExtractor` class from `enhanced_document_processing_service.py`**

Delete lines 380-500 (the `EntityExtractor` class and its methods). Keep the rest of the file intact.

**Step 3: Mark `entity_extraction_service.py` as deprecated**

Add at top of file:

```python
"""DEPRECATED: This module is replaced by llm_entity_extraction.py.
Kept temporarily for reference. Remove after confirming no callers."""
```

Or delete entirely if no callers remain.

**Step 4: Run full test suite to verify nothing breaks**

Run: `cd backend && python -m pytest tests/ -v --no-header 2>&1 | tail -20`

**Step 5: Commit**

```bash
git add backend/src/services/processing/entity_extraction_service.py backend/src/services/documents/enhanced_document_processing_service.py
git commit -m "refactor: remove spaCy entity extraction dead code"
```

---

### Task 14: Integration Smoke Test

**Files:**

- Modify: `backend/tests/services/processing/test_llm_entity_extraction.py`

**Step 1: Add end-to-end integration test with mock**

```python
class TestIntegrationSmoke:
    """End-to-end smoke test simulating agent tool call."""

    @pytest.mark.asyncio
    async def test_academic_paper_extraction(self):
        """Simulate extraction from a realistic academic abstract."""
        abstract = (
            "We introduce LoopMDM, a Looped Masked Diffusion Model for discrete "
            "sequence generation. Our method extends MDLM (Masked Diffusion Language "
            "Model) with iterative refinement loops. We evaluate on GSM8K and "
            "HumanEval benchmarks, achieving state-of-the-art results. The work was "
            "conducted at UC Berkeley by J. Park and collaborators."
        )

        with patch(
            "src.services.processing.llm_entity_extraction.build_lightweight_llm"
        ) as mock_build:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = _mock_llm_response([
                {"name": "LoopMDM", "type": "MODEL", "confidence": 0.95,
                 "description": "Looped Masked Diffusion Model", "aliases": ["Loop MDM"]},
                {"name": "MDLM", "type": "MODEL", "confidence": 0.9,
                 "description": "Masked Diffusion Language Model"},
                {"name": "GSM8K", "type": "DATASET", "confidence": 0.9},
                {"name": "HumanEval", "type": "DATASET", "confidence": 0.9},
                {"name": "UC Berkeley", "type": "ORGANIZATION", "confidence": 0.95},
                {"name": "J. Park", "type": "PERSON", "confidence": 0.85},
                {"name": "iterative refinement", "type": "METHOD", "confidence": 0.8},
                {"name": "masked diffusion", "type": "CONCEPT", "confidence": 0.9},
            ])
            mock_build.return_value = mock_llm

            service = LLMEntityExtractionService()
            service._llm = mock_llm
            result = await service.extract_entities(abstract)

            assert result.error is None
            assert len(result.entities) == 8

            types_found = {e.type for e in result.entities}
            assert "MODEL" in types_found
            assert "DATASET" in types_found
            assert "ORGANIZATION" in types_found
            assert "PERSON" in types_found
            assert "METHOD" in types_found
            assert "CONCEPT" in types_found
```

**Step 2: Run all tests**

Run: `cd backend && python -m pytest tests/services/processing/test_llm_entity_extraction.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add backend/tests/services/processing/test_llm_entity_extraction.py
git commit -m "test: add integration smoke test for LLM entity extraction"
```

---

### Task 15: Final Verification

**Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest tests/ -v --no-header 2>&1 | tail -30`

**Step 2: Type check**

Run: `cd backend && python -m pyright src/services/processing/llm_entity_extraction.py`

**Step 3: Verify imports resolve**

Run: `cd backend && python -c "from src.services.processing.llm_entity_extraction import LLMEntityExtractionService, chunk_text, merge_entities, parse_llm_response, map_to_entity_type; print('All imports OK')"`

**Step 4: Commit any fixes**

**Step 5: Squash-ready summary commit (optional)**

```bash
git log --oneline -15  # review all commits from this plan
```
