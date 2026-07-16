import asyncio
import logging
import sys
import os
import sys

# Add the parent directory to sys.path to allow imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

# Import base models first to ensure registry is populated
from src.models import *  # This triggers import of many models

# Explicitly import A/B testing models which might be missing from __init__ or have circular deps
from src.models.ab_testing import (
    Experiment,
    Variant,
    ExperimentAssignment,
    ExperimentMetric,
)

from src.core.database import SessionLocal
from src.models.document import Document
from src.services.services.entity_extraction_service import EntityExtractionService
from src.services.knowledge_graph_service import knowledge_graph_service
from src.models.graph import (
    CreateEntityRequest,
    CreateRelationshipRequest,
    BatchEntityRequest,
    EntityType,
    RelationshipType,
    ExtractionMethod,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def safe_enum_value(enum_cls, value, default):
    """Safely convert string to enum value"""
    try:
        # Try exact match
        return enum_cls(value)
    except ValueError:
        # Try case-insensitive match
        for member in enum_cls:
            if member.value.lower() == str(value).lower():
                return member
        return default


async def process_document(
    db: Session, doc: Document, extraction_service: EntityExtractionService
):
    logger.info(f"Processing document: {doc.title} ({doc.id})")

    if not doc.content_text:
        logger.warning(f"Document {doc.id} has no content text. Skipping.")
        return

    try:
        # Extract entities and relationships
        # The service returns a mixed list of dicts
        extracted_data = await extraction_service.extract_entities(
            doc.content_text, str(doc.id)
        )

        entities_req = []
        relationships_req = []

        for item in extracted_data:
            # Check if it's a relationship (has source/target entity ids)
            if "source_entity_id" in item and "target_entity_id" in item:
                # It's a relationship
                try:
                    rel_type = safe_enum_value(
                        RelationshipType,
                        item.get("relationship_type"),
                        RelationshipType.RELATED_TO,
                    )

                    req = CreateRelationshipRequest(
                        source_entity_id=item[
                            "source_entity_id"
                        ],  # Note: extract_service returns names as IDs sometimes?
                        target_entity_id=item["target_entity_id"],
                        relationship_type=rel_type,
                        strength=float(item.get("strength", 0.5)),
                        confidence_score=float(item.get("confidence_score", 0.7)),
                        context=item.get("context"),
                        evidence=item.get("evidence", []),
                        metadata=item.get("metadata", {}),
                        source_document_id=str(doc.id),
                    )
                    relationships_req.append(req)
                except Exception as e:
                    logger.warning(f"Skipping invalid relationship: {e}")

            elif "name" in item and "entity_type" in item:
                # It's an entity
                try:
                    ent_type = safe_enum_value(
                        EntityType, item.get("entity_type"), EntityType.OTHER
                    )

                    ext_method = safe_enum_value(
                        ExtractionMethod,
                        item.get("extraction_method"),
                        ExtractionMethod.RULE_BASED,
                    )

                    req = CreateEntityRequest(
                        name=item["name"],
                        entity_type=ent_type,
                        confidence_score=float(item.get("confidence_score", 0.7)),
                        extraction_method=ext_method,
                        position=item.get("position"),
                        context=item.get("context"),
                        metadata=item.get("metadata", {}),
                        source_document_id=str(doc.id),
                    )
                    entities_req.append(req)
                except Exception as e:
                    logger.warning(f"Skipping invalid entity: {e}")

        logger.info(
            f"Found {len(entities_req)} entities and {len(relationships_req)} relationships."
        )

        if not entities_req and not relationships_req:
            return

        # Batch create in KG
        batch_req = BatchEntityRequest(
            entities=entities_req,
            relationships=relationships_req,
            upsert=True,
            document_id=str(doc.id),
        )

        # This is a synchronous call in the service, but let's check if we need to run it in executor
        # knowledge_graph_service.create_entities_batch is synchronous DB operation
        response = knowledge_graph_service.create_entities_batch(batch_req)

        logger.info(
            f"KG Batch Result: {len(response.created_entities)} created, {len(response.errors)} errors."
        )
        if response.errors:
            logger.error(f"Errors: {response.errors}")

    except Exception as e:
        logger.error(f"Failed to process document {doc.id}: {e}")
        import traceback

        traceback.print_exc()


async def main():
    logger.info("Starting Knowledge Graph Repair/Sync...")

    # Initialize extraction service
    extraction_service = EntityExtractionService()

    # Get DB session
    db = SessionLocal()

    try:
        # Fetch documents
        total_docs = db.query(Document).count()
        logger.info(f"Total documents in DB: {total_docs}")

        documents = db.query(Document).filter(Document.content_text.isnot(None)).all()
        logger.info(f"Found {len(documents)} documents with content.")

        for doc in documents:
            await process_document(db, doc, extraction_service)

    finally:
        db.close()
        knowledge_graph_service.close()


if __name__ == "__main__":
    asyncio.run(main())
