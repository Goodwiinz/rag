# Knowledge Graph Sync — Trigger.dev Scheduled Task Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Trigger.dev scheduled task that periodically reconciles Postgres ↔ Neo4j knowledge graph state, detecting and (optionally) repairing drift.

**Architecture:** A `schedules.task` runs every 6h, calling a new internal backend endpoint `POST /api/v1/infrastructure/kg-sync`. The backend `KGSyncService` runs four checks (orphan KG nodes, missing KG nodes, entity-count drift, tenant-id presence), writes a run record to a new `kg_sync_runs` audit table, and conditionally repairs drift based on `KG_SYNC_AUTO_REPAIR` env. Prometheus metrics + structlog correlation IDs surface results.

**Tech Stack:** Trigger.dev v3 SDK (TypeScript), FastAPI, Alembic, SQLAlchemy 2.x async, Neo4j Python driver, Prometheus client, pytest + pytest-asyncio.

**Conventions referenced:**

- Trigger pattern: `src/trigger/scheduled/health-check.ts` (existing example)
- Backend client: `src/trigger/_lib/backend-client.ts` (use `backendClient.post`)
- Service layout: `backend/src/services/knowledge_graph/` (existing dir)
- Migration style: `backend/alembic/versions/` (current head: `v0a1b2c3d4e5`)
- Internal-ish endpoints live under `backend/src/api/infrastructure/`
- Service-role auth via `SUPABASE_SERVICE_ROLE_KEY` (handled by backend-client)
- Test layout: `backend/tests/unit/services/test_*.py` + integration variant

---

## Task 1: Alembic migration — `kg_sync_runs` table

**Files:**

- Create: `backend/alembic/versions/w1b2c3d4e5f6_add_kg_sync_runs.py`
- Test: `backend/tests/unit/test_kg_sync_runs_migration.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_kg_sync_runs_migration.py
import pytest
from sqlalchemy import inspect

@pytest.mark.asyncio
async def test_kg_sync_runs_table_exists(db_session):
    def _inspect(conn):
        insp = inspect(conn)
        assert "kg_sync_runs" in insp.get_table_names()
        cols = {c["name"] for c in insp.get_columns("kg_sync_runs")}
        assert {
            "id", "run_id", "started_at", "completed_at",
            "orphan_count", "missing_count", "drift_count",
            "fixed_count", "status", "error", "run_metadata",
        }.issubset(cols)
    await db_session.run_sync(lambda s: _inspect(s.connection()))
```

**Step 2: Run test, verify it fails**

```bash
cd backend && pytest tests/unit/test_kg_sync_runs_migration.py -v
```

Expected: FAIL — table missing.

**Step 3: Write migration**

```python
# backend/alembic/versions/w1b2c3d4e5f6_add_kg_sync_runs.py
"""add kg_sync_runs

Revision ID: w1b2c3d4e5f6
Revises: v0a1b2c3d4e5
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "w1b2c3d4e5f6"
down_revision = "v0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kg_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"),
                  primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=False, unique=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("orphan_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("drift_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fixed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("run_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','success','failed')",
            name="kg_sync_runs_status_check",
        ),
    )
    op.create_index("ix_kg_sync_runs_started_at", "kg_sync_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_kg_sync_runs_started_at", table_name="kg_sync_runs")
    op.drop_table("kg_sync_runs")
```

**Step 4: Apply migration + re-run test**

```bash
cd backend && alembic upgrade head
pytest tests/unit/test_kg_sync_runs_migration.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/alembic/versions/w1b2c3d4e5f6_add_kg_sync_runs.py \
        backend/tests/unit/test_kg_sync_runs_migration.py
git commit -m "feat(kg-sync): add kg_sync_runs audit table"
```

---

## Task 2: SQLAlchemy model for `KGSyncRun`

**Files:**

- Create: `backend/src/models/kg_sync_run.py`
- Modify: `backend/src/models/__init__.py` (add export)
- Test: `backend/tests/unit/models/test_kg_sync_run.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/models/test_kg_sync_run.py
import pytest
from datetime import datetime, timezone
from src.models.kg_sync_run import KGSyncRun

@pytest.mark.asyncio
async def test_kg_sync_run_insert_roundtrip(db_session):
    row = KGSyncRun(
        run_id="kg-sync-2026-05-21-test",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    assert row.id is not None
    assert row.orphan_count == 0
```

