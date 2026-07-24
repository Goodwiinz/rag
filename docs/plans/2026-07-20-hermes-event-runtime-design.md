# Hermes-Style Event Runtime for `/chat` — Design

**Date:** 2026-07-20
**Status:** Approved
**Target:** Primary NOUS `/chat` surface

## Summary

NOUS will replace the primary chat page's connection-scoped streaming and
split browser session state with durable, run-scoped events and a
server-authoritative projection. Every submitted turn receives a stable run
identity. PostgreSQL owns the run lifecycle, ordered event history, replay,
and final message projection; Redis accelerates live delivery but is not a
source of truth.

The migration preserves the existing LangGraph execution, project skill and
tool runtime snapshots, message idempotency, citations, plans, tool activity,
usage accounting, stop behavior, and HITL safeguards. It first dual-writes
events, then moves `/chat` to a deterministic event reducer behind a feature
flag, and removes the legacy stream/session path only after production parity.

## Goals

- Give every agent turn a durable `run_id` independent of an HTTP connection.
- Make replay and refresh correct without depending on Redis retention.
- Make the server authoritative for lifecycle, messages, tools, approvals,
  citations, usage, and terminal outcomes.
- Let the frontend derive UI state deterministically from committed messages
  plus an ordered active-run projection.
- Keep cached thread switching synchronous and isolate background runs by
  thread.
- Reduce token rendering to at most one React commit per animation frame and
  avoid rich Markdown/citation parsing until an answer completes.
- Roll out without breaking the CLI, queued execution, or the existing
  `/agent/stream` consumers.

## Non-Goals

- Rewriting the LangGraph or agent node implementation.
- Migrating the global chat widget in this project.
- Adding multi-run concurrency within one thread.
- Persisting LangGraph's internal callback vocabulary as a public contract.
- Using PostgreSQL `LISTEN/NOTIFY` as the durable event store.
- Retaining unredacted prompts, secrets, or complete tool results in events.

## Existing Foundation

The implementation must evolve these current primitives rather than duplicate
them:

- `backend/src/api/agent/streaming.py` translates LangGraph events into a
  sequence-numbered SSE vocabulary and persists final messages.
- `backend/src/services/agent/stream_buffer.py` provides best-effort Redis
  replay for an active stream.
- `backend/src/models/agent_run.py` and
  `backend/src/services/agent/agent_run_service.py` project job lifecycle into
  PostgreSQL.
- `backend/src/models/agent_runtime_snapshot.py` freezes the eligible tool
  registry and approved project skill versions for a turn.
- `backend/src/models/chat_message.py` already deduplicates user and assistant
  messages with thread-scoped `client_message_id` indexes.
- `frontend/src/services/agentChatService.ts` parses the legacy event stream.
- `frontend/src/hooks/chat/useChatStreaming.ts` currently owns send, resume,
  stop, persistence reconciliation, HITL, and most live projections.
- `frontend/src/store/chat/slices/messageSlice.ts` owns bounded message pages
  and the thread cache.

## Core Architecture

The runtime has four durable concepts:

1. A `ChatMessage` is a committed transcript projection.
2. An `AgentRun` is one attempt to produce an assistant turn.
3. An `AgentRunEvent` is an immutable ordered fact about that run.
4. An `AgentRuntimeSnapshot` freezes the approved tools and project skills used
   by the run.

The request/execute/deliver flow is:

```text
/chat -> create run -> PostgreSQL transaction -> dispatch graph
                                        |
LangGraph -> event translator -> durable event append -> Redis publish
                                        |
/chat <- SSE replay + tail <- PostgreSQL catch-up + Redis live fan-out
                                        |
                           deterministic frontend projection
```

PostgreSQL is authoritative. Redis may provide low-latency notification and a
short hot cache, but a Redis outage or eviction cannot erase a run, prevent a
terminal status, or make replay impossible.

## Persistence Model

### `agent_runs`

Evolve the existing table rather than create a competing run table. Keep
`job_id` as the primary key during compatibility rollout and expose it as
`run_id` at the new API boundary. Add:

- `conversation_id`, `project_id`, and the existing ownership-verified
  `thread_id` as UUID foreign keys;
- `user_message_id` and `assistant_message_id`;
- `runtime_snapshot_id`;
- `client_message_id` and tenant-scoped idempotency metadata;
- lifecycle timestamps: `started_at`, `completed_at`, `cancel_requested_at`;
- `last_event_seq` with a zero default;
- structured `error_code`, client-safe `error`, `usage`, and `metadata`;
- a lease generation/version used by the worker and sweeper.

The lifecycle is:

```text
queued -> running -> awaiting_approval -> running
                    |                   |
                    +-------------------+
                              |
               completed | failed | cancelled
```

`stopping` is a visible transient state after a cancellation request. Terminal
states are absorbing. A partial unique index enforces one non-terminal run per
thread. The create API returns HTTP 409 with `active_run_id` when that invariant
is violated.

### `agent_run_events`

Add an append-only table containing:

- UUID `id` for globally unique event identity;
- `run_id` foreign key with cascade delete;
- monotonically increasing integer `seq`;
- versioned `event_type` string;
- redacted JSONB `payload`;
- server timestamp `created_at`.

