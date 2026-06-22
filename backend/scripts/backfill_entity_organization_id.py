"""Backfill organization_id on legacy NULL-org :Entity nodes (KG Phase 2 gate).

Phase 2 (#842) makes organization_id part of the entity MERGE identity
(canonical_key, type, organization_id). Entities written before Phase 1 have
organization_id = NULL, so after the key change a re-ingest for org X would NOT
match them (NULL != "X") and would create a DUPLICATE node, stranding the
legacy one. This one-off backfill stamps every NULL-org entity so it lines up
with the new identity:

  - Derive the org from the entity's source_document_id -> Document.organization_id
    (Postgres). This adopts the legacy node into its real owning org, so the next
    ingest dedups onto it.
  - Fall back to "" (the same sentinel new org-less writes use) when the org
    can't be derived, so NULL and "" org-less identities don't split.

Idempotent: only touches nodes whose organization_id IS NULL. Safe to re-run.

Run ONCE on the target Neo4j BEFORE (or immediately as part of) the #842
rollout, so re-ingests dedup onto existing nodes instead of duplicating.

Usage:
    python scripts/backfill_entity_organization_id.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.models.document import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _doc_org_map(source_document_ids: List[str]) -> Dict[str, str]:
    """Map source_document_id -> organization_id from Postgres."""
    if not source_document_ids:
        return {}
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document.id, Document.organization_id).where(
                Document.id.in_(source_document_ids)
            )
        )
        return {
            str(doc_id): str(org_id)
            for doc_id, org_id in result.all()
            if org_id is not None
        }


async def backfill(dry_run: bool) -> int:
    driver = GraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    try:
        with driver.session() as session:
            null_nodes = session.run(
                "MATCH (e:Entity) WHERE e.organization_id IS NULL "
                "RETURN e.id AS id, e.source_document_id AS sdid"
            ).data()
            logger.info("Found %d entities with NULL organization_id", len(null_nodes))
            if not null_nodes:
                logger.info("Nothing to backfill.")
                return 0

            sdids = sorted({n["sdid"] for n in null_nodes if n["sdid"]})
            org_map = await _doc_org_map(sdids)

            rows = [
                {"id": n["id"], "org": org_map.get(n["sdid"]) or ""}
                for n in null_nodes
            ]
            derived = sum(1 for r in rows if r["org"])
            logger.info(
                "Derived a real org for %d node(s); '' sentinel for %d node(s)",
                derived,
                len(rows) - derived,
            )

            if dry_run:
                logger.info("--dry-run: no writes performed.")
                return 0

            session.run(
                "UNWIND $rows AS row "
                "MATCH (e:Entity {id: row.id}) "
                "SET e.organization_id = row.org",
                {"rows": rows},
            )
            remaining = session.run(
                "MATCH (e:Entity) WHERE e.organization_id IS NULL "
                "RETURN count(e) AS c"
            ).single()["c"]
            if remaining == 0:
                logger.info("SUCCESS: all entities now carry organization_id.")
            else:
                logger.warning("%d entities still have NULL organization_id", remaining)
            return 0
    finally:
        driver.close()
        logger.info("Neo4j connection closed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(backfill(args.dry_run)))
