Status: approved

Dependencies:

- Production dependency image: private DigitalOcean registry tag `3a436b2-r1`, resolved and recorded as `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`; the pinned repository backend source is copied over `/app` at build time.
- FastAPI/backend container: isolated build from the pinned repository revision.
- Azure/OpenAI chat deployments: live, used only until the first assistant token is observed.
- PostgreSQL: simulated isolated service initialized from the pinned repository's current SQLAlchemy metadata.
- Redis: simulated isolated service using the production stream-buffer protocol and TTL behavior.
- Authentication: simulated task-local JWT/session for one seeded user.
- Production Supabase, Redis, storage, LangSmith, DigitalOcean, Cohere, arXiv, frontend, and ingress: blocked.

Backend contracts: `POST /api/v1/agent/stream` must durably accept one idempotent submission, emit monotonically sequenced envelopes, and bind the stream to its run/thread. Closing the client after a non-empty token must close the graph iterator, persist the partial assistant row with `stopped=true`, clear the active stream pointer, transition the same AgentRun to `cancelled`, and append exactly one absorbing `run.cancelled` event. A later resume read must not expose a completion generated after Stop.

Data:

- One fixed synthetic organization, active user, workspace, conversation, and empty thread.
- Fixed fresh user `client_message_id`; no prior active AgentRun, checkpoint, assistant row, or stream pointer.
- Request chosen to take the graph path rather than a greeting/fast path.
- Storage: PostgreSQL tables created from production model metadata plus isolated Redis.
- Reset: flush the task Redis namespace and recreate PostgreSQL from production model metadata and the fixed seed before every trial, even after client, Harness, timeout, or Verifier failure.

Isolation: one app/database/Redis namespace per trial; allowlist only approved model hosts; bounded polling; real monotonic clock. If no non-empty token arrives within 45 seconds, or dependencies fail, classify the trial as infrastructure error rather than agent failure.

Fidelity limits: excludes browser rendering, real network loss, ingress timeouts, multi-pod buffer races, and long TTL expiry. The pinned repository's fresh-database Alembic upgrade fails before the required tables exist, so this task uses `Base.metadata.create_all()` and does not establish migration correctness. Field-encryption data keys are process-local at this revision, so the seed process and FastAPI subprocess cannot share the synthetic user's encrypted name key; authentication remains valid, but app logs contain name-decryption errors. It measures the server's run-scoped Stop terminalization and durable projection at the production API boundary.
