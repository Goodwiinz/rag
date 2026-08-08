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

**Known gaps — closed by #1353:** the Postgres hybrid-fallback contexts and
`search_documents` tool results now pass `redact_pii` before the model
boundary, so the "any model-visible context" scope is enforced on both
retrieval paths, not just the DO KB branch. The preconditions above still
apply for exercising the DO KB branch specifically.

**Semantic gate:** Answer supported by retrieved context per independent judge.

### 3. Stream cancellation durability

**Preconditions:** the turn must be accepted with a durable run
(`_accept_eligible` true; confirm-path `active_run` non-null) — otherwise zero
terminal events is correct behaviour, not a violation. The Luna fast path's
prefix and linkage defects were fixed in #1353 (emit-before-append ordering,
`assistant_message_id` in the cancel payload), so fast-path-eligible prompts
are no longer excluded by construction — capability 13 covers them.

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
| 6 | Writing flow | task landed | `create_draft` (HITL), `export_bibliography`, `compare_documents` (Harbor task `agent-writing-flow-v1`; awaiting first recorded run — `create_project_note` still uncovered) |
| 7 | Knowledge-graph flow | next | `extract_entities`, `search_knowledge_graph`, `explore_entity_neighborhood`, `find_entity_paths`, `get_graph_stats` |
| 8 | HITL interrupt lifecycle | next | `interrupt_node`, confirm/reject/timeout, resume semantics |
| 9 | Memory round-trip | later | `memory_retrieval` → `memory_save_node`, `forget_memory`, redaction at the memory boundary |
| 10 | Error recovery | later | `error_recovery.py` taxonomy, tool-hint honouring, MAX_ERRORS, degraded final message |
| 11 | Long-run controls | later | `compactor_node`, `force_synthesis_node`, `reflection_gate`, iteration ledger |
| 12 | Tenant isolation probes | next | cross-org probes against every read tool + RAG node |
| 13 | Luna fast path | next | `fast_path.py` — cancel defects fixed in #1353; same invariants as capability 3 |
| 14 | Project management | task landed | `create_project`, `add_document_to_project`, `create_project_note`, `list_project_documents` read-back, three-step HITL ordering (Harbor task `agent-project-management-v1`; awaiting first recorded run — soft-delete visibility still uncovered) |
| 15 | Knowledge-base retrieval | task landed | `search_documents`, `do_kb_retrieve` (Harbor task `agent-kb-retrieval-v1`; awaiting first recorded run — `summarize_document` deferred, see coverage note) |

### 5. arXiv research flow

Objective gates: `search_arxiv` returns results; `ingest_arxiv_papers` fires
`interrupt()` before mutation; after approval, follow-up tool calls use the
returned `document_ids` (UUIDs), never arXiv paper ids; ingested docs are
org-scoped rows with non-null `storage_path`; long-timeout budget respected
(arXiv endpoints are 5-min class). Semantic: answer cites ingested papers.
Near-boundary: reject the interrupt → zero rows persisted.

### 6. Writing flow

**Preconditions:** the seeded workspace (`00000000-0000-4000-8000-000000000603`)
in org `00000000-0000-4000-8000-000000000601` holds one active project
`Tool Coverage Writing Study` (`00000000-0000-4000-8000-000000000604`) with
exactly two pre-loaded, non-deleted documents already attached: `Graph Neural
Networks for Molecular Property Prediction`
(`00000000-0000-4000-8000-000000000605`) and `Attention Mechanisms in
Transformer Architectures` (`00000000-0000-4000-8000-000000000606`).
`create_draft` is the sole destructive tool in scope (`tools.py:633`); it
fires `interrupt()` before any generation is enqueued, and its async shape
(`DraftGenerationService.generate_draft` returns a `task_id` + non-terminal
status from a fire-and-forget background task) is the fake-success trap this
capability targets — a result claiming a terminal status or carrying draft
content is fabricated evidence, not a completed synchronous draft.
`compare_documents` (`tools.py:498`) and `export_bibliography`
(`tools.py:661`) are non-destructive and execute directly with no interrupt
of their own.

**Objective gates:**
- No mutation lands before the approval that releases it. The load-bearing
  proof is `evidence["database"]["before_approvals"][0]` — a row snapshot
  taken immediately before the single approval is sent — asserted as zero
  `generated_drafts` rows for the seeded project
  (`tests/verify.py:435-465`). The `create_draft_success` milestone is
  secondary and only catches a doctored evidence file
  (`tests/verify.py:382-413`).
- `create_draft`'s result carries a `task_id` and a non-terminal
  `DraftGenerationStatus` (`pending`/`analyzing`/`generating`/`citing`/
  `reviewing`), never `content`, `generated_draft_id`, `draft_id`, or
  `version` — a terminal status or artifact key this soon means the result
  was fabricated to look synchronous (`tests/verify.py:467-507`).
- Real call order proven over `raw_tool_executions` positions (not the
  post-loop success milestones, which the adapter always appends after
  `approval:create_draft` regardless of actual order): `compare_documents` <
  `create_draft` < `export_bibliography` (`tests/verify.py:415-433`).
