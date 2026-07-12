"""CLI: repair/re-sync the Neo4j knowledge graph from stored document text.

Thin wrapper over the extracted idempotent core
``src.services.knowledge_graph.repair.repair_document_graph`` (audit D1 /
P2.3) — the same function the scheduled satellite reconciler
(``src.tasks.reconcile_tasks``) uses to re-drive documents whose ingestion
fan-out recorded ``neo4j_index_status='failed'``. Do not re-implement the
per-document logic here.

Usage:
  python -m scripts.repair_kg            # every document with content_text
  python -m scripts.repair_kg --failed   # only documents marked failed

Each processed document's ``neo4j_index_status`` / ``neo4j_indexed_at`` is
updated to the honest outcome, so a CLI run also clears reconciler backlog.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

# Add the parent directory to sys.path to allow imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import base models first to ensure registry is populated
from src.models import *  # noqa: F401,F403 - triggers import of many models

from src.core.database import SessionLocal
from src.models.document import Document
from src.services.knowledge_graph.knowledge_graph_service import (
    knowledge_graph_service,
)
from src.services.knowledge_graph.repair import repair_document_graph
from src.shared.enums import SatelliteSyncStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--failed",
        action="store_true",
        help="Only repair documents with neo4j_index_status='failed'",
    )
    args = parser.parse_args()

    logger.info("Starting Knowledge Graph Repair/Sync...")

    # One shared spaCy service for the whole run (model load is heavy).
    from src.services.processing.entity_extraction_service import (
        EntityExtractionService,
    )

    extraction_service = EntityExtractionService()

    db = SessionLocal()
    try:
        total_docs = db.query(Document).count()
        logger.info(f"Total documents in DB: {total_docs}")

        query = db.query(Document).filter(
            Document.content_text.isnot(None),
            Document.is_deleted == False,  # noqa: E712
        )
        if args.failed:
            query = query.filter(
                Document.neo4j_index_status == SatelliteSyncStatus.FAILED.value
            )
        documents = query.all()
        logger.info(f"Found {len(documents)} documents to repair.")

        repaired = 0
        failed = 0
        for doc in documents:
            logger.info(f"Processing document: {doc.title} ({doc.id})")
            outcome = repair_document_graph(
                doc,
                extraction_service=extraction_service,
                kg_service=knowledge_graph_service,
            )
            logger.info(
                "KG repair result for %s (org %s): entities %s/%s, "
                "relationships %s, errors %s%s",
                doc.id,
                doc.organization_id,
                outcome.entities_created,
                outcome.entities_found,
                outcome.relationships_created,
                outcome.errors,
                f", error={outcome.error_message}" if outcome.error_message else "",
            )
            # Record the honest per-satellite outcome (audit D1) so the
            # reconciler and this CLI stay in agreement.
            if outcome.ok:
                doc.neo4j_index_status = SatelliteSyncStatus.COMPLETED.value
                doc.neo4j_indexed_at = datetime.now(timezone.utc)
                repaired += 1
            else:
                doc.neo4j_index_status = SatelliteSyncStatus.FAILED.value
                failed += 1
            db.commit()

        logger.info(f"Done: {repaired} repaired, {failed} still failed.")
    finally:
        db.close()
        knowledge_graph_service.close()


if __name__ == "__main__":
    main()
