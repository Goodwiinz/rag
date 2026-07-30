# Agent Audit P2 PR Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to
> implement this plan task-by-task.

**Goal:** Reduce the coupling, duplicated contracts, and ambiguous ownership
that caused the audited reliability and correctness failures, without delaying
P0/P1 production work.

**Architecture:** HTTP routes and agent tools become thin adapters over shared
use-case services. Use-case boundaries own transactions; leaf services flush.
Each domain exposes one canonical route, status vocabulary, pagination shape,
cache owner, and realtime transport. Neo4j receives an explicit derived-data
disaster-recovery contract.

**Tech Stack:** FastAPI, SQLAlchemy async, Celery, Pydantic/OpenAPI, Next.js,
TanStack Query, Zustand, Redis/WebSocket, Neo4j, pytest, Vitest.

---

## P2-A: Finish agent and message service boundaries

**Files:**

- Modify: `backend/src/services/agent/agent_execution_service.py`
- Modify: `backend/src/services/agent/tools.py`
- Modify: shared document/project/note services
- Modify: `backend/src/services/threads/chat_service.py`
- Modify: `backend/src/api/threads/workspace_routes/messages.py`
- Create/modify: architecture and parity tests

**Red tests:**

- Inventory direct ORM writes in agent tools and message routes.
- For each duplicated operation, run route and tool adapters against the same
  fixture and assert equal authorization, persistence, and error behavior.

**Implementation:**

1. Move remaining business rules into one service function per operation.
2. Collapse project ownership checks into one organization-aware helper.
3. Route all message creation through one idempotent `MessageService`/chat
   use case.
4. Ban imports from `src.api` inside `src.services`.
5. Keep temporary re-export shims for one release, then remove them.

**Exit gate:** Architecture guard is green and parity tests cover every migrated
operation.

**Commit:** `refactor(agent): finish service boundary extraction`

## P2-B: Unit-of-work and session ownership

**Files:**

- Modify: `backend/src/api/threads/workspace_routes/*.py`
- Modify: `backend/src/services/threads/*_service.py`
- Modify: agent tool session helpers
- Create/modify: transaction ownership tests

**Red tests:**

- Characterize which current services commit versus flush.
- Prove a composed use case cannot roll back atomically when a leaf commits.

**Implementation:**

1. Put transaction ownership at the request/use-case boundary.
2. Make leaf services call `flush()` and remove `commit: bool` parameters.
3. Pass IDs through LangGraph configuration, never live sessions or ORM users.
4. Use one `tool_session()` and one worker `run_async` boundary.
5. Add a guard forbidding commits in migrated leaf-service directories.

**Exit gate:** Composed failure rolls back all writes, and no AsyncSession is
shared across concurrent tasks.

**Commit:** `refactor(db): establish use-case transaction ownership`

## P2-C: Canonical API, statuses, and pagination

**Files:**

- Modify: router registration in `backend/src/main.py`
- Modify: agent/thread/document routers
- Modify: `backend/src/shared/enums.py`
- Modify: generated OpenAPI/TypeScript artifacts
- Modify: frontend API consumers
- Create/modify: route inventory and contract tests

**Red tests:**

- Inventory multiple message-creation, thread-stream, document-status, and
  pagination contracts.
- Assert one canonical route/type and an explicit deprecation/removal date for
  every loser.

**Implementation:**

1. Decide whether `v2` is a true version or the thread domain and document it.
2. Remove deprecated message and stream routes after telemetry proves no use.
3. Expand `ApiDocumentStatus`, `JobStatus`, `PaginationParams`, and `Page[T]`
   adoption across high-churn domains.
4. Keep prefixes in `main.py`, not split between router modules and mounting.
5. Generate frontend wire types; keep view models handwritten.

**Exit gate:** OpenAPI has one supported contract per concern and compatibility
tests pass.

**Commit:** `refactor(api): consolidate public contracts`

## P2-D: Dead code and legacy generation removal

**Files:**

- Delete only paths proven unreachable by import/route/runtime inventory
- Modify: route registration and package exports
- Create/modify: dead-package and import-smoke tests

**Red tests:**

- Fail when both search generations or deprecated websocket/stream clients are
  mounted/imported.
- Produce an import/call-site inventory before deletion.

**Implementation:**

1. Select the supported multi-agent search generation from actual traffic and
   feature parity.
2. Remove deprecated WebSocket/SSE clients and routers after P1-E.
3. Remove remaining never-imported packages and compatibility shims.
4. Preserve Git history; do not keep dead files as comments or archives.

**Exit gate:** Backend import smoke, frontend type-check, route snapshot, and
targeted E2E tests pass.

**Commit:** `chore(architecture): remove superseded runtime paths`

## P2-E: Neo4j disaster-recovery contract

**Files:**

- Modify: `docs/operations/` Neo4j runbook
- Modify: Helm values/templates only if backup is selected
- Modify: `backend/scripts/repair_kg.py`
- Create/modify: rebuild/restore verification tests

**Decision test:** Measure the time and LLM cost to rebuild a representative
tenant graph from PostgreSQL/documents. Compare that with the required RTO/RPO.

**Implementation options:**

1. If rebuild meets RTO/RPO, formally classify Neo4j as derived data, automate
   `repair_kg.py`, and test a clean-volume rebuild.
2. If rebuild misses RTO/RPO, implement encrypted scheduled backup, retention,
   restore verification, and alerting.
3. In either case, test organization scope and relationship completeness after
   recovery.

**Exit gate:** A dev disaster drill restores/rebuilds the graph within the
documented RTO/RPO and produces a comparison report.

**Commit:** `docs(kg): establish tested disaster recovery`

## P2-F: Frontend server-state ownership

**Files:**

- Modify: `docs/engineering/frontend.md`
- Modify: chat/workspace/query store modules
- Modify: `frontend/src/services/realtimeWebSocketService.ts`
- Create/modify: architecture and deterministic interleaving tests

**Red tests:**

- Reproduce stale A/B response ordering, thread switch during stream, and
  duplicate cache ownership.

**Implementation:**

1. Make TanStack Query the default server-state owner.
2. Keep the server-canonical chat transcript as the documented narrow Zustand
   exception.
3. Prohibit one entity from being independently cached by both systems.
4. Add deterministic deferred-promise interleavings for request generations,
   stream ownership, HITL, and pagination.
5. Add import-boundary guards for the documented ownership rules.

**Exit gate:** All stale-response interleavings preserve the newest server
state and exactly one cache owns each entity.

**Commit:** `test(frontend): enforce server-state ownership`

## P2 sequencing

P2-A precedes P2-B and P2-C. P2-D follows P1-E and P2-C so compatibility paths
are removed only after migration. P2-E is independent after P1-B establishes
convergence metrics. P2-F may run independently after P1-E selects the realtime
transport.
