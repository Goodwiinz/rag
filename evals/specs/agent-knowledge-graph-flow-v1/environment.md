Status: approved

Dependencies:

- Production dependency image: private DigitalOcean registry tag `3a436b2-r1`, resolved and recorded as `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`; the pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live and read-only, with bounded inference cost.
- Neo4j: a real `neo4j:5` container on the internal benchmark network, not a mock -- the production driver, circuit breaker, and the tool-level 15s `wait_for` timeout are all genuinely exercised.
- PostgreSQL: simulated isolated service initialized from the pinned repository's current SQLAlchemy metadata and seeded with the synthetic organization/user/workspace triple that `knowledge_graph`-intent tool execution requires for authentication.
- Judge model: live but isolated from the Harness; receives only the seeded graph as trusted sources and bounded task output.
- Production Supabase, DigitalOcean, Cohere, object storage, Redis, arXiv, and LangSmith: blocked.

Backend contracts: `search_knowledge_graph` runs a fulltext-indexed lookup (`entity_fulltext_idx`, created on first driver connect) scoped by `organization_id`; `explore_entity_neighborhood` traverses `RELATED_TO` edges up to a clamped depth with both path endpoints scoped to the caller's organization; `get_graph_stats` derives `total_entities`/`total_relationships` from per-type Cypher aggregates, both scoped by `organization_id` (the relationship aggregate scopes only the edge's source endpoint, matching `get_graph_analytics`'s own predicate). All three read paths share the same tenant-scoping helpers (`_entity_scope_predicate`, `_two_endpoint_scope`) the production code uses for every other Neo4j read.

Data: a fixed ~20-entity graph seeded under the benchmark organization via the same `knowledge_graph_service` singleton instance the DATA-subgraph tools import -- never a freshly constructed `KnowledgeGraphService()` -- so the class-level shared Neo4j driver the tools read from is guaranteed to already hold the seeded rows before the graph runs. A disjoint 3-entity graph is seeded under a second, unrelated organization purely as the tenant-scoping negative probe; no tool call in this task is ever authenticated as that organization, so its entities must never appear in a result.

Storage and reset: PostgreSQL is recreated from production model metadata and reseeded before each trial; Neo4j starts empty and is reseeded from the fixed fixture graph (`tests/truth.json` records the same entities/relationships for the verifier's independent cross-check and the judge's trusted sources) before each trial.

Isolation: one organization and thread per trial; allowlist only the model host (and, for the verifier alone, the judge host) through the Squid egress sidecar; Neo4j and PostgreSQL are reachable only on the internal-only benchmark network, proven by a private-reachability probe; no production credentials; deterministic seed data; real monotonic timing.

Fidelity limits: does not reproduce Neo4j's clustering/replication behavior or reproduce the production circuit breaker's failure-injection paths. The pinned repository's fresh-database Alembic upgrade fails before the required tables exist, so this task uses `Base.metadata.create_all()` for PostgreSQL and does not establish migration correctness. It faithfully exercises the repository's Neo4j driver singleton, tenant-scoped Cypher, fulltext search, neighborhood traversal, graph analytics, and grounded entity-answer synthesis boundary.