**Step 2: Run, verify FAIL** (module not found).

```bash
cd backend && pytest tests/unit/models/test_kg_sync_run.py -v
```

**Step 3: Implement model**

```python
# backend/src/models/kg_sync_run.py
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import CheckConstraint, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


class KGSyncRun(Base):
    __tablename__ = "kg_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','success','failed')",
            name="kg_sync_runs_status_check",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    orphan_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    drift_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    fixed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    run_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
```

Add export in `backend/src/models/__init__.py`:

```python
from src.models.kg_sync_run import KGSyncRun  # noqa: F401
```

**Step 4: Run test, verify PASS.**

```bash
cd backend && pytest tests/unit/models/test_kg_sync_run.py -v
```

**Step 5: Commit**

```bash
git add backend/src/models/kg_sync_run.py backend/src/models/__init__.py \
        backend/tests/unit/models/test_kg_sync_run.py
git commit -m "feat(kg-sync): add KGSyncRun ORM model"
```

---

## Task 3: `KGSyncService` skeleton + dry-run contract test

**Files:**

- Create: `backend/src/services/knowledge_graph/sync_service.py`
- Test: `backend/tests/unit/services/test_kg_sync_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/services/test_kg_sync_service.py
import pytest
from unittest.mock import AsyncMock
from src.services.knowledge_graph.sync_service import KGSyncService, KGSyncResult


@pytest.mark.asyncio
async def test_sync_returns_result_in_dry_run_mode():
    pg = AsyncMock()
    neo4j = AsyncMock()
    pg.fetch_indexed_document_ids.return_value = set()
    neo4j.fetch_document_node_ids.return_value = set()
    neo4j.fetch_entity_counts.return_value = {}
    pg.fetch_entity_counts.return_value = {}
    neo4j.fetch_nodes_missing_tenant.return_value = []

    svc = KGSyncService(pg=pg, neo4j=neo4j, auto_repair=False)
    result = await svc.run(run_id="test-run")

    assert isinstance(result, KGSyncResult)
    assert result.orphan_count == 0
    assert result.fixed_count == 0
    assert result.status == "success"
```

**Step 2: Run, verify FAIL.**

```bash
cd backend && pytest tests/unit/services/test_kg_sync_service.py -v
```

**Step 3: Implement skeleton**

```python
# backend/src/services/knowledge_graph/sync_service.py
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

            pg_counts = await self.pg.fetch_entity_counts()
            kg_counts = await self.neo4j.fetch_entity_counts()
            drift_docs = [
                d for d in pg_counts.keys() | kg_counts.keys()
                if abs(pg_counts.get(d, 0) - kg_counts.get(d, 0)) >= self.DRIFT_THRESHOLD
            ]
            result.drift_count = len(drift_docs)

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
```

**Step 4: Run, verify PASS.**

```bash
cd backend && pytest tests/unit/services/test_kg_sync_service.py -v
```

**Step 5: Commit**

```bash
git add backend/src/services/knowledge_graph/sync_service.py \
        backend/tests/unit/services/test_kg_sync_service.py
git commit -m "feat(kg-sync): scaffold KGSyncService with dry-run baseline"
```

---

## Task 4: Orphan detection + repair behavior tests

**Files:**

- Modify: `backend/tests/unit/services/test_kg_sync_service.py` (add cases)

**Step 1: Add failing tests**

