Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, checkpointer, and `Command(resume=...)` semantics used by production.

Source: repository revision `261273129dbea6f646c9662566ff5a7eea61545a` (`feat/tool-coverage-bench-plan1` off `develop`; agent code delivered by `261273129dbea6f646c9662566ff5a7eea61545a`).

Preserved behavior: production classifier and action override; intent routing; planners and subgraphs; production tool registry and the `create_project`, `list_projects`, `add_document_to_project`, `create_project_note`, and `list_project_documents` implementations; HITL interrupt; per-turn tool deduplication; compaction; reflection; model selection, retries, and stopping.

Adapter: create one compiled graph per trial, seed the tenant and the single `Seed Paper` document, build the production-shaped initial state, send the instruction as a `HumanMessage`, then stream updates in a loop — on each HITL interrupt record the requested tool and arguments and resume the same graph session with `Command(resume={"confirmed": true})` — until the graph completes. The adapter translates the final state into Harbor output but does not alter prompts, routes, tool arguments, or results.

Session: four user actions in one thread: the initial request, followed by three approvals, each sent only after the agent requests that confirmation. Future input is not preloaded.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`. No production database credential is permitted.

Recorded evidence: user and assistant messages; classifier intent, confidence, and source; plan; model calls and usage; tool calls, arguments, results, retries, and errors; every interrupt and its approval as ordered milestones; termination reason; elapsed time; and the Environment's initial/final database state.

Reconstruction differences: the HTTP/SSE, Redis buffering, and canonical chat-message projection layers are intentionally excluded. The graph, tool implementations, HITL behavior, and persistence services called by the tools remain production code; backing state is isolated and synthetic.
