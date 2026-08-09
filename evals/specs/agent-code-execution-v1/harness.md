Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, checkpointer, and `Command(resume=...)` semantics used by production.

Source: repository revision `38ef8876c4d63596817c670895bb8991246bbb80`, containing the execute-code reachability fix.

Preserved behavior: production tool registry and `execute_code` implementation, including the impl-level execution cap, timeout, and DESTRUCTIVE-tag HITL gate (`interrupt_node`); the `SandboxManager`'s per-thread sandbox statefulness and dependency-priming call; per-turn tool deduplication; compaction; reflection; model selection, retries, and stopping. The adapter sends a normal `initial_agent_state` through live classification; the observed checkpoint intent must be `research`, whose subgraph contains `execute_code`.

Adapter: create one compiled graph per trial; monkeypatch `e2b_code_interpreter.code_interpreter_async.AsyncSandbox._jupyter_url` to the mock double's host (the code-interpreter execute route ignores `E2B_SANDBOX_URL` — a spike finding, not an environment-only seam) before compiling; snapshot checkpoint message IDs, send the real instruction, drive the graph to the `execute_code` HITL interrupt, snapshot the double's event log before approving (must be empty), approve, drive to completion; explicitly tear down the sandbox (`SandboxManager.cleanup`) so the double's `kill` route is genuinely exercised, since production never calls it within a single turn. The adapter translates the final state into Harbor output but does not alter prompts, routes, tool arguments, or results.

Session: single real classified turn on one thread — no scripted follow-up turns.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`. `E2B_API_KEY=benchmark-token` with `E2B_VALIDATE_API_KEY=false` satisfies the SDK's client-side key-format check; no production database or E2B credential is permitted or required — the mock double needs none.

Recorded evidence: user and assistant messages; pre-turn message IDs and newly appended matching human-message IDs; the observed post-routing intent (must be the real `research` AgentIntent); model calls and usage; the `execute_code` tool call, arguments, result, and any retry or error; interrupt and resume; the E2B environment/patch values actually applied; the mock double's full `GET /events` request log, including a pre-approval snapshot; final assistant message; termination reason; and elapsed time.

Reconstruction differences: the HTTP/SSE and Redis chat-stream buffering layers are intentionally excluded — this task has no chat-stream Redis usage at all (no Redis service is provisioned). The graph, classifier, tool implementation, HITL behavior, and `SandboxManager` remain production code; the E2B backing sandbox is isolated and synthetic, and the adapter only supplies the Harbor turn envelope and wire-double patches.