```python
@pytest.mark.asyncio
async def test_sync_counts_orphans_when_kg_has_extra_docs():
    pg = AsyncMock()
    neo4j = AsyncMock()
    pg.fetch_indexed_document_ids.return_value = {"a", "b"}
    neo4j.fetch_document_node_ids.return_value = {"a", "b", "c", "d"}
    pg.fetch_entity_counts.return_value = {}
    neo4j.fetch_entity_counts.return_value = {}
    neo4j.fetch_nodes_missing_tenant.return_value = []

    svc = KGSyncService(pg=pg, neo4j=neo4j, auto_repair=False)
    result = await svc.run(run_id="t-orphans")

    assert result.orphan_count == 2
    assert result.fixed_count == 0
    neo4j.delete_orphan_documents.assert_not_called()


@pytest.mark.asyncio
async def test_sync_repairs_orphans_when_auto_repair_enabled():
    pg = AsyncMock()
    neo4j = AsyncMock()
    pg.fetch_indexed_document_ids.return_value = {"a"}
    neo4j.fetch_document_node_ids.return_value = {"a", "b", "c"}
    pg.fetch_entity_counts.return_value = {}
    neo4j.fetch_entity_counts.return_value = {}
    neo4j.fetch_nodes_missing_tenant.return_value = []
    neo4j.delete_orphan_documents.return_value = 2

    svc = KGSyncService(pg=pg, neo4j=neo4j, auto_repair=True)
    result = await svc.run(run_id="t-repair")

    assert result.orphan_count == 2
    assert result.fixed_count == 2
    neo4j.delete_orphan_documents.assert_awaited_once_with({"b", "c"})
```

**Step 2: Run, verify both PASS** (service already supports this from Task 3).

```bash
cd backend && pytest tests/unit/services/test_kg_sync_service.py -v
```

If any fail, fix `sync_service.py` minimally.

**Step 3: Commit**

```bash
git add backend/tests/unit/services/test_kg_sync_service.py \
        backend/src/services/knowledge_graph/sync_service.py
git commit -m "test(kg-sync): cover orphan detect + repair gating"
```

---

## Task 5: Drift + tenant-isolation test cases

**Files:**

- Modify: `backend/tests/unit/services/test_kg_sync_service.py`

**Step 1: Add failing tests**

```python
@pytest.mark.asyncio
async def test_sync_flags_entity_count_drift_above_threshold():
    pg = AsyncMock()
    neo4j = AsyncMock()
    pg.fetch_indexed_document_ids.return_value = {"a", "b", "c"}
    neo4j.fetch_document_node_ids.return_value = {"a", "b", "c"}
    pg.fetch_entity_counts.return_value = {"a": 10, "b": 20, "c": 3}
    neo4j.fetch_entity_counts.return_value = {"a": 10, "b": 4, "c": 3}
    neo4j.fetch_nodes_missing_tenant.return_value = []

    svc = KGSyncService(pg=pg, neo4j=neo4j, auto_repair=False)
    result = await svc.run(run_id="t-drift")

    assert result.drift_count == 1  # only doc "b" exceeds threshold


@pytest.mark.asyncio
async def test_sync_reports_untenanted_nodes_in_metadata():
    pg = AsyncMock()
    neo4j = AsyncMock()
    pg.fetch_indexed_document_ids.return_value = set()
    neo4j.fetch_document_node_ids.return_value = set()
    pg.fetch_entity_counts.return_value = {}
    neo4j.fetch_entity_counts.return_value = {}
    neo4j.fetch_nodes_missing_tenant.return_value = [f"node-{i}" for i in range(75)]

    svc = KGSyncService(pg=pg, neo4j=neo4j, auto_repair=False)
    result = await svc.run(run_id="t-tenant")

    assert result.metadata["untenanted_total"] == 75
    assert len(result.metadata["untenanted_node_ids"]) == 50
```

**Step 2: Run, verify PASS.**

```bash
cd backend && pytest tests/unit/services/test_kg_sync_service.py -v
```

**Step 3: Commit**

```bash
git add backend/tests/unit/services/test_kg_sync_service.py
git commit -m "test(kg-sync): cover drift threshold + tenant-id audit"
```

---

## Task 6: Postgres gateway adapter

**Files:**

- Create: `backend/src/services/knowledge_graph/gateways/pg_gateway.py`
- Create: `backend/src/services/knowledge_graph/gateways/__init__.py` (empty)
- Test: `backend/tests/integration/services/test_kg_pg_gateway.py`

**Step 1: Write the failing integration test**

```python
# backend/tests/integration/services/test_kg_pg_gateway.py
import pytest
from src.services.knowledge_graph.gateways.pg_gateway import PostgresKGGateway

@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_indexed_document_ids_returns_indexed_only(db_session, indexed_doc_factory, pending_doc_factory):
    indexed = await indexed_doc_factory()
    await pending_doc_factory()
    gw = PostgresKGGateway(session=db_session)
    ids = await gw.fetch_indexed_document_ids()
    assert str(indexed.id) in ids
    assert len(ids) == 1
```

