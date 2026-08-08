Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, and checkpointer used by production.

Source: repository revision `c19b1aeafa50507e9aa827eac966b1c6dece446c` (`feat/tool-coverage-bench-plan4`, cut off `develop`).

Preserved behavior: production tool registry and `search_external_database`/`list_external_databases` implementations, including the impl-level `max_results` cap, connector/domain name validation, and the `connector_registry` singleton's real availability logic; per-turn tool deduplication; compaction; reflection; model selection, retries, and stopping. The only non-production element is the routing entry point: instead of live classification, the adapter seeds the checkpoint with a sentinel intent via `aupdate_state(..., as_node="preprocessing_node")` so `route_by_intent` falls through to the general path's `llm_node`, which binds `ALL_TOOLS` for any intent outside `AgentIntent`'s `Literal` type (`_nodes_llm.py:122-127`) — the only way this pinned image's routing exposes these two tools, whose `intents=frozenset()`/`subgraphs=frozenset()` metadata is otherwise dead under both intent- and subgraph-scoped binding. Neither tool is DESTRUCTIVE, so unlike the sibling code-execution task, this turn never raises a HITL interrupt.

Adapter: create one compiled graph per trial; monkeypatch `src.services.connectors.pubmed._ESEARCH`/`_EFETCH` and `src.services.connectors.fred._BASE_URL` to the mock double's host before compiling; seed the sentinel-intent state; drive the graph to completion in a single pass (no interrupt/resume loop). The adapter translates the final state into Harbor output but does not alter prompts, routes, tool arguments, or results.

Session: single sentinel-seeded turn on one thread — no scripted follow-up turns.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`. `FRED_API_KEY=benchmark-fred-token` is provisioned so the `fred` connector is genuinely available; `ALPHA_VANTAGE_API_KEY`/`COSMIC_AUTH` are deliberately unset. No production database or upstream connector credential is permitted or required — the mock double needs none.

Recorded evidence: user and assistant messages; the observed post-routing intent (must equal the seeded sentinel); model calls and usage; the `list_external_databases`/`search_external_database` tool calls, arguments, and full results; the connector-patch values actually applied; the mock double's full `GET /events` request log; final assistant message; termination reason; and elapsed time.

Reconstruction differences: the HTTP/SSE and Redis chat-stream buffering layers are intentionally excluded — this task has no chat-stream Redis usage at all (no Redis service is provisioned). The graph, tool implementations, and connector registry remain production code; the PubMed/FRED backing services are isolated and synthetic, and the routing entry point is adapter-synthesized rather than classifier-derived, as documented in environment.md Fidelity limits.
