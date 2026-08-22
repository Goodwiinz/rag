"""Backfill organization_id on legacy NULL-org :Citation nodes.

``CitationGraphService.get_citation_graph`` now hard-requires an
organization_id and post-filters every returned node on it. Every :Citation
node written by older code carries organization_id = NULL, so without this
backfill legacy citation graphs render completely empty.

Resolution chain per NULL-org node:

  1. node.document_id  -> documents.organization_id
  2. node.citation_id  -> citations.id -> citations.document_id
                       -> documents.organization_id
     (the Postgres `citations` table has no org column of its own)

Unattributable nodes are left NULL and reported. Fail closed: unlike the entity
backfill there is no "" sentinel, because "" matches no real org on read and
would only hide the fact that a node is unowned.

Idempotent: only touches nodes whose organization_id IS NULL. Safe to re-run.

Usage:
    python scripts/backfill_citation_organization_id.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase  # noqa: E402
from sqlalchemy import select  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.core.database import AsyncSessionLocal  # noqa: E402
from src.models.citation import Citation  # noqa: E402
from src.models.document import Document  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _doc_org_map(document_ids: List[str]) -> Dict[str, str]:
    """Map document_id -> organization_id from Postgres."""
    if not document_ids:
        return {}
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document.id, Document.organization_id).where(
                Document.id.in_(document_ids)
            )
        )
        return {
            str(doc_id): str(org_id)
            for doc_id, org_id in result.all()
            if org_id is not None
        }


async def _citation_doc_map(citation_ids: List[str]) -> Dict[str, str]:
    """Map citation_id -> document_id from Postgres (citations has no org)."""
    if not citation_ids:
        return {}
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Citation.id, Citation.document_id).where(
                Citation.id.in_(citation_ids)
            )
        )
        return {
            str(cid): str(doc_id) for cid, doc_id in result.all() if doc_id is not None
        }


async def _resolve_orgs(batch: List[Dict[str, Any]]) -> Dict[str, str]:
    """Resolve citation_id -> organization_id for one batch of graph nodes."""
    # Step 1: direct node.document_id -> documents.organization_id
    direct_docs = sorted({n["doc_id"] for n in batch if n["doc_id"]})
    org_by_doc = await _doc_org_map(direct_docs)

    resolved: Dict[str, str] = {}
    unresolved: List[str] = []
    for node in batch:
        org = org_by_doc.get(node["doc_id"]) if node["doc_id"] else None
        if org:
            resolved[node["citation_id"]] = org
        else:
            unresolved.append(node["citation_id"])

    # Step 2: node.citation_id -> citations.document_id -> documents
    if unresolved:
        doc_by_citation = await _citation_doc_map(unresolved)
        org_by_doc2 = await _doc_org_map(sorted(set(doc_by_citation.values())))
        for citation_id, doc_id in doc_by_citation.items():
            org = org_by_doc2.get(doc_id)
            if org:
                resolved[citation_id] = org

    return resolved


def _null_org_count(session: Any) -> int:
    """Count :Citation nodes still missing an organization_id."""
    record = session.run(
        "MATCH (c:Citation) WHERE c.organization_id IS NULL RETURN count(c) AS c"
    ).single()
    return int(record["c"]) if record else 0


async def backfill(dry_run: bool, batch_size: int) -> int:
    driver = GraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    try:
        with driver.session() as session:
            total = _null_org_count(session)
            logger.info("Found %d citations with NULL organization_id", total)
            if total == 0:
                logger.info("Nothing to backfill.")
                return 0

            processed = derived_total = 0
            while True:
                # Read a bounded batch. On a real run the resolved nodes leave
                # the NULL set, so a plain LIMIT advances; unresolved ones stay
                # NULL, so page past them with SKIP (as on a dry-run, where
                # nothing changes at all).
                batch = session.run(
                    "MATCH (c:Citation) WHERE c.organization_id IS NULL "
                    "RETURN c.citation_id AS citation_id, c.document_id AS doc_id "
                    "SKIP $skip LIMIT $limit",
                    {
                        "skip": processed if dry_run else processed - derived_total,
                        "limit": batch_size,
                    },
                ).data()
                if not batch:
                    break

                resolved = await _resolve_orgs(batch)
                rows = [
                    {"citation_id": cid, "org": org} for cid, org in resolved.items()
                ]
                derived_total += len(rows)
                processed += len(batch)

                if not dry_run and rows:
                    session.run(
                        "UNWIND $rows AS row "
                        "MATCH (c:Citation {citation_id: row.citation_id}) "
                        "SET c.organization_id = row.org",
                        {"rows": rows},
                    )
                logger.info("Processed %d/%d", processed, total)
                if processed >= total:
                    break

            logger.info(
                "Derived a real org for %d node(s); %d node(s) unattributable "
                "(left NULL — they stay invisible to org-scoped reads)",
                derived_total,
                processed - derived_total,
            )
            if dry_run:
                logger.info("--dry-run: no writes performed.")
                return 0

            remaining = _null_org_count(session)
            if remaining == 0:
                logger.info("SUCCESS: all citations now carry organization_id.")
            else:
                logger.warning(
                    "%d citation(s) still have NULL organization_id "
                    "(no document to attribute them to)",
                    remaining,
                )
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
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Nodes (and Postgres lookups) per batch. Default 1000.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(backfill(args.dry_run, args.batch_size)))