**Step 2: Run, verify FAIL.**

```bash
cd backend && pytest tests/integration/services/test_kg_pg_gateway.py -v
```

**Step 3: Implement gateway**

```python
# backend/src/services/knowledge_graph/gateways/pg_gateway.py
from __future__ import annotations
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.document import Document
from src.models.entity import Entity  # adjust import to actual entity model


class PostgresKGGateway:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def fetch_indexed_document_ids(self) -> set[str]:
        result = await self.session.execute(
            select(Document.id).where(Document.status == "indexed")
        )
        return {str(row[0]) for row in result}

    async def fetch_entity_counts(self) -> dict[str, int]:
        result = await self.session.execute(
            select(Entity.document_id, func.count(Entity.id)).group_by(Entity.document_id)
        )
        return {str(doc_id): cnt for doc_id, cnt in result}
```

> **Note for executor:** Verify the actual entity model location with `grep -r "class Entity" backend/src/models/`. If named differently, adjust import + relationship column. If no `Entity` model exists yet, return `{}` and add a TODO comment — the drift check degrades gracefully.

**Step 4: Run integration test (requires `rag-postgres-1` running)**

```bash
cd backend && pytest tests/integration/services/test_kg_pg_gateway.py -v -m integration
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/knowledge_graph/gateways/
git add backend/tests/integration/services/test_kg_pg_gateway.py
git commit -m "feat(kg-sync): add Postgres gateway for KG reconciliation"
```

---

## Task 7: Neo4j gateway adapter

**Files:**

- Create: `backend/src/services/knowledge_graph/gateways/neo4j_gateway.py`
- Test: `backend/tests/integration/services/test_kg_neo4j_gateway.py`

**Step 1: Write the failing integration test**

```python
# backend/tests/integration/services/test_kg_neo4j_gateway.py
import pytest
from src.services.knowledge_graph.gateways.neo4j_gateway import Neo4jKGGateway

@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_document_node_ids_and_orphan_delete(neo4j_driver):
    async with neo4j_driver.session() as s:
        await s.run("MATCH (n) DETACH DELETE n")
        await s.run(
            "CREATE (:Document {document_id: 'a', tenant_id: 't1'}),"
            "       (:Document {document_id: 'b', tenant_id: 't1'})"
        )

    gw = Neo4jKGGateway(driver=neo4j_driver)
    ids = await gw.fetch_document_node_ids()
    assert ids == {"a", "b"}

    deleted = await gw.delete_orphan_documents({"b"})
    assert deleted == 1

    remaining = await gw.fetch_document_node_ids()
    assert remaining == {"a"}
```

**Step 2: Run, verify FAIL.**

```bash
cd backend && pytest tests/integration/services/test_kg_neo4j_gateway.py -v -m integration
```

**Step 3: Implement gateway**

```python
# backend/src/services/knowledge_graph/gateways/neo4j_gateway.py
from __future__ import annotations
from neo4j import AsyncDriver


class Neo4jKGGateway:
    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def fetch_document_node_ids(self) -> set[str]:
        async with self.driver.session() as s:
            result = await s.run(
                "MATCH (d:Document) RETURN d.document_id AS id"
            )
            return {record["id"] async for record in result if record["id"]}

    async def fetch_entity_counts(self) -> dict[str, int]:
        async with self.driver.session() as s:
            result = await s.run(
                "MATCH (d:Document)<-[:MENTIONED_IN]-(e:Entity) "
                "RETURN d.document_id AS doc_id, count(e) AS cnt"
            )
            return {r["doc_id"]: r["cnt"] async for r in result if r["doc_id"]}

    async def fetch_nodes_missing_tenant(self) -> list[str]:
        async with self.driver.session() as s:
            result = await s.run(
                "MATCH (n) WHERE n.tenant_id IS NULL "
                "RETURN coalesce(n.document_id, toString(elementId(n))) AS id LIMIT 1000"
            )
            return [r["id"] async for r in result]

    async def delete_orphan_documents(self, doc_ids: set[str]) -> int:
        if not doc_ids:
            return 0
        async with self.driver.session() as s:
            result = await s.run(
                "MATCH (d:Document) WHERE d.document_id IN $ids "
                "DETACH DELETE d RETURN count(d) AS deleted",
                ids=list(doc_ids),
            )
            record = await result.single()
            return int(record["deleted"]) if record else 0
```

