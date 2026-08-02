# Agent Production Baseline P0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the missing P0 production contracts around the deployed agent stream while preserving the existing Luna fast path, durable `/execute` dispatch, and fail-closed shared-environment persistence.

**Architecture:** Keep the current SSE event vocabulary and payload fields backward compatible, but add a versioned common envelope and standards-compatible replay cursor. Instrument the existing sequence emitter so every route records the same bounded, low-cardinality SLIs without duplicating terminal handling. Extend the non-production benchmark into a release gate for accepted latency, first-token latency, completion latency, route correctness, and failures.

**Tech Stack:** FastAPI, SSE, Redis stream buffer, Prometheus client, OpenTelemetry trace context, Next.js/TypeScript, pytest, Vitest, Helm.

---

### Task 1: Establish the Current P0 Baseline

**Files:**

- Modify: `backend/tests/agent/test_streaming_resume.py`
- Verify: `backend/tests/unit/agent/test_dispatch_backend.py`
- Verify: `backend/tests/unit/agent/test_durable_state_gate.py`
- Verify: `backend/tests/test_health_readiness_cache.py`

**Steps:**

1. Repair stale stream-test request fixtures so they include the current `use_rag` field and ownership-resolved UUID thread.
2. Run the resume suite and confirm its remaining failure is the missing sequence id on the initial accepted frame.
3. Run the dispatch, durability, and readiness suites and record any actual baseline failures.

### Task 2: Add a Versioned, Resumable SSE Envelope

**Files:**

- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/src/api/agent/execute.py`
- Modify: `backend/tests/agent/test_streaming_resume.py`
- Modify: `frontend/src/services/agentChatService.ts`
- Modify: `frontend/src/services/__tests__/agentChatService.test.ts`

**Steps:**

1. Write failing backend tests that every emitted frame contains `schema_version`, `sequence`, `event_id`, `occurred_at`, `trace_id`, `thread_id`, and `route` while retaining event-specific fields.
2. Write failing endpoint tests that `Last-Event-ID` is accepted as the replay cursor, takes precedence over the compatibility query parameter, and rejects invalid numeric cursors.
3. Write a failing frontend test that replay sends `Last-Event-ID`.
4. Add a per-turn trace id and bounded route/thread context to `_SeqEmitter`; make the initial unbuffered accepted event sequence-numbered without exposing an unverified thread id.
5. Add standards-compatible replay-header parsing while retaining `?after=` for existing clients.
6. Update the frontend replay request to send both mechanisms during the compatibility window.
7. Run backend and frontend streaming contract suites.

### Task 3: Add Route-Specific Streaming SLIs

**Files:**

- Modify: `backend/src/services/agent/observability.py`
- Modify: `backend/src/api/agent/streaming.py`
- Create: `backend/tests/unit/services/agent/test_stream_slo_metrics.py`

**Steps:**

1. Write failing tests for accepted latency, first-token-once, terminal latency/status, and bounded route normalization.
2. Add Prometheus histograms/counters for accepted, first token, completion, and terminal outcomes using only `pending`, `luna`, `graph`, and `unknown` route labels.
3. Attach one tracker to `_SeqEmitter` so Luna, graph, confirm, error, cancellation, and replay-safe terminal paths share the same accounting.
4. Run the focused metric and stream tests.

### Task 4: Strengthen the Non-Production Release Gate

**Files:**

- Modify: `scripts/perf/benchmark_agent_fast_path.py`
- Modify: `backend/tests/perf/test_agent_luna_fast_path.py`
- Create: `docs/operations/agent-production-baseline.md`

**Steps:**

1. Write failing tests for independent accepted, first-token, completion, route, sample-count, and zero-failure thresholds.
2. Add explicit CLI thresholds with the current fast-path defaults: accepted p95 250 ms, first-token p95 5,000 ms, completion p95 5,000 ms, minimum 20 samples, zero failures, and 100% Luna routing for the fast benchmark corpus.
3. Emit a machine-readable gate result showing every failed criterion.
4. Document the SLOs, PromQL queries, privacy/cardinality rules, rollback controls, and exact benchmark command.
5. Run the benchmark unit tests.

### Task 5: Verify the Complete P0 Contract

**Files:**

- Verify: `infrastructure/helm/knowledge-graph-analytics/values-dev.yaml`
- Verify: `infrastructure/helm/knowledge-graph-analytics/templates/backend-deployment.yaml`
- Verify: `.github/workflows/test-pipeline.yml`

**Steps:**

1. Run the focused backend SSE, observability, durability, dispatch, readiness, and benchmark suites.
2. Run the focused frontend SSE suites and TypeScript.
3. Render the dev Helm chart and confirm dependency-aware readiness, durable Celery dispatch, Luna routing, and single-worker configuration.
4. Run changed-file formatting/lint checks and `git diff --check`.
5. Review the full diff for tenant identifiers, prompt content, or unbounded metric labels.
