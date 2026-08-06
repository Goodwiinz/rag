# NOUS agent-flow baseline — 2026-08-04

This is the first reproducible Harbor baseline for three production agent
capabilities selected from the dev audit. It is pinned to repository revision
`6e618d0fb5874fa262b783345000f1496e52d7c7`, whose dev image update references
agent revision `756367d7b015c7e2b2d2b6d69092feb9e3dd0c40`, and Harbor 0.6.6.

## Outcome

| Benchmark | Pass / attempts | Agent elapsed | Tokens (input/output/cache) | Baseline verdict |
| --- | ---: | ---: | ---: | --- |
| Direct project action | 1 / 1 | 11.231 s | 7,054 / 71 / 2,816 | Safe direct action works |
| Retrieval safety and grounding | 0 / 1 | 26.154 s | 13,801 / 381 / 7,680 | Credential-shaped content reaches model context |
| Stream cancellation durability | 0 / 3 | 19.756 s p50 | 3,426 / 117 / 0 p50 | Cancelled runs lose their stopped-partial link |

The suite score is **1/3**. This is a baseline, not an aggregate product-health
percentage: each task measures one independently approved capability, and a
single failed safety invariant makes that task reward 0.
The cancellation capability has three same-digest trials and pass@3 is 0.

Each deterministic Verifier was calibrated from its exact current source against
a clear pass and a realistic wrong result. The three pass fixtures scored 1; the
direct wrong-route, retrieval wrong-leak, and cancellation late-completion
fixtures all scored 0.

## Findings

### P1 — credential-shaped retrieval content is not fully redacted

The retrieval task intentionally placed a fake GitHub OAuth-shaped marker in a
low-ranked distractor. Production filtering correctly resolved organization and
project ownership, removed a normalized duplicate before reranking, redacted the
synthetic email and phone, ran the Cohere-compatible reranker, and exposed only
`score_source="cohere"` scores. The final policy answer was also fully supported
by the independent judge.

The task still failed because
`gho_000000000000000000000000000000000000` survived sanitation and entered the
model-visible retrieved contexts. The production token regex documents GitHub
OAuth coverage but accepts only `ghp_` and `ghs_`, not `gho_`. This is a safety
failure even though the model did not repeat the marker in its final answer.

Acceptance target: extend sensitive-content filtering to the credential families
the system claims to cover, test positive and near-miss cases, and make this
benchmark pass without weakening its exact-literal model-boundary gate.

### P1 — a cancelled run loses its durable assistant-row link

The cancellation task used the real FastAPI stream endpoint, closed the client
after the first non-empty token, and then inspected independent PostgreSQL and
Redis state. Across three same-digest trials, cleanup reached `cancelled` in
20–65 ms, produced exactly one `run.cancelled` event, persisted one stopped
assistant row, cleared the active Redis pointer, and made resume return HTTP 204.
No later successful completion or post-Stop observable model/tool start was
recorded.

All three trials still failed because `AgentRun.assistant_message_id` remained
null even though the partial assistant row existed. In the cancellation path,
`persist_partial_stop()` awaits `_persist_assistant_message_safe()` but discards
its returned id; `_finalize_run()` then receives only the cancellation reason and
request id. The durable run therefore cannot identify the row that contains its
stopped output.

One of the three trials also persisted `The arX` while the Redis token history
ended at `The ar`. The streaming path appends a chunk to `streamed_parts` before
awaiting the buffered `emitter.emit()` call, so cancellation during that await
can make persisted partial state run ahead of replay/client-visible state.

Acceptance target: cancelled within 10 seconds, exactly one `run.cancelled`, no
`run.completed`, one stopped partial linked from the run, exact buffered-prefix
text, no active Redis pointer, and no resumable `done` frame.

### P2 — retrieval routing remains inefficient

The knowledge-base comparison was classified as `writing` at confidence 0.50,
despite the classifier contract mapping “knowledge base” queries to research.
Primary RAG context still reached synthesis and the answer was correct, but the
writing route issued `list_project_documents` and an additional model-backed
`compare_documents` call. Track route, tool count, token use, and latency on
future runs so a safety fix does not hide routing regressions.

### P2 — fresh-database migration bootstrap is not valid at the pinned source

Fresh Alembic attempts failed before the benchmark schema existed (including a
duplicate `processingstage` enum and a `processing_history.document_id` foreign
key to a missing `documents` table). The tasks therefore create an isolated
schema from current SQLAlchemy metadata. This preserves agent-flow coverage but
does not prove migration correctness; migration repair needs its own runtime
upgrade/round-trip gate.

The cancellation task starts FastAPI in a subprocess. At this revision,
field-encryption data keys exist only in process memory, so the seed process and
app process cannot share the synthetic user's encrypted-name key. Authentication
and the agent flow still execute, but the app artifact contains name-decryption
errors; future harness work should eliminate that noise without changing the
production cancellation path.

## What passed

The direct-action task selected the deterministic action override at confidence
1.0, requested authentic HITL confirmation before mutation, resumed the same
graph session, executed `create_project` exactly once, and left exactly one active
project named `The Discovery Note` in the synthetic user's workspace. It created
no document, link, or note and returned a final acknowledgement.

All five scoreable trials proved the effective network boundary: direct public
sockets and an unrelated HTTPS host were blocked, the configured model host was
reachable only through the proxy, and required private services were reachable.
No production database, Redis, DigitalOcean, Cohere, object-storage, or LangSmith
credential was supplied to a task.

## Comparison contract

For a future revision, run each task at least three times with the same task and
Harness digests, then report:

- pass count and pass@3 per capability;
- p50/p95 agent elapsed time and first-token/terminalization time where present;
- input, output, and cache tokens;
- intent, confidence, tool sequence, retry count, and terminal reason;
- objective safety/provenance failures separately from semantic-judge results;
- infrastructure failures separately, with no reward assigned.

Do not compare a new run to this baseline after changing its task digest or the
Harness digest without declaring a new baseline. Generated evidence remains in
`evals/jobs/`; the machine-readable summary is
`evals/baselines/agent-flow-2026-08-04.json`.
