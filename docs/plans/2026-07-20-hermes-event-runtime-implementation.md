# Hermes-Style `/chat` Event Runtime Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `/chat`'s connection-scoped streaming/session layer with durable run-scoped events and a server-authoritative frontend projection while preserving the existing agent graph and chat features.

**Architecture:** PostgreSQL owns `AgentRun`, ordered `AgentRunEvent` rows, replay, and terminal message projection. Redis is a best-effort low-latency wake-up channel. The frontend consumes a versioned event envelope through an idempotent reducer, keeps projections isolated by run and thread, and reconciles to committed chat messages at terminal state.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic, PostgreSQL JSONB, Redis, LangGraph, Pydantic, Next.js 16, React 18, TypeScript, Zustand/Immer, Vitest/RTL, Playwright, pytest.

---

## Execution Rules

- Read `docs/plans/2026-07-20-hermes-event-runtime-design.md` before editing.
- Use @superpowers:test-driven-development for every behavior change.
- Use @superpowers:verification-before-completion before each PR boundary.
- Preserve `AgentRuntimeSnapshot`; one run gets one snapshot and HITL resume
  must reuse it.
- Preserve the current LangGraph and tool authorization paths. Extract event
  translation; do not rewrite nodes.
- Do not extend `frontend/src/services/streamingService.ts` or
  `frontend/src/store/chat/slices/streamingSlice.ts`; both are deprecated.
- Do not migrate the global chat widget. Feature-gate only the primary
  `frontend/app/(dashboard)/chat/page.tsx` surface.
- Keep legacy `/api/v1/agent/stream` working until the final removal task and
  a production observation window are complete.
- Run commands from the repository root unless a step explicitly starts with
  `cd frontend`.
- Use the pinned frontend package manager: `corepack pnpm@10.18.2`.
- Keep commits limited to the named task. Do not combine schema, backend
  cutover, frontend cutover, and cleanup in one commit or PR.

## Delivery Sequence

Build this as six reviewable PRs:

1. Schema, typed event contract, and event store (Tasks 1-3).
2. Durable run lifecycle and graph dual-write (Tasks 4-7).
3. Run API, replay/tail, cancellation, and approval (Tasks 8-10).
4. Frontend client, reducer, and store (Tasks 11-13).
5. `/chat` cutover and performance hardening (Tasks 14-16).
6. Legacy removal after production acceptance (Task 17).

Do not begin a later PR until the earlier PR is merged or rebased cleanly onto
its merged result.

### Task 1: Expand the run lifecycle vocabulary

**Files:**
- Modify: `backend/src/shared/enums.py`
- Modify: `backend/src/models/agent_run.py`
- Modify: `backend/src/services/agent/agent_run_service.py`
- Modify: `frontend/src/services/agentChatService.ts`
- Test: `backend/tests/unit/agent/test_agent_run_service.py`
- Test: `frontend/src/services/__tests__/agentChatService.jobStatus.test.ts`

**Step 1: Write failing lifecycle tests**

Add tests that require `queued` and `stopping`, classify only completed,
failed, and cancelled as terminal, and reject transitions out of terminal
states.

```python
@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.RUNNING,
                                    JobStatus.AWAITING_CONFIRMATION,
                                    JobStatus.STOPPING])
def test_non_terminal_run_statuses(status: JobStatus) -> None:
    assert status.is_terminal is False
```

Update the TypeScript exhaustiveness table with the same two statuses.

**Step 2: Run the focused tests and confirm failure**

```bash
pytest backend/tests/unit/agent/test_agent_run_service.py -q
cd frontend && corepack pnpm@10.18.2 vitest run src/services/__tests__/agentChatService.jobStatus.test.ts
```

Expected: failures because `QUEUED` and `STOPPING` do not exist.

**Step 3: Add the statuses without changing legacy aliases**

```python
class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

Keep `"error" -> FAILED` compatibility. Update the model check constraint
source and service transition rules. Do not make `stopping` terminal.

**Step 4: Run focused tests**

Run the commands from Step 2. Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/shared/enums.py backend/src/models/agent_run.py \
  backend/src/services/agent/agent_run_service.py \
  backend/tests/unit/agent/test_agent_run_service.py \
  frontend/src/services/agentChatService.ts \
  frontend/src/services/__tests__/agentChatService.jobStatus.test.ts
git commit -m "feat(agent): define durable run lifecycle"
```

### Task 2: Add durable run and event schema

**Files:**
- Create: `backend/src/models/agent_run_event.py`
- Modify: `backend/src/models/agent_run.py`
- Modify: `backend/src/models/agent_runtime_snapshot.py`
- Modify: `backend/src/models/__init__.py`
- Create: `backend/alembic/versions/<revision>_add_agent_run_events.py`
- Create: `backend/tests/unit/models/test_agent_run_event_models.py`
- Create: `backend/tests/unit/test_agent_run_events_migration.py`