- `compare_documents` targets exactly the two seeded `document_ids` within
  the impl's 5-document cap; an over-cap near-boundary call must fail with
  the impl's exact cap message, classified `fatal` (no `TOOL_ERROR_HINTS`
  entry or keyword fallback matches it) — verified against
  `backend/src/services/agent/error_recovery.py`
  (`tests/verify.py:288-360`).
- `export_bibliography` targets exactly the two seeded documents in the
  requested format and returns non-empty bibliography text
  (`tests/verify.py:509-538`).
- No unapproved or unsanctioned destructive execution — any destructive-set
  tool besides `create_draft` is a failure outright
  (`tests/verify.py:540-568`).
- State exactness in PostgreSQL, read independently of the adapter: the
  seeded project remains present and active, and exactly the two seeded
  documents remain present and non-deleted; the adapter's own final document
  set must equal the verifier's independent read
  (`tests/verify.py:570-611`).
- Final message and termination: a non-empty user-visible final assistant
  message, no pending tool calls, `termination_reason = "completed"`
  (`tests/verify.py:613-625`).

**Semantic gate:** draft/summary faithful to the two source documents
(`harbor_common/judge.py`, folded in only after every objective check runs).

**Coverage note:** this task exercises compare → draft (HITL) → export in
one trial and the async-draft fake-success trap. It does not yet cover
`create_project_note`, ownership verification via the Workspace join
(Collection has no `owner_id`), or soft-deleted projects being excluded as
write targets — those remain the next increments on this capability.

**Status:** NOT YET GATED — awaits first recorded run.

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

### 13. Luna fast path

Same invariants as capability 3 but on the fast-path route. Unblocked by
#1353 (emit-before-append ordering + cancel linkage now match the graph
path); regression-tested at the unit level by
`test_fast_path_cancel_links_partial_and_keeps_prefix`. Known tolerance: the
outer route-agnostic handler fires a second unlinked `run.cancelled` finalize
that the terminal unique index absorbs — the durable event is the linked one.

### 14. Project management

**Preconditions:** the seeded workspace
(`00000000-0000-4000-8000-000000000503`) starts with zero projects, zero
collection-document links, and zero project notes, and holds exactly one
pre-loaded document `Seed Paper` (`00000000-0000-4000-8000-000000000505`) in
org `00000000-0000-4000-8000-000000000501`. All three writes are in the
production destructive set (`_nodes_tools.py:59` builds it from every
descriptor tagged `ToolPolicyTag.DESTRUCTIVE`), so each must park an
`interrupt()` before it runs — a run that never interrupts is a gate failure,
not a fast completion.

**Objective gates:**
- No mutation lands before the approval that releases it. The load-bearing
  proof is `evidence["database"]["before_approvals"]` — a row snapshot taken
  immediately before each approval is sent (`environment/run_agent.py:365`) —
  asserted as mutated rows ≤ approvals already granted across `collections`,
  `collection_documents`, and `project_notes`
  (`tests/verify.py:379-438`). The milestone comparison
  (`<tool>_success` after `approval:<tool>`) is secondary: the adapter emits
  success milestones after the drive loop returns, so it only catches a
  doctored evidence file.
- No unapproved destructive execution. Any tool in the mirrored destructive
  registry outside the three the task sanctions is a failure outright, and any
  successful execution whose name reads as a write (`create_`, `add_`,
  `delete_`, `update_`, `ingest_`, … prefix sweep) must show an approved
  interrupt (`tests/verify.py:441-472`).
- Three HITL approvals, in order, with exact arguments: `create_project`
  (`tools.py:351`) with `name="Tool Coverage Study"`;
  `add_document_to_project` (`tools.py:326`) targeting the pre-loaded
  `document_id`; `create_project_note` (`tools.py:380`) with
  `title="Kickoff"` and the requested content. Each interrupt carries non-empty
  args and an `approved_at` timestamp; interrupt and approval milestone indices
  are both ascending in that order (`tests/verify.py:292-368`). Ordering is
  asserted by index containment, never list equality — the adapter may append
  additive milestones.
- State exactness in PostgreSQL, read independently of the adapter: exactly
  one non-deleted project named `Tool Coverage Study` in the seeded workspace,
  exactly one `collection_documents` link to the seed document, exactly one
  `Kickoff` note with the requested body, and the one pre-loaded document
  unchanged (`tests/verify.py:475-531`). The adapter's own final counts must
  equal the verifier's independent read (`tests/verify.py:534-546`) — the
  fake-success shape is the target, so rows are the evidence, never a tool's
  success flag.
- Read-back: `list_project_documents` (`tools.py:449`) executed successfully
  after the last approved mutation and its result contains the seed document
  id (`tests/verify.py:549-577`).
- Final message and termination: a non-empty user-visible final assistant
  message naming both the project and the document, no pending tool calls left
  on it, and `termination_reason = "completed"` (`tests/verify.py:580-597`).

**Semantic gate:** N/A (counts as pass — the answer content this capability
cares about is already gated objectively by the final-message name checks).