> **Note:** Confirm actual relationship name (`MENTIONED_IN` vs `HAS_ENTITY` etc.) with `grep -ri "MERGE.*Entity" backend/src/services/knowledge_graph/`. Adjust before running.

**Step 4: Run, verify PASS.**

```bash
cd backend && pytest tests/integration/services/test_kg_neo4j_gateway.py -v -m integration
```

**Step 5: Commit**

```bash
git add backend/src/services/knowledge_graph/gateways/neo4j_gateway.py \
        backend/tests/integration/services/test_kg_neo4j_gateway.py
git commit -m "feat(kg-sync): add Neo4j gateway for KG reconciliation"
```

---

## Task 8: Internal API endpoint `POST /api/v1/infrastructure/kg-sync`

**Files:**

- Create: `backend/src/api/infrastructure/kg_sync.py`
- Modify: `backend/src/api/infrastructure/__init__.py` (register router)
- Test: `backend/tests/unit/api/test_kg_sync_endpoint.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/api/test_kg_sync_endpoint.py
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_kg_sync_endpoint_requires_service_role(client: AsyncClient):
    res = await client.post("/api/v1/infrastructure/kg-sync")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_kg_sync_endpoint_returns_result(service_role_client: AsyncClient):
    fake_result = AsyncMock()
    fake_result.run_id = "abc"
    fake_result.orphan_count = 0
    fake_result.missing_count = 0
    fake_result.drift_count = 0
    fake_result.fixed_count = 0
    fake_result.status = "success"
    with patch(
        "src.api.infrastructure.kg_sync._build_service"
    ) as build:
        build.return_value.run = AsyncMock(return_value=fake_result)
        res = await service_role_client.post(
            "/api/v1/infrastructure/kg-sync",
            headers={"X-Idempotency-Key": "kg-sync-2026-05-21-abc"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["run_id"] == "kg-sync-2026-05-21-abc"
```

**Step 2: Run, verify FAIL.**

```bash
cd backend && pytest tests/unit/api/test_kg_sync_endpoint.py -v
```

**Step 3: Implement endpoint**

```python
# backend/src/api/infrastructure/kg_sync.py
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import require_service_role  # adjust to actual dep
from src.api.dependencies.db import get_db_session
from src.models.kg_sync_run import KGSyncRun
from src.services.knowledge_graph.gateways.pg_gateway import PostgresKGGateway
from src.services.knowledge_graph.gateways.neo4j_gateway import Neo4jKGGateway
from src.services.knowledge_graph.sync_service import KGSyncService
from src.core.neo4j import get_neo4j_driver  # adjust to actual neo4j accessor

router = APIRouter(prefix="/infrastructure", tags=["infrastructure"])


def _build_service(session: AsyncSession) -> KGSyncService:
    return KGSyncService(
        pg=PostgresKGGateway(session=session),
        neo4j=Neo4jKGGateway(driver=get_neo4j_driver()),
        auto_repair=os.getenv("KG_SYNC_AUTO_REPAIR", "false").lower() == "true",
    )


@router.post("/kg-sync", dependencies=[Depends(require_service_role)])
async def run_kg_sync(
    session: AsyncSession = Depends(get_db_session),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    run_id = idempotency_key or f"kg-sync-{datetime.now(timezone.utc).isoformat()}-{uuid.uuid4().hex[:8]}"

    from sqlalchemy import select
    existing = await session.scalar(select(KGSyncRun).where(KGSyncRun.run_id == run_id))
    if existing:
        raise HTTPException(status_code=409, detail={"reason": "duplicate_run", "run_id": run_id})

    record = KGSyncRun(run_id=run_id, started_at=datetime.now(timezone.utc), status="running")
    session.add(record)
    await session.commit()

    svc = _build_service(session)
    result = await svc.run(run_id=run_id)

    record.completed_at = result.completed_at
    record.orphan_count = result.orphan_count
    record.missing_count = result.missing_count
    record.drift_count = result.drift_count
    record.fixed_count = result.fixed_count
    record.status = result.status
    record.error = result.error
    record.run_metadata = result.metadata
    await session.commit()

    return {
        "run_id": result.run_id,
        "status": result.status,
        "orphan_count": result.orphan_count,
        "missing_count": result.missing_count,
        "drift_count": result.drift_count,
        "fixed_count": result.fixed_count,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "error": result.error,
    }
```

