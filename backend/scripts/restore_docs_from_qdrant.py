#!/usr/bin/env python3
"""
Restore Documents from Qdrant to Postgres
Phase 1: Just restore the document content, no entity extraction.
Phase 2: Use backfill_knowledge_graph.py to extract entities.
"""

import logging
import json
import uuid
import sys
import os
import requests
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from src.core.database import SessionLocal

# Import ALL models to ensure SQLAlchemy registry is complete
from src.models import *
from src.models.ab_testing import (
    Experiment,
    Variant,
    ExperimentAssignment,
    ExperimentMetric,
)

from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.user import User
from src.models.organization import Organization

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
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
            )

            if resp.status_code != 200:
                logger.error(f"Error scrolling points: {resp.text}")
                break

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

        except Exception as e:
            logger.error(f"Error connecting to Qdrant: {e}")
            break

    logger.info(f"Total chunks fetched: {len(chunks)}")
    return chunks


def group_chunks_by_document(points):
    """Group chunks by document_id and reconstruct content"""
    documents = {}

    for point in points:
        payload = point.get("payload", {})

        # Try top-level document_id first
        doc_id = payload.get("document_id")

        # Then try metadata
        if not doc_id:
            metadata = payload.get("metadata", {})
            if isinstance(metadata, dict):
                doc_id = metadata.get("document_id") or metadata.get(
                    "additional_data", {}
                ).get("document_id")

        # Try arxiv_id
        if not doc_id:
            metadata = payload.get("metadata", {})
            if isinstance(metadata, dict):
                doc_id = metadata.get("additional_data", {}).get("arxiv_id")

        if not doc_id:
            continue

        if doc_id not in documents:
            documents[doc_id] = {"chunks": [], "metadata": payload.get("metadata", {})}

        # Get chunk index and text
        chunk_index = 0
        text = ""

        metadata = payload.get("metadata", {})
        if isinstance(metadata, dict):
            chunk_index = metadata.get("chunk_index", 0)
            text = payload.get("text", "") or metadata.get("chunk_text", "")
        else:
            text = payload.get("text", "")

        documents[doc_id]["chunks"].append({"index": chunk_index, "text": text})

    # Reassemble text
    restored_docs = []
    for doc_id, data in documents.items():
        # Sort chunks by index
        sorted_chunks = sorted(data["chunks"], key=lambda x: x["index"])
        full_text = " ".join([c["text"] for c in sorted_chunks if c["text"]])

        # Get metadata fields
        meta = data["metadata"]
        additional = meta.get("additional_data", {}) if isinstance(meta, dict) else {}

        restored_docs.append(
            {
                "doc_id": doc_id,
                "title": additional.get("title", f"Restored Document {doc_id}"),
                "text": full_text,
                "metadata": additional,
            }
        )

    return restored_docs


def restore_document(db: Session, doc_data: Dict, user_id, org_id) -> bool:
    """Restore a single document to Postgres"""
    doc_id = doc_data["doc_id"]

    # Check if already exists
    existing = db.query(Document).filter(Document.filename == f"{doc_id}.pdf").first()
    if existing:
        logger.info(f"Document {doc_id} already exists, skipping")
        return False

    # Create document
    new_uuid = uuid.uuid4()
    safe_metadata = doc_data["metadata"].copy() if doc_data["metadata"] else {}
    safe_metadata["paper_id"] = doc_id

    doc = Document(
        id=new_uuid,
        title=doc_data["title"],
        filename=f"{doc_id}.pdf",
        file_path=f"restored/{doc_id}.pdf",
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
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Restore documents from Qdrant to Postgres"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of documents to restore"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be restored"
    )
    args = parser.parse_args()

    # Get chunks from Qdrant
    chunks = get_all_chunks_from_qdrant()
    if not chunks:
        logger.error("No chunks found in Qdrant")
        return

    # Group and reassemble
    restored_docs = group_chunks_by_document(chunks)
    logger.info(f"Reassembled {len(restored_docs)} documents")

    if args.limit:
        restored_docs = restored_docs[: args.limit]
        logger.info(f"Limited to {len(restored_docs)} documents")

    if args.dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN - Documents that would be restored:")
        print("=" * 70 + "\n")
        for i, doc in enumerate(restored_docs[:20], 1):
            text_len = len(doc["text"]) if doc["text"] else 0
            print(f"{i:3}. {doc['title'][:55]:55} | {text_len:6} chars")
        if len(restored_docs) > 20:
            print(f"... and {len(restored_docs) - 20} more")
        print(f"\nTotal: {len(restored_docs)} documents")
        return

    # Get DB session
    db = SessionLocal()

    try:
        # Get user and org
        user = db.query(User).first()
        org = db.query(Organization).first()

        if not user or not org:
            logger.error("No user or organization found. Create them first.")
            return

        logger.info(f"Using user: {user.email}, org: {org.name}")

        # Restore documents
        restored_count = 0
        skipped_count = 0

        for i, doc_data in enumerate(restored_docs, 1):
            try:
                if restore_document(db, doc_data, user.id, org.id):
                    restored_count += 1
                else:
                    skipped_count += 1

                # Commit in batches
                if i % 50 == 0:
                    db.commit()
                    logger.info(f"Progress: {i}/{len(restored_docs)} documents")

            except Exception as e:
                logger.error(f"Error restoring {doc_data['doc_id']}: {e}")
                db.rollback()

        # Final commit
        db.commit()

        print("\n" + "=" * 70)
        print("Restoration Complete!")
        print("=" * 70)
        print(f"  Documents restored: {restored_count}")
        print(f"  Documents skipped:  {skipped_count}")
        print(f"\nNext step: Run entity extraction:")
        print(f"  python examples/backfill_knowledge_graph.py --batch-size 10")
        print("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
