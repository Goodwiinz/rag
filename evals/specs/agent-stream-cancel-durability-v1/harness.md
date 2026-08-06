Status: approved

Entrypoint: the production FastAPI application and `POST /api/v1/agent/stream`, followed by `GET /api/v1/agent/stream/resume/{thread_id}` through a Harbor HTTP/SSE adapter.

Source: repository revision `6e618d0fb5874fa262b783345000f1496e52d7c7` (`develop`; agent code delivered by `756367d7b015c7e2b2d2b6d69092feb9e3dd0c40`).

Preserved behavior: request validation and authentication; submission acceptance and idempotency; graph input assembly; production graph and model loop; sequence-numbered SSE emitter; Redis stream buffer; disconnect detection; graph iterator cancellation; partial assistant persistence; AgentRun finalization; append-only run events; trace metadata; and resume lookup.

Adapter: start the real app, authenticate as the synthetic user, post one request with fixed `client_message_id`, parse and record SSE frames in order, and close the response immediately after the first non-empty assistant token. After bounded terminalization, query the resume endpoint and collect independent database/Redis evidence. The adapter does not send a second agent message or alter server cancellation handling.

Session: one HTTP stream and one follow-up resume read for the same accepted run and thread. The disconnect is a scripted user Stop action, not a Harness prompt.

Credentials: Harness model variables listed in `agent-direct-project-action-v1/harness.md`, plus a task-local signing secret used only for the synthetic user's authentication. No production database, Redis, Supabase, LangSmith, or browser credential is permitted.

Recorded evidence: request identifiers; status and headers; every SSE frame with sequence, event, trace ID, route, and timestamp; accepted run/thread/message identifiers; disconnect timing; model/tool events observed before Stop; termination reason; AgentRun and run-event rows; assistant message projection; Redis active pointer/buffer metadata; resume response; and resolved non-secret configuration.

Reconstruction differences: runs on one local app process without ingress, browser Fetch, proxy buffering, HPA, or multi-pod races. The complete production API, streaming, graph, persistence, event-store, and Redis code paths remain unchanged.
