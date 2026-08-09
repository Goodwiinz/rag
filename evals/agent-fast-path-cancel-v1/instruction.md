Stream one fast-path-eligible turn (an ungrounded, non-agentic question with
`use_rag=false` and no grounded page context) through the real `/api/v1/agent/stream`
endpoint, disconnect the client immediately after the first non-empty assistant
token, and record: the SSE frames actually observed, the adapter's own
before/after instrumentation of the emit-then-append ordering for each model
chunk, every `run.cancelled` finalize attempt the production code path issues
(the fast path's own linked call and the outer route-agnostic handler's
unlinked duplicate), the persisted partial assistant row, and an independent
read of the durable run/event/message state after the client disconnects.
