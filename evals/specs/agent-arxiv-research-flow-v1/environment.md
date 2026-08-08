Status: approved

Dependencies:

- Production dependency image: private DigitalOcean registry tag `3a436b2-r1`, resolved and recorded as `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`; the pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live, model inference only, using the Harness credential names. Effects are bounded API calls and token cost.
- PostgreSQL: simulated isolated service, initialized from the pinned repository's current SQLAlchemy metadata. Effects are confined to the per-trial database.
- Redis: simulated isolated `redis:7.4-alpine` service on the internal network, backing the production arXiv search-result cache and rate gate (`REDIS_URL=redis://redis:6379/0`).
- Mock services: a deterministic HTTP double simulating the arXiv Atom search API and PDF download endpoint, serving a fixed two-paper corpus and recording every request to a `GET /events` log.
- LangGraph checkpointer: the repository's PostgreSQL checkpointer against the same isolated database.
- LangSmith, DigitalOcean KB, Cohere, and production Supabase: disabled or network-blocked because the task does not exercise them.

Backend contracts: the production `search_arxiv` and `ingest_arxiv_papers` tools receive the fixed synthetic user/workspace/project context; the impl-level `search_arxiv` cap (≤5 results, 250-char abstracts) and the shared Redis result cache (`arxiv:search:<sha1>` key, `payload`/`cached_at` envelope, TTL≈1800s) are exercised exactly as in production; HITL must prevent `ingest_arxiv_papers`'s writes until approval; a successful ingest downloads the PDF from the double, promotes it to local object storage under `documents/<org>/<doc>/<filename>`, persists a `Document` row with a `search_vector`, and links it into the seeded project. Tool requests, database mutations, Redis cache state, and mock-double requests are all recorded independently.

Data:

- One fixed synthetic organization, active user, owned workspace, and one empty project (`Benchmark Research Project`) with neutral UUIDs.
- User email `benchmark-route@example.invalid`.
- The arXiv double's fixture corpus: two papers (`2401.10001`, `2401.10002`) with fixed titles, abstracts, and deterministic PDF byte content whose sha256 is recorded in `tests/truth.json`.
- No document, project-link, or Redis `arxiv:search:*` key exists at trial start.
- Storage: PostgreSQL tables created from production model metadata; local-backend object storage under `/benchmark/uploads`, used by the production `store_arxiv_pdf` storage layer exactly as deployed.
- Reset: recreate the database, Redis, and local storage volume from a clean state before every trial, including after timeout or Verifier failure.

Isolation: one database, one Redis instance, and one graph thread per trial; outbound network allowlisted only to the approved model endpoint, the mock double, and Redis — all three on an internal-only network; no production credentials; real monotonic time; deterministic UUID fixtures except the server-created document identifiers.

Fidelity limits: excludes FastAPI authentication, SSE framing, browser confirmation UI, and multi-pod concurrency (the shared arXiv rate gate and cross-pod cache dedup are exercised against a single replica only). The arXiv client's `ARXIV_API_BASE`/`ARXIV_PDF_BASE` are hard-coded class attributes, not environment-driven — the adapter patches them to the mock double's host directly on the imported class before compiling the graph, a seam that is documented but not itself under test. Because the double answers instantly, the production 5-minute arXiv request budget is never exercised. The Redis result-cache TTL is written with ±15% jitter by the shared cache-set helper; the verifier's upper bound absorbs that jitter rather than asserting exactly 1800s. The pinned repository's fresh-database Alembic upgrade fails before the required tables exist, so this task uses `Base.metadata.create_all()` and does not establish migration correctness. It measures whether the production graph selects and safely completes the arXiv search-and-ingest capability, not upstream arXiv fidelity.
