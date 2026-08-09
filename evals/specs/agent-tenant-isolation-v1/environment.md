Status: approved

Dependencies:

- Production dependency image: the same private DigitalOcean registry tag
  used by `agent-hitl-lifecycle-v1` (`3a436b2-r1`, resolved digest
  `sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34`);
  the pinned repository backend source is copied over `/app` at build time.
- Azure/OpenAI chat deployments: live, reachable only through the Squid
  egress proxy. No probe in this task depends on model output — the
  network-boundary preflight still runs so a mis-wired environment fails as
  `InfrastructureFailure` up front rather than as an unexplained probe
  failure later.
- PostgreSQL: simulated isolated service, initialized from the pinned
  repository's current SQLAlchemy metadata (`Base.metadata.create_all`) —
  same fidelity limit every post-2026-08-07 task documents (the fresh-DB
  Alembic chain is independently broken).
- Neo4j: real `neo4j:5`-class container, same pattern
  `agent-knowledge-graph-flow-v1` (plan 3, PR #1362) established — entities
  and relationships are seeded through the production
  `knowledge_graph_service` singleton (never a fresh client instance), with
  the same landmine-1 self-check (`verify_seed_queryable`) run for **both**
  orgs before the graph is touched, because an empty-graph false pass here is
  exactly the failure mode this whole capability exists to prevent.
- Redis: simulated isolated service, used only for the LangGraph store
  backing long-term memory (`get_memory_store`); flushed before use.
- DigitalOcean Knowledge Base (`DO_KB_ENABLED`): disabled. The `rag_node`
  probe exercises the Postgres hybrid-search fallback path
  (`_legacy_hybrid_search_fallback`), not the DO KB primary read, so this
  task's isolation guarantee is scoped to that fallback; DO KB's own
  tenant-scoping is out of scope here (tracked separately).
- arXiv, object storage, LangSmith, production Supabase: disabled or
  network-blocked; this task does not exercise them.

Backend contracts exercised (direct function calls, not the full graph —
this task probes the tool/node *implementations* the graph would otherwise
route to, exactly as `agent-project-management-v1`'s `before_approvals`
snapshot reads the ORM directly rather than reconstructing the whole turn):
`src/services/agent/tools_impl.py` (`_tool_search_documents`,
`_tool_summarize_document`, `_tool_compare_documents`,
`_tool_list_projects`, `_tool_list_project_documents`,
`_tool_search_knowledge_graph`, `_tool_explore_entity_neighborhood`,
`_tool_find_entity_paths`, `_tool_get_graph_stats`,
`_tool_load_project_skill`), `src/services/agent/_nodes_memory.py`
(`memory_retrieval_node`), `src/services/agent/_nodes_rag.py` (`rag_node`).

Data:

- Org A (`00000000-0000-4000-8000-000000000801` /
  `…0802` user / `…0803` workspace) — the victim tenant, seeded with:
  - one `Document` ("Org A Confidential Report",
    `org-a-confidential-report.pdf`);
  - one `Collection` (project) ("Org A Research Project") with the document
    attached via `collection_documents`;
  - a 2-entity, 1-relationship Neo4j graph ("Org A Principal Investigator"
    `WORKS_FOR` "Org A Research Lab"), seeded through
    `knowledge_graph_service` exactly as plan 3's task does;
  - one long-term memory for user A (`save_memory`) whose text contains a
    distinctive, greppable fragment ("org-a-eyes-only-budget-figure");
  - one project-skill-catalog row bound to the Org A project, resolvable by
    `load_project_skill`.
- Org B (`00000000-0000-4000-8000-000000000810` /
  `…0811` user / `…0812` workspace) — the attacking tenant, mirroring the
  disjoint-second-org shape of `agent-knowledge-graph-flow-v1`
  (plan 3/PR #1362 `OTHER_ORG_ID` pattern): its own organization/user/
  workspace rows, zero content beyond what login/authentication requires. No
  probe seeds anything under org B that shadows org A's fixture data —
  finding zero is only meaningful if org B never had its own copy to
  legitimately return.
- Every id (document, project, entity, memory key, skill) that org A's seed
  step mints is captured and handed to the corresponding org-B probe
  verbatim — org B's probes never receive a fabricated id, they receive
  org A's real one, because a probe that queries a made-up id would trivially
  return nothing regardless of whether isolation exists.
- Storage: PostgreSQL tables from production model metadata; Neo4j from a
  disposable container; Redis flushed before use.
- Reset: recreate the database, wipe the Neo4j graph, and flush Redis before
  every trial.

Isolation: one Postgres instance, one Neo4j instance, one Redis instance per
trial; outbound network allowlisted only to the approved model endpoint; no
production credentials; deterministic UUID fixtures for every seeded row.

Fidelity limits: probes call tool/node implementation functions directly with
a synthetic `db` session and a synthetic `current_user`/`config["configurable"]`
context, rather than driving full agent turns through the LangGraph graph and
LLM tool selection. This is a deliberate scope cut — the property under test
is server-side tenant scoping in the data-access layer, which is identical
whether the call arrives via a real model tool-call or this harness's direct
invocation; it is not a claim about routing or prompt-following. DO KB's own
primary-read isolation and `search_arxiv`/`ingest_arxiv_papers`/
`search_external_database`/`list_external_databases` (no per-org data to
leak — arXiv and configured external databases are not tenant-partitioned)
are out of scope; `create_project_note`, `create_draft`,
`export_bibliography`, `execute_code`, `forget_memory`, and
`add_document_to_project` are write/destructive tools and out of scope for a
read-isolation sweep.
