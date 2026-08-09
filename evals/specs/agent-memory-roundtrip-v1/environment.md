Status: approved

Dependencies:

- Production dependency image: private DigitalOcean registry tag `3a436b2-r1`, resolved and recorded as `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`; the pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live, model inference only, using the Harness credential names. Effects are bounded API calls and token cost.
- PostgreSQL: simulated isolated service, initialized from the pinned repository's current SQLAlchemy metadata. Effects are confined to the per-trial database. The same database backs both the LangGraph checkpointer and the long-term memory store (`AsyncPostgresStore`) — `ENVIRONMENT` is set to `benchmark`, never `testing`, so the production store class initializes rather than being swapped for `InMemoryStore`.
- `COHERE_API_KEY` is unset. The memory store therefore initializes without a semantic index, so `asearch` returns `score=None` for every result and `forget_memory` takes the substring-match fallback path rather than the 0.6 semantic-score threshold — the store-backend choice this task is pinned to and asserts.
- LangSmith, DigitalOcean KB, arXiv, Neo4j, Redis, object storage, and production Supabase: disabled or network-blocked because the task does not exercise them.

Backend contracts: `memory_save_node` computes a deterministic per-turn key (`md5(f"{thread_id}:{turn_index}:{content[:100]}")[:12]`) and dispatches the embed+write as a fire-and-forget background `asyncio.Task`; the adapter polls the store for that key rather than sleeping a fixed duration. `redact_pii` runs on the stored `query` field before it is persisted. `memory_retrieval_node` searches the same store namespace on every non-greeting turn. `forget_memory` is registered with no top-level intent and no subgraph (`intents=frozenset()`, `subgraphs=frozenset()`), so no classified intent (research/writing/knowledge_graph/general) ever binds it to the model — it is reachable only through the `ALL_TOOLS` fallback in `_get_tools_for_intent`, which fires when the turn's `intent` value is not one of the four `AgentIntent` members.

Data:

- One fixed synthetic organization, active user, and owned workspace with neutral UUIDs.
- One fixed thread carrying all three turns. Two additional UUIDs (a second thread, a second user) exist only as no-bleed probe targets — no state is ever seeded under them.
- User email `benchmark-route@example.invalid`; workspace name `Benchmark Workspace`.
- No memory rows for the user before turn 1.
- Storage: PostgreSQL tables created from production model metadata; the memory store's own tables are created by `AsyncPostgresStore.setup()`.
- Reset: recreate the database from production model metadata and the fixed seed before every trial, including after timeout or Verifier failure.

Isolation: one database, one graph thread, and one long-term memory namespace per trial; outbound network allowlisted only to the approved model endpoint; no production credentials; real monotonic time; deterministic UUID fixtures.

Fidelity limits: excludes FastAPI authentication, SSE framing, Redis replay, browser confirmation UI, and multi-pod concurrency. Turn 3 is driven onto the `ALL_TOOLS` binding path via `graph.aupdate_state(..., as_node="preprocessing_node")` — a documented LangGraph checkpoint-editing API, not a monkeypatch — because no live classifier output ever emits an intent outside the four known values; `interrupt_node`, `tool_node`, and `forget_memory` itself run unmodified production code once that state is in place. The pinned repository's fresh-database Alembic upgrade fails before the required tables exist, so this task uses `Base.metadata.create_all()` and does not establish migration correctness.
