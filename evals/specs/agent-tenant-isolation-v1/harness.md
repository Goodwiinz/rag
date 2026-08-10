Status: approved

Entrypoint: `environment/run_agent.py`, invoked directly by Harbor (no FastAPI
process boot — unlike `agent-hitl-lifecycle-v1`, this task never needs the
job/confirm HTTP surface, only tool/node implementations and two seeded
tenants).

Source: repository revision (this branch's `git rev-parse HEAD`) — see
`task.toml` `source_revision`.

Adapter sequence:

1. `bootstrap_schema()` (Postgres), then `seed_tenant()` twice — once for org
   A, once for org B — via `harbor_common.db.seed_tenant`.
2. Seed org A's fixture content: one `Document`, one `Collection` (project)
   with the document attached, a 2-entity/1-relationship Neo4j graph via the
   `knowledge_graph_service` singleton (plan 3's landmine-1
   `verify_seed_queryable` self-check is run for org A's entity before the
   probe matrix starts — a dead Neo4j client must fail as
   `InfrastructureFailure`, not silently produce a clean-looking probe),
   one long-term memory for user A, and one project-skill-catalog row.
   Record every minted id.
3. Confirm org B has none of this by construction (no seed call references
   `OTHER_ORG_ID`/`OTHER_USER_ID` for any of org A's fixture content).
4. Run the 12-probe matrix declared in `task.md`. For each probe:
   a. Call the production implementation as **user A** with the probe's
      query (free-text for search-shaped tools; org A's real minted id for
      id-shaped tools). Record the raw result and derive `org_a_rows` — the
      list of ids/titles/names actually returned that match org A's seeded
      fixture.
   b. Call the same production implementation as **user B**, passing the
      **identical** query parameters (same query text, or org A's real id
      passed to user B's call — modeling an attacker who has obtained or
      guessed it). Record the raw result, derive `org_b_rows` the same way,
      and separately capture any `error`/`error_type` string the call
      returned.
   c. Append one `{"probe_id", "category", "query", "org_a_rows",
      "org_b_rows", "org_b_error"}` record to `evidence.probes`.
5. Independent post-run reads: the same three tables
   (`documents`, `collections`, `collection_documents`) the verifier itself
   re-reads, taken by the adapter's own session, purely as a secondary
   snapshot — the verifier's authoritative signal is its own psycopg
   connection, not this record (same trust split as
   `agent-hitl-lifecycle-v1`).

Per-probe call shapes (production function, args, what "org A row" means):

- `documents.search_documents` — `_tool_search_documents({"query": <title
  substring>}, db, user)`; org-A row = a returned `documents[].id` equal to
  the seeded document id, or `.title` equal to the seeded title.
- `documents.summarize_document` — `_tool_summarize_document({"document_id":
  <org-A doc id>}, db, user_b)`; org-A row = any non-error summary content
  (a summary at all, for a document user B does not own, is the leak — there
  is no "partial" summarize).
- `documents.compare_documents` — `_tool_compare_documents({"document_ids":
  [<org-A doc id>, <org-A doc id>]}, db, user_b)`; org-A row = any non-error
  comparison result.
- `projects.list_projects` — `_tool_list_projects({}, db, user)`; org-A row =
  a returned project id/name equal to the seeded project.
- `projects.list_project_documents` — `_tool_list_project_documents(
  {"project_id": <org-A project id>}, db, user_b)`; org-A row = any returned
  document id/title.
- `knowledge_graph.search_knowledge_graph` — `_tool_search_knowledge_graph(
  {"query": <org-A entity name>}, user)`; org-A row = a returned entity id
  equal to the seeded entity, or name equal to the seeded name.
- `knowledge_graph.explore_entity_neighborhood` —
  `_tool_explore_entity_neighborhood({"entity_id": <org-A entity id>},
  user_b)`; org-A row = any non-empty neighborhood result.
- `knowledge_graph.find_entity_paths` — `_tool_find_entity_paths(
  {"source_entity_id": <org-A entity id>, "target_entity_id": <org-A entity
  id 2>}, user_b)`; org-A row = any non-empty path result.
- `knowledge_graph.get_graph_stats` — `_tool_get_graph_stats({}, user)`;
  org-A row = `total_entities`/`total_relationships` counted for org A
  matching the independent Cypher count from the seed step. **Scoping
  assumption, stated explicitly:** `get_graph_stats` takes no query
  argument, so the org-B side's "leaked row" signal is simply "any nonzero
  `total_entities` came back for org B's own scoped call." That is only a
  valid leak signal because this task's org B is seeded with **zero** graph
  content by construction (see `environment.md`) — a nonzero count for org
  B can only mean org A's entities bled into org B's scope. If a future
  revision of this task ever seeds org B with its own real graph content,
  this probe's `rows_fn` must be rescoped to compare against the
  independently-seeded org-A count specifically (e.g. asserting org B's
  count never exceeds org B's own seeded total), not a raw nonzero check —
  otherwise it would raise a false gate *failure* for org B's legitimate
  data, not a false pass.
- `memory.memory_retrieval_node` — `search_memories(store, <user_id>,
  "org-a-eyes-only-budget-figure", limit=5)` called once with `user_id =
  USER_A_ID` and once with `user_id = USER_B_ID`; org-A row = any returned
  memory entry whose text contains the fragment.
- `suggestions.load_project_skill` — seed one approved skill version and a
  production runtime snapshot, then call `_tool_load_project_skill({"skill_name":
  <seeded name>}, user_id=<user id>, project_id=<org-A project id>,
  runtime_snapshot_id=<org-A snapshot id>, db=db)`; org-A row = any non-error
  skill payload. Org B receives the same project, snapshot, and skill name.
- `rag.rag_node` — `rag_node(state, config)` with `configurable.user_id` /
  `organization_id` set to org B's ids and `state["messages"]` containing
  the org-A document's distinctive text fragment as the query. Both calls
  carry org A's project id as the active project because production RAG
  intentionally skips retrieval without project context; org-A row = any
  retrieved context chunk whose source document id equals org A's seeded
  document.

Session shape: one process, one seeded pair of tenants, all 12 probes run
back-to-back in the order declared in `task.md` — this is the "same trial
batch" gate 3 requires; no probe reseeds or resets state for a later probe.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`,
`AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`,
`AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`.
No production database, Supabase, or DO KB credential is permitted.

Recorded evidence (the `evidence.json` envelope the verifier reads):

- `probes`: list of 12 records, each `{"probe_id", "category", "query",
  "org_a_rows", "org_b_rows", "org_b_error"}` as built above.
- `seed`: the minted org-A ids (`document_id`, `project_id`, `entity_id`,
  `entity_id_2`, `memory_fragment`, `skill_id`) plus the independent
  pre-run Neo4j entity/relationship counts (landmine-1 self-check result).
- `leak_vocabulary`: the human-readable org-A strings no probe query is
  built from and which therefore never appear in `seed` — `DOCUMENT_TITLE`,
  `DOCUMENT_FILENAME`, the project name, and both entity names. Required
  and non-empty; gate 2 (`tests/verify.py:check_no_leaked_identifiers`)
  unions this with `seed`'s ids to build its full leak vocabulary.
- `synthetic_actor`: `organization_id`/`user_id`/`workspace_id` for both org
  A and org B.
- `network_boundary`, `termination_reason`, `model_usage`, `elapsed_ms`,
  `schema_version`, `benchmark_id`, `source_revision`, `agent_revision`.

Reconstruction differences: probes call tool/node implementations directly
with a synthetic session/user rather than driving full LangGraph turns with
LLM tool selection (see `environment.md`'s fidelity-limits note). Data-access
scoping (the SQL/Cypher predicates and the `search_memories` namespace key)
is production code; the org/user context around each call is synthetic.
