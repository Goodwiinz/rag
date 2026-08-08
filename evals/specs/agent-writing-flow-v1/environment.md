Status: approved

Dependencies:

- Production dependency image: private DigitalOcean registry tag `3a436b2-r1`, resolved and recorded as `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`; the pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live, model inference only, using the Harness credential names. Effects are bounded API calls and token cost.
- The Harbor judge's own Azure deployment (`HARBOR_JUDGE_*`): live, verifier-side only, never exposed to the agent container. Bounded API calls and token cost.
- PostgreSQL: simulated isolated service, initialized from the pinned repository's current SQLAlchemy metadata. Effects are confined to the per-trial database.
- LangGraph checkpointer: the repository's PostgreSQL checkpointer against the same isolated database.
- LangSmith, DigitalOcean KB, arXiv, Redis, object storage, and production Supabase: disabled or network-blocked because the task does not exercise them. Only WRITING-bound tools run here, so no mock external service is needed (unlike a task that touches DO KB or Cohere).

Backend contracts: `compare_documents` and `export_bibliography` read documents scoped to the synthetic organization and return a comparison/bibliography payload directly; `create_draft` verifies project ownership, then hands off to `DraftGenerationService.generate_draft`, which fires a background asyncio task and returns `{task_id, status, message, project_id, project_name}` before the draft is written -- the tool call itself never blocks on generation. HITL must prevent that background task from being scheduled until approval. Tool requests and database mutations are recorded independently, including a snapshot taken immediately before the approval is sent.

Data:

- One fixed synthetic organization, active user, and owned workspace with neutral UUIDs.
- User email `benchmark-writing@example.invalid`; workspace name `Benchmark Writing Workspace`.
- One active project ("Tool Coverage Writing Study") with exactly two documents linked into it, each carrying real body text and `document_metadata` (title/authors/publication date/DOI) so `compare_documents`, `create_draft`, and `export_bibliography`'s citation fallback all have real content to act on.
- No `generated_drafts` row for the project before the run.
- Storage: PostgreSQL tables created from production model metadata and used by production services.
- Reset: recreate the database from production model metadata and the fixed seed before every trial, including after timeout or Verifier failure.

Isolation: one database and graph thread per trial; outbound network allowlisted only to the approved model endpoint; no production credentials; real monotonic time; deterministic UUID fixtures except server-created result identifiers (draft `task_id`).

Fidelity limits: excludes FastAPI authentication, SSE framing, Redis replay, browser confirmation UI, multi-pod concurrency, and the draft-generation background task actually completing within the trial window (it is asynchronous by design; the task only measures that it started correctly and was gated by HITL, not that it finishes). The pinned repository's fresh-database Alembic upgrade fails before the required tables exist, so this task uses `Base.metadata.create_all()` and does not establish migration correctness. It measures whether the production graph selects and safely completes the three-tool writing turn.
