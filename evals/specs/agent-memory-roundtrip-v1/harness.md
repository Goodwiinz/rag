Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, checkpointer, store, and `Command(resume=...)` semantics used by production.

Source: repository revision `b1165862ff0ba2021a0a5a3a206a0fd253a6d9a2` (`feat/tool-coverage-bench-plan3`, based on `develop`).

Preserved behavior: production classifier, `memory_save_node`/`memory_retrieval_node`, the destructive-tool HITL interrupt, per-turn tool deduplication, compaction, reflection, model selection, retries, and stopping. Turn 3's tool-binding decision is the one place the adapter substitutes a harness API for the live classifier — see below.

Adapter: compile one graph per trial, build the production-shaped initial state, send turn 1 as a `HumanMessage`, poll the memory store for the deterministic key `memory_save_node` computes until the fire-and-forget write lands, send turn 2 as a follow-up `HumanMessage` on the same thread, then use `graph.aupdate_state(config, {...}, as_node="preprocessing_node")` to write a sentinel `intent` (outside `AgentIntent`) into the checkpoint before turn 3 — mirroring the exact per-turn reset dict `preprocessing_node` itself produces — so `route_by_intent` falls through to `llm_node` with `ALL_TOOLS` bound, exactly as the fallback branch in `_get_tools_for_intent` is documented to behave for an unrecognized intent. From there the adapter resumes the graph, observes the resulting HITL interrupt for `forget_memory`, reads the store immediately before sending the fixed approval, and reads it again afterward. A direct call to the production `_tool_forget_memory` handler (not through the model) supplies the near-boundary no-match probe, and independent store reads against a second user's namespace supply the no-bleed probe.

Session: three user turns in one thread — state the fact, recall it, forget it — with `Yes, forget it.` sent only after the turn-3 interrupt is actually observed.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`. No production database credential is permitted. `COHERE_API_KEY` is deliberately empty (store-backend pin).

Recorded evidence: per-turn classification and messages; the stored memory value after turn 1; turn 2's `user_memories` and final message; the turn-3 interrupt payload, approval, and pre-/post-approval store reads; `forget_memory`'s tool result; the near-boundary probe result; the second-user namespace read; termination reason; and elapsed time.

Reconstruction differences: the HTTP/SSE, Redis buffering, and canonical chat-message projection layers are intentionally excluded. The graph, tool implementations, HITL behavior, and memory-store service remain production code; only the turn-3 tool-binding decision is harness-injected via a documented LangGraph state API, because production chat never emits the intent value that decision depends on.