In `backend/src/api/infrastructure/__init__.py`:

```python
from src.api.infrastructure.kg_sync import router as kg_sync_router
# then ensure included in the infrastructure aggregator router with .include_router(kg_sync_router)
```

> **Note:** Verify exact names of `require_service_role`, `get_db_session`, `get_neo4j_driver` by grepping existing infrastructure endpoints. Reuse, don't invent.

**Step 4: Run, verify PASS.**

```bash
cd backend && pytest tests/unit/api/test_kg_sync_endpoint.py -v
```

**Step 5: Commit**

```bash
git add backend/src/api/infrastructure/kg_sync.py \
        backend/src/api/infrastructure/__init__.py \
        backend/tests/unit/api/test_kg_sync_endpoint.py
git commit -m "feat(kg-sync): expose internal POST /infrastructure/kg-sync"
```

---

## Task 9: Prometheus metrics

**Files:**

- Modify: `backend/src/services/knowledge_graph/sync_service.py` (emit metrics in `run`)
- Modify: `backend/src/core/metrics.py` (register counters/histograms)
- Test: `backend/tests/unit/services/test_kg_sync_metrics.py`

**Step 1: Add metric definitions**

```python
# backend/src/core/metrics.py — APPEND
from prometheus_client import Counter, Histogram

kg_sync_drift_total = Counter(
    "kg_sync_drift_total",
    "Drift detected by KG sync runs.",
    ["drift_type"],
)
kg_sync_duration_seconds = Histogram(
    "kg_sync_duration_seconds",
    "Wall-clock duration of KG sync runs.",
)
kg_sync_runs_total = Counter(
    "kg_sync_runs_total",
    "Completed KG sync runs.",
    ["status"],
)
```

**Step 2: Write failing test**

```python
# backend/tests/unit/services/test_kg_sync_metrics.py
import pytest
from unittest.mock import AsyncMock
from prometheus_client import REGISTRY
from src.services.knowledge_graph.sync_service import KGSyncService


@pytest.mark.asyncio
async def test_sync_emits_drift_metrics():
    pg = AsyncMock()
    neo4j = AsyncMock()
    pg.fetch_indexed_document_ids.return_value = {"a"}
    neo4j.fetch_document_node_ids.return_value = {"a", "b"}
    pg.fetch_entity_counts.return_value = {}
    neo4j.fetch_entity_counts.return_value = {}
    neo4j.fetch_nodes_missing_tenant.return_value = []

    before = REGISTRY.get_sample_value("kg_sync_drift_total", {"drift_type": "orphan"}) or 0
    svc = KGSyncService(pg=pg, neo4j=neo4j, auto_repair=False)
    await svc.run(run_id="t-metrics")
    after = REGISTRY.get_sample_value("kg_sync_drift_total", {"drift_type": "orphan"}) or 0
    assert after - before == 1
```

**Step 3: Run, verify FAIL.**

```bash
cd backend && pytest tests/unit/services/test_kg_sync_metrics.py -v
```

**Step 4: Wire metrics into `sync_service.py`**

In `KGSyncService.run`, after `result.completed_at` is set:

```python
from src.core.metrics import (
    kg_sync_drift_total, kg_sync_duration_seconds, kg_sync_runs_total,
)
# ...
duration = (result.completed_at - result.started_at).total_seconds()
kg_sync_duration_seconds.observe(duration)
kg_sync_drift_total.labels(drift_type="orphan").inc(result.orphan_count)
kg_sync_drift_total.labels(drift_type="missing").inc(result.missing_count)
kg_sync_drift_total.labels(drift_type="entity_count").inc(result.drift_count)
kg_sync_runs_total.labels(status=result.status).inc()
```

**Step 5: Re-run + commit**

