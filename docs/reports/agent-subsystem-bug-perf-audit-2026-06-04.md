# NOUS RAG — Agent Subsystem Bug & Performance Audit

**Date:** 2026-06-04
**Scope:** `backend/src/services/agent/` (30 files) + `backend/src/api/agent/` driver (`tools_impl.py`, `jobs.py`, `streaming.py`, `execute.py`) + `backend/src/services/processing/llm_entity_extraction.py` — ~13,500 LOC.
**Audited at:** commit `433a4b6` (PR #562 head). Every audited file except those in PR #562 is unchanged from `develop` (`3923362`), so the line references below apply to `develop`.
**Method:** multi-agent audit — 15 finders (10 per-area + 5 cross-cutting lenses) → **per-finding adversarial verification** → dedupe/rank synthesis. 103 agents total.

---

## Summary

The agent subsystem is broadly sound, but the audit surfaced a cluster of genuine, reachable defects concentrated in three areas: **tool dispatch** (a tool advertised to the LLM with no execution branch; broken sandbox isolation), **async correctness** (blocking I/O on the event loop; `CancelledError` mishandled at the graph entry), and **job-store consistency + LLM-client caching** (fire-and-forget Redis writes with no monotonic guard; LLM clients rebuilt on every call). Most fixes are mechanical.

**Funnel:** 87 raw findings → **64 survived** independent verification → **18 distinct** after dedupe. The verification pass refuted or downgraded 23 findings (e.g. a "mismatched `db` parameter" claim was refuted; the `memory_store` "critical" was downgraded to low as dead code).

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 6 |
| 🟡 Medium | 8 |
| ⚪ Low | 3 |

---

## 🔴 Critical / 🟠 High bugs

### 1. `forget_memory` is 100% broken — registered for the LLM, missing from the dispatcher *(critical, high confidence)*
- **Where:** `backend/src/api/agent/tools_impl.py:593–642` (dispatcher) · `backend/src/services/agent/tools.py:761` (in `ALL_TOOLS`) · impl exists at `tools_impl.py:2368`
- **Impact:** `forget_memory` is in `ALL_TOOLS`, so the LLM can invoke it, but `execute_tool` has no branch for it — every call falls through to `return {"error": f"Unknown tool: {tool_name}"}`. It is in `DESTRUCTIVE_TOOLS`, so the user is asked to confirm first and the action then fails after confirmation. Contained (returns an error, no crash) but a guaranteed-broken advertised capability.
- **Fix:** add, before the catch-all:
  ```python
  if tool_name == "forget_memory":
      return await _tool_forget_memory(query=args.get("query", ""), user_id=user_id, page_context=None)
  ```

### 2. Blocking synchronous file I/O on the event loop *(high)*
- **Where:** `backend/src/services/agent/_nodes_memory.py:97` (`write_iteration`) · `backend/src/api/agent/tools_impl.py:1580,1681,1747` (`extract_text_content`)
- **Impact:** `memory_save_node` calls the synchronous `write_iteration()` (mkdir / `write_text` / `os.replace`, `iteration_ledger.py:217+`) on every turn, blocking the loop ~10–50 ms and delaying token streaming. Three async tools (`_tool_summarize_document`, `_tool_compare_documents`, `_tool_extract_entities`) call `FileService.extract_text_content()`, which does blocking PDF/CSV/Excel parsing directly in async context. Under concurrency these stall all other coroutines.
- **Fix:** offload to a thread — `await asyncio.to_thread(write_iteration, thread_id, dict(state))` and `await loop.run_in_executor(None, file_service.extract_text_content, doc)`. The codebase already uses this pattern elsewhere.

### 3. `execute_code` sandbox isolation broken — hardcoded `thread_id=""` *(high)*
- **Where:** `backend/src/api/agent/tools_impl.py:638`
- **Impact:** the dispatcher calls `_tool_execute_code(args, thread_id="", ...)`. `SandboxManager` keys sandboxes by `thread_id`, so all concurrent code executions in a worker **share one sandbox session**, leaking variables / files / installed packages across different users' jobs.
- **Fix:** thread the real `configurable["thread_id"]` (set in `jobs.py:590`) through `execute_tool` to `_tool_execute_code` instead of `""`.

### 4. `CancelledError` mishandled at the graph entry — crashes instead of propagating *(high)*
- **Where:** `backend/src/services/agent/_nodes_classify.py:178–183`
- **Impact:** `asyncio.gather(..., return_exceptions=True)` over the rag/classify/memory subtasks; `CancelledError` is a `BaseException`, not `Exception`, so `isinstance(result, Exception)` is `False` and control falls to `merged.update(<CancelledError>)` → `TypeError: 'CancelledError' object is not iterable`. A client disconnect / the 300 s streaming timeout cancels these tasks at the graph entry, turning a clean cancellation into a crash and breaking propagation to LangGraph.
- **Fix:** check `isinstance(result, asyncio.CancelledError)` first and re-raise before the generic `Exception` branch.
- **Note:** this is the same `BaseException`/`CancelledError` footgun fixed in `llm_entity_extraction.py` (PR #562). Worth a repo-wide grep — see Themes.

### 5. Job-store: fire-and-forget Redis write can stomp newer state *(high)*
- **Where:** `backend/src/api/agent/jobs.py:57–76` · `backend/src/services/agent/job_store.py:137,184`
- **Impact:** `_set_job()` writes L1, then spawns `loop.create_task(_write_to_redis_only)` with the T1 payload. A later write pushes newer state (T2) to Redis; the delayed T1 task then overwrites Redis unconditionally — the Redis writers call `setex()` with no `created_at` comparison (the monotonic guard at `job_store.py:137` only protects L1). On worker restart (L1 lost), `get_job()` seeds L1 from stale Redis with no timestamp check (`:184`), so polling can report `running` for a job that already completed.
- **Fix:** add a `created_at`/sequence guard to the Redis writes (compare-and-set, or skip if existing `created_at >= payload.created_at`) and apply the same guard when seeding L1 from Redis.

### 7. Stale `project_id`: text-extracted URL overrides current project — cross-project scoping risk *(high, medium confidence)*
- **Where:** `backend/src/services/agent/_nodes_rag.py:346–348,377,379`
- **Impact:** `resolved_project_id = extracted_pid or existing_project_id or None` prefers a `/projects/<uuid>` URL parsed from the user's message text over `state.current_project_id` / `page_context`. A message containing an old/quoted/pasted project URL after the user switched projects scopes RAG retrieval to the wrong project — potential cross-project document exposure to the LLM. Requires the specific stale-URL-in-message condition.
- **Fix:** don't let implicit message-text extraction override an explicit `page_context`/state project; only honor an extracted URL as a deliberate switch (gate on `page_context.type` or compare against `current_project_id`).

---

## 🟠 High-impact performance

### 8. LLM clients rebuilt on every call — no caching in `llm_factory` *(high)* — best single win
- **Where:** `backend/src/services/agent/llm_factory.py:125–178` (`build_lightweight_llm` / `build_synthesis_llm`) · callers: `_nodes_llm.py:195,280`, `planner.py:82–89,105`, `memory_store.py:287,298`, `subgraphs/{research,writing,data}_agent.py`
- **Impact:** unlike `classifier`/`compactor`/`reflection` (which cache module-level), `build_synthesis_llm`/`build_lightweight_llm` construct a fresh `ChatOpenAI`/`AzureChatOpenAI` + HTTP client (~30–50 ms, documented at `graph.py:217`) on **every** call. `llm_node` hits this every synthesis turn, looping up to `MAX_TOOL_LOOPS(4)+1` per user turn; subgraphs loop similarly. All `build_synthesis_llm` call sites use identical `max_tokens=4096`.
- **Fix:** module-level caches keyed by `(deployment, max_tokens)` (`_SYNTHESIS_LLM` / `_LIGHTWEIGHT_LLM`) using the `classifier.py:83–97` null-check pattern. Every caller benefits with no per-file change. (Subsumes the compactor/reflection cache races in #11.)

### 9. O(n) L1 cleanup under lock on every job write *(high)*
- **Where:** `backend/src/services/agent/job_store.py:139`
- **Impact:** `set_job()` unconditionally runs `_l1_cleanup()` (iterates up to 500 entries, FIFO-evicts) while holding `_l1_lock`, on every status transition (multiple per execution). The throttled `_l1_maybe_cleanup()` (60 s) already exists and is used on the read path but not the write path → needless lock contention and CPU under load.
- **Fix:** replace `_l1_cleanup()` at line 139 with `_l1_maybe_cleanup()`.

---

## 🟡 Medium

| # | Kind | Issue | Location | Fix |
|---|------|-------|----------|-----|
| 6 | bug | `await kb_db.merge(d)` — `AsyncSession.merge()` is synchronous in SQLAlchemy 2.0 → `TypeError`, swallowed by the surrounding `try/except` → the DO-KB dual-write silently never happens | `tools_impl.py:950–953` | drop the `await`: `merged = [kb_db.merge(d) for d in persisted_documents]` |
| 10 | perf | Tool-dedupe key is computed from the original args **before** `project_id` is injected from `page_context`, so a repeat call with `project_id` omitted misses the dedupe cache and re-executes | `_nodes_tools.py:207–213,300–310,339–344` | inject `page_context` `project_id` before computing the dedupe key |
| 11 | perf | Unprotected `if-None-then-build` race on `_COMPACTOR_LLM`/`_REFLECTION_LLM` caches → duplicate client builds; `reflection.py:32` declares `_REFLECTION_LLM_LOCK` but never uses it | `compactor.py:166,169–175` · `reflection.py:32,53–65` | double-checked locking with `asyncio.Lock` (or just implement #8, which subsumes this) |
| 12 | perf | Redundant `list(state["messages"])` shallow copy per `llm_node` call — `_sanitize_messages` doesn't mutate its input | `_nodes_llm.py:167` (+ `research_agent.py:94`, `writing_agent.py:122`, `data_agent.py:74`) | pass `state["messages"]` directly; keep the copy only where the list is mutated (`force_synthesis_node:264`) |
| 13 | bug | `extract_insights` builds an LLM and `ainvoke`s a "return an empty response" prompt, then discards it and returns `[]`, when `messages` is empty | `memory_store.py:285–295` | `if not messages: return []` before any LLM construction |
| 14 | perf | ArXiv search cache key embeds minute-precision `now()` in the query string, so identical searches > 1 min apart miss the bounded 429-avoidance cache | `tools_impl.py:656–658,668,730–741` | compute the cache key before applying the date filter, or coarsen the cutoff to day granularity |
| 15 | bug | L1 monotonic guard uses `existing.created_at <= data.created_at` → an equal-timestamp write can overtake an out-of-order newer one | `job_store.py:137` | add a per-job sequence/version number and compare on that (avoid a naive `<=`→`<` swap, which can drop valid same-tick updates) |
| 16 | perf | Fire-and-forget `create_task(_write_to_redis_only)` has no done-callback → Redis failures are invisible and the unreferenced task can be GC'd | `jobs.py:72–76` | keep a task reference + `add_done_callback` to log/metric failures (pairs with #5) |

---

## ⚪ Low

- **17 — Keyword classifier uses substring matching** (`classifier.py:172–178`). `if kw in query_lower` lets `'graph'` match `'biography'`, `'entity'` match `'identity'`. Mitigated: such matches yield low (non-zero) confidence that escalates to the LLM classifier rather than mis-routing, so the net effect is occasional extra LLM round-trips. **Fix:** match on word boundaries (`re.search(r'\b'+re.escape(kw)+r'\b', query_lower)`).
- **18 — `memory_store.py` `search_memories`/`save_memory` are broken but dead code** (`:148–166`, `:209–231`). `search_memories` calls `result.scalars().all()` on `select(table)` then accesses `.content`/`.memory_type` on scalar UUIDs (`AttributeError`); `save_memory` builds a non-ORM object via `type('AgentMemory',(),{...})` that never persists. Both are real bugs but unreachable — production memory goes through `services/agent/memory.py` (LangGraph `AsyncPostgresStore`); these are only imported by mocked tests. **Fix:** delete the dead functions, or fix + add a non-mocked test if intended for use.

---

## Cross-cutting themes

1. **`BaseException`/`CancelledError` footgun** (#4, plus the instance fixed in PR #562). Grep for `isinstance(.*, Exception)` immediately after `gather(return_exceptions=True)` — `CancelledError`/`KeyboardInterrupt`/`SystemExit` slip past and are then processed as success values. At least one live instance remains (#4).
2. **Per-call LLM client construction** (#8, #11). A single factory-level cache fixes the whole cluster and is the highest-leverage perf change.
3. **Job-store L1/L2 consistency** (#5, #9, #15, #16). The fire-and-forget Redis path needs a single guarded writer with a monotonic guard applied to both L2 writes and L1-seed-from-L2.

---

## Method & rigor

- **Finders (15):** 10 per-area (graph/routing, llm-nodes, rag/memory, tools graph-side, tools-impl, jobs/streaming, state/compaction, reflection/planner, subgraphs, entity-extraction) + 5 cross-cutting lenses (async-blocking, DB-queries, LLM-cost, concurrency, resource/error-handling).
- **Verification:** every raw finding was handed to an independent agent instructed to *refute by default* and re-check against the source. 23 of 87 were refuted or downgraded to non-issue.
- **Synthesis:** survivors were deduped by root cause (4 LLM-caching findings → #8; reflection+compactor races → #11; `execute_code`+`thread_id` pair → #3; Redis-guard reports → #5) and ranked by severity × confidence × blast radius.

Recommended fix order: **#1, #4, #8, #9, #13** (contained, mechanical, high value), then **#2, #3, #5, #7**, then the medium table.