**Coverage note:** this task exercises the create/attach/note/read-back path
and the HITL ordering around it. It does **not** yet cover `list_projects`
soft-delete visibility (the nine-copy predicate sweep, #1285),
`add_document_to_project`'s flush-before-KG-enqueue ordering (no orphan on
failure, #956), or cross-org scoping of `list_projects` (`tools.py:410`) and
`list_project_documents` (`tools.py:449`) — those remain the next increments
on this capability.

**Status:** GATED. Harbor task landed (`evals/agent-project-management-v1`),
calibration 1 pass + 1 wrong verified, and first baseline run recorded 2026-08-08
against develop@79af897f (reward 1.0, verifier passed, 3 HITL approvals, all five
tools executed via the general route). See
`baselines/agent-flow-2026-08-07-tools.json`. The run needed four develop fixes
to pass — #1356, #1357, #1358, #1355 — none of which the pinned source
(261273129) carried; the capability was genuinely broken until they landed.

### 15. Knowledge-base retrieval

**Preconditions:** the seeded org (`00000000-0000-4000-8000-000000000701`)
has a provisioned `do_kb_uuid` and holds exactly two non-deleted documents:
`API Rate Limit Policy` (`00000000-0000-4000-8000-000000000704`) and
`Webhook Retry Policy` (`00000000-0000-4000-8000-000000000705`). No tool in
scope for this task is destructive, so no interrupt is expected — a paused
graph is itself a gate failure.

**Objective gates:**
- `search_documents` (`tools.py:272`) executes within its `max_results` cap
  and surfaces the seeded `API Rate Limit Policy` document
  (`tests/verify.py:204-220`).
- `do_kb_retrieve` (`tools.py:293`, impl `tools_impl.py:1616`) executes
  within its `top_k` cap and returns `source: "do_kb"` with a `chunks` list.
  `reason: "disabled"` or `reason: "not_provisioned"` is a Layer A failure
  (environment misconfiguration), not a legitimate empty result; a
  zero-`chunks` success must never carry a fabricated `error` field — the
  retrieval fake-success trap this capability targets
  (`tests/verify.py:229-267`).
- Real call order: `search_documents` before `do_kb_retrieve`
  (`tests/verify.py:270-280`).
- No destructive tool executes; this task sanctions only `search_documents`
  and `do_kb_retrieve` (`tests/verify.py:282-289`).
- The mock DO KB service recorded at least one `do_retrieve` request with a
  valid Bearer authorization header (`tests/verify.py:291-310`).
- No pending HITL interrupt on exit (`tests/verify.py:312-318`).
- State exactness in PostgreSQL, read independently of the adapter: org
  `do_kb_uuid` matches, and exactly the two seeded documents remain present
  and non-deleted (`tests/verify.py:320-334`).
- Final message and termination: a non-empty user-visible final assistant
  message, no pending tool calls, `termination_reason = "completed"`
  (`tests/verify.py:336-348`).

**Semantic gate:** answer summarizes only what `do_kb_retrieve` actually
returned, citing the source — grounding is judged, not assumed
(`harbor_common/judge.py`, folded in only after every objective check runs).

**Coverage note:** scope decision (plan Task 3 Risk 1): this task covers
`search_documents` + `do_kb_retrieve` only. `summarize_document` is deferred
— it sits on the writing/general routing side rather than the research-only,
empty-intent path these two tools share, and cross-binding it here would
force a pass rather than resolve the routing question. Also not yet covered:
cross-org scoping of either tool (capability 12 covers tenant probes
generally, not this task specifically) and the Postgres hybrid-search
fallback path when DO KB is unavailable.

**Status:** NOT YET GATED — awaits first recorded run.

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

All five closed by PR #1353 (kept for history):

1. ~~Postgres hybrid-fallback contexts and `search_documents` results bypass
   `redact_pii`~~ — fixed in #1353: both paths redact before the model
   boundary (hybrid redacts before the 3000-char slice).
2. ~~Luna fast path: persist-before-emit ordering and discarded persisted-row
   id on cancel~~ — fixed in #1353: fast path now matches the graph path's
   prefix + linkage invariants. (Pre-existing residual, noted in the fast-path
   cancel test: the outer route-agnostic handler issues a second unlinked
   `run.cancelled` finalize, absorbed by `uq_agent_run_events_one_terminal`.)
3. ~~`AgentRun.assistant_message_id` column is dead~~ — fixed in #1353:
   `finalize_submission` projects the id from terminal payloads onto the run
   row (UUID-guarded).
4. ~~`score_source` dropped from `AgentExecuteResponse.retrieved_contexts`~~ —
   fixed in #1353. Note: the field surfaces in runtime job-result payloads and
   the SSE `rag.context` frame; it does NOT appear in `openapi.json` because
   `AgentExecuteResponse` is not any route's `response_model` (job-based API).
   Still not persisted on citations (accepted).
5. ~~Weak-but-nonzero keyword hits override sub-0.7 LLM verdicts~~ — fixed in
   #1353: a specialized LLM verdict ≥ 0.60 that is more confident than the
   keyword hit now wins; ties and stronger keyword hits keep the keyword
   result.

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