**Step 1: Write failing model tests**

Pin all required columns and constraints:

```python
def test_event_identity_and_ordering() -> None:
    table = AgentRunEvent.__table__
    assert {"id", "run_id", "seq", "event_type", "payload", "created_at"} <= set(table.c.keys())
    assert any(
        constraint.name == "uq_agent_run_events_run_seq"
        for constraint in table.constraints
    )
```

Also assert the expanded run columns: `conversation_id`, UUID `thread_id`,
`project_id`, `user_message_id`, `assistant_message_id`,
`runtime_snapshot_id`, `client_message_id`, `last_event_seq`, lifecycle
timestamps, structured usage/metadata, and lease generation.

**Step 2: Run tests and confirm import/schema failure**

```bash
pytest backend/tests/unit/models/test_agent_run_event_models.py -q
```

**Step 3: Implement the ORM model and migration**

Use `GUID()` for UUID identifiers and JSONB for payloads. The event model must
be append-only at the service layer:

```python
class AgentRunEvent(BaseModel):
    __tablename__ = "agent_run_events"
    run_id = Column(String(36), ForeignKey("agent_runs.job_id", ondelete="CASCADE"), nullable=False)
    seq = Column(Integer, nullable=False)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict, server_default="{}")
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_agent_run_events_run_seq"),
        Index("idx_agent_run_events_run_seq", "run_id", "seq"),
    )
```

Create the one-active-run-per-thread partial unique index over statuses
`queued`, `running`, `awaiting_confirmation`, and `stopping`. Scope the
idempotency index so different users/organizations cannot collide.

The migration must preserve existing rows, convert valid string thread UUIDs,
and leave invalid legacy correlations nullable rather than failing deployment.
Add foreign keys only after the data conversion.

**Step 4: Test upgrade and downgrade**

```bash
pytest backend/tests/unit/models/test_agent_run_event_models.py \
  backend/tests/unit/test_agent_run_events_migration.py -q
```

Expected: PASS, including upgrade against legacy fixture rows and downgrade.

**Step 5: Commit**

```bash
git add backend/src/models backend/alembic/versions \
  backend/tests/unit/models/test_agent_run_event_models.py \
  backend/tests/unit/test_agent_run_events_migration.py
git commit -m "feat(agent): persist run-scoped event history"
```

### Task 3: Define and validate the versioned event envelope

**Files:**
- Create: `backend/src/schemas/agent_run_events.py`
- Create: `backend/src/services/agent/run_event_types.py`
- Create: `backend/tests/unit/services/agent/test_run_event_types.py`

**Step 1: Write failing contract tests**

Test every public type, its payload model, JSON serialization, payload byte
limit, and redaction. Include a forward-compatible unknown-event parsing test.

```python
def test_delta_envelope_is_versioned_and_scoped() -> None:
    event = make_event("assistant.delta", AssistantDeltaPayload(text="hello"))
    body = AgentRunEventEnvelope.model_validate(event).model_dump(mode="json")
    assert body["version"] == 1
    assert body["type"] == "assistant.delta"
    assert body["seq"] > 0
```

**Step 2: Run and confirm failure**

```bash
pytest backend/tests/unit/services/agent/test_run_event_types.py -q
```

**Step 3: Implement the registry and schemas**

Use a `StrEnum` for the initial names and a payload-model map. Payloads must be
display-safe and bounded; `assistant.delta.text` is capped, tool arguments go
through the existing `redact_tool_args`, and error payloads expose a code plus
client-safe message only.

Do not expose LangGraph callback names in the public envelope.

**Step 4: Run tests**

```bash
pytest backend/tests/unit/services/agent/test_run_event_types.py -q
```

**Step 5: Commit**

```bash
git add backend/src/schemas/agent_run_events.py \
  backend/src/services/agent/run_event_types.py \
  backend/tests/unit/services/agent/test_run_event_types.py
git commit -m "feat(agent): define versioned run event contract"
```

### Task 4: Build the transactional event store

**Files:**
- Create: `backend/src/services/agent/run_event_store.py`
- Create: `backend/tests/unit/agent/test_run_event_store.py`

**Step 1: Write failing service tests**

Cover append, batch append, replay after a cursor, ownership filters,
concurrent append attempts, lifecycle projection, and terminal absorption.

```python
async def test_append_locks_run_and_allocates_monotonic_sequence(db, run):
    first = await append_event(db, run.job_id, RunEventType.RUN_STARTED, {})
    second = await append_event(db, run.job_id, RunEventType.PLAN_UPDATED, {"steps": []})
    assert [first.seq, second.seq] == [1, 2]
    assert run.last_event_seq == 2
```

**Step 2: Run and confirm failure**

```bash
pytest backend/tests/unit/agent/test_run_event_store.py -q
```

**Step 3: Implement the minimal store**

