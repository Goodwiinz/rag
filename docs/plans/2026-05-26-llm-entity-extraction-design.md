# LLM Entity Extraction — Design

**Date:** 2026-05-26
**Status:** Approved
**Approach:** A — LLM-only extraction (replace spaCy entirely)

## Problem

Entity extraction uses spaCy `en_core_web_sm`, which:

1. Cannot detect CONCEPT, METHOD, MODEL, DATASET, TECHNOLOGY — not in its NER training set
2. Performs poorly on academic text (author citations, institutional names, LaTeX artifacts)
3. Agent tool uses thin `EntityExtractor` wrapper, not richer `EntityExtractionService`
4. Text truncated to 10k chars — loses most of paper body

Result: extraction returns near-zero useful entities on academic papers. Neo4j knowledge graph stays empty.

## Solution

Replace spaCy with gpt-5-nano (Azure OpenAI lightweight deployment) for all entity extraction. Full paper text, chunked, with structured JSON output.

## Architecture

```
Document text (PostgreSQL content_text)
    |
+---------------------------------------------+
| LLMEntityExtractionService                  |
|                                             |
| 1. Text chunker (~4k token windows, 200 overlap)
| 2. Per-chunk: gpt-5-nano structured extraction
| 3. Cross-chunk merge + deduplication        |
| 4. Confidence scoring                       |
+---------------------------------------------+
    |                          |
Neo4j Knowledge Graph    Agent tool response
(at ingest, background)  (on-demand, inline)
```

### New file

`backend/src/services/processing/llm_entity_extraction.py`

### Reuses

- `llm_factory.build_lightweight_llm()` — Azure routing, gpt-5-nano quirks, timeouts
- `EntityType` enum from `models/entity.py`
- `CreateEntityRequest` / `create_entities_batch()` for Neo4j storage
- `ExtractionMethod.OPENAI` enum value
- `tiktoken` `cl100k_base` for token counting

### Replaces

- `EntityExtractor` class in `enhanced_document_processing_service.py`
- `EntityExtractionService` in `processing/entity_extraction_service.py`

### Callers updated

- `tools_impl.py:_tool_extract_entities()` — new service, no truncation, optional entity_types param
- `processing_tasks.py:kg_extract_entities_job()` — new service for background ingest
- `processing_tasks.py:extract_entities()` — new service

### Removed deps

- `spacy`, `en_core_web_sm` (flag for removal from requirements/Dockerfile)

## Chunking & Extraction Flow

### Text chunking

- Split on paragraph boundaries (double newline)
- Target ~4k tokens per chunk
- 200-token overlap between chunks
- Token counting via `tiktoken` `cl100k_base`

### LLM call per chunk

- `build_lightweight_llm()` with `max_tokens=2048`
- System prompt defines entity types + output schema
- gpt-5-nano: no temperature, `reasoning_effort="minimal"`
- 30s timeout per chunk

### Structured output schema

```json
{
  "entities": [
    {
      "name": "LoopMDM",
      "type": "MODEL",
      "canonical_name": "loopmdm",
      "description": "Looped Masked Diffusion Model for discrete sequence generation",
      "confidence": 0.95,
      "aliases": ["Loop MDM", "Looped MDM"]
    }
  ]
}
```

### Entity types

PERSON, ORGANIZATION, CONCEPT, METHOD, MODEL, DATASET, TECHNOLOGY, METRIC, LOCATION, RESEARCH

Type mapping to existing enum: DATASET→PRODUCT, METRIC→NUMBER, rest 1:1.

### Cross-chunk merge

- Group by `canonical_name` (lowercased, stripped)
- Merge aliases across chunks
- Keep highest confidence score
- First non-empty description wins
- Track source chunks for provenance

### Concurrency

- `asyncio.gather()` with `asyncio.Semaphore(3)` — max 3 concurrent chunk calls
- Large docs (50+ chunks): process in batches of 10

## Integration Points

### Agent tool (`tools_impl.py:_tool_extract_entities`)

- Remove 10k truncation
- Call `LLMEntityExtractionService.extract_entities(text, document_id)`
- Add optional `entity_types` param to tool schema
- 90s total timeout, return partial on budget exhaust

### Background ingest (`processing_tasks.py:kg_extract_entities_job`)

- Swap to `LLMEntityExtractionService`
- Same Neo4j storage path
- `extraction_method = ExtractionMethod.OPENAI`
- 5min total timeout
- Progress tracking unchanged

### Tool schema update

```json
{
  "name": "extract_entities",
  "description": "Extract named entities from a document using LLM analysis. Finds people, organizations, concepts, methods, models, datasets, and more.",
  "parameters": {
    "document_id": { "type": "string", "required": true },
    "entity_types": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Optional filter: PERSON, ORGANIZATION, CONCEPT, METHOD, MODEL, DATASET, TECHNOLOGY, METRIC"
    }
  }
}
```

### Untouched

- `search_knowledge_graph` tool
- `DOKnowledgeBaseClient` (KBaaS retrieval)
- Neo4j service (consumer, not producer)
- `EntityType` / `ExtractionMethod` enums

## Error Handling & Resilience

### Circuit breaker

- New key: `"llm_entity_extraction"`
- `failure_threshold=5`, `recovery_timeout=60.0`, `half_open_max_calls=2`
- Separate from main agent LLM circuit breaker

### Per-chunk failure isolation

- Each chunk is independent `asyncio.Task`
- Failed chunk: log warning, skip, continue
- 0 chunks succeed: return empty + error message (no exception)

### Structured output parsing

- `json.loads()` with `JSONDecodeError` catch
- Fallback: regex extraction from raw text
- Parse failure per chunk: skip (isolated)

### Rate limiting

- `asyncio.Semaphore(3)` concurrent cap
- Azure 429: handled by `llm_factory` retry/backoff
- Large docs: batch chunks in groups of 10

### Timeout budget

- Agent tool: 90s total, stop submitting new chunks on exhaust
- Background ingest: 5min total
- Return partial results on timeout

### Graceful degradation

- Circuit breaker open: `{"entities": [], "error": "Entity extraction temporarily unavailable"}`
- No spaCy fallback (LLM-only, clean break)

## Testing

### Unit tests (`backend/tests/services/processing/test_llm_entity_extraction.py`)

- `test_text_chunker_splits_on_paragraphs`
- `test_text_chunker_small_doc_single_chunk`
- `test_merge_deduplicates_by_canonical_name`
- `test_merge_combines_aliases`
- `test_entity_type_mapping`
- `test_parse_llm_response_valid_json`
- `test_parse_llm_response_malformed`
- `test_partial_results_on_chunk_failure`

### Integration tests (mocked Azure)

- `test_extract_entities_academic_paper`
- `test_extract_entities_tool_invocation`
- `test_kg_ingest_stores_entities`
- `test_circuit_breaker_trips_on_failures`
- `test_timeout_budget_returns_partial`

### Eval tests (`@langsmith` marker, real LLM)

- `test_extraction_quality_golden_paper`
- `test_extraction_consistency`
