"""
Repair/rebuild Neo4j knowledge graph from existing documents.

Uses spaCy NER to extract entities from document content_text
and batch-inserts them into Neo4j via knowledge_graph_service.
"""

import logging
import os
import sys
import time

# Add backend root to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import spacy
from sqlalchemy.orm import Session

# Import base models first to ensure registry is populated
from src.models import *  # noqa: F401, F403

from src.models.ab_testing import (  # noqa: F401
    Experiment,
    ExperimentAssignment,
    ExperimentMetric,
    Variant,
)

from src.core.database import SessionLocal
from src.models.document import Document
from src.models.graph import (
    BatchEntityRequest,
    CreateEntityRequest,
    EntityType,
    ExtractionMethod,
)
from src.core.circuit_breaker import get_circuit_breaker
from src.services.knowledge_graph.knowledge_graph_service import (
    KnowledgeGraphService,
    knowledge_graph_service,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Map spaCy NER labels to our EntityType enum
SPACY_TO_ENTITY_TYPE = {
    "PERSON": EntityType.PERSON,
    "ORG": EntityType.ORGANIZATION,
    "GPE": EntityType.LOCATION,
    "LOC": EntityType.LOCATION,
    "PRODUCT": EntityType.PRODUCT,
    "EVENT": EntityType.EVENT,
    "WORK_OF_ART": EntityType.CONCEPT,
    "LAW": EntityType.CONCEPT,
    "LANGUAGE": EntityType.CONCEPT,
    "DATE": EntityType.DATE,
    "TIME": EntityType.DATE,
    "MONEY": EntityType.FINANCIAL,
    "PERCENT": EntityType.FINANCIAL,
    "QUANTITY": EntityType.CONCEPT,
    "CARDINAL": EntityType.CONCEPT,
    "ORDINAL": EntityType.CONCEPT,
    "NORP": EntityType.CONCEPT,  # Nationalities, religious/political groups
    "FAC": EntityType.LOCATION,  # Facilities
}


def extract_entities_spacy(nlp, text: str, document_id: str) -> list[CreateEntityRequest]:
    """Extract entities from text using spaCy NER, return CreateEntityRequest list."""
    # Limit text length to avoid spaCy memory issues
    max_chars = 100_000
    if len(text) > max_chars:
        text = text[:max_chars]

    doc = nlp(text)
    seen = set()  # deduplicate by (name_lower, entity_type)
    entities = []

    for ent in doc.ents:
        name = ent.text.strip()
        if len(name) < 2 or len(name) > 200:
            continue

        entity_type = SPACY_TO_ENTITY_TYPE.get(ent.label_)
        if entity_type is None:
            continue

        key = (name.lower(), entity_type)
        if key in seen:
            continue
        seen.add(key)

        # Get surrounding context
        start = max(0, ent.start_char - 50)
        end = min(len(text), ent.end_char + 50)
        context = text[start:end]

        entities.append(
            CreateEntityRequest(
                name=name,
                entity_type=entity_type,
                confidence_score=0.75,
                extraction_method=ExtractionMethod.SPACY_NER,
                position=[ent.start_char, ent.end_char],
                context=context,
                metadata={"spacy_label": ent.label_},
                source_document_id=document_id,
            )
        )

    return entities


def process_document(nlp, doc: Document):
    """Extract entities from a document and insert into Neo4j."""
    logger.info(f"Processing: {doc.title} ({doc.id})")

    if not doc.content_text or len(doc.content_text.strip()) < 10:
        logger.warning(f"  Skipping - no/short content")
        return

    entities = extract_entities_spacy(nlp, doc.content_text, str(doc.id))
    if not entities:
        logger.info(f"  No entities found")
        return

    logger.info(f"  Extracted {len(entities)} entities")

    batch_req = BatchEntityRequest(
        entities=entities,
        relationships=[],
        upsert=True,
        document_id=str(doc.id),
    )

    response = knowledge_graph_service.create_entities_batch(batch_req)
    logger.info(
        f"  KG result: {len(response.created_entities)} created, "
        f"{len(response.errors)} errors"
    )
    if response.errors:
        for err in response.errors[:3]:
            logger.error(f"  Error: {err}")


def main():
    logger.info("=== Knowledge Graph Rebuild ===")

    # Load spaCy model
    logger.info("Loading spaCy model...")
    nlp = spacy.load("en_core_web_sm")
    logger.info("spaCy model loaded")

    db = SessionLocal()
    try:
        total_docs = db.query(Document).count()
        logger.info(f"Total documents in DB: {total_docs}")

        documents = db.query(Document).filter(Document.content_text.isnot(None)).all()
        logger.info(f"Documents with content: {len(documents)}")

        total_entities = 0
        total_errors = 0

        for i, doc in enumerate(documents, 1):
            logger.info(f"[{i}/{len(documents)}]")
            try:
                entities = extract_entities_spacy(nlp, doc.content_text, str(doc.id))
                if not entities:
                    logger.info(f"  No entities found in: {doc.title}")
                    continue

                logger.info(f"  Extracted {len(entities)} entities from: {doc.title}")

                # Chunk into batches of 50 to avoid overwhelming Neo4j
                chunk_size = 50
                doc_created = 0
                doc_errors = 0
                for start in range(0, len(entities), chunk_size):
                    chunk = entities[start : start + chunk_size]
                    batch_req = BatchEntityRequest(
                        entities=chunk,
                        relationships=[],
                        upsert=True,
                        document_id=str(doc.id),
                    )

                    # Retry with reconnection on failure
                    for attempt in range(3):
                        response = knowledge_graph_service.create_entities_batch(batch_req)
                        if not response.errors:
                            break
                        # Check if it's a connection error
                        err_str = str(response.errors[0].get("error", ""))
                        if "Connection refused" in err_str or "defunct" in err_str or "circuit breaker" in err_str:
                            logger.warning(f"  Neo4j connection lost, waiting 15s (attempt {attempt + 1}/3)...")
                            time.sleep(15)
                            # Reset circuit breaker and reconnect
                            breaker = get_circuit_breaker("neo4j")
                            if breaker:
                                breaker.reset()
                            KnowledgeGraphService._driver_instance = None
                            knowledge_graph_service.driver = None
                            knowledge_graph_service._connect()
                            response = type(response)()  # Reset response for retry
                        else:
                            break

                    doc_created += len(response.created_entities)
                    doc_errors += len(response.errors)

                    if response.errors:
                        for err in response.errors[:2]:
                            logger.error(f"  Error: {err}")

                    # Small delay between chunks to reduce Neo4j pressure
                    time.sleep(0.1)

                total_entities += doc_created
                total_errors += doc_errors
                logger.info(f"  KG: {doc_created} created, {doc_errors} errors")

            except Exception as e:
                logger.error(f"  Failed to process {doc.id}: {e}")
                import traceback
                traceback.print_exc()

        logger.info("=== Summary ===")
        logger.info(f"Documents processed: {len(documents)}")
        logger.info(f"Total entities created: {total_entities}")
        logger.info(f"Total errors: {total_errors}")

    finally:
        db.close()
        knowledge_graph_service.close()


if __name__ == "__main__":
    main()