`append_event` must select the run with `FOR UPDATE`, calculate the next
sequence on the server, validate/redact the payload, insert the event, and
update the run projection without committing. The caller owns commit/rollback.

Provide:

```python
async def append_event(db, *, run_id, event_type, payload, message_id=None) -> AgentRunEvent
async def append_events(db, *, run_id, events) -> list[AgentRunEvent]
async def list_events_after(db, *, run_id, owner, after, limit=500) -> list[AgentRunEvent]
async def get_owned_run(db, *, run_id, owner, for_update=False) -> AgentRun
```

Map uniqueness conflicts to a typed service error; never retry by guessing a
new sequence outside the row lock.

**Step 4: Run tests**

```bash
pytest backend/tests/unit/agent/test_run_event_store.py -q
```

**Step 5: Commit**

```bash
git add backend/src/services/agent/run_event_store.py \
  backend/tests/unit/agent/test_run_event_store.py
git commit -m "feat(agent): add transactional run event store"
```

### Task 5: Create runs atomically

**Files:**
- Create: `backend/src/services/agent/run_lifecycle_service.py`
- Modify: `backend/src/services/agent/runtime_snapshot.py`
- Modify: `backend/src/services/agent/agent_run_service.py`
- Create: `backend/tests/unit/agent/test_run_lifecycle_service.py`

**Step 1: Write failing creation tests**

Cover ownership, user-message deduplication, run idempotency, snapshot binding,
`run.created` sequence one, and the active-run conflict response.

```python
async def test_create_run_commits_turn_snapshot_and_first_event_together(db):
    created = await create_run(db, command)
    assert created.run.user_message_id == created.user_message.id
    assert created.run.runtime_snapshot_id == created.snapshot.id
    assert created.event.seq == 1
```

Use an injected dispatcher spy and assert it is not called until after commit.

**Step 2: Run and confirm failure**

```bash
pytest backend/tests/unit/agent/test_run_lifecycle_service.py -q
```

**Step 3: Implement create-run orchestration**

Reuse `_resolve_thread`, guarded user-message persistence semantics, project
binding, and `create_runtime_snapshot`; move shared persistence code into
services only as needed to avoid importing an API module.

Return a typed `ActiveRunConflict(run_id)` for the partial-index violation.
Return the existing run for an exact idempotent retry.

**Step 4: Run tests**

```bash
pytest backend/tests/unit/agent/test_run_lifecycle_service.py \
  backend/tests/api/agent/test_persist_thread_messages.py \
  backend/tests/unit/services/test_agent_runtime_snapshot.py -q
```

**Step 5: Commit**

```bash
git add backend/src/services/agent backend/tests/unit/agent \
  backend/tests/api/agent/test_persist_thread_messages.py
git commit -m "feat(agent): create durable runs atomically"
```

### Task 6: Extract transport-neutral graph events

**Files:**
- Create: `backend/src/services/agent/graph_run_events.py`
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/src/shared/enums.py`
- Create: `backend/tests/unit/services/agent/test_graph_run_events.py`
- Modify: `backend/tests/unit/api/test_stream_integration.py`
- Modify: `frontend/src/services/__tests__/agentStreamEvents.contract.test.ts`

**Step 1: Write mapping tests first**

For each current `AgentStreamEvent`, pin its new event mapping and legacy
adapter output. Include token, tool start/end, RAG, plan, reflection, trace,
usage, confirmation, done, error, and heartbeat behavior.

**Step 2: Run and confirm failure**

```bash
pytest backend/tests/unit/services/agent/test_graph_run_events.py \
  backend/tests/unit/api/test_stream_integration.py -q
```

**Step 3: Extract a single translator**

Create a transport-neutral async iterator that converts LangGraph callback
events into typed run events. Keep heartbeat as transport metadata rather than
a durable event. Make the legacy SSE formatter consume the same typed events:

```python
async for run_event in graph_run_events(graph, state, config, request):
    if durable_writer is not None:
        await durable_writer.write(run_event)
    yield legacy_sse_adapter(run_event)
```

Maintain existing PII redaction, tool result caps, keepalive behavior, and
disconnect draining. Do not change user-visible wire behavior in this task.

**Step 4: Run legacy and new contract tests**

```bash
pytest backend/tests/unit/services/agent/test_graph_run_events.py \
  backend/tests/unit/api/test_stream_integration.py \
  backend/tests/unit/api/test_stream_tool_args_preview.py \
  backend/tests/unit/api/test_agent_streaming_done_ids.py -q
cd frontend && corepack pnpm@10.18.2 vitest run src/services/__tests__/agentStreamEvents.contract.test.ts
```

**Step 5: Commit**

```bash
git add backend/src/services/agent/graph_run_events.py \
  backend/src/api/agent/streaming.py backend/src/shared/enums.py \
  backend/tests/unit/services/agent/test_graph_run_events.py \
  backend/tests/unit/api frontend/src/services/__tests__/agentStreamEvents.contract.test.ts
