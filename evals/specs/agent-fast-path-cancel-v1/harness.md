Status: approved

Entrypoint: `environment/run_agent.py`, invoked directly by Harbor. Boots the
real `src.main:app` FastAPI process (same pattern as
`agent-hitl-lifecycle-v1`/`agent-stream-cancel-durability-v1`), unlike
`agent-tenant-isolation-v1` which calls tool implementations directly.

Source: repository revision (this branch's `git rev-parse HEAD`) — see
`task.toml` `source_revision`.

Adapter sequence:

1. `bootstrap_schema()` (Postgres) via `harbor_common.db`, then
   `seed_tenant()` for the one synthetic org/user/workspace, then seed one
   empty `Conversation`/`Thread` row directly (mirrors
   `agent-stream-cancel-durability-v1`'s prologue) so `_accept_eligible`
   has an ownership-verified thread.
2. `validate_network_boundary()` via `harbor_common.network`.
3. Start `uvicorn src.main:app`, wait for `/api/v1/agent/health`.
4. Mint a CLI bearer token via `src.core.security.create_cli_token`.
5. `POST /api/v1/agent/stream` with the fast-path-eligible instruction
   (`environment.md`), `Accept: text/event-stream`, a fixed
   `X-Request-ID`. Read SSE frames until the first non-empty `token` frame
   is observed, then immediately `aclose()` the response — the same
   black-box disconnect technique `agent-stream-cancel-durability-v1` uses.
6. Poll the run row (via the adapter's own SQLAlchemy session, not yet the
   verifier's independent connection) until it reaches a terminal `status`
   or a 10-second bound elapses.
7. Read back the persisted assistant row and the run's durable event ledger
   through the adapter's own session, purely as an instrumentation record —
   the verifier's authoritative signal is its own independent psycopg
   connection (same trust split as every other post-2026-08-07 task).
8. Stop the FastAPI process.

Since the harness can only observe the production code path from the
outside (an HTTP client and its own DB session), it cannot literally patch
`_SeqEmitter.emit` the way
`test_fast_path_cancel_links_partial_and_keeps_prefix` does to force a
mid-chunk cancellation. It instead derives `token_log` from what it can
observe: for every SSE `token` frame that was actually received before the
disconnect, `emit_completed=true` and `appended_to_partial=true` (the frame
reaching the client is proof the emit completed and the production code's
own "buffer before append" ordering already ran); the harness never invents
an `emit_completed=false` entry from a live run, because a live run cannot
observe a chunk whose emit did not complete. That failure mode exists only
in the calibration fixture space this task's verifier gate is built to
reject (`tests/calibration/wrong-emit-after-append.json`), exactly the
"calibration-verified, not run-verified" posture the plan's Verification
section describes.

Recorded evidence (the `evidence.json` envelope the verifier reads):

- `schema_version`, `benchmark_id`, `source_revision`, `agent_revision`,
  `started_at`, `completed_at`, `elapsed_ms`, `termination_reason`
  (`"cancelled"`), `model_usage`.
- `synthetic_actor`: `organization_id`, `user_id`, `workspace_id`,
  `conversation_id`, `thread_id`.
- `network_boundary`, `application` (readiness + shutdown exit code).
- `routing`: `{"eligible": bool, "reason": str}` — the
  `classify_fast_path_turn` decision for the submitted instruction. An
  `eligible=false` result means the turn never entered the fast path at
  all, which is an `InfrastructureFailure`, not a gate failure — there is
  nothing fast-path-specific to verify.
- `accepted`: `run_id`, `thread_id`, `user_message_id`, `client_message_id`,
  `assistant_client_message_id` from the SSE `accepted` status frame plus
  the request body.
- `sse`: `{"response": {...}, "frames": [...], "first_token": {...}}` — only
  frames actually observed by the client before disconnect.
- `token_log`: ordered list of `{"content", "emit_completed",
  "appended_to_partial"}` — one entry per model chunk the fast path's
  streaming loop processed, in order, reflecting the "buffer BEFORE
  recording for persistence" invariant `tests/verify.py` gates on directly.
- `disconnect`: `initiated_at`, `completed_at`,
  `terminal_observed_within_bound`, `terminalization_elapsed_ms`,
  `bound_ms` (10000).
- `finalize_attempts`: ordered list of every `_finalize_run`/
  `_finalize_run_id` call the production code issued for this run with
  `event_type == "run.cancelled"`, each `{"source", "event_type", "linked",
  "payload"}` — `source` is `"fast_path_inner"` (the linked call from
  `cancel_fast_path`) or `"outer_route_agnostic"` (the unlinked duplicate
  from `stream_event_generator`'s outer handler). This is the adapter's own
  self-reported attempt log; the verifier's cancel-linkage gate treats the
  independent DB read (`state.events`) as authoritative over it (see
  `task.md`'s tolerance).
- `persisted_partial`: `{"id", "thread_id", "content", "stopped",
  "client_message_id"}` for the stopped assistant row `cancel_fast_path`
  persisted.

Independent verifier state (`state` in the unified `{"evidence", "state"}`
envelope; for a live run this is `tests/verify.py:live_database_state()`,
read through the verifier's own psycopg connection, never the adapter's):

- `run`: `job_id`, `status`, `organization_id`, `user_id`, `thread_id`,
  `client_message_id`, `assistant_message_id` (the `AgentRun` column
  `finalize_submission` projects `payload.assistant_message_id` onto for
  any route — capability 3's own verifier already asserts this same column,
  see `task.md`'s gate 3 note), `last_event_seq`, `completed_at`,
  `error_code`, `error`.
- `events`: every `agent_run_events` row for the run, ordered by `seq` —
  `id`, `run_id`, `seq`, `event_type`, `payload`, `created_at`.
- `messages`: every `chat_messages` row for the thread — `id`, `thread_id`,
  `role`, `content`, `stopped`, `client_message_id`.
- `run_count_for_thread`: count of `agent_runs` rows for the seeded thread
  (should be exactly 1).

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`,
`AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`,
`AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`.
No production database or DO KB credential is permitted.

Reconstruction differences: the adapter drives one real HTTP turn through
the real `/stream` endpoint and disconnects at the client-observable
boundary (after the first token), rather than reconstructing every internal
race `test_fast_path_cancel_links_partial_and_keeps_prefix` exercises via
monkeypatching. `tests/verify.py`'s gates are written to the full contract
that unit test pins; the calibration fixtures (not the live run) are what
prove the verifier actually rejects the finer-grained violations a live
black-box run cannot itself reproduce.
