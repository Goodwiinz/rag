"""
Rebuild Neo4j knowledge graph using Azure OpenAI gpt-4o extraction.

Wipes Neo4j, then for each document:
  - Chunks text (3K tokens with 200-token overlap)
  - Calls gpt-4o to extract research-focused entities and relationships
  - Batch-inserts into Neo4j via knowledge_graph_service

Usage:
  docker exec -e PYTHONPATH=/app rag_system-backend-1 \
    python scripts/maintenance/rebuild_kg_llm.py
"""

import asyncio
import json
import logging
import os
import re
import sys
import time

# Configure logging BEFORE imports (imports set up their own handlers)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Add backend root to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# Import base models first to ensure registry is populated
from src.models import *  # noqa: F401, F403

from src.models.ab_testing import (  # noqa: F401
    Experiment,
    ExperimentAssignment,
    ExperimentMetric,
    Variant,
)

from src.core.circuit_breaker import get_circuit_breaker
from src.models.graph import (
    BatchEntityRequest,
    CreateEntityRequest,
    CreateRelationshipRequest,
    EntityType,
    ExtractionMethod,
    RelationshipType,
)
from src.services.infrastructure.azure_openai_service import azure_openai_service
from src.services.knowledge_graph.knowledge_graph_service import (
    KnowledgeGraphService,
    knowledge_graph_service,
)

# Suppress noisy loggers from imports
logging.getLogger("src.services.infrastructure").setLevel(logging.WARNING)

# ── Type Mappings ──────────────────────────────────────────────────────────

LLM_ENTITY_TYPE_MAP = {
    "person": EntityType.PERSON,
    "author": EntityType.PERSON,
    "organization": EntityType.ORGANIZATION,
    "org": EntityType.ORGANIZATION,
    "university": EntityType.ORGANIZATION,
    "lab": EntityType.ORGANIZATION,
    "company": EntityType.ORGANIZATION,
    "methodology": EntityType.RESEARCH,
    "method": EntityType.RESEARCH,
    "model": EntityType.TECHNOLOGY,
    "algorithm": EntityType.TECHNOLOGY,
    "framework": EntityType.TECHNOLOGY,
    "tool": EntityType.TECHNOLOGY,
    "dataset": EntityType.CONCEPT,
    "benchmark": EntityType.CONCEPT,
    "metric": EntityType.CONCEPT,
    "task": EntityType.CONCEPT,
    "research_topic": EntityType.TOPIC,
    "topic": EntityType.TOPIC,
    "citation": EntityType.DOCUMENT,
}

LLM_RELATIONSHIP_TYPE_MAP = {
    "AUTHORED": RelationshipType.CREATED_BY,
    "AFFILIATED_WITH": RelationshipType.WORKS_FOR,
    "USES": RelationshipType.RELATED_TO,
    "EVALUATED_ON": RelationshipType.RELATED_TO,
    "ACHIEVES": RelationshipType.RELATED_TO,
    "IMPROVES": RelationshipType.RELATED_TO,
    "CITES": RelationshipType.CITED,
    "EXTENDS": RelationshipType.REFERENCES,
    "PART_OF": RelationshipType.PART_OF,
    "COMPARED_WITH": RelationshipType.RELATED_TO,
    "PROPOSES": RelationshipType.CREATED_BY,
    "APPLIED_TO": RelationshipType.RELATED_TO,
    "OUTPERFORMS": RelationshipType.RELATED_TO,
    "BASED_ON": RelationshipType.REFERENCES,
}

# ── Extraction Prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful assistant that builds knowledge graphs from academic text. Given a passage, identify the key entities and relationships between them.

Entity types to look for: person, organization, methodology, model, dataset, metric, research_topic, tool, task, citation.

Relationship types: AUTHORED, AFFILIATED_WITH, USES, EVALUATED_ON, ACHIEVES, IMPROVES, CITES, EXTENDS, PART_OF, COMPARED_WITH, PROPOSES, APPLIED_TO, OUTPERFORMS, BASED_ON.

Respond with JSON containing "entities" (each with "name", "type", "description") and "relationships" (each with "source", "target", "type", "context"). Use canonical names. Keep descriptions under 10 words. Focus on the most important entities only (max 30 entities, max 30 relationships per response)."""

USER_PROMPT_TEMPLATE = """Please identify the key entities (people, organizations, methods, models, datasets, metrics, topics, tools, tasks, citations) and relationships in this academic text. Return the result as JSON.

