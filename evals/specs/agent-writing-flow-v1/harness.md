Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, checkpointer, and `Command(resume=...)` semantics used by production.

Source: repository revision `b67ebbf1b067d5f5b1e74299535244e58df41a68` (`develop`, carrying plan 1's `harbor_common` and `agent-project-management-v1` via #1354).

Preserved behavior: production classifier and action override; intent routing into the WRITING subgraph; the production tool registry and the real `compare_documents`, `create_draft`, and `export_bibliography` implementations (including the 5-document impl cap and the async `DraftGenerationService` handoff); HITL interrupt on `create_draft` only; per-turn tool deduplication; compaction; reflection; model selection, retries, and stopping.

Adapter: create one compiled graph per trial, build the production-shaped initial state, set `page_context={"type": "project", "project_id": ...}` so the tools resolve the open project the same way the frontend would, send the instruction as a `HumanMessage`, record updates until the `create_draft` HITL interrupt, take a database snapshot, then send the fixed approval as `Command(resume={"confirmed": true})` in the same graph session. The adapter translates the final state into Harbor output but does not alter prompts, routes, tool arguments, or results.

Session: two user actions in one thread: the initial request, followed by approval only after the agent requests confirmation for `create_draft`. Future input is not preloaded.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT` for the agent container; `HARBOR_JUDGE_ENDPOINT`, `HARBOR_JUDGE_API_KEY`, `HARBOR_JUDGE_MODEL`, and `HARBOR_JUDGE_API_VERSION` for the verifier only, never passed to the agent environment. No production database credential is permitted.

Recorded evidence: user and assistant messages; classifier intent, confidence, and source; plan; model calls and usage; tool calls, arguments, results, retries, and errors for all three tools; the interrupt and resume for `create_draft`; termination reason; elapsed time; and the Environment's initial/pre-approval/final database state.

Reconstruction differences: the HTTP/SSE, Redis buffering, and canonical chat-message projection layers are intentionally excluded. The graph, tool implementations, HITL behavior, and persistence services called by the tools remain production code; backing state is isolated and synthetic. The draft-generation background task is allowed to still be in flight when the trial ends -- the harness does not wait for it, matching the tool's own fire-and-forget contract.
