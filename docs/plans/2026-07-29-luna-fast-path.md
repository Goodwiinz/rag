# Luna Fast Path Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a durable, fail-closed GPT-5.6 Luna fast lane that targets first-token p95 at or below five seconds while preserving the existing LangGraph path for grounded, tool-using, or ambiguous turns.

**Architecture:** The authenticated SSE endpoint emits an immediate, unbuffered status frame, resolves and ownership-checks the thread, then applies a deterministic local policy. Eligible turns stream directly from a dedicated Luna deployment while the user row is persisted concurrently; finalization persists the assistant row and appends the deterministic Human/AI pair to the LangGraph checkpoint before `done`. Ineligible turns continue through the existing graph and emit truthful phase-status frames. One Gunicorn worker per pod is made configurable so bounded speculation cannot run inside the current two-worker memory cliff.

**Tech Stack:** FastAPI, LangChain/AzureChatOpenAI, LangGraph, SQLAlchemy async, SSE, Next.js/React/Zustand, Vitest, pytest, Helm, Docker.

---

### Task 1: Deterministic Fast-Path Policy and Configuration

**Files:**
- Create: `backend/src/services/agent/fast_path.py`
- Modify: `backend/src/core/config.py`
- Modify: `backend/src/services/agent/schemas.py`
- Test: `backend/tests/unit/services/agent/test_fast_path.py`
- Test: `backend/tests/unit/services/test_llm_factory.py`

**Steps:**
1. Write failing tests for a fail-closed policy: bare conversational turns may use Luna; explicit RAG, project/document references, tool/action language, prior assistant/tool-dependent references, and ambiguous questions must use LangGraph.
2. Run the focused tests and verify they fail because the policy/configuration does not exist.
3. Add `AGENT_FAST_PATH_ENABLED`, `AGENT_FAST_PATH_DEPLOYMENT`, input/output budgets, and a pure `classify_fast_path_turn()` implementation.
4. Add Luna to the supported internal/request deployment vocabulary without changing the live main deployment.
5. Run the focused tests and verify they pass.

### Task 2: Phase-Aware SSE Contract

**Files:**
- Modify: `backend/src/shared/enums.py`
- Modify: `backend/src/api/agent/execute.py`
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `frontend/src/services/agentStreamEvents.ts`
- Modify: `frontend/src/services/agentChatService.ts`
- Modify: `frontend/src/store/chat/types.ts`
- Modify: `frontend/src/store/chat/initialState.ts`
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts`
- Modify: `frontend/src/components/chat/aui/AuiMessage.tsx`
- Test: `backend/tests/contract/test_sse_event_vocabulary.py`
- Test: `frontend/src/services/__tests__/agentStreamEvents.contract.test.ts`
- Test: `frontend/src/services/__tests__/agentChatService.test.ts`
- Test: `frontend/src/components/chat/aui/__tests__/StreamingThinkingPill.test.tsx`

**Steps:**
1. Write failing backend/frontend contract tests for `status` frames and phase dispatch.
2. Run the focused tests and verify the missing event/callback failures.
3. Add the frozen `status` wire event and a small phase payload.
4. Emit `accepted` before thread/database setup without exposing or buffering an unverified thread id.
5. Render backend phases truthfully instead of deriving “Reading sources” solely from the local RAG toggle.
6. Run the focused contract/component tests and verify they pass.

### Task 3: Durable Direct-Luna Streaming

**Files:**
- Modify: `backend/src/services/agent/fast_path.py`
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/src/services/agent/agent_execution_service.py`
- Test: `backend/tests/api/agent/test_stream_fast_path.py`
- Test: `backend/tests/api/agent/test_stream_persistence_order.py`
- Test: `backend/tests/api/agent/test_stream_response_latency.py`

**Steps:**
1. Write failing generator tests proving eligible turns bypass `astream_events`, early model chunks remain buffered until user persistence completes, tokens stream in order, and ineligible turns still invoke LangGraph.
2. Write failing durability tests proving successful and partial Luna responses persist with deterministic ids and are appended to checkpoint state before `done`.
3. Run the focused tests and verify the intended failures.
4. Implement a bounded direct-Luna producer using the existing Azure/LangChain factory and shared `_SeqEmitter`.
5. Start the Luna request and guarded user persistence concurrently after ownership resolution; release buffered tokens only after persistence settles.
6. Reuse the existing assistant persistence metadata and partial-stop behavior.
7. Reconcile Human/AI messages through `graph.aupdate_state()` before the terminal event, preserving deterministic message ids.
8. Add cancellation, timeout, usage, metrics, and fail-closed fallback behavior without duplicating the SSE lifecycle.
9. Run the focused tests and verify they pass.

