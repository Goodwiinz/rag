# Session Fixes — Codex Audit & Verify Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or dispatch codex:codex-rescue per task) to run this plan task-by-task.

**Goal:** Independently audit and verify today's three fixes (#1406 arXiv fielded query, #1407 server-side-history enable, #1405 multi-worker benchmark tasks) with Codex before/while they merge.

**Architecture:** Each open PR gets one focused Codex audit pass (read the diff + the code it activates, hunt for regressions), then a verify pass (run the relevant tests / reproduce the fixed behavior). Findings route back as PR fixes or explicit accepts.

**Tech Stack:** codex:codex-rescue subagent, pytest (main-repo venv `/Users/goodwiinz/development/RAG_system/backend/.venv`), gh CLI, live arXiv API.

---

### Task 1: Codex audit — #1406 arXiv fielded query

**Files:**
- Read: `backend/src/services/agent/tools_impl.py` (`_field_arxiv_query`, `_tool_search_arxiv`, `_sanitize_arxiv_query`, cache-key helpers)
- Read: `backend/tests/api/test_arxiv_search_sanitize.py`

**Audit questions:**
1. Does `_ARXIV_QUERY_SYNTAX` misclassify any legitimate plain-keyword query (e.g. keywords containing a colon like `C++:` or parens in paper titles)? Consequence of a false positive = passthrough (old behavior), false negative = broken arXiv syntax — verify which side errs.
2. Cache keys use `original_query` — confirm fielding does not split the cache (same raw query → same key pre/post fix) and does not serve stale unfielded results as if fielded (key includes no fielding marker — is a stale-window collision possible right after deploy?).
3. Interaction with `#1404` (recency params PR, same file area) — mechanical-conflict check only.
4. Empty-after-sanitize edge: `_sanitize_arxiv_query` can return original stopword query; fielding then ANDs stopwords (`all:recent AND all:papers`) — is result acceptable (over-restrictive beats junk) or regression?

**Verify:**
- Run: `/Users/goodwiinz/development/RAG_system/backend/.venv/bin/pytest tests/api/test_arxiv_search_sanitize.py -q` (cwd `backend/`) — expect 19 pass.
- Live probe: fielded query returns on-topic titles under `sortBy=submittedDate` (script in PR body).

### Task 2: Codex audit — #1407 Option B activation (highest risk)

**Files:**
- Read: `infrastructure/helm/knowledge-graph-analytics/values-dev.yaml` (diff)
- Read: `backend/src/services/agent/agent_execution_service.py:279-650` (`build_graph_input_messages`, `build_thread_seed_messages`, `_seed_message_id`, divergence guard)
- Read: `backend/src/api/agent/streaming.py:1280-1320` (call site + fallback)

**Audit questions:**
1. Flag flips a shared dev env: enumerate every path where Option B returns `None`/raises and confirm the legacy fallback still runs (no turn can be lost).
2. Seeding path (`count == 0`): can it race a concurrent turn on the same thread (two requests both see empty checkpoint → double seed)? add_messages id-keyed — confirm convergence.
3. HITL resume: confirm/interrupt turns re-enter the graph with `resume` input, not messages — does Option B's "append newest turn" interact with a pending interrupt (the observed 4× duplication case)? Does the flag fix or merely halve that case?
4. Old threads with existing duplicates: Option B counts checkpoint humans (`count > 0` → append-only) — confirm no attempt to reconcile/reseed that could clobber live state.
5. Existing tests covering Option B — name them, run them.

**Verify:**
- Run the Option B test set Codex identifies; expect green.
- Post-merge (after ArgoCD sync): send 2 turns on a fresh dev thread, dump checkpointer skeleton, assert one human per turn (repeat of today's trace method).

### Task 3: Codex audit — #1405 multi-worker benchmark tasks (merged)

**Files:**
- Read: `evals/agent-fast-path-cancel-v1/environment/run_agent.py`, `evals/agent-hitl-lifecycle-v1/environment/run_agent.py`, `evals/agent-stream-cancel-durability-v1/environment/run_agent.py` (uvicorn `--workers 2`)
- Read: `backend/src/services/agent/job_store.py`, `backend/src/services/agent/stream_buffer.py` (cross-worker safety claims)

**Audit questions:**
1. Anything in those three tasks that assumes same-process state (module globals, in-proc probes hitting a different worker's state, port readiness with 2 workers)?
2. `stop_application` SIGTERM on the uvicorn parent — confirm children reaped (no zombie holding port 8081 across phases).
3. L1 cache in job_store (process-local OrderedDict) — any read path that can serve stale L1 over Redis truth cross-worker?

**Verify:** static audit only (full benchmark run is expensive; user triggers separately).

### Task 4: Findings → actions

- Real defects: fix on the PR branch, re-run tests, push.
- Accepted risks: one line each in the PR description.
- Then hand the PR set to the merge loop.
