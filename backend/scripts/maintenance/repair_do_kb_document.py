#!/usr/bin/env python3
"""Repair a document that failed to index in DO KB.

Usage:
    # Repair a specific document by ID:
    python scripts/maintenance/repair_do_kb_document.py --document-id 71bd17fe-fe6b-40c0-8c05-faba933de6dd

    # Dry-run (show what would change, don't commit):
    python scripts/maintenance/repair_do_kb_document.py --document-id <id> --dry-run

    # Find and repair all documents with content_text but no do_kb_data_source_uuid:
    python scripts/maintenance/repair_do_kb_document.py --find-orphans

What this script does (for a single document):
1. Loads the document from the DB.
2. If content_text is empty, re-extracts text from the source file (PyMuPDF).
3. Calls unsync_document_from_kb (deletes the old data source from DO KB).
4. Calls sync_document_to_kb (uploads canonical .txt, creates new data source).
5. Triggers a re-index on the KB.

Must be run from the backend directory with the virtualenv active.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path

# Make `src` importable when run as `python scripts/maintenance/repair_do_kb_document.py`
# (backend root is two parents up: scripts/maintenance/<file> → backend/).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)


async def repair_document(document_id: str, *, dry_run: bool = False) -> dict:
    """Repair a single document's DO KB indexing.

    Returns a dict with the repair result.
    """
    from src.core.database import AsyncSessionLocal
    from src.models.document import Document, ProcessingStatus
    from src.services.do_kb import sync_document_to_kb, unsync_document_from_kb

    async with AsyncSessionLocal() as session:
        doc = await session.get(Document, uuid.UUID(document_id))
        if doc is None:
            logger.error("Document %s not found", document_id)
            return {"document_id": document_id, "status": "not_found"}

        result = {
            "document_id": document_id,
            "title": doc.title,
            "had_content_text": bool(doc.content_text),
            "had_do_kb_uuid": bool(doc.do_kb_data_source_uuid),
        }

        # Step 1: Ensure content_text is populated
        if not doc.content_text:
            logger.info("Re-extracting text for document %s", document_id)
            try:
                from src.services.documents.storage_utils import (
                    local_file_for_document,
                )
                from src.services.documents.file_service import FileService

                file_service = FileService()
                with local_file_for_document(doc) as file_path:
                    text = file_service._extract_text_from_path(file_path, doc)

                if text:
                    doc.content_text = text
                    logger.info(
                        "Extracted %d characters for document %s",
                        len(text), document_id,
                    )
                    result["extracted_chars"] = len(text)
                else:
                    logger.error(
                        "Text extraction returned empty for document %s",
                        document_id,
                    )
                    result["status"] = "extraction_failed"
                    return result
            except Exception as exc:
                logger.error("Text extraction failed: %s", exc)
                result["status"] = "extraction_error"
                result["error"] = str(exc)
                return result

        if dry_run:
            result["status"] = "dry_run"
            return result

        # Step 2: Remove the old (failing) data source from DO KB
        if doc.do_kb_data_source_uuid:
            logger.info(
                "Unsyncing document %s (ds_uuid=%s)",
                document_id, doc.do_kb_data_source_uuid,
            )
            await unsync_document_from_kb(session, doc)
            await session.refresh(doc)

        # Step 3: Re-sync with the canonical .txt path
        logger.info("Re-syncing document %s to DO KB", document_id)
        ds_uuid = await sync_document_to_kb(session, doc)

        if ds_uuid:
            doc.is_embedded = True
            doc.processing_status = ProcessingStatus.COMPLETED
            await session.commit()
            result["status"] = "repaired"
            result["new_ds_uuid"] = ds_uuid
            logger.info("Document %s repaired successfully", document_id)
        else:
            result["status"] = "sync_failed"
            logger.error("Re-sync failed for document %s", document_id)

        return result


async def find_orphans() -> list[dict]:
    """Find documents with content_text but no do_kb_data_source_uuid."""
    from sqlalchemy import select
    from src.core.database import AsyncSessionLocal
    from src.models.document import Document, ProcessingStatus

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Document.id, Document.title)
            .where(
                Document.content_text.isnot(None),
                Document.content_text != "",
                Document.do_kb_data_source_uuid.is_(None),
                Document.processing_status == ProcessingStatus.COMPLETED,
                Document.is_deleted.is_(False),
            )
            .limit(100)
        )
        rows = await session.execute(stmt)
        return [
            {"document_id": str(row.id), "title": row.title}
            for row in rows
        ]


def main():
    parser = argparse.ArgumentParser(
        description="Repair DO KB indexing for a document"
    )
    parser.add_argument(
        "--document-id", type=str, help="Document UUID to repair"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without committing",
    )
    parser.add_argument(
        "--find-orphans",
        action="store_true",
        help="List documents with content but no DO KB data source",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.find_orphans:
        orphans = asyncio.run(find_orphans())
        if orphans:
            print(f"\nFound {len(orphans)} orphaned documents:")
            for o in orphans:
                print(f"  {o['document_id']}  {o['title']}")
            print(f"\nRepair with: python scripts/maintenance/repair_do_kb_document.py --document-id <id>")
        else:
            print("No orphaned documents found.")
        return

    if not args.document_id:
        parser.error("--document-id is required (or use --find-orphans)")

    result = asyncio.run(repair_document(args.document_id, dry_run=args.dry_run))
    print(f"\nResult: {result}")
    sys.exit(0 if result.get("status") in ("repaired", "dry_run") else 1)


if __name__ == "__main__":
    main()