git commit -m "refactor(agent): unify graph event translation"
```

### Task 7: Dual-write events and terminal projections

**Files:**
- Modify: `backend/src/core/config.py`
- Modify: `backend/src/services/agent/run_lifecycle_service.py`
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/src/tasks/agent_runs.py`
- Modify: `backend/src/tasks/sweepers.py`
- Create: `backend/tests/integration/agent/test_durable_run_execution.py`
- Modify: `backend/tests/unit/tasks/test_agent_run_tasks.py`
- Modify: `backend/tests/unit/tasks/test_sweepers.py`

**Step 1: Write failing end-to-end service tests**

Prove that success writes the assistant message, citations/tool metadata,
terminal event, and terminal run status in one transaction. Repeat for failure,
cancellation, and sweeper recovery. Force a projection insert failure and
assert no terminal event/status commits.

**Step 2: Run and confirm failure**

```bash
pytest backend/tests/integration/agent/test_durable_run_execution.py \
  backend/tests/unit/tasks/test_agent_run_tasks.py \
  backend/tests/unit/tasks/test_sweepers.py -q
```

**Step 3: Add dual-write behind a backend flag**

Add `AGENT_RUN_EVENTS_DUAL_WRITE: bool = False`. When a durable `run_id` is
present, append typed events and publish legacy SSE from the same translated
event. When absent or flag-off, preserve the legacy path unchanged.

Batch adjacent `assistant.delta` fragments for PostgreSQL by a small bounded
time/byte window, while emitting them live without waiting. One persisted delta
event may therefore contain several live fragments; its sequence remains
strict and replay renders identical text.

Create terminal service methods:

```python
async def complete_run(db, *, run_id, assistant_projection) -> AgentRun
async def fail_run(db, *, run_id, code, message, partial_projection=None) -> AgentRun
async def acknowledge_cancel(db, *, run_id, partial_projection=None) -> AgentRun
```

Make sweeper terminalization call `fail_run` and rely on terminal-event
uniqueness/idempotency.

**Step 4: Run regression tests**

```bash
pytest backend/tests/integration/agent/test_durable_run_execution.py \
  backend/tests/agent/test_streaming_resume.py \
  backend/tests/agent/test_stream_confirm_claim.py \
  backend/tests/unit/tasks/test_agent_run_tasks.py \
  backend/tests/unit/tasks/test_sweepers.py -q
```

**Step 5: Commit and close PR 2**

```bash
git add backend/src/core/config.py backend/src/services/agent \
  backend/src/api/agent/streaming.py backend/src/tasks \
  backend/tests/integration/agent backend/tests/unit/tasks
git commit -m "feat(agent): dual-write durable run events"
```

### Task 8: Add the run resource API

**Files:**
- Create: `backend/src/api/agent/runs.py`
- Modify: `backend/src/api/agent/__init__.py`
- Modify: `backend/src/main.py`
- Create: `backend/src/schemas/agent_runs.py`
- Create: `backend/tests/api/agent/test_run_api.py`

**Step 1: Write API tests**

Cover `POST /api/v1/agent/runs` 202, idempotent retry, active-run 409 with
`active_run_id`, project/thread authorization, and `GET /runs/{id}` tenant
isolation.

**Step 2: Run and confirm 404/import failure**

```bash
pytest backend/tests/api/agent/test_run_api.py -q
```

**Step 3: Implement schemas and endpoints**

The create response must be usable before the worker begins:

```json
{
  "run_id": "uuid",
  "thread_id": "uuid",
  "status": "queued",
  "user_message_id": "uuid",
  "runtime_snapshot_id": "uuid",
  "last_event_seq": 1
}
```

Dispatch only after the creation transaction commits. Convert the active-run
service error into a structured 409. All cross-tenant lookups return 404.

**Step 4: Run API tests and regenerate OpenAPI**

```bash
pytest backend/tests/api/agent/test_run_api.py -q
python scripts/ci/generate_openapi.py
cd frontend && corepack pnpm@10.18.2 generate:api-types
```

**Step 5: Commit**

```bash
git add backend/src/api/agent backend/src/schemas/agent_runs.py \
  backend/src/main.py backend/tests/api/agent/test_run_api.py \
  backend/openapi.json frontend/src/types/generated/api.d.ts
git commit -m "feat(agent): expose durable run resources"
```

### Task 9: Implement PostgreSQL replay and Redis-assisted tailing

**Files:**
- Create: `backend/src/services/agent/run_event_broker.py`
- Modify: `backend/src/api/agent/runs.py`
- Modify: `backend/src/core/config.py`
- Create: `backend/tests/agent/test_run_event_stream.py`

**Step 1: Write failing replay/tail tests**

Test `after=0`, `after=N`, disconnect, terminal exit, Redis notification,
Redis unavailable, periodic database catch-up, no missed event between replay
and subscription, and heartbeat comments.