The primary ordering constraint is unique `(run_id, seq)`. Indexes support
`run_id, seq`, terminal-event lookup, and operational retention scans. Clients
never supply sequence numbers. Event insertion locks the run row, increments
`last_event_seq`, inserts the event, and applies any lifecycle projection in a
single transaction.

Event payloads are deliberately bounded. Large retrieval bodies and tool
results remain in their canonical stores; events carry IDs, summaries, status,
and display-safe excerpts.

### Approvals

The existing HITL checkpoint logic remains the execution safeguard. Add a
mutable `agent_run_approvals` command-state table with a stable `approval_id`,
`run_id`, `tool_call_id`, pending/resolved state, decision, and resolver. Keep
the existing `agent_hitl_audit` table append-only: a successful compare-and-swap
decision writes its immutable audit row. `approval.required` and
`approval.resolved` events refer to the approval record. Approval resolution
uses a compare-and-swap transition, so retries cannot execute a destructive
tool twice.

## Versioned Event Contract

Every event returned by the new API uses this envelope:

```json
{
  "version": 1,
  "event_id": "uuid",
  "run_id": "uuid",
  "conversation_id": "uuid",
  "thread_id": "uuid",
  "message_id": "uuid-or-null",
  "seq": 12,
  "timestamp": "2026-07-20T12:34:56.000Z",
  "type": "assistant.delta",
  "payload": {"text": "bounded fragment"}
}
```

The initial public vocabulary is:

- `run.created`, `run.started`, `run.stopping`;
- `assistant.delta`;
- `retrieval.context`;
- `plan.updated`, `reflection.completed`;
- `tool.started`, `tool.completed`;
- `approval.required`, `approval.resolved`;
- `usage.updated`;
- `run.completed`, `run.failed`, `run.cancelled`.

The backend owns a typed event registry and payload validation. Unknown event
types are ignored by older clients but retained in sequence accounting. The
legacy `token`, `tool_start`, `done`, and related names are produced by an
adapter from the typed internal event, never by a second translation path.

## API

Add a run-scoped API under `/api/v1/agent/runs`:

- `POST /runs` validates ownership, deduplicates the user message, creates the
  run and snapshot, appends `run.created`, commits, dispatches execution, and
  returns HTTP 202 with the run resource.
- `GET /runs/{run_id}` returns the tenant-filtered lifecycle projection and
  stream cursor.
- `GET /runs/{run_id}/events?after={seq}` first replays PostgreSQL rows and
  then tails new events through Redis notification with periodic database
  catch-up. SSE `id` equals the event sequence.
- `POST /runs/{run_id}/cancel` records a cancellation request and returns the
  current run. The worker emits the terminal cancellation event.
- `POST /runs/{run_id}/approvals/{approval_id}` resolves a pending decision by
  compare-and-swap and schedules graph resume.

All reads and mutations filter through the run's organization, user, and
thread/workspace ownership. Cross-tenant objects return 404.

The existing `/agent/stream`, `/agent/stream/confirm`, and
`/agent/stream/resume/{thread_id}` endpoints remain during migration. Their
wire output is generated from the new durable events once dual-write parity is
proven.

## Transaction Boundaries

Run creation is one transaction:

1. Verify thread and optional project ownership.
2. Insert or retrieve the user message by `client_message_id`.
3. Create the run in `queued` state.
4. Create and bind the immutable runtime snapshot.
5. Append `run.created` at sequence one.
6. Commit, then dispatch the worker.

Normal event append is one transaction containing the run-row lock, sequence
increment, event insert, and lifecycle update.

Successful completion is one transaction containing the idempotent final
assistant message and its citations/tool metadata, `assistant_message_id`, the
`run.completed` event, usage, and terminal run status. Failure and cancellation
use equivalent terminal transactions. This prevents terminal streams without a
message and messages whose run remains active.

## Runner Integration

Extract the current graph-to-wire translation in
`backend/src/api/agent/streaming.py` into a transport-neutral runner that emits
typed internal events. The runner receives a durable run and its already-bound
runtime snapshot. It must not create another snapshot during resume.

The worker acquires and renews the existing execution lease. It checks
cancellation between graph events and before executing a tool. A disconnect
never cancels the run. The sweeper terminalizes expired leases and appends a
single `run.failed` event using the same service transaction.

## Frontend Runtime

The frontend adds three layers:

1. `agentRunService` creates, reads, cancels, approves, and subscribes to runs.
2. A pure `runEventReducer` projects ordered events into an active assistant
   message, activities, citations, approval, usage, error, and status.
3. A normalized Zustand slice stores projections by `run_id`, active run by
   `thread_id`, and last sequence by run.

The reducer is idempotent. Events at or below the applied sequence are ignored.
A gap pauses application, fetches the missing range, and resumes in order.
Terminal events trigger a bounded message-page refresh and retire the transient
projection only after the committed assistant message is present.

`useChatSession.ts` becomes a selector/action composition over the normalized
store rather than owning another transcript. `useChatStreaming.ts` is replaced
incrementally by small hooks for submission, subscription, cancellation, and
approval. The visible thread is always:

