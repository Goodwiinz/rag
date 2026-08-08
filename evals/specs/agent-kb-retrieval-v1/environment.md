Status: approved

Dependencies:
- PostgreSQL 16, recreated from production model metadata before each trial.
- A local mock-services host reproducing the DigitalOcean Knowledge Base retrieval wire protocol.
- A Squid egress proxy allowlisting only the model host; the main service reaches the internet through no other path.

Backend contracts: DO KB authenticates a fixed synthetic Bearer token, enforces `top_k`, and returns chunks the repository resolves to same-organization documents. `do_kb_retrieve` marks its result with `source: "do_kb"` and a chunks list; a disabled or unprovisioned KB surfaces a `reason` (`disabled` / `not_provisioned`) that the verifier treats as misconfiguration, never a legitimate empty result. `search_documents` returns title/filename matches capped at 50 results.

Data: two seeded `Document` rows — "API Rate Limit Policy" (`…000704`) and "Webhook Retry Policy" (`…000705`) — plus an immutable knowledge-base fixture whose single rate-limit chunk is the only grounded source for the answer.

Storage and reset: immutable JSON fixtures feed the mock KB; PostgreSQL is recreated from production model metadata and seed data before each trial. The mock service logs bounded request metadata (authorization validity, acceptance, kb uuid) without document bodies or credentials, exposed via `GET /events`.

Isolation: one organization and thread per trial; allowlist only the model host (and, for the verifier alone, the judge host); no production credentials; deterministic service responses; real monotonic timing. The KB host is reachable only inside the internal benchmark network, proven by a private-reachability probe.

Fidelity limits: does not reproduce DO's embedding model or approximate-nearest-neighbor behavior. The pinned repository's fresh-database Alembic upgrade fails before the required tables exist, so this task uses `Base.metadata.create_all()` and does not establish migration correctness. It faithfully exercises the repository's document search, DO KB wire parsing, organization/document resolution, and grounded synthesis boundary.