**Step 2: Run and confirm failure**

```bash
pytest backend/tests/agent/test_run_event_stream.py -q
```

**Step 3: Implement correctness-first tailing**

The endpoint algorithm is:

```text
read PostgreSQL rows after cursor
emit rows in sequence order
if terminal: close
subscribe to Redis run channel
read PostgreSQL again to close the replay/subscribe race
on notification or poll interval: read PostgreSQL after cursor
on idle interval: emit SSE comment heartbeat
```

Redis messages carry only `run_id` and latest sequence, never the event body.
The endpoint always reads the durable row before delivery. Add bounded page
size, connection duration, and database poll interval settings.

**Step 4: Run tests**

```bash
pytest backend/tests/agent/test_run_event_stream.py \
  backend/tests/agent/test_streaming_resume.py -q
```

**Step 5: Commit**

```bash
git add backend/src/services/agent/run_event_broker.py \
  backend/src/api/agent/runs.py backend/src/core/config.py \
  backend/tests/agent/test_run_event_stream.py
git commit -m "feat(agent): replay and tail durable run events"
```

### Task 10: Add durable cancellation and approval commands

**Files:**
- Modify: `backend/src/api/agent/runs.py`
- Modify: `backend/src/services/agent/run_lifecycle_service.py`
- Modify: `backend/src/services/agent/graph_run_events.py`
- Create: `backend/src/models/agent_run_approval.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/services/agent/_nodes_tools.py`
- Create: `backend/alembic/versions/<revision>_scope_hitl_to_agent_runs.py`
- Create: `backend/tests/api/agent/test_run_commands.py`
- Modify: `backend/tests/agent/test_stream_confirm_claim.py`
- Modify: `backend/tests/agent/test_hitl_audit_idempotency.py`

**Step 1: Write failing command tests**

Cover running-to-stopping, repeated cancel, worker acknowledgement, terminal
cancel no-op, approval ownership, stale approval 409, double approval, and
exactly-once graph resume.

**Step 2: Run and confirm failure**

```bash
pytest backend/tests/api/agent/test_run_commands.py \
  backend/tests/agent/test_stream_confirm_claim.py \
  backend/tests/agent/test_hitl_audit_idempotency.py -q
```

**Step 3: Implement commands**

`POST /runs/{run_id}/cancel` locks the run, changes a running or awaiting run
to `stopping`, records `cancel_requested_at`, appends `run.stopping`, and
signals the runner. It does not claim cancellation has completed.

`POST /runs/{run_id}/approvals/{approval_id}` compare-and-swaps an
`AgentRunApproval` row from pending to resolved, writes the existing immutable
`AgentHitlAudit` decision row, appends `approval.resolved`, changes the run to
running when needed, and dispatches resume after commit. Reuse the current
checkpoint-anchored idempotency protection. Do not turn `agent_hitl_audit` into
mutable command state.

**Step 4: Run tests**

Run the Step 2 command. Expected: PASS.

**Step 5: Commit and close PR 3**

```bash
git add backend/src/api/agent/runs.py backend/src/services/agent \
  backend/src/models/agent_run_approval.py backend/src/models/__init__.py \
  backend/alembic/versions \
  backend/tests/api/agent/test_run_commands.py backend/tests/agent
git commit -m "feat(agent): add durable run commands"
```

### Task 11: Add the frontend run client and generated contract adapter

**Files:**
- Create: `frontend/src/services/agentRunService.ts`
- Create: `frontend/src/services/agentRunEvents.ts`
- Create: `frontend/src/services/__tests__/agentRunService.test.ts`
- Create: `frontend/src/services/__tests__/agentRunEvents.contract.test.ts`

**Step 1: Write failing client tests**

Use mocked fetch streams to test create/get/cancel/approve, SSE framing,
`Last-Event-ID`, reconnect with `after`, abort, structured 409, and unknown
event types.

**Step 2: Run and confirm failure**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/services/__tests__/agentRunService.test.ts \
  src/services/__tests__/agentRunEvents.contract.test.ts
```

**Step 3: Implement the typed adapter**

Domain types must wrap generated OpenAPI types rather than duplicating server
response shapes. Define the discriminated event union and preserve unknown
events as an opaque envelope so their sequence still advances.

```ts
export type AgentRunEvent =
  | RunStartedEvent
  | AssistantDeltaEvent
  | ToolStartedEvent
  | ToolCompletedEvent
  | ApprovalRequiredEvent
  | RunTerminalEvent
  | UnknownRunEvent;
```

The SSE parser must treat the SSE `id` and envelope `seq` mismatch as a
protocol error and reconnect from the last successfully applied sequence.

**Step 4: Run tests and type-check**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/services/__tests__/agentRunService.test.ts \
  src/services/__tests__/agentRunEvents.contract.test.ts && \
  corepack pnpm@10.18.2 type-check
```

