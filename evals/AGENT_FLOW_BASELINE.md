# NOUS agent-flow baseline — 2026-08-07

Regression gate for three production agent capabilities. Successor to the
2026-08-04 incident baseline (PR #1345); this revision integrates the P1 fixes
from PR #1350, hardens the benchmark contract for CI gating, and was corrected
against a source audit of the agent implementation (2026-08-07, Fable master +
Opus subagents; findings inline below).

## Manifest (immutable per baseline)

Every run records this block verbatim; cross-digest comparisons are rejected.

| Key | Value |
| --- | --- |
| `repo_sha` | _filled at run time_ |
| `agent_sha` | _filled at run time_ (dev image tag from gitops workflow) |
| `harbor_version` | ≥ 0.6.6 |
| `runner_digest` | `sha256:` of Harbor runner image (`registry.digitalocean.com/ragsystemregistry/backend:<tag>`) |
| `python_version` | 3.12.x (exact patch from runner) |
| `pytest_version` | from `pytest --version` |
| `task_digests` | Per-capability SHA-256, as recorded in `evals/source-manifests/` |
| `harness_digest` | SHA-256 of sorted `shasum -a 256` over `evals/harbor_agents/*.py` |
| `dataset_digest` | SHA-256 of sorted `shasum -a 256` over `evals/<task>/tests/**/*` (calibration + truth) |
| `env_flags` | The flag set the run executed under — at minimum `DO_KB_ENABLED`, `DO_KB_PRIMARY_READ`, `AGENT_DOKB_COHERE_RERANK`, `AGENT_FAST_PATH_ENABLED` |

Digest computation matches the algorithm in `source-manifests/agent-flow-2026-08-04.json`:
SHA-256 of sorted `shasum -a 256` lines using repository-relative paths, `__pycache__` excluded.

**Rule:** a run whose `task_digest` or `harness_digest` differs from the
declared baseline is a _new_ baseline, not a regression comparison. Tooling
must reject mismatched digests unless `--force-new-baseline` is passed.
`env_flags` is likewise part of the comparison identity: a run under a
different flag set is a different baseline (several gates below are only
exercised under specific flags).

## Scoring layers

Each trial produces three independent verdicts:

### A. Objective gates (deterministic, binary)

Hard pass/fail on observable state — no LLM judge involved:

- Token leakage: credential-shaped content must not appear in model-visible context.
- Routing: intent classification matches expected route and confidence band.
- Tool events: expected tool subset invoked, loop ceiling respected, no extra mutations.
- State transitions: DB rows, Redis keys, run status fields match postconditions.
- Cancellation invariants: prefix, pointer cleanup, terminal-event counts.

### B. Semantic gates (LLM judge)

Answer correctness, fidelity to source, absence of hallucination. Scored by
calibrated judge with known pass/fail fixtures (judge must score its own
calibration set 100% before the run is valid). A capability with no judgeable
answer (e.g. cancellation) records semantic = N/A, which **counts as pass**
in the suite score.

### C. Infrastructure gate (non-scoring)

Missing dependency, timeout, unavailable service, seed/config mismatch,
network policy failure unrelated to agent logic. Reported but does **not**
contribute 0 or 1 to the capability score. A run with any C-failures is
flagged `infra-degraded` and must be retried before merging.

**Capability score** = A ∧ B (both must pass; C excluded; B = N/A passes).

## Trial structure

Each capability runs **5 trials minimum**:

| Trial class | Count | Purpose |
| --- | ---: | --- |
| Canonical (fixed seed) | 3 | Deterministic regression detection |
| Near-boundary (seeded variants) | 2 | Phrasing/ordering robustness |

Near-boundary variants use different query phrasing, document order, or
timing but target the same capability and invariants.

### Go/no-go threshold

- **Objective gates: all 5 trials must pass** (zero tolerance on safety).
- **Semantic gates: ≥ 4 of 5 trials pass** (one soft miss acceptable; N/A = pass).
- **Zero infrastructure failures** required (retry until clean or declare blocked).

No confidence-interval requirement at n=5: a binomial 95% lower bound of 0.80
needs ≥ 14 consecutive passes, so it is unattainable at this trial count and
was removed. If a statistical bound is wanted later, raise the trial count to
≥ 14 first and only then reinstate the CI rule.

Report p50/p95 agent elapsed, first-token latency, and terminalization time for
both canonical and near-boundary sets.

## Capabilities

The gated suite is **capabilities 1–3** (N = 3). Capability 4 (intent routing)
is an acceptance spec for a harness that does not exist yet and is excluded
from the suite score until `agent-intent-routing-v1` lands.

### 1. Direct project action

**Objective gates:**
- Classifier source = `action_override`, intent = `research`, confidence = 1.0.
  (`action_override` is a *source*, not an intent — the override table
  `ACTION_INTENT_OVERRIDES` in `_prompts.py` maps "create a project" phrasings
  to intent `research`, which routes to `research_subgraph` where
  `create_project` is bound.)
- HITL confirmation requested before mutation (interrupt with matching tool/args).
- Exactly one `create_project` tool call, status = success.
- Post-state: one project with expected name in workspace, zero documents/notes/links.
- Milestone ordering: interrupt → pre-approval DB check → approval → tool success → post-DB → final message.

**Semantic gate:** Final acknowledgement names the created project.

### 2. Retrieval safety and grounding

**Preconditions (mandatory):** `DO_KB_ENABLED=true`, `DO_KB_PRIMARY_READ=true`,
and a provisioned org KB. Under default config (`config.py` defaults both
flags false) `do_kb_retrieve` returns an empty success payload
(`reason="disabled"`, `tools_impl.py:1635`) and the RAG node takes the legacy
Postgres hybrid fallback — which performs **no redaction at all**
(`_nodes_rag.py:495-515`). Running this capability under default flags
measures an unexercised code path.

**Objective gates:**
- No credential-shaped token present in any model-visible context or final
  answer. Credential families per `_TOKEN_RE` (`_pii_redact.py`): JWT,
  `sk-proj-`/`sk-ant-`, `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` with ≥ 30-char
  alphanumeric body, and `github_pat_` with ≥ 30-char body. (There is **no**
  bare 40-char-alphanum rule; prefix matching is case-sensitive.)
- Organization and project ownership correctly resolved.
- `score_source` ∈ {`upstream`, `rank_proxy`, `cohere`}; `cohere` required
  only when `AGENT_DOKB_COHERE_RERANK=true` and the Cohere service is enabled.
  Observable via the `rag.context` SSE frame and the `do_kb_retrieve` tool
  result only — the field is dropped from `AgentExecuteResponse.retrieved_contexts`
  (`schemas.py`) and not persisted on citations.
- Near-miss negatives (`ghx_`, `gh_`, under-length bodies) are NOT redacted
  (covered by `backend/tests/services/agent/test_pii_redact.py::TestRedactPII::test_leaves_non_token_lookalikes_intact`).

**Known gaps (tracked, not gated):** the Postgres hybrid-fallback contexts and
`search_documents` tool results are returned unredacted
(`_nodes_rag.py:495-515`, `tools_impl.py:1594-1606`), and both feed the system
prompt / SSE `rag.context` frame / persisted citations verbatim. The "any
model-visible context" scope is therefore aspirational today: only the DO KB
branch is enforced. Closing this is an implementation work item, not a spec
change.

**Semantic gate:** Answer supported by retrieved context per independent judge.

### 3. Stream cancellation durability

**Preconditions:** the turn must be accepted with a durable run
(`_accept_eligible` true; confirm-path `active_run` non-null) — otherwise zero
terminal events is correct behaviour, not a violation. The Luna fast path
must be **excluded** (gate `AGENT_FAST_PATH_ENABLED=false` for this task, or
use fast-path-ineligible prompts): the fast path appends to the persist buffer
*before* `emitter.emit()` and discards the persisted row id on cancel
(`streaming.py:316-397`), so it currently violates both the prefix and the
linkage invariants by construction. Tracked as an implementation gap.

**Objective gates (current harness: first-token position only; harness v2
target: 3 positions — first-token, mid-stream, 95th-percentile partial
length):**

| Invariant | Assertion |
| --- | --- |
| Timing | Disconnect *detection* ≤ 10 s (`_SSE_KEEPALIVE_SECONDS` polling path; immediate on the ASGI-cancel path), full terminalization within 15 s of disconnect |
| Terminal event | Exactly one terminal run event (`uq_agent_run_events_one_terminal` partial unique index enforces this DB-side). It is `run.cancelled` when the abort precedes the `done` frame; an abort *after* `done` legitimately leaves `run.completed` (first-writer-wins) — harness v2's late-cancel position must tolerate that |
| Partial link | The `run.cancelled` **event payload** carries `assistant_message_id` pointing at the stopped partial row (`agent_run_events.payload->>'assistant_message_id'`). Absent when nothing streamed before the abort. Note: the `AgentRun.assistant_message_id` *column* is never written by any code path and stays NULL — do not assert on it |
| Prefix | Persisted partial is an exact prefix of the buffered stream (`len(persisted) <= len(buffered)`). Assumes Redis buffering succeeded per chunk — `emit()` swallows append failures, so a prefix violation with no cancellation involved indicates a buffering fault, which scores as C (infra), not A |
| Redis cleanup | Active pointer key deleted. The replay list key survives under its 3600 s TTL **by design** — it is expected post-run state, not a stale-key violation |
| Resume safety | Resume after cancel of a plain `/stream` turn returns HTTP 204. Cancelling a `/stream/confirm` resume leaves the HITL interrupt parked in the checkpoint, and resume then returns **200 + a re-delivered `confirmation` frame** — assert that, not 204. Either way: zero new model/tool starts (the resume path is a pure read — ownership SELECT, Redis reads, `graph.aget_state`) |
| Idempotency | A second resume returns the *same* status and payload as the first (204 or 200+confirmation), with zero side effects |

**Semantic gate:** N/A (counts as pass — no answer to judge on cancellation).

**Coverage note:** the shipped regression tests
(`test_stream_cancel_run_linkage.py`, `test_stream_cancel_buffer_prefix.py`)
cover only `stream_event_generator`'s disconnect branch. The `CancelledError`
cleanup handler, confirm-stream cancel, fast-path cancel, and resume-after-cancel
are not yet regression-tested; this gate is the spec for that work, not a claim
it exists.

### 4. Intent routing (deterministic, table-driven — NOT YET GATED)

Promoted from P2 note to acceptance spec. Intent enum:
`research | writing | knowledge_graph | general` (`classifier.py:35`).
`action_override` is a classifier **source**, not an intent. Routing is
**confidence-blind**: `route_by_intent` (`_nodes_classify.py:239-248`) keys
only off the intent string — the 0.70 / 0.60 constants inside the classifier
rewrite the intent, they do not gate the edge. `knowledge_graph` routes to
`data_subgraph` (there is no separate knowledge-graph subgraph).

Keyword confidence is quantized (`score/(score+2)` → 0.33, 0.5, 0.6, 0.67 …),
and a weak-but-nonzero keyword hit still overrides a sub-0.7 LLM verdict
(`classifier.py:466-470`; the ≥ 0.60 specialized-intent rescue from #1305
applies only when the keyword score is zero). 0.5 is therefore the *typical*
confidence for all three natural-language rows below, and the likeliest
routing-regression signal this gate exists to catch.

| Query pattern | Expected intent (route) | Confidence band | Required tool subset | Loop ceiling |
| --- | --- | --- | --- | --- |
| "Compare documents in my knowledge base" | `research` (`research_subgraph`) | [0.33, 1.0]; 0.5 typical | `search_documents`; `do_kb_retrieve` with non-empty `chunks` (empty + `reason="disabled"` = precondition failure, scores C) | ≤ 5 (`MAX_RESEARCH_TOOL_LOOPS`) |
| "Create a new project called X" | `research`, source = `action_override` (`research_subgraph`) | 1.0 (deterministic) | `create_project`, exactly one call | 1 observed (not code-enforced) |
| "Summarize this paper" | `writing` (`writing_subgraph`) | [0.33, 1.0]; 0.5 typical | `summarize_document` | ≤ 8 (`MAX_WRITING_TOOL_LOOPS`) |
| "What entities are connected to X" | `knowledge_graph` (`data_subgraph`) | [0.33, 1.0]; 0.5 typical | `search_knowledge_graph` | ≤ 8 (`MAX_DATA_TOOL_LOOPS`) |
| _near-boundary phrasings per row_ | same | same | same | same |

Ceilings count **tool loops**, not tool calls — one AI message with N parallel
tool calls consumes one loop (`subgraphs/_factory.py:135-145`). Per-row max
*call* counts are not enforced anywhere in code today; the harness measures
and reports calls, and gates only on the loop ceiling plus
"no unexpected mutating tool".

**Metrics tracked:** precision, recall, false-positive rate per intent class,
plus latency and token cost. A routing regression (precision drop > 5pp from
baseline) blocks merge even if the downstream answer is correct.

**Status:** requires a new Harbor task (`agent-intent-routing-v1`); not yet
implemented in the harness and **excluded from the suite score** (see
Capabilities preamble). The table above is the acceptance spec.

## Coverage roadmap — full agent surface

The gated suite (1–3) plus spec 4 covers routing, one mutation, one retrieval
path, and cancellation. The agent's full surface is 23 tools across 4
subgraphs, 10 root-graph nodes, HITL, memory, error recovery, and the fast
path. Capabilities 5–12 below extend the gate to that surface. Each follows
the same contract (5 trials, A/B/C scoring, manifest identity); promotion
order is the tier column — a capability enters the suite score only when its
Harbor task lands and its calibration fixtures pass.

| # | Capability | Tier | Surface covered |
| --- | --- | --- | --- |
| 5 | arXiv research flow | next | `search_arxiv`, `ingest_arxiv_papers` (HITL), post-ingest `document_ids` handoff |
| 6 | Writing flow | next | `create_draft` (HITL), `create_project_note`, `export_bibliography`, `compare_documents` |
| 7 | Knowledge-graph flow | next | `extract_entities`, `search_knowledge_graph`, `explore_entity_neighborhood`, `find_entity_paths`, `get_graph_stats` |
| 8 | HITL interrupt lifecycle | next | `interrupt_node`, confirm/reject/timeout, resume semantics |
| 9 | Memory round-trip | later | `memory_retrieval` → `memory_save_node`, `forget_memory`, redaction at the memory boundary |
| 10 | Error recovery | later | `error_recovery.py` taxonomy, tool-hint honouring, MAX_ERRORS, degraded final message |
| 11 | Long-run controls | later | `compactor_node`, `force_synthesis_node`, `reflection_gate`, iteration ledger |
| 12 | Tenant isolation probes | next | cross-org probes against every read tool + RAG node |
| 13 | Luna fast path | blocked | `fast_path.py` — blocked on the cancel defects in "Open implementation gaps" |
| 14 | Project management | later | `list_projects`, `add_document_to_project`, `list_project_documents`, soft-delete visibility |

### 5. arXiv research flow

Objective gates: `search_arxiv` returns results; `ingest_arxiv_papers` fires
`interrupt()` before mutation; after approval, follow-up tool calls use the
returned `document_ids` (UUIDs), never arXiv paper ids; ingested docs are
org-scoped rows with non-null `storage_path`; long-timeout budget respected
(arXiv endpoints are 5-min class). Semantic: answer cites ingested papers.
Near-boundary: reject the interrupt → zero rows persisted.

### 6. Writing flow

Objective gates: `create_draft` and `create_project_note` fire `interrupt()`
(destructive set); notes/drafts land as DB rows in the *requested* project
(ownership verified via Workspace join — Collection has no `owner_id`);
soft-deleted projects never offered as write targets; `export_bibliography`
output parses (BibTeX/CSL). The fake-success shape is the primary target:
**verify the artifact row exists, never the tool's success flag.**
Semantic: draft/summary faithful to source documents.

### 7. Knowledge-graph flow

Objective gates: every KG tool result scoped to the caller's org (Neo4j
queries carry the tenant filter); `explore_entity_neighborhood` /
`find_entity_paths` return only entities reachable from org-owned documents;
`get_graph_stats` counts match a direct Cypher count. Known trap: importing
`knowledge_graph_service` binds the submodule, not the singleton — a dead
hybrid-search path scores as C (infra) until fixed. Semantic: entity answer
consistent with graph contents.

