Status: approved

Capability: cross-tenant isolation probes (`AGENT_FLOW_BASELINE.md` §12) —
NOUS's recurring defect class (#1219, #1292, hunt-6). This task makes the
sweep continuous instead of episodic: it is **pure objective**, no judge, no
ambiguity, and it exists to catch the day a new read tool ships without a
matching probe.

Two disjoint synthetic organizations are seeded in one trial:

- Org A (`…0801`/`…0802`/`…0803`) — the victim tenant. Seeded with exactly
  one of each: a document, a project (with one document attached), a
  knowledge-graph entity pair + relationship, a saved long-term memory for
  user A, and a project-skill-catalog entry bound to the project.
- Org B (`…0810`/`…0811`/`…0812`) — the attacking tenant, mirroring plan 3's
  `agent-knowledge-graph-flow-v1` two-org fixture shape (disjoint org id,
  disjoint user id, disjoint workspace id, zero content of its own beyond
  what a probe requires to authenticate).

For every probe below, user B issues **the same query parameters** (same
free-text query string, or — where the tool takes an id — org A's real,
just-seeded id, modeling an attacker who has guessed or observed it) that
user A's own probe uses, through the identical production tool function.

**The enumerated read surface (12 probes) — determined from
`backend/src/services/agent/tool_registry.py` / `tools.py` / `tools_impl.py`
/ `_nodes_rag.py` / `_nodes_memory.py`, not assumed:**

| # | probe_id | category | production entry point |
| - | -------- | -------- | ----------------------- |
| 1 | `documents.search_documents` | documents | `_tool_search_documents` (title/filename `ILIKE`, scoped by `Document.organization_id`) |
| 2 | `documents.summarize_document` | documents | `_tool_summarize_document` (by `document_id`) |
| 3 | `documents.compare_documents` | documents | `_tool_compare_documents` (by `document_ids`) |
| 4 | `projects.list_projects` | projects | `_tool_list_projects` (by owning user/workspace) |
| 5 | `projects.list_project_documents` | projects | `_tool_list_project_documents` (by `project_id`) |
| 6 | `knowledge_graph.search_knowledge_graph` | knowledge_graph | `_tool_search_knowledge_graph` (fulltext, scoped by `organization_id`) |
| 7 | `knowledge_graph.explore_entity_neighborhood` | knowledge_graph | `_tool_explore_entity_neighborhood` (by `entity_id`) |
| 8 | `knowledge_graph.find_entity_paths` | knowledge_graph | `_tool_find_entity_paths` (by `source_entity_id`/`target_entity_id`) |
| 9 | `knowledge_graph.get_graph_stats` | knowledge_graph | `_tool_get_graph_stats` (org-scoped analytics) |
| 10 | `memory.memory_retrieval_node` | memory | `memory_retrieval_node` / `search_memories` (graph node, not a LangChain tool — keyed by `user_id`, so org B's probe is user B's own `search_memories` call against user A's saved-memory text) |
| 11 | `suggestions.load_project_skill` | suggestions | `_tool_load_project_skill` (project-skill-catalog read, by `project_id`) — **deviation from the brief:** the current tool registry has no tool literally named "suggestions"; this is the nearest read-only, per-project "what's available to suggest next" surface in `tools.py`/`tools_impl.py`, and is used in its place. Reported as a deviation, not silently substituted. |
| 12 | `rag.rag_node` | rag | `rag_node` (`_nodes_rag.py`) — the graph node, distinct from `do_kb_retrieve`/`search_documents`, that answers `use_rag=True` turns via DO KB / hybrid-search fallback |

`do_kb_retrieve` is intentionally **not** a separate probe: it is the
DO-Knowledge-Base-backed tool wrapper around the same retrieval path
`rag_node` exercises for its fallback, and this task treats `rag_node` as
that surface's probe of record (see `environment.md` for why DO KB itself is
disabled in this environment).

**Coverage-hole guard:** `evidence.probes` MUST contain **exactly** one
record per `probe_id` above — 12 total, no more, no fewer, no duplicates.
The verifier compares `{p["probe_id"] for p in evidence.probes}` against this
literal 12-entry set. A future tool added to `tools.py` without a matching
probe entry here, or a probe silently dropped, fails this gate — it does
not silently pass because 11 of 12 still look clean.

**The critical anti-false-pass design point:** an empty database makes
"perfect isolation" and "total breakage" look identical — both return zero
rows to org B. Therefore every probe record carries **both** organizations'
raw results, and the verifier gate order is, per probe:

1. Assert org A's own query (same probe, run as user A) returns at least one
   row/id/title that is actually org A's seeded fixture data. If it does
   not, this is not a passing isolation probe — it is an
   **infrastructure failure** (`InfrastructureFailure`, verifier exit 2),
   because the probe cannot distinguish "isolated" from "the database never
   had anything to leak."
2. Only once (1) holds: assert org B's identical query returns **zero**
   rows/ids/titles that match any of org A's seeded identifiers (document
   id, document title, document filename, project id, project name, entity
   id, entity name, memory text fragment, skill id).

Pass iff (three objective gates, verbatim from `AGENT_FLOW_BASELINE.md` §12):

1. For **every** one of the 12 enumerated read tools/nodes, org B's probe
   returns zero rows/titles/ids belonging to org A (evaluated only after the
   org-A-non-empty precondition above holds for that probe).
2. Error messages leak **no** cross-tenant identifiers: no org-A UUID
   (document id, project id, entity id, workspace id), title, or filename
   appears in any `error` string recorded for any probe, on either side.
   **Matching rule:** the verifier's leak vocabulary is the union of
   `evidence["seed"]` (the ids probes use to build their queries) and
   `evidence["leak_vocabulary"]` (human-readable strings no probe query is
   built from — the document title, the document filename, the project
   name, the entity names — which is why they don't already live in `seed`).
   Every token is matched as a **whole value** — the full seeded string
   tested as a substring of the error text, never split into words — and
   tokens under 6 characters are dropped, so a short or common-word
   fragment can never make ordinary error prose fail the gate. Both fields
   are required, non-empty evidence keys; a run that omits either is an
   `InfrastructureFailure`, not a pass.
3. All 12 probes run in the **same trial batch** (one `evidence.probes`
   list, one seeded pair of tenants, one process) — not resampled
   independently per probe — so a regression in any one tool is caught by
   the same run that catches every other.

**Semantic gate:** N/A — every probe is a deterministic row/id comparison.

Verifier: deterministic, no LLM judge. Live-run state cross-check reads the
`documents`, `collections` (projects), and `collection_documents` tables
directly through the verifier's own psycopg connection, independent of
anything the adapter self-reports (same anti-fabrication posture as
`agent-hitl-lifecycle-v1`/`agent-project-management-v1`).

Accepted alternatives: none — this is a security invariant, not a behavior
with acceptable variation. A probe returning org-A data under any framing
(exact id match, exact title match, exact filename match) is a failure.
