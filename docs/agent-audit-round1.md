# Agent audit round 1 — started 2026-08-16
Source: opencode session, 4 parallel explore agents over backend/src/services/agent + backend/src/api/agent

| ID | Finding (one line) | Sev | Status | Owner | PR | Updated |
|----|--------------------|-----|--------|-------|----|---------|
| H1 | `_tool_ingest_arxiv` (tools_impl.py:1225) missing `current_user` auth guard — full ingest pipeline runs unauthenticated; also phantom document_ids via getattr fallback (1345) | high | open | — | — | 08-16 |
| H2 | terminal `set_job` → `record_job_status(raise_on_error=True)` (job_store.py:345) raises before L1/Redis writes → handler task dies, job stuck "running" 30min, sweeper overwrites real error (agent_execution_service.py:2374-2420) | high | open | — | — | 08-16 |
| H3 | streaming.py:1250-1253 degraded path uses raw client `thread_id` as checkpoint key when `_resolve_thread` returns None → cross-tenant checkpoint read/write, HITL confirm hijack; `/execute` sanitizes this case, `/stream` does not | high | open | — | — | 08-16 |
| M1 | `tool_executions` never reset per turn (_nodes_classify.py:220-240) → memory_save gate + tools_used polluted by prior turns; noise-recall bug | med | open | — | — | 08-16 |
| M2 | ownership-check exception → `scoped_project_id=None` → org-wide DO KB read (_nodes_rag.py:187-189, 399-411) — fail-open widening on DB blip | med | open | — | — | 08-16 |
| M3 | bare-UUID fallback stores any pasted UUID as current_project_id (graph.py:36-37, _nodes_rag.py:694-740) — no ownership check on propagation path | med | open | — | — | 08-16 |
| M4 | stale `last_user_msg` for multimodal turns (_nodes_llm.py:264-280) → canned greeting answers image-only turn, image never sent | med | open | — | — | 08-16 |
| M5 | multimodal content raises in `is_conversational` (_nodes_memory.py:166-179, outside try) → gather swallows, memory recall silently dropped every multimodal turn | med | open | — | — | 08-16 |
| M6 | `return_exceptions=True` (tools_impl.py:3023-3056) — total connector failure returns success-shaped empty result, dedupe blocks retry, misreported to user | med | open | — | — | 08-16 |
| M7 | invalid connector name silently degrades to fan-out across ALL connectors (tools.py:771-776, tools_impl.py:2992-3018) — typo → ~250-connector HTTP burst | med | fixed | clawd | #PRNUM | 08-19 |
| M8 | wrapper silently truncates paper_ids to 10 (tools.py:270) — 15 requested → 10 land, "Ingested 10 of 10", 5 vanish, impl's >10 error unreachable | med | fixed | clawd | #PRNUM | 08-19 |
| M9 | `_resume_agent_graph` pins asyncpg connection up to 360s (agent_execution_service.py:2442, 2558-2595); same in `_run_agent_graph` skill-off path → pool exhaustion | med | open | — | — | 08-16 |
| M10 | `set_job` monotonic guard compares stale pre-await `existing` (job_store.py:311-361) → older status resurrects newer cross-worker; redis_only has no guard | med | open | — | — | 08-16 |
| M11 | circuit-breaker exit + HITL-deny leave dangling tool_calls (_factory.py:182-183, 390-401) → stale previous-turn answer persisted as COMPLETED assistant row | med | open | — | — | 08-16 |
| M12 | get_thread_messages count query omits `before` cursor filter (execute.py:1321-1330) — documented count/filter-drift bug class | med | open | — | — | 08-16 |
| M13 | `replay_buffered_stream` emits no heartbeats (streaming.py:922-969) — proxies kill resumed SSE during silent gaps, reconnect loop | med | open | — | — | 08-16 |
| L1 | sanitizer skips tool_call with empty/missing id — AIMessage keeps unanswered tool_call → 400 + 3 retries (graph.py:100-103) | low | open | — | — | 08-16 |
| L2 | HITL audit-row failure swallowed at DEBUG (_nodes_tools.py:161-174) — compliance record missing invisibly | low | open | — | — | 08-16 |
| L3 | fast_path LLM stream iterator never closed on early exit; persist failure suppressed silently (fast_path.py:144-168) | low | open | — | — | 08-16 |
| L4 | `_LLM_CACHE` key omits credentials (graph.py:244-246) — stale clients after secret rotation without restart | low | open | — | — | 08-16 |
| L5 | `failed_papers` never reconciled after stub-path success (tools_impl.py:1272-1288) — contradictory payload → false failure report | low | open | — | — | 08-16 |
| L6 | `list_project_documents` bypasses status mapping (tools_impl.py:2010-2012) — "completed" vs "indexed" inconsistent for same doc | low | open | — | — | 08-16 |
| L7 | compare_documents cap mismatch: wrapper 10, impl 5 (tools.py:80,528 / tools_impl.py:2299) — guaranteed error loop 6-10 | low | fixed | clawd | #PRNUM | 08-19 |
| L8 | `export_bibliography` never caps document_ids (tools.py:676-692) — unbounded IN-clause | low | fixed | clawd | #PRNUM | 08-19 |
| L9 | `execute_code` falls back to thread_id="default" (tools.py:723) — shared stateful sandbox, cross-conversation leakage | low | fixed | clawd | #PRNUM | 08-19 |
| L10 | project_service.py:72 `search` ilike unescaped — wildcard injection broadens match | low | open | — | — | 08-16 |
| L11 | `_set_job` bypasses L1 monotonic guard, no `_seq` (agent_execution_service.py:119-156) | low | open | — | — | 08-16 |
| L12 | failed Redis init leaks client per retry (job_store.py:129-135) | low | open | — | — | 08-16 |
| L13 | memory namespace lacks organization_id (memory.py:168,194,266) vs org-scoped durable table | low | open | — | — | 08-16 |
| L14 | stream_buffer non-atomic rpush/ltrim/expire — orphan no-TTL key possible; trim gives no gap signal (stream_buffer.py:64-68) | low | open | — | — | 08-16 |
| L15 | `read_after` materializes+parses whole 5000-frame buffer per poll (stream_buffer.py:76-78) | low | open | — | — | 08-16 |

## Log
- 2026-08-16: audit created. 4 explore agents (graph/nodes, tools, subgraphs/execution, API). Verified-clean: checkpointer URL transform, loop bounds, tenant scope on doc/citation/KG queries, project ownership in tools, HITL gating on destructive tools, thread/job/confirm ownership checks (except H3 degraded path), thread summarization session usage, compactor message pairing, tool_dedupe keying.
