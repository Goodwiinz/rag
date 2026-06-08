"""One-time migration: backfill canonical_key + dedup Entity nodes.

Prerequisite for PR #623's idempotent entity MERGE. That change keys entities
on a NEW property `canonical_key` (= lower(trim(name))) and adds a uniqueness
constraint on (canonical_key, type). Existing graphs predate the property and
contain duplicate nodes for the same real-world entity, so:

  1. The constraint cannot be created until duplicates are collapsed.
  2. Existing nodes have no canonical_key, so new MERGEs would not match them
     (creating yet more duplicates) until they are backfilled.

This script fixes both, then creates the constraint + indexes. Idempotent and
safe to re-run.

Phases:
  1. Backfill   — set e.canonical_key = toLower(trim(e.name)) where missing.
  2. Dedup      — per (canonical_key, type) group, keep the highest-confidence
                  survivor, merge the duplicates' relationships onto it, delete
                  the duplicates (apoc.refactor.mergeNodes; preserves rels+props).
  3. Constraints— create entity_canonical_unique + supporting indexes.
  4. Validate   — assert no remaining (canonical_key, type) duplicates.

USAGE (needs a live Neo4j + APOC):
    python -m scripts.maintenance.dedup_entities_add_canonical_key            # apply
    python -m scripts.maintenance.dedup_entities_add_canonical_key --dry-run  # report only

Run as a deploy step for PR #623 on each populated environment BEFORE the new
MERGE write-path takes traffic. APOC is required for phase 2 (the codebase
already relies on apoc.path elsewhere); the script aborts with instructions if
it is absent.
"""
from __future__ import annotations

import argparse
import logging
import sys

from src.services.knowledge_graph.knowledge_graph_service import (
    knowledge_graph_service,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dedup_entities")


def _apoc_available(session) -> bool:
    try:
        rec = session.run(
            "RETURN apoc.version() AS v"
        ).single()
        return rec is not None
    except Exception:
        return False


def _count(session, cypher: str, **params) -> int:
    rec = session.run(cypher, **params).single()
    return int(rec[0]) if rec and rec[0] is not None else 0


def backfill_canonical_key(session, dry_run: bool) -> int:
    """Set canonical_key = lower(trim(name)) on every Entity missing it."""
    missing = _count(
        session,
        "MATCH (e:Entity) WHERE e.canonical_key IS NULL AND e.name IS NOT NULL RETURN count(e)",
    )
    logger.info("Phase 1 backfill: %d entities missing canonical_key", missing)
    if dry_run or missing == 0:
        return missing
    session.run(
        """
        MATCH (e:Entity)
        WHERE e.canonical_key IS NULL AND e.name IS NOT NULL
        SET e.canonical_key = toLower(trim(e.name))
        """
    )
    return missing


def find_duplicate_groups(session):
    """Return [(canonical_key, type, [ids... highest-confidence first])]."""
    result = session.run(
        """
        MATCH (e:Entity)
        WHERE e.canonical_key IS NOT NULL AND e.type IS NOT NULL
        WITH e.canonical_key AS ck, e.type AS t, collect(e) AS nodes
        WHERE size(nodes) > 1
        RETURN ck AS canonical_key, t AS type,
               [n IN nodes | n.id] AS ids,
               [n IN nodes | coalesce(n.confidence_score, 0.0)] AS confidences
        """
    )
    groups = []
    for rec in result:
        pairs = sorted(
            zip(rec["ids"], rec["confidences"]),
            key=lambda p: (p[1] if p[1] is not None else 0.0),
            reverse=True,
        )
        ordered_ids = [pid for pid, _ in pairs]
        groups.append((rec["canonical_key"], rec["type"], ordered_ids))
    return groups


def dedup(session, dry_run: bool) -> int:
    """Collapse each (canonical_key, type) group onto its highest-confidence
    survivor via apoc.refactor.mergeNodes (preserves relationships + props)."""
    groups = find_duplicate_groups(session)
    total_dups = sum(len(ids) - 1 for _, _, ids in groups)
    logger.info(
        "Phase 2 dedup: %d duplicate group(s), %d node(s) to merge away",
        len(groups),
        total_dups,
    )
    if dry_run:
        for ck, t, ids in groups[:25]:
            logger.info("  would merge %d nodes for (%r, %r)", len(ids), ck, t)
        return total_dups

    for _ck, _t, ids in groups:
        # ids[0] is the survivor (highest confidence). mergeNodes merges the
        # rest INTO the first element of the list and rewires relationships.
        session.run(
            """
            UNWIND $ids AS nid MATCH (e:Entity {id: nid}) WITH collect(e) AS nodes
            CALL apoc.refactor.mergeNodes(
                nodes,
                {properties: 'discard', mergeRels: true}
            ) YIELD node
            RETURN node.id
            """,
            ids=ids,
        )
    return total_dups


def ensure_constraints(session, dry_run: bool) -> None:
    stmts = [
        "CREATE CONSTRAINT entity_canonical_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.canonical_key, e.type) IS UNIQUE",
        "CREATE INDEX entity_canonical_key_index IF NOT EXISTS FOR (e:Entity) ON (e.canonical_key)",
        "CREATE INDEX entity_source_doc_index IF NOT EXISTS FOR (e:Entity) ON (e.source_document_id)",
    ]
    logger.info("Phase 3 constraints/indexes: %d statement(s)", len(stmts))
    if dry_run:
        return
    for stmt in stmts:
        try:
            session.run(stmt)
            logger.info("  applied: %s", stmt.split(" IF NOT EXISTS")[0])
        except Exception as e:  # noqa: BLE001
            logger.error("  FAILED: %s -> %s", stmt, e)
            raise


def validate(session) -> int:
    remaining = _count(
        session,
        """
        MATCH (e:Entity) WHERE e.canonical_key IS NOT NULL AND e.type IS NOT NULL
        WITH e.canonical_key AS ck, e.type AS t, count(e) AS c
        WHERE c > 1 RETURN count(*)
        """,
    )
    logger.info("Phase 4 validate: %d remaining duplicate group(s)", remaining)
    return remaining


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only, no writes")
    args = parser.parse_args()

    knowledge_graph_service._connect()
    if not knowledge_graph_service.driver:
        logger.error("No Neo4j connection.")
        return 1

    with knowledge_graph_service.driver.session() as session:
        backfill_canonical_key(session, args.dry_run)
        if not args.dry_run and not _apoc_available(session):
            logger.error(
                "APOC not available — phase 2 needs apoc.refactor.mergeNodes. "
                "Install the APOC plugin or run dedup manually, then re-run."
            )
            return 2
        dedup(session, args.dry_run)
        ensure_constraints(session, args.dry_run)
        if not args.dry_run:
            remaining = validate(session)
            if remaining:
                logger.error("Dedup incomplete: %d group(s) still duplicated", remaining)
                return 3
    logger.info("Done%s.", " (dry-run)" if args.dry_run else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
