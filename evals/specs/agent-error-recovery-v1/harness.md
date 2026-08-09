Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked through the existing NOUS Harbor agent and a task-owned adapter.

Source: repository revision `27018e69c0c9e0339aab5db5f76d34e1715a316c`; final run metadata pins the completed repository and image digests.

Preserved behavior: production classifier and writing subgraph, tool registry, `summarize_document` and `list_project_documents`, payload classification in `error_recovery.py`, tool dedupe/failure cap, `MAX_ERRORS`, message sanitization, reflection, final-response fallback, and memory-save exit.

Adapter: create one production-shaped graph session, send the approved instruction, and record all graph updates through termination. It does not alter errors, counters, tool results, prompts, or routes.

Session: one single-turn session. The request itself contains both the recoverable and exhaustion cases; no simulated follow-up user is used.

Credentials: Harness model variables plus isolated `HARBOR_JUDGE_ENDPOINT`, `HARBOR_JUDGE_API_KEY`, `HARBOR_JUDGE_MODEL`, and `HARBOR_JUDGE_API_VERSION`. Judge credentials are unavailable to the Harness.

Recorded evidence: messages; tool calls/results; raw returned payloads and resulting ToolMessages; `last_error_info`; error and loop counters; dedupe/circuit-breaker records; final response; termination reason; timing; usage; and independent initial/final database state.

Reconstruction differences: backing documents are synthetic and PostgreSQL is isolated. The graph, error classifier, tools, dedupe, counters, and response path are production code; HTTP/SSE rendering is excluded.
