from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
import structlog

log = structlog.get_logger(__name__)


class PGGateway(Protocol):
    async def fetch_indexed_document_ids(self) -> set[str]: ...
    async def fetch_entity_counts(self) -> dict[str, int]: ...


class Neo4jGateway(Protocol):
    async def fetch_document_node_ids(self) -> set[str]: ...
    async def fetch_entity_counts(self) -> dict[str, int]: ...
    async def fetch_nodes_missing_tenant(self) -> list[str]: ...
    async def delete_orphan_documents(self, doc_ids: set[str]) -> int: ...


@dataclass
class KGSyncResult:
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    orphan_count: int = 0
    missing_count: int = 0
    drift_count: int = 0
    fixed_count: int = 0
    status: str = "running"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class KGSyncService:
    DRIFT_THRESHOLD = 5  # absolute entity-count delta per doc to flag

    def __init__(self, pg: PGGateway, neo4j: Neo4jGateway, *, auto_repair: bool) -> None:
        self.pg = pg
        self.neo4j = neo4j
        self.auto_repair = auto_repair

    async def run(self, *, run_id: str) -> KGSyncResult:
        result = KGSyncResult(run_id=run_id, started_at=datetime.now(timezone.utc))
        try:
            pg_docs = await self.pg.fetch_indexed_document_ids()
            kg_docs = await self.neo4j.fetch_document_node_ids()

            orphans = kg_docs - pg_docs
            missing = pg_docs - kg_docs
            result.orphan_count = len(orphans)
            result.missing_count = len(missing)
            result.metadata["orphan_doc_ids"] = sorted(orphans)[:50]
            result.metadata["missing_doc_ids"] = sorted(missing)[:50]

            pg_counts = await self.pg.fetch_entity_counts()
            kg_counts = await self.neo4j.fetch_entity_counts()
            drift_docs = [
                d for d in pg_counts.keys() | kg_counts.keys()
                if abs(pg_counts.get(d, 0) - kg_counts.get(d, 0)) >= self.DRIFT_THRESHOLD
            ]
            result.drift_count = len(drift_docs)
            result.metadata["drift_doc_ids"] = sorted(drift_docs)[:50]

            untenanted = await self.neo4j.fetch_nodes_missing_tenant()
            result.metadata["untenanted_node_ids"] = untenanted[:50]
            result.metadata["untenanted_total"] = len(untenanted)

            if self.auto_repair and orphans:
                result.fixed_count = await self.neo4j.delete_orphan_documents(orphans)

            result.status = "success"
        except Exception as exc:
            log.exception("kg_sync_failed", run_id=run_id)
            result.status = "failed"
            result.error = str(exc)
        finally:
            result.completed_at = datetime.now(timezone.utc)
        return result