### Task 4: Honor the RAG Contract and Add Safe Rollout Controls

**Files:**
- Modify: `backend/src/services/agent/state.py`
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/src/services/agent/_nodes_rag.py`
- Modify: `infrastructure/helm/knowledge-graph-analytics/values.yaml`
- Modify: `infrastructure/helm/knowledge-graph-analytics/values-dev.yaml`
- Test: `backend/tests/services/agent/test_rag_fast_path.py`
- Test: `backend/tests/unit/services/agent/test_fast_path.py`

**Steps:**
1. Write failing tests that `use_rag=False` suppresses retrieval and that the fast policy never overrides explicit grounded/project requests.
2. Run the tests and verify the current graph ignores `use_rag`.
3. Carry `use_rag` into `AgentState` and make `rag_node` honor it while preserving mandatory project/tool ownership checks.
4. Add disabled-by-default chart values and enable the Luna fast lane only in dev with a one-command values rollback.
5. Run focused tests and render the dev Helm chart.

### Task 5: Remove the Gunicorn Worker/Memory Mismatch

**Files:**
- Modify: `backend/docker/Dockerfile.prod`
- Create: `backend/docker/start-production.sh`
- Test: `backend/tests/unit/docker/test_production_entrypoint.py`
- Modify: `infrastructure/helm/knowledge-graph-analytics/values-dev.yaml`

**Steps:**
1. Write a failing static contract test proving the production entrypoint honors `GUNICORN_WORKERS`/`WORKERS` instead of hardcoding two workers.
2. Run the test and verify it fails against the current Docker CMD.
3. Add a non-shell-expansion-risk entrypoint that validates numeric worker/thread/timeouts and execs Gunicorn.
4. Keep dev at one worker per pod and document the rollback.
5. Run the contract test and build or parse-validate the production Dockerfile.

### Task 6: Verification and Benchmark Gate

**Files:**
- Create: `backend/tests/perf/test_agent_luna_fast_path.py`
- Create: `scripts/perf/benchmark_agent_fast_path.py`
- Modify: `docs/plans/2026-07-29-luna-fast-path.md`

**Steps:**
1. Add a non-production benchmark harness that records accepted-event latency, first-token latency, completion latency, route, prompt size, and failures.
2. Run backend unit/contract/integration tests relevant to the agent stream.
3. Run frontend SSE contract, component, type-check, and lint gates.
4. Render Helm dev manifests and inspect image/runtime configuration.
5. Run a bounded authenticated dev benchmark only after deployment; do not claim p95 until a representative sample passes.
6. Review `git diff --check`, the full diff, and current live deployment health before handoff.

---

## Implementation and verification record

- Tasks 1–5 implemented locally with the fast lane disabled by default and
  enabled only in `values-dev.yaml`.
- The direct lane never releases model output before guarded user persistence
  settles, persists partial output on failure/cancellation, and reconciles the
  Human/AI pair into the LangGraph checkpoint before `done`.
- `use_rag=False` now reaches `AgentState` and suppresses `rag_node` retrieval;
  grounded/project/tool turns still fail closed to the graph route.
- Production Gunicorn settings are validated by `start-production.sh`; dev
  explicitly runs one worker per pod.
- Local verification before deployment: 453 relevant backend tests passed
  (10 dependency-gated skips), 1,553 frontend tests passed (8 skips),
  TypeScript passed, the changed-file ESLint ratchet passed, Helm rendered,
  and the production Dockerfile build check reported no warnings.

Run the bounded dev benchmark after the new image is healthy:

```sh
NOUS_BENCHMARK_TOKEN='<short-lived token>' \
  backend/.venv/bin/python scripts/perf/benchmark_agent_fast_path.py \
  --base-url https://dev-api.gen-text.app \
  --samples 20 --warmups 2 --concurrency 1 --target-p95-ms 5000
```

Do not record the p95 target as passed until that deployed run succeeds with
zero failures.
