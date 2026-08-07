Status: approved

Dependencies:

- Production dependency image: private DigitalOcean registry tag `3a436b2-r1`, resolved and recorded as `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`; the pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live, model inference only, using the Harness credential names. Effects are bounded API calls and token cost.
- PostgreSQL: simulated isolated service, initialized from the pinned repository's current SQLAlchemy metadata. Effects are confined to the per-trial database.
- LangGraph checkpointer: the repository's PostgreSQL checkpointer against the same isolated database.
- LangSmith, DigitalOcean KB, arXiv, Redis, object storage, and production Supabase: disabled or network-blocked because the task does not exercise them.

Backend contracts: the production `create_project`, `list_projects`, `add_document_to_project`, `create_project_note`, and `list_project_documents` tools receive the configured synthetic user/workspace context; HITL must prevent each of the three writes until its own approval; the reads must be scoped to the seeded tenant. Tool requests and database mutations are recorded independently.

Data:

- One fixed synthetic organization (`…0501`), active user (`…0502`), and owned workspace (`…0503`) with neutral UUIDs; one graph thread (`…0504`).
- User email `benchmark-route@example.invalid`; workspace name `Benchmark Workspace`.
- One indexed document `…0505` titled `Seed Paper`, owned by the seeded organization, not deleted, and linked to no project.
- No active or deleted project named `Tool Coverage Study`; zero collection, collection-document, and project-note rows before the trial.
- Storage: PostgreSQL tables created from production model metadata and used by production services.
- Reset: recreate the database from production model metadata and the fixed seed before every trial, including after timeout or Verifier failure.

Isolation: one database and graph thread per trial; outbound network allowlisted only to the approved model endpoints; no production credentials; real monotonic time; deterministic UUID fixtures except server-created result identifiers.

Fidelity limits: excludes FastAPI authentication, SSE framing, Redis replay, browser confirmation UI, and multi-pod concurrency. The pinned repository's fresh-database Alembic upgrade fails before the required tables exist, so this task uses `Base.metadata.create_all()` and does not establish migration correctness. It measures whether the production graph sequences and safely completes a dependent multi-tool project-management request.
