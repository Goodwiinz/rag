import asyncio
import logging
import json
import uuid
import sys
import os
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add the parent directory to sys.path to allow imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from src.core.database import SessionLocal

# Import ALL models to ensure registry is populated
from src.models import *
from src.models.ab_testing import *

from src.models.document import Document, DocumentType, ProcessingStatus
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
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "document_chunks"


def get_all_chunks_from_qdrant():
    """Fetch all chunks from Qdrant"""
    chunks = []
    offset = None

    logger.info("Fetching chunks from Qdrant...")

    while True:
        try:
            resp = requests.post(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
                json={
                    "limit": 100,
                    "with_payload": True,
                    "with_vector": False,
                    "offset": offset,
                },
                timeout=30,
            )

            if resp.status_code != 200:
                logger.error(
                    f"Error scrolling points (status {resp.status_code}): {resp.text}"
                )
                break

            resp.raise_for_status()  # Raise exception for bad status codes

            data = resp.json()
            result = data.get("result", {})
            points = result.get("points", [])

            if not points:
                break

            chunks.extend(points)
            offset = result.get("next_page_offset")

            if not offset:
                break

            logger.info(f"Fetched {len(chunks)} chunks so far...")

        except requests.RequestException as e:
            logger.error(f"Request error while fetching from Qdrant: {e}")
            break
        except Exception as e:
            logger.error(f"Unexpected error connecting to Qdrant: {e}", exc_info=True)
            break

    logger.info(f"Total chunks fetched: {len(chunks)}")
    return chunks


def group_chunks_by_document(points):
    """Group chunks by document_id and reconstruction content"""
    documents = {}

    for point in points:
        payload = point.get("payload", {})
        # Try top-level document_id first, then metadata
        doc_id = payload.get("document_id")
        if not doc_id:
            metadata = payload.get("metadata", {})
            if isinstance(metadata, dict):
                doc_id = metadata.get("document_id") or metadata.get(
                    "additional_data", {}
                ).get("document_id")

        # If still no ID, try finding arxiv_id
        if not doc_id:
            metadata = payload.get("metadata", {})
            if isinstance(metadata, dict):
                doc_id = metadata.get("additional_data", {}).get("arxiv_id")

        if not doc_id:
            logger.warning(f"Skipping point {point['id']} - no document ID found")
            continue

        if doc_id not in documents:
            documents[doc_id] = {"chunks": [], "metadata": payload.get("metadata", {})}

        documents[doc_id]["chunks"].append(
            {
                "index": payload.get("metadata", {}).get("chunk_index", 0),
                "text": payload.get("text", "")
                or payload.get("metadata", {}).get("chunk_text", ""),
            }
        )

    # Reassemble text
    restored_docs = []
    for doc_id, data in documents.items():
        # Sort chunks by index
        sorted_chunks = sorted(data["chunks"], key=lambda x: x["index"])
        full_text = " ".join([c["text"] for c in sorted_chunks])

        # Get metadata fields
        meta = data["metadata"]
        additional = meta.get("additional_data", {})

        restored_docs.append(
            {
                "doc_id": doc_id,
                "title": additional.get("title", f"Restored Document {doc_id}"),
                "text": full_text,
                "metadata": additional,
            }
        )

    return restored_docs


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


async def restore_document_and_extract(
    db: Session,
    doc_data: Dict,
    extraction_service: EntityExtractionService,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
):
    doc_id = doc_data["doc_id"]
    logger.info(f"Restoring document: {doc_id}")

    # Check if document exists by title or some metadata since ID format mismatch
    # Qdrant uses ArXiv ID (string), Postgres needs UUID
    # NOTE: avoiding .astext as it fails with generic JSON type
    existing_doc = (
        db.query(Document).filter(Document.filename == f"{doc_id}.pdf").first()
    )

    if existing_doc:
        logger.info(
            f"Document {doc_id} already exists in Postgres with UUID {existing_doc.id}"
        )
        doc = existing_doc
        if not doc.content_text:
            doc.content_text = doc_data["text"]
            logger.info("Updated content text")
    else:
        # Create new document
        new_uuid = uuid.uuid4()

        # Ensure metadata is JSON serializable
        safe_metadata = doc_data["metadata"].copy()
        safe_metadata["paper_id"] = doc_id  # Store original ID

        doc = Document(
            id=new_uuid,
            title=doc_data["title"],
            filename=f"{doc_id}.pdf",
            file_path=f"restored/{doc_id}.pdf",  # Placeholder
            file_size_bytes=len(doc_data["text"]),
            mime_type="application/pdf",
            document_type=DocumentType.PDF,
            content_text=doc_data["text"],
            document_metadata=safe_metadata,
            processing_status=ProcessingStatus.COMPLETED,
            is_embedded=True,
            is_indexed=True,
            organization_id=org_id,
            uploaded_by_user_id=user_id,
        )
        db.add(doc)
        logger.info(f"Created new document with UUID {new_uuid}")

    # Now run extraction
    try:
        logger.info(f"Extracting entities for {doc.title}")
        extracted_data = await extraction_service.extract_entities(
            doc.content_text, str(doc.id)
        )

        entities_req = []
        relationships_req = []

        for item in extracted_data:
            if "source_entity_id" in item and "target_entity_id" in item:
                try:
                    rel_type = safe_enum_value(
                        RelationshipType,
                        item.get("relationship_type"),
                        RelationshipType.RELATED_TO,
                    )
                    req = CreateRelationshipRequest(
                        source_entity_id=item["source_entity_id"],
                        target_entity_id=item["target_entity_id"],
                        relationship_type=rel_type,
                        strength=float(item.get("strength", 0.5)),
                        confidence_score=float(item.get("confidence_score", 0.7)),
                        metadata=item.get("metadata", {}),
                        source_document_id=str(doc.id),
                    )
                    relationships_req.append(req)
                except Exception as e:
                    logger.warning(f"Failed to process relationship item: {e}")

            elif "name" in item:
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
                        metadata=item.get("metadata", {}),
                        source_document_id=str(doc.id),
                    )
                    entities_req.append(req)
                except Exception as e:
                    logger.warning(f"Failed to process entity item: {e}")

        if entities_req:
            batch_req = BatchEntityRequest(
                entities=entities_req,
                relationships=relationships_req,
                upsert=True,
                document_id=str(doc.id),
            )
            knowledge_graph_service.create_entities_batch(batch_req)
            logger.info(f"Pushed {len(entities_req)} entities to Neo4j")

    except Exception as e:
        logger.error(f"Extraction failed: {e}")


async def main():
    # Get chunks
    chunks = get_all_chunks_from_qdrant()
    if not chunks:
        logger.error("No chunks found in Qdrant")
        return

    # Restore docs
    restored_docs = group_chunks_by_document(chunks)
    logger.info(f"Reassembled {len(restored_docs)} documents")

    # Init services
    extraction_service = EntityExtractionService()
    db = SessionLocal()

    try:
        # Get or create a default user/org for restoration
        # Assuming admin user exists or creating one
        user = db.query(User).first()
        if not user:
            logger.error("No users found in DB. Cannot assign owner.")
            return

        org = db.query(Organization).first()
        if not org:
            logger.error("No organization found.")
            return

        for doc_data in restored_docs:
            await restore_document_and_extract(
                db, doc_data, extraction_service, user.id, org.id
            )
        db.commit()

    finally:
        db.close()
        knowledge_graph_service.close()


if __name__ == "__main__":
    asyncio.run(main())