### 8. HITL interrupt lifecycle

Objective gates: interrupt payload names tool + args exactly; **reject**
resumes the graph with zero mutations and a coherent final message; approval
executes exactly once (no double-fire on re-confirm); `POST /confirm/{job_id}`
on an already-resolved interrupt is a no-op with a stable status; cancel while
parked leaves the interrupt re-deliverable (capability 3's confirm-path rule).
Checkpoint URL is `postgresql://` (psycopg v3) — a `+asyncpg` URL is a C
failure. Semantic: N/A.

### 9. Memory round-trip

Objective gates: a fact stated in turn N is retrievable in turn N+1 within the
same thread (memory_save → memory_retrieval); `forget_memory` removes it;
memory rows pass `redact_pii` before storage (`memory_store.py:132`); no
cross-thread or cross-user memory bleed. Semantic: recalled fact used
correctly, not hallucinated.

### 10. Error recovery

Objective gates: a tool returning declared `error_type`/`suggestion` hints has
them honoured, not re-derived (#1288 regression); `transient` never declarable
by tools; MAX_ERRORS terminates the loop with a degraded-but-streamed final
message (pre-built AIMessages need the non-streamed-final fallback — an empty
final render is a hard fail); every AIMessage with `tool_calls` has matching
ToolMessages after sanitization. Semantic: degraded message states what
failed, honestly.

### 11. Long-run controls

Objective gates: a conversation exceeding the compaction threshold triggers
`compactor_node` without losing HITL state or tool linkage; loop-ceiling
exhaustion routes through `force_synthesis_node` and still produces a final
answer; `reflection_gate` decisions logged in the iteration ledger; no
runaway: total loops ≤ ceiling + 1 forced-synthesis pass. Semantic: post-
compaction answer still consistent with earlier turns.

### 12. Tenant isolation probes

Objective gates: for **every** read tool (documents, projects, KG, memory,
suggestions) and the RAG node, a second-org fixture user issues the same
query and receives zero rows/titles/ids belonging to org A; error messages
leak no cross-tenant identifiers; probes run in the same trial batch so
drift is caught per-release. This capability is pure objective — semantic
N/A. Rationale: tenant leaks are NOUS's recurring defect class (#1219,
#1292, hunt-6); the gate makes the sweep continuous instead of episodic.

### 13. Luna fast path (blocked)

Same invariants as capability 3 but on `fast_path.py`. Blocked until gaps 2
(persist-before-emit, discarded row id) close; listing it here keeps the
exclusion in capability 3 honest — the fast path must not stay untested
forever because it is conveniently excluded.

### 14. Project management

Objective gates: `list_projects` excludes soft-deleted rows (the nine-copy
predicate sweep, #1285); `add_document_to_project` flushes before enqueueing
KG jobs (no orphan on failure, #956); `list_project_documents` org-scoped;
project counts match direct DB counts. Semantic: N/A.

**Sequencing note:** "next" tier = highest defect-density areas by repo
history (fake-success writers, HITL, tenant scope, arXiv ingest). Build one
Harbor task per capability; do not batch — each task needs its own digest,
calibration fixtures (1 pass + 1 wrong), and manifest row before it can gate.

## Benchmark hygiene

### Pre-run

- Delete all synthetic user's projects, threads, Redis keys, active traces.
- Verify DB migration state matches `alembic current` at `repo_sha`.
- Confirm verifier calibration fixtures pass (1 pass + 1 wrong per gated task × 3 tasks = 6/6).
- Record manifest block, including `env_flags`.

### Post-run

- Assert no *unexpected* leftover state beyond what the task's success condition requires.
  (e.g., the direct-action task expects one project to exist — that is expected state, not a leak.)
- Expected-state allow-list includes: the task's declared postcondition rows,
  and the stream replay list key under its 3600 s TTL (cancellation task).
- Unexpected rows, Redis keys, or active traces for the synthetic user fail as objective-gate violations.
- Cleanup (teardown) is a harness responsibility and runs after verification.

### Artifact capture (per trial)

Every trial archives to `evals/jobs/<run_id>/`:

| Artifact | Format |
| --- | --- |
| Raw SSE events | `.jsonl` |
| Agent payloads (tool calls, responses) | `.json` |
| DB snapshot (synthetic user rows) | `pg_dump --data-only` filtered |
| Redis snapshot (synthetic keys) | `DUMP` or JSON export |
| Judge prompt + response | `.json` |
| Command used | `command.sh` |
| Manifest block | `manifest.json` |

### Baseline revision rule

If `task_digest`, `harness_digest`, or `env_flags` changes, the old baseline is
archived to `evals/baselines/agent-flow-<date>.json` and a new one is declared.
Never compare across digest boundaries without explicit `--force-new-baseline`.

## Historical context (2026-08-04 baseline)

The initial baseline scored **1/3** and exposed three P1 defects, all fixed in
PR #1350:

1. `_TOKEN_RE` covered only `ghp_`/`ghs_` — `gho_` tokens survived redaction.
2. `persist_partial_stop()` discarded the id from `_persist_assistant_message_safe()`.
3. Token buffer appended before `emitter.emit()` await — cancel could persist unseen chunks.

Defect 1 is unit-regression-tested (regex level; the end-to-end retrieval path
is gated here but only enforced on the DO KB branch — see capability 2 known
gaps). Defects 2–3 are regression-tested on the graph stream path only; the
fast path retains both defect shapes (see capability 3 preconditions). The
2026-08-04 raw data remains in `evals/baselines/agent-flow-2026-08-04.json`.

## Open implementation gaps (from the 2026-08-07 source audit)

Tracked here so the gate's aspirational rows have owners; none of these are
spec bugs:

1. Postgres hybrid-fallback contexts and `search_documents` results bypass
   `redact_pii` (`_nodes_rag.py:495-515`, `tools_impl.py:1594-1606`).
2. Luna fast path: persist-before-emit ordering and discarded persisted-row id
   on cancel (`streaming.py:316-397`).
3. `AgentRun.assistant_message_id` column is dead — either wire it from the
   `run.cancelled`/`run.completed` payloads or drop it.
4. `score_source` is dropped from `AgentExecuteResponse.retrieved_contexts`
   and not persisted on citations.
5. Weak-but-nonzero keyword hits override sub-0.7 LLM verdicts
   (`classifier.py:466-470`) — the residual half of the #1305 fix.

## Comparison contract

For any future revision:

1. Run each gated capability ≥ 5 trials (3 canonical + 2 near-boundary) with matching digests and `env_flags`.
2. Report per capability:
   - Objective: N/5 pass. Semantic: N/5 pass or N/A. Infra failures: count.
   - p50/p95 elapsed, first-token latency, terminalization time.
   - Input/output/cache tokens.
   - Intent, confidence, tool sequence, loop count, tool-call count, retry count, terminal reason.
3. Report aggregate:
   - Suite score = capabilities where (objective 5/5) ∧ (semantic ≥ 4/5 or N/A).
   - Infra health = runs with zero C-failures / total runs.
4. Gate rule: merge requires suite score = 3/3 (gated capabilities only) and infra health = 100%.
5. Evidence in `evals/jobs/`; machine-readable summary in
   `evals/baselines/agent-flow-<date>.json`; source manifest in
   `evals/source-manifests/agent-flow-<date>.json`.
