Status: approved

Entrypoint: the real FastAPI application (`src.main:app`), booted in-process
by the adapter via `uvicorn` on `127.0.0.1:8081` — the same idiom
`agent-stream-cancel-durability-v1/environment/run_agent.py` already uses to
drive production HTTP endpoints from a Harbor adapter, applied here to the
job endpoints (`/execute`, `/jobs/{job_id}`, `/confirm/{job_id}`) instead of
the SSE endpoints. Authentication uses `src.core.security.create_cli_token`
to mint a real HS256 bearer token for the seeded user, exactly as the
stream-cancel adapter does.

Source: repository revision (this branch's `git rev-parse HEAD`) — see
`task.toml` `source_revision`.

Preserved behavior: production job store (`agent_execution_service.py`,
`job_store.py`), the real `/execute` → `/jobs/{job_id}` → `/confirm/{job_id}`
lifecycle, `interrupt_node`'s destructive-tool gate, the production
`create_project` tool, and the checkpointer's Postgres-backed LangGraph
resume semantics.

Adapter: four phases against the booted application, sharing one seeded
org/user/workspace:

1. **Approve-once** — `POST /execute` with the phase-1 instruction; poll
   `GET /jobs/{job_id}` until `status == "awaiting_confirmation"`; record the
   `confirmation` payload verbatim (this is gate 1's evidence); read the
   `projects` row count for the workspace (the pre-approval snapshot);
   `POST /confirm/{job_id}` with `{"confirmed": true}`; poll until terminal;
   record the post-approval row count and the `tool_executions` the job
   reports.
2. **Reject** — same as phase 1 through the interrupt, then
   `POST /confirm/{job_id}` with `{"confirmed": false}`; poll until terminal;
   record the row count (must be unchanged) and the final assistant message.
3. **Re-confirm-resolved** — reusing phase 1's now-terminal `job_id`, issue
   `POST /confirm/{job_id}` with `{"confirmed": true}` two more times,
   recording the HTTP status code and the `projects` row count read
   immediately after each call. Production behavior
   (`src/api/agent/execute.py:confirm_agent_action`) is: the first repeat
   sees `job.status != AWAITING_CONFIRMATION` and returns
   `409 {"detail": "Job is not awaiting confirmation"}` via
   `_validate_confirmable_job`; if a race let it past that check, the atomic
   `compare_and_set_status` CAS would still return `"conflict"` and produce
   the same 409 — there is no 200/no-op success path for a resolved job. The
   task's "no-op with a stable status" gate is therefore stated over **that**
   shape: both repeats return the same status code (409) and neither changes
   the row count.
4. **Cancel-while-parked** — `POST /execute` with the phase-4 instruction;
   poll until `awaiting_confirmation`; record the `confirmation` payload;
   poll `GET /jobs/{job_id}` two more times **without confirming**
   (modeling the client abandoning/cancelling its wait) and record the
   `confirmation` payload from each poll; finally `POST /confirm/{job_id}`
   with `{"confirmed": true}` to bring the job to a terminal state before the
   trial ends (a task must not leave a synthetic job parked forever).
5. **Checkpointer scheme** — read
   `src.services.agent.checkpointer.get_db_uri()` once and record its scheme;
   this is gate 6, evaluated as an infrastructure check, never a lifecycle
   gate. Note: `get_db_uri()` (`checkpointer.py:39-42`) unconditionally
   strips `+asyncpg` from `settings.DATABASE_URL` before returning it, so
   live evidence will not carry that scheme unless that normalization itself
   regresses — this gate is defense-in-depth against a future code
   regression, not something exercised by any runtime path today. Only the
   calibration fixture (`infra-asyncpg-checkpointer.json`) exercises the
   failure branch; do not overclaim it as an observed production failure
   mode.

Session shape: four independent single-turn HTTP sessions (no shared thread
between phases) plus the two extra confirm calls in phase 3 and the two extra
polls in phase 4. No approval or rejection is ever sent before its
corresponding `awaiting_confirmation` status is observed.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`,
`AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`,
`AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`.
`JWT_SECRET_KEY` mints the synthetic bearer token; no production database or
Supabase credential is permitted.

Recorded evidence (the `evidence.json` envelope the verifier reads):

- `phases.approve_once`: `tool`, `args`, `interrupt` (the raw `confirmation`
  payload), `rows_before_approval`, `rows_after_approval`,
  `tool_execution_count_after_approval`, `final_assistant_message`.
- `phases.reject`: `tool`, `args`, `interrupt`, `rows_before_reject`,
  `rows_after_reject`, `final_assistant_message`.
- `phases.reconfirm_resolved`: `job_id` (phase 1's), `attempts`: a list of
  `{"http_status": int, "rows_after": int}`, one entry per repeat call.
- `phases.cancel_while_parked`: `tool`, `args`, `interrupt_first`
  (confirmation payload from the first poll), `polls`: a list of
  confirmation payloads from the subsequent parked polls,
  `resumed_after_cancel` (the terminal status once finally confirmed).
- `checkpointer`: `{"db_uri_scheme": str}`.
- `network_boundary`, `synthetic_actor`, `termination_reason`,
  `model_usage`, `elapsed_ms`, `schema_version`, `benchmark_id`,
  `source_revision`, `agent_revision`.

Reconstruction differences: the browser confirmation UI and SSE framing are
excluded — this task drives the plain job-poll HTTP surface. Redis and
Postgres are isolated single instances; there is no multi-worker race on the
confirm CAS. The graph, tool implementations, HITL node, job store, and
confirm endpoint called are production code; backing state is isolated and
synthetic.
