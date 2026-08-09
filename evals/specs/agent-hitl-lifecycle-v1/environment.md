Status: approved

Dependencies:

- Production dependency image: private DigitalOcean registry tag `3a436b2-r1`,
  resolved and recorded as
  `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`; the
  pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live, model inference only, using the Harness
  credential names. Effects are bounded API calls and token cost.
- PostgreSQL: simulated isolated service, initialized from the pinned
  repository's current SQLAlchemy metadata (`Base.metadata.create_all` — the
  pinned revision's fresh-database Alembic chain is independently broken, the
  same fidelity limit `agent-project-management-v1` and
  `agent-stream-cancel-durability-v1` already document).
- Redis: simulated isolated service. Unlike `agent-project-management-v1`
  (which drives the graph directly and disables Redis), this task drives the
  **real FastAPI job endpoints** — `/execute`, `/jobs/{job_id}`,
  `/confirm/{job_id}` — because gate 4's "stable HTTP status on an
  already-resolved confirm" is a property of the job-store's Redis-backed
  compare-and-set, not of the LangGraph graph object alone. Isolated per
  trial, flushed before use.
- LangGraph checkpointer: the repository's PostgreSQL checkpointer against
  the same isolated database, reached through the real FastAPI process this
  task boots in-container (`uvicorn src.main:app`), exactly as
  `agent-stream-cancel-durability-v1` already does for its SSE endpoints.
- LangSmith, DigitalOcean KB, arXiv, object storage, and production Supabase:
  disabled or network-blocked because the task does not exercise them.

Backend contracts exercised: `POST /api/v1/agent/execute` (job creation),
`GET /api/v1/agent/jobs/{job_id}` (status + `confirmation` poll), and
`POST /api/v1/agent/confirm/{job_id}` (approve/reject/resolved-replay) —
`src/api/agent/execute.py`. The interrupt itself is `interrupt_node`
(`src/services/agent/_nodes_tools.py:236`) via the production `create_project`
tool; the confirm endpoint's atomic
`AWAITING_CONFIRMATION → RUNNING` compare-and-set
(`src/services/agent/job_store.py:compare_and_set_status`) is the mechanism
gate 3 and gate 4 are stated over.

Data:

- One fixed synthetic organization (`…0801`), active user (`…0802`), and
  owned workspace (`…0803`) with neutral UUIDs.
- User email `hitl-lifecycle-benchmark@example.invalid`; workspace name
  `HITL Lifecycle Benchmark Workspace`.
- No pre-existing projects, conversations, or threads. Each phase's
  `POST /execute` call omits `thread_id`, letting the production service
  create its own conversation/thread — this task does not depend on a
  pre-seeded thread, unlike the SSE-based `agent-stream-cancel-durability-v1`.
- Zero `projects` rows in the seeded workspace before every phase.
- Storage: PostgreSQL tables created from production model metadata and used
  by production services; Redis flushed before use.
- Reset: recreate the database and flush Redis before every trial, including
  after timeout or Verifier failure.

Isolation: one database, one Redis instance, and one FastAPI process per
trial; outbound network allowlisted only to the approved model endpoint; no
production credentials; real monotonic time; deterministic UUID fixtures
except server-generated `job_id` and row identifiers.

Fidelity limits: excludes the browser confirmation UI, SSE framing (this
task uses the plain job-poll endpoints, not `/stream` or `/stream/confirm`),
and multi-pod/multi-worker races on the confirm compare-and-set (single
FastAPI process, single Redis instance). "Cancel while parked" is modeled as
the client abandoning the poll loop without confirming and later resuming
polling — this task does not drive an actual client TCP disconnect mid
`/execute`, because that request already returned its `job_id` synchronously
before the interrupt fires; there is nothing to disconnect from once the job
is polling-based. The re-delivery property under test (`GET /jobs/{job_id}`
returning the identical `confirmation` payload on every poll while parked) is
exactly capability 3's confirm-path idempotency rule, restated for the
job-poll transport instead of SSE resume.
