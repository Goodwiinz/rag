"""One-time migration: backfill organization_id onto Entity nodes (audit #50).

KG queries scope by `e.source_document_id IN $org_doc_ids`, shipping a (large)
per-request IN-list to Neo4j. Stamping `organization_id` directly on nodes lets
queries filter `e.organization_id = $org` instead. New writes already stamp it
(create_entity / batch); this backfills existing nodes by joining each node's
source_document_id to the Postgres Document.organization_id.

Phases:
  1. Backfill — for each Entity with a source_document_id but no organization_id,
     look up the document's organization_id in Postgres and SET it (batched).
  2. Index — create entity_organization_index (idempotent).
  3. Report — counts of stamped / still-NULL (orphans with no/unknown source doc).

USAGE (needs live Neo4j + Postgres):
    python -m scripts.maintenance.backfill_entity_organization_id            # apply
    python -m scripts.maintenance.backfill_entity_organization_id --dry-run

Run on each populated env BEFORE flipping read queries from the IN-list to the
`e.organization_id = $org` filter (PR B part 2 — staging-gated).
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import select

from src.core.database import get_db
from src.models.document import Document
from src.services.knowledge_graph.knowledge_graph_service import (
    knowledge_graph_service,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_org_id")

_BATCH = 1000


def _doc_org_map(db) -> dict[str, str]:
    """document_id -> organization_id for all documents."""
    rows = db.execute(select(Document.id, Document.organization_id)).all()
    return {str(did): str(oid) for did, oid in rows if oid is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    knowledge_graph_service._connect()
    if not knowledge_graph_service.driver:
        logger.error("No Neo4j connection.")
        return 1

    db = next(get_db())
    try:
        doc_org = _doc_org_map(db)
    finally:
        db.close()
    logger.info("Loaded %d document→org mappings", len(doc_org))

    with knowledge_graph_service.driver.session() as session:
        need = session.run(
            "MATCH (e:Entity) WHERE e.organization_id IS NULL AND e.source_document_id IS NOT NULL "
            "RETURN count(e) AS c"
        ).single()["c"]
        logger.info("Phase 1: %d entities need organization_id", need)

        if not args.dry_run and need:
            # Build (source_document_id -> org) rows and SET in one UNWIND.
            rows = [{"doc": d, "org": o} for d, o in doc_org.items()]
            for start in range(0, len(rows), _BATCH):
                batch = rows[start : start + _BATCH]
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (e:Entity {source_document_id: row.doc})
                    WHERE e.organization_id IS NULL
                    SET e.organization_id = row.org
                    """,
                    {"rows": batch},
                )

        if not args.dry_run:
            try:
                session.run(
                    "CREATE INDEX entity_organization_index IF NOT EXISTS FOR (e:Entity) ON (e.organization_id)"
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Index create: %s", e)

        stamped = session.run(
            "MATCH (e:Entity) WHERE e.organization_id IS NOT NULL RETURN count(e) AS c"
        ).single()["c"]
        orphans = session.run(
            "MATCH (e:Entity) WHERE e.organization_id IS NULL RETURN count(e) AS c"
        ).single()["c"]
        logger.info(
            "Phase 3: %d stamped, %d still NULL (orphans / unknown source doc)%s",
            stamped,
            orphans,
            " [dry-run]" if args.dry_run else "",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