**Step 5: Commit**

```bash
git add frontend/src/services/agentRunService.ts \
  frontend/src/services/agentRunEvents.ts frontend/src/services/__tests__
git commit -m "feat(chat): add durable run event client"
```

### Task 12: Implement the pure run event reducer

**Files:**
- Create: `frontend/src/store/chat/runEventReducer.ts`
- Create: `frontend/src/store/chat/__tests__/runEventReducer.test.ts`

**Step 1: Write reducer tests**

Cover each event, duplicate suppression, gap detection, wrong-run rejection,
delta concatenation, stable tool identity, approval replacement, terminal
status, and unknown-event cursor advancement.

```ts
it('does not append duplicate delta text', () => {
  const once = reduceRunEvent(initial, delta(2, 'hello'));
  const twice = reduceRunEvent(once.projection, delta(2, 'hello'));
  expect(twice.projection.content).toBe('hello');
  expect(twice.kind).toBe('duplicate');
});
```

**Step 2: Run and confirm failure**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run src/store/chat/__tests__/runEventReducer.test.ts
```

**Step 3: Implement a side-effect-free reducer**

Return one of `applied`, `duplicate`, `gap`, or `wrong_run`. Do not fetch,
schedule animation frames, write Zustand, or mutate event payloads inside the
reducer. Store tools by `tool_call_id` plus a stable display order.

**Step 4: Run tests**

Run Step 2. Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/store/chat/runEventReducer.ts \
  frontend/src/store/chat/__tests__/runEventReducer.test.ts
git commit -m "feat(chat): project ordered run events"
```

### Task 13: Add normalized run state and subscription ownership

**Files:**
- Create: `frontend/src/store/chat/slices/runSlice.ts`
- Modify: `frontend/src/store/chat/types.ts`
- Modify: `frontend/src/store/chat/initialState.ts`
- Modify: `frontend/src/store/chat-store.ts`
- Modify: `frontend/src/store/chat/selectors.ts`
- Create: `frontend/src/store/__tests__/chat-store-runs.test.ts`

**Step 1: Write failing store tests**

Cover projections keyed by run ID, active run keyed by thread ID, two
background runs in different threads, gap repair, rAF delta batching,
subscription supersession, and terminal cleanup only after message refresh.

**Step 2: Run and confirm failure**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run src/store/__tests__/chat-store-runs.test.ts
```

**Step 3: Implement the slice**

Add state shaped like:

```ts
runProjections: Record<string, AgentRunProjection>;
activeRunByThread: Record<string, string | undefined>;
runSubscriptionState: Record<string, { lastSeq: number; status: 'idle' | 'connecting' | 'live' | 'repairing' }>;
```

Keep `AbortController` instances outside persisted Immer state in a request
coordinator keyed by run ID. Queue only delta events into one rAF flush; apply
all other events synchronously. Selectors must return committed message arrays
without changing identity during a delta.

Do not remove legacy streaming fields yet.

**Step 4: Run store regression tests**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/store/__tests__/chat-store-runs.test.ts \
  src/store/__tests__/chat-store-refresh.test.ts \
  src/store/__tests__/chat-store-pagination.test.ts
```

**Step 5: Commit and close PR 4**

```bash
git add frontend/src/store/chat frontend/src/store/chat-store.ts \
  frontend/src/store/__tests__/chat-store-runs.test.ts
git commit -m "feat(chat): store run projections by thread"
```

### Task 14: Build small run hooks and feature-gated `/chat` composition

**Files:**
- Create: `frontend/src/hooks/chat/useAgentRun.ts`
- Create: `frontend/src/hooks/chat/useAgentRunSubscription.ts`
- Create: `frontend/src/hooks/chat/useEventChatRuntime.ts`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Modify: `frontend/src/components/chat/ChatSurface.tsx`
- Create: `frontend/src/hooks/__tests__/useEventChatRuntime.test.tsx`
- Modify: `frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx`

**Step 1: Write failing hook and route tests**

Cover submit, active-run 409, stop, approval, reconnect, reload attachment,
thread switch without aborting another thread's run, and flag-off legacy
behavior.

**Step 2: Run and confirm failure**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/hooks/__tests__/useEventChatRuntime.test.tsx \
  src/components/chat/__tests__/ChatPage.threadSelect.test.tsx
```

**Step 3: Implement the hooks and composition boundary**

`useAgentRun` owns commands. `useAgentRunSubscription` owns attach/reconnect and
gap repair. `useEventChatRuntime` adapts normalized store selectors to the
existing `ChatSurface` prop contract.

At the route composition root choose the runtime once:

```ts
const eventRuntimeEnabled =
  process.env.NEXT_PUBLIC_CHAT_EVENT_RUNTIME === 'true';
const runtime = eventRuntimeEnabled
  ? useEventChatRuntime(/* route context */)
  : useLegacyChatRuntime(/* existing hooks */);
