# Agent performance — tracing harness + audit

`test_agent_langsmith_tracing.py` drives the LangGraph agent through representative
scenarios with **LangSmith tracing on**, tagged so per-scenario latency can be
measured over time and diffed across deploys. It is the repeatable version of the
manual SDK trace audit.

## Run

```sh
# In dev/CI with infra (Azure LLM + Postgres + Neo4j) and a LangSmith key:
RUN_PERF_HARNESS=1 LANGSMITH_API_KEY=… pytest backend/tests/perf -m performance
# or as a script (prints per-scenario wall-clock):
RUN_PERF_HARNESS=1 python -m tests.perf.test_agent_langsmith_tracing
```

Without `RUN_PERF_HARNESS=1` (and infra) every scenario **skips** — it never runs in
the unit lane. Soft per-scenario latency budgets assert only under the gate, so the
harness catches regressions but never red-fails normal CI.

Scenarios: greeting · general · research/arxiv · writing/draft · knowledge-graph · HITL.
Tags: `scenario:<x>`, `perf-harness` + metadata → saved views per scenario in LangSmith.

## Audit findings (live traces, `rag-agent-dev-local`, 30d, 999 runs)

Root chain **p95 = 29s / p99 = 54s** while the **LLM is only p95 = 8s** — the wall-clock
is in retrieval, blocking persistence, the planner, and serialized tool loops. Nine
hot-path findings were confirmed (adversarially verified against the trace data),
clustering into four fixes, ranked by leverage:

| #   | Fix                                                                                                                                                                                                                                                   | Where                                                  | Est. savings                                                   | Confidence |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | -------------------------------------------------------------- | ---------- |
| 1   | **Cap DO-KB `retrieve()` with a tight timeout + fail-fast** (wrap in `asyncio.wait_for(~3s)`, cap retries, fall through to hybrid). Inherits a 30s request default today; a retry loop can stack to ~90s.                                             | `_nodes_rag.py:252`, `…/do_kb/client.py:115`           | ~15–17s off `do_kb` p99 (19.8→~3s); caps catastrophic outliers | high       |
| 2   | **Background `memory_save_node`** — detach the embed + PG write and the every-5th-turn insight-extraction LLM via `create_task`, so the node returns and the `done` event fires right after the last token.                                           | `_nodes_memory.py:91-219`                              | ~6–8s off p95/p99 tail (every persisted turn)                  | high       |
| 3   | **Planner: collapse 2 LLM calls → 1, halve the 20s timeout, writing fast-skip, run non-blocking.** It's the unconditional entry of the writing subgraph and purely advisory.                                                                          | `planner.py:342-365`, `subgraphs/writing_agent.py:363` | ~3–8s typical, up to ~15–20s p99 on planned turns              | medium     |
| 4   | **Collapse serial tool loops** — prompt/bind so the model emits independent tools in one `AIMessage` (one parallel `tool_node` batch) instead of one-per-loop; early-exit when a batch is fully deduped. Each eliminated loop removes a full LLM hop. | `_builders.py:59,210`, `_nodes_tools.py`               | ~8–16s on tail multi-loop turns                                | medium     |

**Do first: #1 (RAG timeout).** Highest impact, high confidence, smallest blast radius —
the DO-KB stall is a single unguarded call inheriting a 30s default.

Notes:

- `p50` is healthy (~6s): the median turn is fine. These fixes target the **p95/p99 tail**.
- arXiv ingest (~34s single tool) is inherently slow — out of scope; it has its own long-timeout tool budget.
- The harness lets the team watch each scenario's p50/p95 per deploy and confirm these fixes land (e.g. `do_kb` p99 dropping after #1).
