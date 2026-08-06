Status: approved

Capability: make a user Stop terminal and durable for the exact accepted run, without later completing that run or losing the partial response.

Request: `Research three approaches to evaluating a production RAG system. Compare retrieval quality, answer faithfulness, latency, and cost, then recommend an approach.`

Initial conditions: one empty synthetic thread and no active run. The adapter starts the request normally and closes the SSE connection immediately after recording the first non-empty assistant token, reproducing the browser Stop boundary.

Why this requires the capability: the graph has begun producing a response, so successful handling requires coordinated cancellation across the iterator, stream buffer, transcript projection, AgentRun row, and terminal ledger. Returning early in the client alone cannot establish durable cancellation.

Pass iff: the accepted run reaches `cancelled` within 10 seconds of disconnect; it has exactly one `run.cancelled` terminal event and no `run.completed` event; the Redis active pointer is cleared; the observed partial assistant text is persisted once with `stopped=true` and linked from that AgentRun; no new model/tool call starts after disconnect and an in-flight call cannot complete the run successfully; and resume either returns 204 or a finite replay with no later `done` completion for that run.

Verifier: deterministic checks over adapter timestamps and frames, PostgreSQL rows/events, Redis state, and the resume response. No LLM judge is used.

Verifier evidence: accepted run/thread/message identifiers; ordered SSE frames; disconnect timestamp; bounded post-disconnect activity log; raw AgentRun, AgentRunEvent, and ChatMessage fields; Redis active-stream lookup; and resume status/body. Missing dependency evidence or timeout is an infrastructure error, not reward 0.

Accepted alternatives: the exact amount of partial text and cancellation acknowledgement wording may vary. Equivalent internal cleanup ordering passes if all durable invariants hold and no post-Stop completion occurs.
