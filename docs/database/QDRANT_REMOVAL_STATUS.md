# Qdrant Removal — Migration Status

Qdrant was dropped; **DO KB (DigitalOcean Knowledge Base)** is the retrieval backend.
This tracks what's done vs. outstanding. Audit date: 2026-06-08.

## Done (code, verified by inspection)

- [x] **Agent retrieval query hardening** — `_nodes_rag.py`: `_build_search_query()` strips
      instruction clauses / prefers quoted entities; `_coerce_text()` flattens multimodal content.
      (Stops feeding raw multi-title+instruction strings to retrieval.)
- [x] **Dead Qdrant client removed from agent memory** — `services/agent/memory_store.py`:
      deleted orphaned `_get_qdrant_client` / `_QDRANT_CLIENT` / `QDRANT_COLLECTION` /
      `_get_embedding_service` + unused `get_settings` import. Semantic recall is served by
      LangGraph `AsyncPostgresStore` (pgvector) in `memory.py`; nothing was lost.

## Outstanding — RUNTIME CODE (needs a working test env to change safely)

- [ ] **Ingest path never reaches DO KB (HIGH).** Legacy Celery `tasks/processing_tasks.py:211`
      → `processing_service.process_embedding_generation` writes only Qdrant (now returns None) and
      does **no** `sync_document_to_kb`. The DO KB sync lives in
      `multimodal_processing_service.py:1093`. **Action:** confirm which ingest path is live; ensure
      every ingest calls `sync_document_to_kb` and drives `document.is_embedded`/`is_indexed` off DO
      KB success, not the dead Qdrant `embedding_id`.
- [ ] **Dead Qdrant write in embedding step.** `process_embedding_generation` → `insert_vectors`
      on a `None` client. Remove; DO KB sync is the index step.
- [ ] **Search service dense leg silently empty.** `services/search/vector_service.py:261`
      (`search_vectors` → HTTP to `QDRANT_URL=None`) returns `[]`; `hybrid_search_service` then runs
      keyword-only (Postgres FTS still works). `/api/v1/search` health probe (`api/search/search.py:725`)
      labels this `qdrant` and reports **healthy**. **Action:** repoint dense leg at DO KB or remove
      it + fix the health probe so it doesn't false-green.
- [ ] **`/api/v1/vectors/*` router** (`api/search/vectors.py`, mounted `main.py:447`) calls
      `vector_service.client` (None) → 500s. **Decision needed:** rebuild on DO KB or remove router.
- [ ] **Capabilities with NO DO KB replacement:** entity vector search
      (`vector_search_service.search_entities`/`index_entity`), hybrid dense leg. Rebuild or formally drop.
- [ ] Dead-import cleanup: `search_service.py:113` module-level `qdrant_client`,
      `hybrid_vector_search_service.py`, `core/database_optimizations/*` Qdrant pools,
      `exceptions/__init__.py` Qdrant*Error, config `QDRANT_*` + validators.

## Outstanding — INFRA / SECRETS (outward-facing; owner action)

- [ ] **PROD CONFIG (HIGH):** `config/environments/.env.production:15,32` still *requires*
      `QDRANT_API_KEY` + `QDRANT_URL`, **zero `DO_KB_*` vars** → prod retrieval has no backend.
      `deployment/github-actions/workflows/deploy.yml:237` creates the qdrant secret, never creates
      `do-kb-credentials`. Add `DO_KB_*`, drop `QDRANT_*`.
- [ ] **Fix placeholder secret:** dev `DO_KB_EMBEDDING_MODEL_UUID = <gte-large-uuid-from-step-1>`
      (literal placeholder) — KB may not be functional. Confirm dev org has `do_kb_uuid` set.
- [ ] **Stop double-spend (Qdrant still provisioned):** `deployment/helm/rag-system` ×2
      (`qdrant.enabled:true`, 3 replicas, ~300Gi PVC), `infrastructure/kubernetes/manifests/databases.yaml`
      StatefulSet, `knowledge-graph-analytics/values-dev.yaml:228`, prod/staging/security compose.
      (prod/staging `knowledge-graph-analytics` already `qdrant.enabled:false` + DO KB secret — correct.)
- [ ] **Monitoring/backups still target Qdrant:** Prometheus scrapes `qdrant:6333`, `QdrantDown`
      alerts, `backup-and-dr.yml` nightly `qdrant backup` → S3, `init-qdrant-collections.sh`,
      startup scripts. Remove.

## Why runtime ingest/search not auto-fixed here
No backend deps (`langchain_core`), no DB, no running app in this sandbox → can't test. Editing a
live ingest pipeline or shared search service blind is unsafe. Do those in an env where
`pytest tests/unit/services/` + an ingest smoke test can confirm.