Text:
{text}"""

# ── Text Chunking ──────────────────────────────────────────────────────────


def chunk_text(text: str, max_tokens: int = 3000, overlap_tokens: int = 200) -> list[str]:
    """Split text into chunks of ~max_tokens with overlap. Approximates 1 token ~ 4 chars."""
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4

    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            para_break = text.rfind("\n\n", start + max_chars // 2, end)
            if para_break > start:
                end = para_break
            else:
                sent_break = text.rfind(". ", start + max_chars // 2, end)
                if sent_break > start:
                    end = sent_break + 1

        chunks.append(text[start:end].strip())
        start = end - overlap_chars

    return [c for c in chunks if c]


# ── LLM Extraction ────────────────────────────────────────────────────────


def parse_llm_json(raw: str) -> dict:
    """Parse LLM response, stripping markdown fences and repairing truncation."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to repair truncated JSON
    repaired = cleaned
    for array_key in ("entities", "relationships"):
        pattern = rf'"{array_key}"\s*:\s*\['
        match = re.search(pattern, repaired)
        if match:
            array_start = match.end()
            last_complete = repaired.rfind("}", array_start)
            if last_complete > array_start:
                next_array = re.search(r',\s*"(entities|relationships)"', repaired[last_complete:])
                if not next_array:
                    repaired = repaired[: last_complete + 1] + "]}"
                    break

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Last resort: extract entities array only
    ent_match = re.search(r'"entities"\s*:\s*\[', cleaned)
    if ent_match:
        start = ent_match.end()
        last_brace = cleaned.rfind("}", start)
        if last_brace > start:
            try:
                entities_str = "[" + cleaned[start : last_brace + 1] + "]"
                entities = json.loads(entities_str)
                return {"entities": entities, "relationships": []}
            except json.JSONDecodeError:
                pass

    raise json.JSONDecodeError("Could not repair truncated JSON", cleaned, 0)


def call_llm(messages: list[dict], doc_title: str) -> dict:
    """Call Azure OpenAI synchronously using asyncio.run() for each call."""

    async def _call():
        return await azure_openai_service.chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=8192,
        )

    for attempt in range(3):
        try:
            result = asyncio.run(_call())
            parsed = parse_llm_json(result["content"])
            return {
                "entities": parsed.get("entities", []),
                "relationships": parsed.get("relationships", []),
                "usage": result.get("usage", {}),
            }
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1} for '{doc_title}': {e}")
            if attempt == 2:
                logger.error(f"Failed to parse LLM output for '{doc_title}' after 3 attempts")
                return {"entities": [], "relationships": [], "usage": {}}
        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str or "ContentFilter" in err_str:
                logger.warning(f"Content filter triggered for '{doc_title}' chunk, skipping")
                return {"entities": [], "relationships": [], "usage": {}}
            if "429" in err_str or "rate" in err_str.lower():
                wait = 2 ** (attempt + 1)
                logger.warning(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"Azure OpenAI error for '{doc_title}': {e}")
                if attempt == 2:
                    return {"entities": [], "relationships": [], "usage": {}}
                time.sleep(2)

    return {"entities": [], "relationships": [], "usage": {}}


