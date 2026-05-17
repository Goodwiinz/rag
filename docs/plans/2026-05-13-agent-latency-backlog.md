# Agent Latency Hotfix Swarm — Follow-up Backlog

Source: LangSmith MCP audit + perf commits `2be54fb3`, `2868b696`, `62d1a5a2`. Linked PR: [#508](https://github.com/Goodwiinz/rag/pull/508).

Linear team `Goodwiinz` hit free-tier issue cap (2026-05-13). Paste these into Linear manually or upgrade workspace.

---

## P2 — Post-restart full latency re-baseline + dashboard alerts

**Labels:** Improvement
**Priority:** 2 (High)

After commits `2be54fb3`, `2868b696`, `62d1a5a2` activate in production, run full LangSmith latency analysis vs documented baseline.

### Targets

- Root p50 ≤ 6s
- Root p95 ≤ 10s
- Root max ≤ 50s (aggregate cap fires)
- Zero `end_time=null` LLM runs in 24h
- Tool spans populated (> 0)
- Retriever spans populated (> 0)

### Output

- Markdown report w/ before/after table
- Top 3 remaining outliers
- Update `memory/projects/nous-platform.md` perf baseline

### Follow-on

- Prometheus alert: `agent_execution_duration_seconds{quantile="0.95"} > 12`
- LangSmith automation: alert on any LLM run > 45s on `gpt-5-mini` deployment
- Per-tool p95 alert once tool spans accumulate

### Reference

- Baseline traces: `019e1d38-35a0-7ea2-9f05-88ac6d7496d1` (73.5s), `019e1a6c-00a5-7bf0-b3f7-32f2c9bbbb09` (70s hang), `019e21fe-922c-7652-ab93-4fed73538640` (90s aggregate stall)

---

## P3 — Verify post-restart: LangSmith tool spans populate

**Labels:** Improvement
**Priority:** 3 (Medium)

After backend restart picks up commit `2868b696`, verify `langsmith.traceable(run_type="tool")` wrapper emits per-tool spans.

### Verification

- Run agent query triggering `search_arxiv` / `do_kb_retrieve` / `search_documents`
- `mcp__langsmith__fetch_runs run_type=tool limit=20 project_name=rag-agent-dev-local`
- Assert > 0 spans, `name` field = tool name
- Confirm per-tool p50/p95 visible

### Expected

- arXiv calls separately surfaced
- KG / Qdrant / Cohere latency isolatable

### Reference

- `backend/src/services/agent/_nodes_tools.py` line ~246

---

## P3 — Verify post-restart: retriever spans populate for DO KB + hybrid search

**Labels:** Improvement
**Priority:** 3 (Medium)

After restart, verify `_maybe_traced_retriever` decorator emits `run_type=retriever` spans.

### Verification

- Trigger RAG retrieval (project-scoped query)
- `mcp__langsmith__fetch_runs run_type=retriever limit=20 project_name=rag-agent-dev-local`
- Assert > 0 spans named `do_kb_retriever` + `hybrid_search_retriever`

### Expected

- DO KB primary path latency visible
- Qdrant + Cohere fallback path latency visible
- Spans link as children of `rag_node`

### Reference

- `backend/src/services/agent/_nodes_rag.py` line ~171

---

## P3 — Verify post-restart: force_synthesis_node fires at MAX_TOOL_LOOPS

**Labels:** Improvement
**Priority:** 3 (Medium)

After restart, verify routing through `force_synthesis_node` when ceiling tripped.

### Verification

- Trigger long general-intent query forcing > 4 tool loops
- LangSmith trace shows `force_synthesis_node` chain span
- Final AIMessage has prose content (not empty + orphan tool_calls)
- `tool_loop_count` capped at 4

### Acceptance

- 3+ traces with `tool_loop_count >= 4` end via `force_synthesis_node`
- Zero traces with empty AIMessage + orphan tool_calls in 1h sample

### Reference

- `backend/src/services/agent/_nodes_llm.py`, `_builders.py`

---

## P3 — Investigate checkpointer SSL timeout (psycopg)

**Labels:** Bug
**Priority:** 3 (Medium)

Verification surfaced one instant-error root at 22:43:00 prior day: psycopg `Operation timed out` on AsyncPostgresSaver. Orthogonal to LLM latency but 100% turn failure when it fires.

### Symptoms

- Root errors at 0.007s
- Error path: `langgraph.checkpoint.postgres.aio.AsyncPostgresSaver`
- Sporadic in current window

### Hypothesis

- Supabase session-mode idle drop; keepalive sockopt no-op on macOS dev
- Pool conn age > NAT rebind window
- `_pool_utils.py` WIP adds `_MAX_IDLE_SECONDS=60` + `check_connection` pre-flight (may already fix)

### Action

- Wait for `_pool_utils.py` WIP to land
- Tail backend logs for psycopg reconnect attempts
- Re-query LangSmith for checkpointer error filter after 1 week

### Reference

- `backend/src/services/agent/_pool_utils.py`

---

## P4 — Resolve silent main deployment override (frontend hardcodes gpt-5-mini)

**Labels:** Code Quality
**Priority:** 4 (Low)

LangSmith audit (A1) discovered: `.env` sets `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=model-router` but frontend `AgentExecuteRequest.model` hardcodes `gpt-5-mini`. `graph.py:_build_llm` accepts `model_override` which wins. Env-configured meta-router never exercised on chat surface.

`.env` patched in commit `1a587dbc` to default `gpt-5-mini` (matches reality). Override path remains config smell.

### Action

Pick one:

1. Remove frontend hardcode → respect env default. Audit model-router routing perf separately.
2. Document override convention + remove `model-router` from `SUPPORTED_MODELS` if unused.
3. Add log line when `model_override` differs from env default so config drift becomes visible.

### Reference

- `backend/src/services/agent/graph.py:_build_llm` ~line 219
- `backend/src/api/agent/execute.py:113` `SUPPORTED_MODELS`
- `backend/.env:56`
