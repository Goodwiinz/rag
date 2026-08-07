# NOUS agent-flow baseline — 2026-08-07

Regression gate for three production agent capabilities. Successor to the
2026-08-04 incident baseline (PR #1345); this revision integrates the P1 fixes
from PR #1350 and hardens the benchmark contract for CI gating.

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

Digest computation matches the algorithm in `source-manifests/agent-flow-2026-08-04.json`:
SHA-256 of sorted `shasum -a 256` lines using repository-relative paths, `__pycache__` excluded.

**Rule:** a run whose `task_digest` or `harness_digest` differs from the
declared baseline is a _new_ baseline, not a regression comparison. Tooling
must reject mismatched digests unless `--force-new-baseline` is passed.

## Scoring layers

Each trial produces three independent verdicts:

### A. Objective gates (deterministic, binary)

Hard pass/fail on observable state — no LLM judge involved:

- Token leakage: credential-shaped content must not appear in model-visible context.
- Routing: intent classification matches expected route and confidence band.
- Tool events: exact expected tool sequence, max call count, no extra mutations.
- State transitions: DB rows, Redis keys, run status fields match postconditions.
- Cancellation invariants: prefix, pointer cleanup, event counts.

### B. Semantic gates (LLM judge)

Answer correctness, fidelity to source, absence of hallucination. Scored by
calibrated judge with known pass/fail fixtures (judge must score its own
calibration set 100% before the run is valid).

### C. Infrastructure gate (non-scoring)

Missing dependency, timeout, unavailable service, seed/config mismatch,
network policy failure unrelated to agent logic. Reported but does **not**
contribute 0 or 1 to the capability score. A run with any C-failures is
flagged `infra-degraded` and must be retried before merging.

**Capability score** = A ∧ B (both must pass; C excluded).

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
- **Semantic gates: ≥ 4 of 5 trials pass** (one soft miss acceptable).
- **Zero infrastructure failures** required (retry until clean or declare blocked).
- Binomial 95% CI lower bound ≥ 0.80 for semantic score across all trials.

Report p50/p95 agent elapsed, first-token latency, and terminalization time for
both canonical and near-boundary sets.

## Capabilities

### 1. Direct project action

**Objective gates:**
- Classifier source = `action_override`, confidence = 1.0 (deterministic override, not LLM-routed).
- HITL confirmation requested before mutation (interrupt with matching tool/args).
- Exactly one `create_project` tool call, status = success.
- Post-state: one project with expected name in workspace, zero documents/notes/links.
- Milestone ordering: interrupt → pre-approval DB check → approval → tool success → post-DB → final message.

**Semantic gate:** Final acknowledgement names the created project.

### 2. Retrieval safety and grounding

**Objective gates:**
- No credential-shaped token (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` families,
  40-char alphanum) present in any model-visible context or final answer.
- Organization and project ownership correctly resolved.
- Reranker scores from expected source.
- Near-miss negatives (`ghx_`, `gh_`, under-length) are NOT redacted.

**Semantic gate:** Answer supported by retrieved context per independent judge.

### 3. Stream cancellation durability

**Objective gates (current harness: first-token position only; harness v2 target: 3 positions — first-token, mid-stream, 95th-percentile partial length):**

| Invariant | Assertion |
| --- | --- |
| Timing | Cancelled within 10 s of client disconnect |
| Event count | Exactly one `run.cancelled`, zero `run.completed` |
| Partial link | `AgentRun.assistant_message_id` points to the stopped partial row |
| Prefix | `len(persisted_text) <= len(buffered_text)` and persisted is exact prefix |
| Redis cleanup | Active pointer = null, no stale replay keys |
| Resume safety | Subsequent resume returns HTTP 204, no new model/tool starts |
| Idempotency | Second resume after successful Stop returns same 204, no side effects |

**Semantic gate:** N/A (no answer to judge on cancellation).

### 4. Intent routing (deterministic, table-driven)

Promoted from P2 note to first-class gate. Intent enum: `research | writing | knowledge_graph | general`.
Note: "direct action" uses `action_override` (deterministic), not LLM classification.

| Query pattern | Expected intent | Confidence band | Required tool subset | Max tool calls |
| --- | --- | --- | --- | --- |
| "Compare documents in my knowledge base" | `research` | [0.70, 1.0] | `search_documents`, `do_kb_retrieve` | 4 |
| "Create a new project called X" | `action_override` | 1.0 (deterministic) | `create_project` | 1 |
| "Summarize this paper" | `writing` | [0.60, 1.0] | `summarize_document` | 2 |
| "What entities are connected to X" | `knowledge_graph` | [0.60, 1.0] | `search_knowledge_graph` | 3 |
| _near-boundary phrasings per row_ | same | same | same | same |

**Metrics tracked:** precision, recall, false-positive rate per intent class,
plus latency and token cost. A routing regression (precision drop > 5pp from
baseline) blocks merge even if the downstream answer is correct.

**Status:** this capability requires a new Harbor task (`agent-intent-routing-v1`);
not yet implemented in the harness. The table above is the acceptance spec.

## Benchmark hygiene

### Pre-run

- Delete all synthetic user's projects, threads, Redis keys, active traces.
- Verify DB migration state matches `alembic current` at `repo_sha`.
- Confirm verifier calibration fixtures pass (1 pass + 1 wrong per task × 3 tasks = 6/6).
- Record manifest block.

### Post-run

- Assert no *unexpected* leftover state beyond what the task's success condition requires.
  (e.g., the direct-action task expects one project to exist — that is expected state, not a leak.)
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

If `task_digest` or `harness_digest` changes, the old baseline is archived to
`evals/baselines/agent-flow-<date>.json` and a new one is declared. Never
compare across digest boundaries without explicit `--force-new-baseline`.

## Historical context (2026-08-04 baseline)

The initial baseline scored **1/3** and exposed three P1 defects, all fixed in
PR #1350:

1. `_TOKEN_RE` covered only `ghp_`/`ghs_` — `gho_` tokens survived redaction.
2. `persist_partial_stop()` discarded the id from `_persist_assistant_message_safe()`.
3. Token buffer appended before `emitter.emit()` await — cancel could persist unseen chunks.

These are now regression-tested by the objective gates above. The 2026-08-04
raw data remains in `evals/baselines/agent-flow-2026-08-04.json`.

## Comparison contract

For any future revision:

1. Run each capability ≥ 5 trials (3 canonical + 2 near-boundary) with matching digests.
2. Report per capability:
   - Objective: N/5 pass. Semantic: N/5 pass. Infra failures: count.
   - p50/p95 elapsed, first-token latency, terminalization time.
   - Input/output/cache tokens.
   - Intent, confidence, tool sequence, retry count, terminal reason.
3. Report aggregate:
   - Suite score = capabilities where (objective 5/5) ∧ (semantic ≥ 4/5).
   - Infra health = runs with zero C-failures / total runs.
4. Gate rule: merge requires suite score = N/N and infra health = 100%.
5. Evidence in `evals/jobs/`; machine-readable summary in
   `evals/baselines/agent-flow-<date>.json`; source manifest in
   `evals/source-manifests/agent-flow-<date>.json`.