def extract_from_chunk(text: str, doc_title: str) -> dict:
    """Extract entities and relationships from a text chunk."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(text=text)},
    ]
    return call_llm(messages, doc_title)


def deduplicate_entities(all_entities: list[dict]) -> list[dict]:
    """Deduplicate entities by normalized name + type."""
    seen = {}
    for ent in all_entities:
        key = (ent["name"].strip().lower(), ent.get("type", "").lower())
        if key not in seen:
            seen[key] = ent
        else:
            existing = seen[key]
            new_conf = ent.get("confidence", 0.8)
            old_conf = existing.get("confidence", 0.8)
            if new_conf > old_conf:
                seen[key] = ent
    return list(seen.values())


# ── Neo4j Operations ──────────────────────────────────────────────────────


def wipe_neo4j():
    """Delete all nodes and relationships from Neo4j."""
    logger.info("Wiping Neo4j...")
    driver = knowledge_graph_service.driver
    if not driver:
        reconnect_neo4j()
        driver = knowledge_graph_service.driver

    if not driver:
        logger.error("Cannot connect to Neo4j for wipe")
        sys.exit(1)

    with driver.session() as session:
        while True:
            result = session.run(
                "MATCH (n) WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) as deleted"
            )
            deleted = result.single()["deleted"]
            if deleted == 0:
                break
            logger.info(f"  Deleted {deleted} nodes...")

    logger.info("Neo4j wiped clean.")


def reconnect_neo4j():
    """Force reconnect to Neo4j with circuit breaker reset."""
    breaker = get_circuit_breaker("neo4j")
    if breaker:
        breaker.reset()
    KnowledgeGraphService._driver_instance = None
    knowledge_graph_service.driver = None
    knowledge_graph_service._connect()


def insert_entities_batch(
    entities: list[dict], doc_id: str, chunk_size: int = 50
) -> dict[str, str]:
    """Insert entities into Neo4j in chunks. Returns name->neo4j_id mapping."""
    name_to_id = {}
    create_requests = []

    for ent in entities:
        ent_type = LLM_ENTITY_TYPE_MAP.get(ent.get("type", "").lower(), EntityType.OTHER)
        confidence = float(ent.get("confidence", 0.85))

        create_requests.append(
            CreateEntityRequest(
                name=ent["name"].strip(),
                entity_type=ent_type,
                confidence_score=min(max(confidence, 0.0), 1.0),
                extraction_method=ExtractionMethod.LLM_EXTRACTION,
                context=ent.get("description", ""),
                metadata={"llm_type": ent.get("type", "unknown"), "source": "gpt-4o"},
                source_document_id=doc_id,
            )
        )

    for start in range(0, len(create_requests), chunk_size):
        chunk = create_requests[start : start + chunk_size]
        batch_req = BatchEntityRequest(
            entities=chunk,
            relationships=[],
            upsert=True,
            document_id=doc_id,
        )

        for attempt in range(3):
            try:
                response = knowledge_graph_service.create_entities_batch(batch_req)
                for created in response.created_entities + response.updated_entities:
                    name_to_id[created.name.lower()] = created.id

                if response.errors:
                    conn_errors = [
                        e
                        for e in response.errors
                        if any(
                            kw in str(e.get("error", ""))
                            for kw in ("Connection refused", "defunct", "circuit breaker")
                        )
                    ]
                    if conn_errors and attempt < 2:
                        logger.warning(
                            f"Neo4j connection error, reconnecting (attempt {attempt + 1})..."
                        )
                        time.sleep(15)
                        reconnect_neo4j()
                        continue
                    for err in response.errors:
                        logger.warning(f"  Entity error: {err.get('error', 'unknown')}")
                break
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Batch insert error: {e}, retrying...")
                    time.sleep(15)
                    reconnect_neo4j()
                else:
                    logger.error(f"Failed to insert entity batch after 3 attempts: {e}")

        time.sleep(0.1)

    return name_to_id


def insert_relationships(
    relationships: list[dict], name_to_id: dict[str, str], doc_id: str
):
    """Insert relationships, resolving entity names to Neo4j IDs."""
    created = 0
    skipped = 0

    for rel in relationships:
        source_name = rel.get("source", "").strip().lower()
        target_name = rel.get("target", "").strip().lower()
        rel_type_str = rel.get("type", "RELATED_TO")

        source_id = name_to_id.get(source_name)
        target_id = name_to_id.get(target_name)

        if not source_id or not target_id:
            skipped += 1
            continue

        mapped_type = LLM_RELATIONSHIP_TYPE_MAP.get(rel_type_str, RelationshipType.RELATED_TO)

        req = CreateRelationshipRequest(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=mapped_type,
            confidence_score=0.85,
            context=rel.get("context", ""),
            metadata={"llm_type": rel_type_str, "source": "gpt-4o"},
            source_document_id=doc_id,
        )

        for attempt in range(3):
            try:
                knowledge_graph_service.create_relationship(req)
                created += 1
                break
            except Exception as e:
                if attempt < 2 and any(
                    kw in str(e) for kw in ("Connection refused", "defunct", "circuit breaker")
                ):
                    time.sleep(15)
                    reconnect_neo4j()
                else:
                    logger.warning(f"  Relationship error ({source_name} -> {target_name}): {e}")
                    skipped += 1
                    break

    return created, skipped


# ── Main ──────────────────────────────────────────────────────────────────


def main():
    logger.info("=" * 60)
    logger.info("Knowledge Graph Rebuild with Azure OpenAI gpt-4o")
    logger.info("=" * 60)

    # Check Azure OpenAI availability
    if not azure_openai_service.is_chat_available():
        logger.error(
            "Azure OpenAI chat not available. Check env vars:\n"
            "  AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,\n"
            "  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME, AZURE_OPENAI_CHAT_API_VERSION"
        )
        sys.exit(1)

    deployment = azure_openai_service.get_chat_deployment()
    logger.info(f"Using deployment: {deployment}")

    # Connect to Neo4j
    knowledge_graph_service._connect()

    # Step 1: Wipe Neo4j
    wipe_neo4j()

    # Step 2: Query documents from PostgreSQL
    from sqlalchemy import create_engine, text

    pg_url = os.environ.get(
        "KG_DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/multimodal_rag_dev",
    )
    logger.info(f"Connecting to PostgreSQL: {pg_url.split('@')[1] if '@' in pg_url else pg_url}")
    pg_engine = create_engine(pg_url)
    try:
        with pg_engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, title, filename, content_text FROM documents "
                    "WHERE content_text IS NOT NULL AND content_text != ''"
                )
            ).fetchall()
        documents = [
            {"id": str(row[0]), "title": row[1], "filename": row[2], "content_text": row[3]}
            for row in rows
        ]
        logger.info(f"Found {len(documents)} documents with content")
    finally:
        pg_engine.dispose()

    if not documents:
        logger.warning("No documents found. Exiting.")
        sys.exit(0)

    # Step 3: Process each document
    total_entities = 0
    total_relationships = 0
    total_input_tokens = 0
    total_output_tokens = 0
    start_time = time.time()

    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        doc_title = doc["title"] or doc["filename"] or f"doc-{doc_id[:8]}"
        text_content = doc["content_text"].strip()

        logger.info(f"\n[{i}/{len(documents)}] Processing: {doc_title}")
        logger.info(f"  Text length: {len(text_content):,} chars (~{len(text_content)//4:,} tokens)")

        chunks = chunk_text(text_content)
        logger.info(f"  Chunks: {len(chunks)}")

        all_entities = []
        all_relationships = []

        for j, chunk in enumerate(chunks, 1):
            logger.info(f"  Extracting chunk {j}/{len(chunks)}...")
            result = extract_from_chunk(chunk, doc_title)

            all_entities.extend(result["entities"])
            all_relationships.extend(result["relationships"])

            usage = result.get("usage", {})
            total_input_tokens += usage.get("prompt_tokens", 0)
            total_output_tokens += usage.get("completion_tokens", 0)

        # Deduplicate entities across chunks
        unique_entities = deduplicate_entities(all_entities)
        logger.info(
            f"  Extracted: {len(all_entities)} entities -> {len(unique_entities)} unique, "
            f"{len(all_relationships)} relationships"
        )

        # Insert entities
        name_to_id = insert_entities_batch(unique_entities, doc_id)
        total_entities += len(name_to_id)

        # Insert relationships
        rel_created, rel_skipped = insert_relationships(all_relationships, name_to_id, doc_id)
        total_relationships += rel_created
        logger.info(
            f"  Inserted: {len(name_to_id)} entities, "
            f"{rel_created} relationships ({rel_skipped} skipped)"
        )

        # Rate limit protection between documents
        if i < len(documents):
            time.sleep(2)

    # Summary
    elapsed = time.time() - start_time
    input_cost = (total_input_tokens / 1_000_000) * 2.50
    output_cost = (total_output_tokens / 1_000_000) * 10.00
    total_cost = input_cost + output_cost

    logger.info("\n" + "=" * 60)
    logger.info("REBUILD COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Documents processed: {len(documents)}")
    logger.info(f"Total entities:      {total_entities}")
    logger.info(f"Total relationships: {total_relationships}")
    logger.info(f"Time elapsed:        {elapsed:.1f}s")
    logger.info(
        f"Tokens used:         {total_input_tokens:,} input + {total_output_tokens:,} output"
    )
    logger.info(
        f"Estimated cost:      ${total_cost:.2f} (${input_cost:.2f} input + ${output_cost:.2f} output)"
    )
    logger.info("=" * 60)

    knowledge_graph_service.close()


if __name__ == "__main__":
    main()