```text
committed cached messages + active run projection for this thread
```

Only `assistant.delta` updates are queued through
`requestAnimationFrame`. Lifecycle, tool, approval, and failure events apply
immediately. Committed row identity remains stable during token delivery.
Streaming text uses a lightweight preformatted/plain renderer; the existing
citation-aware Markdown renderer mounts after terminal reconciliation.

## Recovery and Consistency

- **Browser disconnect:** the run continues; reconnect starts at the client's
  last sequence and replays PostgreSQL events.
- **Redis unavailable:** SSE falls back to bounded database polling. Execution
  and persistence remain correct.
- **Duplicate submission:** the tenant/thread/client-message idempotency key
  returns the existing run.
- **Concurrent submission:** the active-run constraint returns 409 and its run
  ID; the UI offers stop before resend.
- **Duplicate/out-of-order event:** the reducer ignores duplicates and repairs
  gaps through replay.
- **Worker crash:** lease expiry is converted to exactly one terminal failure.
- **Cancellation:** `stopping` is not terminal; only runner acknowledgement or
  sweeper recovery emits `run.cancelled`.
- **Approval retry:** compare-and-swap permits one decision and one resume.
- **Projection failure:** terminalization rolls back with message persistence;
  the service retries safely using message and event uniqueness constraints.

## Rollout

1. Add schema, typed events, event store, and lifecycle transaction service.
2. Dual-write durable events from the existing streaming runner behind
   `AGENT_RUN_EVENTS_DUAL_WRITE` and measure mapping parity.
3. Add the run API and use PostgreSQL replay plus Redis wake-ups.
4. Add the frontend run client, reducer, and normalized slice behind
   `NEXT_PUBLIC_CHAT_EVENT_RUNTIME`.
5. Cut over only `/chat`, retain the legacy path for immediate rollback, and
   observe lifecycle, replay, gap, latency, and projection metrics.
6. Route legacy SSE through the durable event adapter.
7. After the observation window, delete the old Redis stream buffer, orphaned
   `streamingService.ts`, deprecated streaming slice, and superseded orchestration
   from `useChatStreaming.ts`.

Each deploy step must remain backward compatible. Database migration lands
before code that writes new columns. Removal is a separate PR after the feature
flag has been fully enabled and rollback is no longer required.

## Observability

Structured logs and metrics include `run_id`, tenant-safe thread correlation,
event type and sequence, snapshot ID, delivery source, and terminal reason.
Required metrics cover:

- run creation, active-run conflicts, duration, and terminal outcomes;
- event append latency, sequence conflicts, payload bytes, and mapping parity;
- SSE connection count, database replay count, Redis wake-up latency, gaps,
  reconnects, and duplicate suppression;
- time to first event, time to first delta, and terminal projection delay;
- frontend commits per animation frame and cached-thread first paint.

Never log event payload bodies, skill instructions, prompts, secrets, or full
tool results.

## Testing and Acceptance

Backend unit and integration tests prove:

- tenant isolation and one-active-run enforcement;
- idempotent run creation and message persistence;
- monotonic event sequencing under concurrent append attempts;
- transactionally consistent completion, failure, and cancellation;
- durable replay with Redis unavailable;
- disconnect without execution cancellation;
- approval compare-and-swap and resume idempotency;
- runtime snapshot stability across pause and resume;
- sweeper terminalization without duplicate terminal events;
- exact legacy-to-new event mapping during dual-write.

Frontend unit and component tests prove:

- reducer idempotency, ordering, gap detection, and every event projection;
- per-thread run isolation during rapid switching;
- terminal reconciliation without blank or duplicate assistant messages;
- no committed-row rerender during token delivery;
- at most one delta-driven React commit per animation frame;
- lightweight live rendering and rich completed rendering;
- stop, failure, approval, RAG, plan, usage, tool, and citation parity.

Playwright scenarios cover disconnect/reconnect, reload during execution, rapid
thread switching with a background run, double-submit, approval retries, stop,
Redis-degraded replay, and 200/1,000-message threads.

The performance acceptance targets are:

- cached thread content paints within one animation frame under local test
  conditions;
- token delivery causes no more than one React commit per animation frame;
- committed messages do not rerender because of `assistant.delta`;
- reconnect and replay produce no duplicate characters or tool cards;
- Redis loss cannot lose a completed answer or terminal status.

## Risks and Mitigations

- **Large migration surface:** use dual-write, feature flags, and separate
  removal work.
- **Database write amplification:** batch adjacent deltas for persistence while
  retaining strict sequence order; cap payloads and measure append latency.
- **PostgreSQL polling load:** Redis only wakes subscribers; periodic database
  catch-up guarantees correctness.
- **Two protocols drifting:** generate legacy events from the typed event
  adapter and enforce contract tests.
- **Frontend double sources of truth:** the event runtime owns active
  projection, message pages own committed history, and terminal reconciliation
  is the only handoff.
- **Partial rollout across processes:** schema-first deployment and feature
  flags keep old readers and writers valid throughout migration.
