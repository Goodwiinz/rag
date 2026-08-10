Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, checkpointer, store, and `Command(resume=...)` semantics used by production.

Source: repository revision `03091c6534971d83a35bf941af3077a2e35a987b` (`develop` HEAD; re-pinned after the sentinel-intent routing workaround was removed — `forget_memory` now binds live on `AgentIntent.GENERAL`, commit `fe76f434`).

Preserved behavior: production classifier, `memory_save_node`/`memory_retrieval_node`, the destructive-tool HITL interrupt, per-turn tool deduplication, compaction, reflection, model selection, retries, and stopping. All three turns — including turn 3 — go through the same live classifier; the adapter no longer substitutes a harness API for any tool-binding decision.

Adapter: compile one graph per trial, build the production-shaped initial state, send turn 1 as a `HumanMessage`, poll the memory store for the deterministic key `memory_save_node` computes until the fire-and-forget write lands, and send turn 2 as a follow-up `HumanMessage` on the same thread. Turn 2 must not call a tool: otherwise turn 3 would carry prior-tool context and lose the deterministic short-query classifier path. The adapter then sends the five-word, zero-keyword turn 3 (`Forget my saved contact email.`), which production classifies as `general` before consulting the prior arXiv reply — the intent `forget_memory` is registered against (`intents=frozenset({AgentIntent.GENERAL})`, develop `03091c65`). The verifier consumes the raw `turn3` `preprocessing_node` stream update and requires its intent to match the final checkpoint, rejecting `graph.aupdate_state(..., as_node="preprocessing_node")` injection. From there the adapter observes the resulting HITL interrupt for `forget_memory`, reads the store immediately before sending the fixed approval, and reads it again afterward. A direct call to the production `_tool_forget_memory` handler (not through the model) supplies the near-boundary no-match probe, and independent store reads against a second user's namespace supply the no-bleed probe.

Session: three user turns in one thread — state the fact, recall it, forget it — with `Yes, forget it.` sent only after the turn-3 interrupt is actually observed.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`. No production database credential is permitted. `COHERE_API_KEY` is deliberately empty (store-backend pin).

Recorded evidence: per-turn classification and messages; the stored memory value after turn 1; turn 2's `user_memories` and final message; the turn-3 interrupt payload, approval, and pre-/post-approval store reads; `forget_memory`'s tool result; the near-boundary probe result; the second-user namespace read; termination reason; and elapsed time.

Reconstruction differences: the HTTP/SSE, Redis buffering, and canonical chat-message projection layers are intentionally excluded. The graph, tool implementations, HITL behavior, classifier, and memory-store service all remain production code, including turn 3's tool-binding decision — no harness injection remains in this task.