```

Because hooks cannot be called conditionally, implement two child composition
components selected by a parent flag, not a conditional around hook calls.
Keep the flag default off.

**Step 4: Run focused regression tests**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/hooks/__tests__/useEventChatRuntime.test.tsx \
  src/components/chat/__tests__/ChatPage.threadSelect.test.tsx \
  src/components/chat/__tests__/ChatPage.turnPersistence.test.tsx \
  src/components/chat/__tests__/ChatPage.citations.test.tsx
```

**Step 5: Commit**

```bash
git add frontend/src/hooks/chat frontend/app/'(dashboard)'/chat/page.tsx \
  frontend/src/components/chat/ChatSurface.tsx frontend/src/hooks/__tests__ \
  frontend/src/components/chat/__tests__
git commit -m "feat(chat): gate the event runtime into /chat"
```

### Task 15: Make terminal reconciliation server-authoritative

**Files:**
- Modify: `frontend/src/hooks/chat/useChatSession.ts`
- Modify: `frontend/src/hooks/chat/useEventChatRuntime.ts`
- Modify: `frontend/src/components/chat/shared/cloudMessageView.ts`
- Modify: `frontend/src/store/chat/slices/messageSlice.ts`
- Create: `frontend/src/hooks/__tests__/useEventChatReconciliation.test.tsx`
- Modify: `frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts`

**Step 1: Write reconciliation tests**

Test that the active projection remains visible after a terminal event until
the committed assistant message with `assistant_message_id` arrives. Test no
blank frame, no duplicate row, delayed refresh, stopped partial, and a thread
switch during reconciliation.

**Step 2: Run and confirm failure**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/hooks/__tests__/useEventChatReconciliation.test.tsx \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts
```

**Step 3: Implement the handoff**

The event runtime must never POST an assistant message from the browser.
Terminal handling calls the existing bounded `refreshMessages(threadId,
expectation)`. Retire the transient projection only when the expected server
message ID is present. `useChatSession` reads the store's committed message
selector; do not maintain an independent transcript for the event path.

**Step 4: Run chat regression tests**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/hooks/__tests__/useEventChatReconciliation.test.tsx \
  src/store/__tests__/chat-store-refresh.test.ts \
  src/components/chat/__tests__/ChatPage.turnPersistence.test.tsx \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts
```

**Step 5: Commit**

```bash
git add frontend/src/hooks/chat frontend/src/components/chat/shared \
  frontend/src/store/chat/slices/messageSlice.ts frontend/src/hooks/__tests__
git commit -m "feat(chat): reconcile run projections to server messages"
```

### Task 16: Enforce interaction and rendering performance budgets

**Files:**
- Create: `frontend/src/components/chat/StreamingText.tsx`
- Modify: `frontend/src/components/chat/shared/ChatBubble.tsx`
- Modify: `frontend/src/components/chat/ChatMessageList.tsx`
- Create: `frontend/src/components/chat/__tests__/ChatStreamingPerformance.test.tsx`
- Create: `frontend/e2e/nous-flows/chat-event-runtime.spec.ts`
- Modify: `frontend/e2e/utils/performance-monitor.ts`

**Step 1: Write performance guard tests**

Use React Profiler and render counters to assert:

- N deltas in one frame cause one projection commit;
- committed rows do not rerender for deltas;
- streaming content does not invoke `CitationRenderer`/ReactMarkdown;
- cached thread selection paints existing content synchronously;
- terminal reconciliation mounts the rich renderer once.

Add Playwright cases for reload during a run, disconnect/reconnect, rapid
thread switching, double-submit, stop, approval retry, and 200/1,000-message
threads.

**Step 2: Run tests and capture the failing baseline**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/components/chat/__tests__/ChatStreamingPerformance.test.tsx
```

Record profiler counts in the test failure output; do not weaken thresholds to
match the old implementation.

**Step 3: Implement the rendering boundary**

Use `StreamingText` for active `assistant.delta` content. It must not parse
Markdown, syntax-highlight, or resolve citations. `ChatBubble` mounts the
existing `CitationRenderer` only for committed/terminal content. Memoize
committed rows by stable message identity and keep the virtualized threshold
behavior intact.

Add performance marks for cached-thread selection, first delta, terminal
event, and committed-message reconciliation.

**Step 4: Run frontend verification**

```bash
cd frontend && corepack pnpm@10.18.2 vitest run \
  src/components/chat/__tests__/ChatStreamingPerformance.test.tsx \
  src/components/chat/__tests__/ChatMessageList.threadSwitch.test.tsx \
  src/components/chat/__tests__/ChatMessageList.prepend.test.tsx && \
  corepack pnpm@10.18.2 type-check && \
  corepack pnpm@10.18.2 lint:changed
