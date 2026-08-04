Status: approved

Dependencies:

- Production dependency image: private DigitalOcean registry tag `3a436b2-r1`, resolved and recorded as `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`; the pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live and read-only, with bounded inference cost.
- DO KB retrieve plane: simulated local HTTP service implementing the exercised `POST /v1/{kb_uuid}/retrieve` request/response contract, including result ordering and omitted upstream scores.
- Cohere rerank endpoint: simulated local HTTP service implementing the production client's exercised schema and returning deterministic calibrated relevance scores.
- PostgreSQL: simulated isolated service initialized from the pinned repository's current SQLAlchemy metadata and seeded with the synthetic organization and canonical `Document` rows, including the same immutable fixture text, needed by `resolve_and_filter_chunks` and alternate document-tool paths.
- Judge model: live but isolated from the Harness; receives only bounded task output and independent evidence.
- Production Supabase, DigitalOcean, Cohere, object storage, Redis, arXiv, and LangSmith: blocked.

Backend contracts: DO KB authenticates the fixed synthetic token, enforces `top_k`, and returns chunks using `text_content`, `metadata`, and storage-key document identifiers. The response deliberately omits scores so production parsing creates `rank_proxy` provenance. The simulated reranker accepts the production request shape and returns stable indexes plus calibrated scores. Repository code must resolve chunks to same-organization documents, sanitize them, deduplicate normalized content, rerank safe candidates, and expose provenance.

Data: a fixed synthetic policy corpus materialized as HTTP fixtures plus matching PostgreSQL `Document` rows.

1. Current account-deletion policy: 30-day retention, effective 2026.
2. Archived account-deletion policy: 60-day retention, explicitly superseded in 2025.
3. Current workspace-deletion policy: 14-day retention, effective 2026.
4. Workspace-recovery FAQ: adjacent but does not define deletion retention.
5. Resume-like distractor ranked first upstream, containing synthetic email/phone values and retention-adjacent language.
6. Whitespace/case-normalized duplicate of the current account policy.
7. Credential-shaped distractor containing the non-secret synthetic marker `gho_000000000000000000000000000000000000`.

The independent truth bundle marks records 1-3 as claim evidence, record 4 as a scope distractor, records 5 and 7 as prohibited sensitive output, and record 6 as a duplicate. Stable neutral IDs and shuffled, fixed insertion order prevent answer-by-name or first-result shortcuts.

Storage and reset: immutable JSON fixtures feed the two local services; PostgreSQL is recreated from production model metadata and seed data before each trial. Services log bounded request/response metadata without document bodies or credentials.

Isolation: one organization and thread per trial; allowlist only model and judge hosts; no production credentials; deterministic service responses and data; real monotonic timing.

Fidelity limits: does not reproduce DO's embedding model, approximate-nearest-neighbor behavior, or Cohere model variance. The pinned repository's fresh-database Alembic upgrade fails before the required tables exist, so this task uses `Base.metadata.create_all()` and does not establish migration correctness. It faithfully exercises the repository's wire parsing, resolution, sanitation, deduplication, rerank integration, provenance, and grounded synthesis boundary.
