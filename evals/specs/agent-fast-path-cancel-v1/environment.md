Status: approved

Dependencies:

- Production dependency image: the same private DigitalOcean registry tag
  used by `agent-hitl-lifecycle-v1`/`agent-tenant-isolation-v1`
  (`3a436b2-r1`, resolved digest
  `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`);
  the pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live, reachable only through the Squid
  egress proxy — the fast path's model output content is not asserted by any
  gate (this task tests cancellation durability, not answer quality), but a
  real streaming completion is still required to produce chunks to cancel
  mid-stream.
- PostgreSQL: simulated isolated service, initialized from the pinned
  repository's current SQLAlchemy metadata (`Base.metadata.create_all`) —
  same fidelity limit every post-2026-08-07 task documents (the fresh-DB
  Alembic chain is independently broken).
- Redis: simulated isolated service. Unlike `agent-tenant-isolation-v1`
  (which uses Redis only for the long-term-memory store), this task's Redis
  instance also backs the shared `_SeqEmitter`/`stream_buffer` SSE replay
  mechanism `_stream_luna_fast_path` uses via `emitter.emit()` — the same
  mechanism capability 3 (`agent-stream-cancel-durability-v1`) exercises on
  the graph route.
- Neo4j: not started. The fast path never touches the knowledge graph;
  `NEO4J_URI` is pointed at a closed local port purely to satisfy the
  settings validator, mirroring `agent-hitl-lifecycle-v1`.
- DigitalOcean Knowledge Base, arXiv, object storage, LangSmith, production
  Supabase: disabled or network-blocked; this task does not exercise them.

Backend contracts exercised: `backend/src/api/agent/streaming.py` (the real
`/api/v1/agent/stream` route, `_stream_luna_fast_path`, `_finalize_run` /
`_finalize_run_id`, the outer route-agnostic `CancelledError` handler),
`backend/src/services/agent/fast_path.py` (`classify_fast_path_turn`,
`build_fast_path_messages`, `stream_fast_path_chunks`),
`backend/src/services/agent/agent_submission_service.py`
(`accept_submission`, `finalize_submission`),
`backend/src/services/agent/run_event_store.py` (`append_event`,
`RunAlreadyTerminalError`), `backend/src/models/agent_run_event.py`
(`uq_agent_run_events_one_terminal`).

Data:

- One synthetic org/user/workspace/conversation/thread
  (`00000000-0000-4000-8000-000000000d01` / `…0d02` / `…0d03` / `…0d04` /
  `…0d05`), seeded via `harbor_common.db.seed_tenant` plus one empty `Thread`
  row (mirroring `agent-stream-cancel-durability-v1`'s prologue) so the
  accept transaction (`_accept_eligible`) has an ownership-verified thread to
  commit against.
- One fast-path-eligible instruction: an ungrounded, non-agentic question
  ("Explain why the sky appears blue in one sentence.") with `use_rag=false`
  and `page_context={"type": "chat"}` — deliberately avoiding
  `fast_path._AGENT_CAPABILITY_RE` keywords (search/find/list/document/
  project/etc.) and `_CONTEXT_DEPENDENT_RE` phrasing, so
  `classify_fast_path_turn` returns `eligible=True, reason="ungrounded_generation"`.
- Storage: PostgreSQL tables from production model metadata; Redis flushed
  before use.
- Reset: recreate the database and flush Redis before the trial.

Isolation: one Postgres instance, one Redis instance per trial; outbound
network allowlisted only to the approved model endpoint; no production
credentials; deterministic UUID fixtures for every seeded row.

Fidelity limits: a single local FastAPI process (no ingress, browser Fetch,
HPA, or multi-pod race), same limit `agent-stream-cancel-durability-v1`
documents. The harness can only disconnect the HTTP client *between* SSE
frames — it cannot reproduce the exact mid-`emitter.emit()` cancellation
race `test_fast_path_cancel_links_partial_and_keeps_prefix` constructs at the
unit level by patching `_SeqEmitter.emit`. This task's live run therefore
exercises the disconnect-after-first-token boundary (same black-box
technique as capability 3); the emit-before-append ordering gate itself is
still fully exercised at the verifier level because the adapter records its
own before/after instrumentation for every chunk it processes
(`token_log`), and the calibration fixtures cover the mid-emit race
directly by construction — this is a calibration-verified task, not a
run-verified one, per `AGENT_FLOW_BASELINE.md`'s Verification section.