```

Run the new Playwright suite against a backend with
`AGENT_RUN_EVENTS_DUAL_WRITE=true` and frontend with
`NEXT_PUBLIC_CHAT_EVENT_RUNTIME=true`:

```bash
cd frontend && corepack pnpm@10.18.2 playwright test \
  e2e/nous-flows/chat-event-runtime.spec.ts --config=playwright.nous.config.ts
```

**Step 5: Commit and close PR 5**

```bash
git add frontend/src/components/chat frontend/e2e
git commit -m "perf(chat): keep event streaming interaction-first"
```

### Task 17: Observe, cut over, and remove the legacy runtime

**Files:**
- Modify: `backend/src/api/agent/execute.py`
- Modify: `backend/src/api/agent/streaming.py`
- Delete: `backend/src/services/agent/stream_buffer.py`
- Delete: `frontend/src/services/streamingService.ts`
- Delete: `frontend/src/store/chat/slices/streamingSlice.ts`
- Refactor or delete: `frontend/src/hooks/chat/useChatStreaming.ts`
- Modify: `frontend/src/store/chat-store.ts`
- Modify: `frontend/src/store/chat/types.ts`
- Modify: `frontend/src/store/chat/initialState.ts`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Modify/delete corresponding legacy tests only after equivalent event-runtime coverage exists.

**Step 1: Prove the removal gate before editing**

Do not start removal until production telemetry for the agreed observation
window shows:

- no unexplained dual-write mapping mismatches;
- terminal projection success at the agreed SLO;
- reconnects produce no duplicate text/tool cards;
- Redis-degraded replay succeeds;
- active-run conflicts and approval retries behave as designed;
- `/chat` event runtime feature flag is fully enabled;
- rollback to the legacy runtime has not been needed.

Document the evidence in the PR description. If any item is missing, stop and
leave the compatibility path in place.

**Step 2: Write architecture tests that fail while legacy code exists**

Add/extend `frontend/src/test/architecture/__tests__/maintenanceContracts.test.ts`
and a backend contract test to forbid imports or route registration for the
orphaned streaming service, Redis stream buffer, and deprecated slice.

**Step 3: Remove legacy paths**

Delete the thread-scoped Redis replay route and legacy browser stream path only
after confirming the CLI either consumes the new run API or retains a small
explicit adapter. Remove global streaming fields from `ChatState`; all active
state must be run/thread scoped.

Keep reusable graph execution, legacy CLI compatibility if still required,
and `AgentStreamEvent` only if a supported consumer still depends on it.

**Step 4: Run the full relevant verification matrix**

```bash
pytest backend/tests/agent backend/tests/api/agent \
  backend/tests/unit/agent backend/tests/unit/services/agent \
  backend/tests/integration/agent -q
python -m pip install ruff==0.15.15 black==26.5.1 isort==5.13.2
ruff check backend/src backend/tests
black --check backend/src backend/tests
isort --check-only backend/src backend/tests
cd frontend && corepack pnpm@10.18.2 type-check && \
  corepack pnpm@10.18.2 vitest run && \
  corepack pnpm@10.18.2 lint:changed
```

Run the event-runtime Playwright suite again. Expected: PASS with the legacy
feature flag and endpoints absent.

**Step 5: Commit and close PR 6**

```bash
git add -A backend/src/api/agent backend/src/services/agent backend/tests \
  frontend/src frontend/app/'(dashboard)'/chat frontend/e2e
git commit -m "refactor(chat): retire the legacy streaming runtime"
```

## Final Acceptance Checklist

- [ ] Every `/chat` turn has a stable run ID before execution begins.
- [ ] One and only one non-terminal run can exist per thread.
- [ ] Run creation, user message, runtime snapshot, and first event are atomic.
- [ ] Every durable event is ordered and replayable from PostgreSQL.
- [ ] Redis failure degrades latency, not correctness.
- [ ] A disconnected browser does not cancel execution.
- [ ] Success atomically writes the final assistant message and terminal event.
- [ ] Failure, cancellation, and sweeper recovery each emit one terminal event.
- [ ] Approval retries cannot execute a destructive tool twice.
- [ ] HITL resume reuses the original runtime snapshot.
- [ ] The frontend reducer is idempotent and repairs sequence gaps.
- [ ] Active projections are isolated by run and thread.
- [ ] The browser never persists assistant messages for the event path.
- [ ] Cached thread switching paints within one animation frame locally.
- [ ] Delta delivery causes at most one React commit per animation frame.
- [ ] Committed rows do not rerender for each delta.
- [ ] Streaming text avoids rich Markdown/citation parsing.
- [ ] Reload/reconnect creates no duplicated characters or tool cards.
- [ ] Citations, RAG, plans, reflections, tools, usage, stop, and HITL retain
      functional parity.
- [ ] Backend focused suites, migration tests, formatting gates, frontend type
      check, focused Vitest tests, and Playwright scenarios pass.
- [ ] Legacy removal happens only after documented production acceptance.
