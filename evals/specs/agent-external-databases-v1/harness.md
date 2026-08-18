Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, and checkpointer used by production.

Source: repository revision `38ef8876c4d63596817c670895bb8991246bbb80`, containing the connector reachability fix.

Preserved behavior: production tool registry and `search_external_database`/`list_external_databases` implementations, including the impl-level `max_results` cap, connector/domain name validation, and the `connector_registry` singleton's real availability logic; per-turn tool deduplication; compaction; reflection; model selection, retries, and stopping. The adapter sends a normal `initial_agent_state` through live classification and the observed checkpoint intent must be `general`, which binds both tools. Neither tool is DESTRUCTIVE, so unlike the sibling code-execution task, this turn never raises a HITL interrupt.

Adapter: create one compiled graph per trial; monkeypatch `src.services.connectors.pubmed._ESEARCH`/`_EFETCH` and `src.services.connectors.fred._BASE_URL` to the mock double's host before compiling; snapshot checkpoint message IDs, send the real instruction, and drive the graph to completion in a single pass (no interrupt/resume loop). The adapter translates the final state into Harbor output but does not alter prompts, routes, tool arguments, or results.

Session: single real classified turn on one thread — no scripted follow-up turns.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`. `FRED_API_KEY=benchmark-fred-token` is provisioned so the `fred` connector is genuinely available; `ALPHA_VANTAGE_API_KEY`/`COSMIC_AUTH` are deliberately unset. No production database or upstream connector credential is permitted or required — the mock double needs none.

Recorded evidence: user and assistant messages; pre-turn message IDs and newly appended matching human-message IDs; the observed post-routing intent (must be the real `general` AgentIntent); model calls and usage; the `list_external_databases`/`search_external_database` tool calls, arguments, and full results; the connector-patch values actually applied; the mock double's full `GET /events` request log; final assistant message; termination reason; and elapsed time.

Reconstruction differences: the HTTP/SSE and Redis chat-stream buffering layers are intentionally excluded — this task has no chat-stream Redis usage at all (no Redis service is provisioned). The graph, classifier, tool implementations, and connector registry remain production code; the PubMed/FRED backing services are isolated and synthetic, and the adapter only supplies the Harbor turn envelope and wire-double patches.
