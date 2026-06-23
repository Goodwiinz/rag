# Knowledge graph service layer

Neo4j-backed service responsible for storing, querying, and visualizing the entities and relationships extracted from ingested documents. The main FastAPI backend (port 8000) calls into `KnowledgeGraphService` directly; two optional standalone microservices (`knowledge_graph_main.py` port 8003, `graph_analytics_microservice.py` port 8009) provide extended REST surfaces when deployed separately.

## Where it sits

- **Agent data subgraph** — the LangGraph `data` route calls KG query tools in `backend/src/api/agent/execute.py` to answer entity/relationship questions.
- **KG REST API** — `backend/src/api/knowledge_graph/` routes delegate CRUD and search to `KnowledgeGraphService`.
- **Graph visualization panel** — the frontend graph explorer hits the visualization endpoints, which call `get_neighborhood`, `find_paths`, and `graph_visualization_service.py`.

## Key files

| File                                  | Purpose                                                                                                                                                                                                                                       |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `knowledge_graph_service.py`          | Core synchronous service — entity/relationship CRUD, full-text search, path traversal, neighborhood queries. The canonical implementation used by the main backend.                                                                           |
| `knowledge_graph_service_improved.py` | `ResilientKnowledgeGraphService` wrapper — offloads blocking Neo4j calls to `asyncio.to_thread`, adds per-operation retry logic for connection failures.                                                                                      |
| `knowledge_graph_main.py`             | Standalone FastAPI microservice (port 8003) — async driver, Redis caching, WebSocket broadcasts for real-time updates, and an entity-extraction endpoint that calls `EntityExtractionService`.                                                |
| `graph_algorithms.py`                 | `GraphAlgorithms` class — centrality, community detection, path finding, anomaly detection. Validates `organization_id` as a UUID before any GDS query (prevents cross-tenant leakage and parameter injection into GDS `nodeFilter` strings). |
| `graph_analytics_microservice.py`     | Standalone FastAPI microservice (port 8009) — exposes graph analytics over HTTP, backed by Celery for long-running background jobs.                                                                                                           |
| `graph_visualization_service.py`      | Standalone FastAPI microservice (port 8010) — prepares visualization payloads, delegates layout computation to `LayoutAlgorithms`.                                                                                                            |
| `layout_algorithms.py`                | Pure-Python layout algorithms (force-directed Fruchterman-Reingold, others) — iterations are bounded by graph size to avoid blocking the event loop on large graphs.                                                                          |

## Neo4j connection

**URI:** `bolt://localhost:7687` (configured via `settings.NEO4J_URI`)  
**Auth:** `settings.NEO4J_USER` / `settings.NEO4J_PASSWORD`  
**Driver:** Shared singleton (`KnowledgeGraphService._driver_instance`) with double-checked locking. Pool size 50, connection lifetime 3600 s. The driver is not closed on `__aexit__` — call `KnowledgeGraphService.close_driver()` explicitly at shutdown.

Schema constraints and indexes applied at startup:

- Unique constraint on `Entity.id` and `(Entity.canonical_key, Entity.type, Entity.organization_id)` (`entity_canonical_org_unique`) — the composite constraint enables idempotent, org-isolated `MERGE` on re-ingest and concurrent writes.
- Indexes on `Entity.name`, `Entity.type`, `Entity.source_document_id`, `Entity.organization_id`.
- Fulltext index `entity_fulltext_idx` on `Entity.name` — used by `search_entities` with Lucene prefix matching; falls back to `CONTAINS` if the index call fails.
- Index on `RELATED_TO.strength` and `RELATED_TO.created_at` (pagination ordering).

## Circuit breaker

`get_session()` checks `get_circuit_breaker("neo4j")` before every query. On `ServiceUnavailable` or `SessionExpired` it calls `breaker.record_failure()`; clean exits call `breaker.record_success()`. When the breaker is open, `get_session()` raises `CircuitBreakerError` immediately without touching the driver. The breaker implementation lives in `backend/src/core/circuit_breaker.py`.

## Cypher patterns

- **Entity upsert** — `MERGE (e:Entity {canonical_key, type, organization_id}) ON CREATE SET ... ON MATCH SET ...`. `organization_id` is part of the MERGE identity (constraint `entity_canonical_org_unique`) so two orgs' same name+type entities are distinct nodes; it is coalesced to `""` because Cypher cannot MERGE on a null key. `confidence_score` is updated only if the new value is higher.
- **Traversal depth** — `find_related_entities`, `get_neighborhood`, and `find_paths` all clamp `max_depth` to `[1, 5]` and restrict the pattern to `[:RELATED_TO*1..N]`. Untyped `[*1..N]` patterns and unbounded depth cause combinatorial fanout on hub nodes and are explicitly avoided.
- **Batch relationship fetch** — `get_relationships_among` and `get_relationships_for_entities` retrieve all edges in a single query rather than N per-entity calls.

## Authorization and scoping

All query methods accept `organization_id` and/or `source_document_ids`. The `_entity_scope_predicate` and `_two_endpoint_scope` helpers inject a WHERE clause that prefers the indexed `organization_id` equality, falling back to `source_document_id IN [...]` for environments where the backfill has not yet run. **Path traversal queries scope both endpoints** — a path node that satisfies the start-entity filter but whose far endpoint belongs to a different organization is not returned.

`graph_algorithms.py` enforces that `organization_id` is a valid UUID before interpolating it into GDS `nodeFilter` strings (GDS projection parameters cannot use Cypher bind variables, so the UUID format check is the injection boundary).

## Gotchas

- `metadata` and `evidence` fields are stored as JSON strings in Neo4j (not native maps). `_parse_metadata` handles JSON, Python `repr` strings (legacy), and native dicts. Always `json.dumps` before writing.
- The standalone microservice in `knowledge_graph_main.py` was written with `tenant_id` semantics; the main-backend service uses `organization_id`. Both refer to the same concept but the property name differs in older nodes.
- `updated_at` must be set with the Cypher function `datetime()` inline — passing the string `"datetime()"` as a bind parameter stores the literal text, not a timestamp.
- The `KnowledgeGraphService` driver is synchronous (`neo4j.GraphDatabase`). Calling it directly from async FastAPI handlers blocks the event loop; use `ResilientKnowledgeGraphService` (which wraps calls in `asyncio.to_thread`) or the async driver in the standalone microservices.
