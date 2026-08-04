Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, checkpointer, and `Command(resume=...)` semantics used by production.

Source: repository revision `6e618d0fb5874fa262b783345000f1496e52d7c7` (`develop`; agent code delivered by `756367d7b015c7e2b2d2b6d69092feb9e3dd0c40`).

Preserved behavior: production classifier and action override; intent routing; planners and subgraphs; production tool registry and `create_project` implementation; HITL interrupt; per-turn tool deduplication; compaction; reflection; model selection, retries, and stopping.

Adapter: create one compiled graph per trial, build the production-shaped initial state, send the instruction as a `HumanMessage`, record updates until the HITL interrupt, then send the fixed approval as `Command(resume={"confirmed": true})` in the same graph session. The adapter translates the final state into Harbor output but does not alter prompts, routes, tool arguments, or results.

Session: two user actions in one thread: the initial request, followed by approval only after the agent requests confirmation. Future input is not preloaded.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`. No production database credential is permitted.

Recorded evidence: user and assistant messages; classifier intent, confidence, and source; plan; model calls and usage; tool calls, arguments, results, retries, and errors; interrupt and resume; termination reason; elapsed time; and the Environment's initial/final database state.

Reconstruction differences: the HTTP/SSE, Redis buffering, and canonical chat-message projection layers are intentionally excluded. The graph, tool implementation, HITL behavior, and persistence service called by the tool remain production code; backing state is isolated and synthetic.