```bash
cd backend && pytest tests/unit/services/test_kg_sync_metrics.py tests/unit/services/test_kg_sync_service.py -v
git add backend/src/core/metrics.py backend/src/services/knowledge_graph/sync_service.py \
        backend/tests/unit/services/test_kg_sync_metrics.py
git commit -m "feat(kg-sync): emit prometheus drift + duration metrics"
```

---

## Task 10: Trigger.dev scheduled task

**Files:**

- Create: `src/trigger/scheduled/kg-sync.ts`
- Create: `src/trigger/_lib/schemas.ts` updates (add `KGSyncResponseSchema`)
- Test: `src/trigger/scheduled/__tests__/kg-sync.test.ts` (if test infra exists; otherwise skip and rely on dev-server smoke test in Task 11)

**Step 1: Add response schema**

Append to `src/trigger/_lib/schemas.ts`:

```ts
import { z } from "zod";

export const KGSyncResponseSchema = z.object({
  run_id: z.string(),
  status: z.enum(["running", "success", "failed"]),
  orphan_count: z.number().int(),
  missing_count: z.number().int(),
  drift_count: z.number().int(),
  fixed_count: z.number().int(),
  started_at: z.string(),
  completed_at: z.string().nullable(),
  error: z.string().nullable(),
});
export type KGSyncResponse = z.infer<typeof KGSyncResponseSchema>;
```

**Step 2: Create the task**

```ts
// src/trigger/scheduled/kg-sync.ts
import { logger, schedules } from "@trigger.dev/sdk/v3";
import { backendClient, BackendApiError } from "../_lib/backend-client";
import { KGSyncResponseSchema } from "../_lib/schemas";

export const kgSyncTask = schedules.task({
  id: "scheduled/kg-sync",
  cron: "0 */6 * * *",
  maxDuration: 900,
  retry: { maxAttempts: 3, factor: 2, minTimeoutInMs: 30_000 },
  run: async (payload, { ctx }) => {
    const dayKey = payload.timestamp.toISOString().slice(0, 10);
    const idempotencyKey = `kg-sync-${dayKey}-${ctx.run.id}`;

    logger.info("Starting KG sync", { idempotencyKey });

    try {
      const result = await backendClient.post(
        "/api/v1/infrastructure/kg-sync",
        {},
        KGSyncResponseSchema,
        { "X-Idempotency-Key": idempotencyKey },
      );

      logger.info("KG sync completed", {
        run_id: result.run_id,
        status: result.status,
        orphan_count: result.orphan_count,
        missing_count: result.missing_count,
        drift_count: result.drift_count,
        fixed_count: result.fixed_count,
      });

      if (result.status === "failed") {
        throw new Error(
          `KG sync reported failure: ${result.error ?? "unknown"}`,
        );
      }
      return result;
    } catch (err) {
      const message =
        err instanceof BackendApiError
          ? `HTTP ${err.status}: ${err.body}`
          : String(err);
      logger.error("KG sync request failed", { error: message });
      throw err;
    }
  },
});
```

**Step 3: Type-check**

```bash
pnpm tsc -p tsconfig.json --noEmit
```

Expected: no errors in `src/trigger/scheduled/kg-sync.ts` or `_lib/schemas.ts`.

**Step 4: Commit**

```bash
git add src/trigger/scheduled/kg-sync.ts src/trigger/_lib/schemas.ts
git commit -m "feat(kg-sync): add scheduled Trigger.dev task (6h cron)"
```

---

## Task 11: Dev-server smoke test + register in `trigger.config.ts`

**Files:**

- Modify: `trigger.config.ts` (only if its glob doesn't already pick up the new file — likely already does; verify)

**Step 1: Verify glob picks up new file**

```bash
grep -n "scheduled" trigger.config.ts
```

If the dirs config already includes `./src/trigger` or `./src/trigger/scheduled`, no change needed. Otherwise add `./src/trigger/scheduled/kg-sync.ts` explicitly.

**Step 2: Boot dev server**

```bash
pnpm dlx trigger.dev@latest dev
```

Expected: log line referencing `scheduled/kg-sync` task registered alongside existing tasks.

**Step 3: Trigger manually via MCP**

Use Trigger.dev MCP `trigger_task` with id `scheduled/kg-sync` (one-off invoke). Confirm:

- Backend receives POST at `/api/v1/infrastructure/kg-sync`
- A row appears in `kg_sync_runs` with `status='success'`
- Logs include `run_id`, drift counts

**Step 4: Verify metric scrape**

```bash
curl -s http://localhost:8000/metrics | grep kg_sync_
```

Expected: counters/histograms present and non-zero.

**Step 5: Commit (only if config was modified)**

```bash
git add trigger.config.ts
git commit -m "chore(kg-sync): ensure scheduled/kg-sync registered in trigger config"
```

---

## Task 12: Rollout doc + env flag wiring

**Files:**

- Create: `docs/runbooks/kg-sync.md`
- Modify: `.env.example` (add `KG_SYNC_AUTO_REPAIR=false`)

**Step 1: Add runbook**

````markdown
# docs/runbooks/kg-sync.md

# KG Sync Runbook

## Schedule

Cron `0 */6 * * *` (every 6h UTC). Trigger.dev task: `scheduled/kg-sync`.

## Env

- `KG_SYNC_AUTO_REPAIR` (default `false`). When `true`, orphan KG documents are detach-deleted.

## Rollout

1. **Dev** — repair off. Observe `kg_sync_drift_total` for 24h to set baseline.
2. **Staging** — repair on. Alert if `kg_sync_drift_total{drift_type="orphan"}` increases > 100 per run.
3. **Prod** — repair on once staging baseline is stable for 7 days.

## Manual run

```bash
# Service-role token required
curl -X POST https://api.<env>.gen-text.app/api/v1/infrastructure/kg-sync \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "X-Idempotency-Key: kg-sync-manual-$(date +%s)"
```
````

## Failure modes

- 401 → service-role token misconfigured on Trigger.dev side.
- 409 → idempotency-key collision; expected on same-day manual reruns.
- Status `failed` → check `kg_sync_runs.error` and structlog `kg_sync_failed`.

```

**Step 2: Update `.env.example`**

Append:
```

# KG sync (Trigger.dev scheduled task)

KG_SYNC_AUTO_REPAIR=false

````

**Step 3: Commit**

```bash
git add docs/runbooks/kg-sync.md .env.example
git commit -m "docs(kg-sync): add runbook + env flag default"
````

---

## Final verification checklist

Run all in order before opening PR:

```bash
# Backend
cd backend && alembic upgrade head
cd backend && pytest tests/unit/services/test_kg_sync_service.py \
                      tests/unit/services/test_kg_sync_metrics.py \
                      tests/unit/api/test_kg_sync_endpoint.py \
                      tests/unit/models/test_kg_sync_run.py \
                      tests/unit/test_kg_sync_runs_migration.py -v

# Integration (requires docker-compose stack up)
cd backend && pytest tests/integration/services/test_kg_pg_gateway.py \
                      tests/integration/services/test_kg_neo4j_gateway.py -v -m integration

# TS type-check
pnpm tsc -p tsconfig.json --noEmit

# Trigger.dev local registration
pnpm dlx trigger.dev@latest dev
# expect: "scheduled/kg-sync" listed
```

Then open PR targeting `develop`:

```bash
git push -u origin claude/recursing-morse-5df460
gh pr create --base develop --title "feat(kg-sync): scheduled KG reconciliation task" \
  --body "Adds Trigger.dev scheduled/kg-sync (6h cron) + KGSyncService + audit table. Dry-run by default; KG_SYNC_AUTO_REPAIR=true to enable orphan cleanup. See docs/runbooks/kg-sync.md."
```

---

## Notes for executor

- Whenever a referenced symbol (e.g. `require_service_role`, `get_neo4j_driver`, `Entity` model, relationship name `MENTIONED_IN`) doesn't match the codebase, **grep first, adopt the existing name, don't invent**. Do not introduce new auth dependencies or DB accessors.
- Keep `auto_repair=False` as the default everywhere. Only flip via env in staging/prod after baseline observation.
- Every task ends with a commit. Do not batch.
- If a TDD step's "minimal implementation" already exists from an earlier task, skip ahead — the test should immediately pass; record that fact in the commit message.
- Frequent small commits > one big diff. Same branch (`claude/recursing-morse-5df460`).
