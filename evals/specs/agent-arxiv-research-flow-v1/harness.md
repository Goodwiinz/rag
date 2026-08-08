Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by a Harbor adapter with the same `AgentState`, configurable identifiers, checkpointer, and `Command(resume=...)` semantics used by production.

Source: repository revision `2c5e7a824cf29c3a15f52c3c1e94e3d6e2b4b9a1` (`feat/tool-coverage-bench-plan4`, cut off `develop`).

Preserved behavior: production classifier and intent routing into the research subgraph; the research subgraph's direct-arXiv-search fast path, planner, and HITL interrupt; production tool registry and `search_arxiv`/`ingest_arxiv_papers` implementations, including the impl-level result cap, the two-layer (in-process + Redis) search cache, the shared arXiv rate gate, and the `store_arxiv_pdf` object-storage layer; per-turn tool deduplication; compaction; reflection; model selection, retries, and stopping.

Adapter: create one compiled graph per trial; patch `ArXivIngestionService.ARXIV_API_BASE`/`ARXIV_PDF_BASE` to the mock double's internal host before compiling; build the production-shaped initial state for each of three turns on one thread — search, a byte-identical repeat search, then the ingest request — approving any HITL interrupt only after it is observed, in the same graph session. The adapter translates the final state into Harbor output but does not alter prompts, routes, tool arguments, or results.

Session: three user turns in one thread: the initial search (the instruction under test), a harness-scripted byte-identical repeat search that proves the Redis cache path, and a harness-scripted ingest request naming the two fixture paper IDs and the seeded project. Only the first turn's text is checked against `HARBOR_INSTRUCTION`; the two follow-up turns are fixed adapter constants, not client-supplied input, the same way a prior task's HITL approval text is a fixed constant rather than part of the instruction contract.

Credentials: `AZURE_OPENAI_CHAT_ENDPOINT`, `AZURE_OPENAI_CHAT_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_CHAT_API_VERSION`, `AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT`, and `AZURE_OPENAI_SYNTHESIS_DEPLOYMENT`. No production database, Redis, or arXiv credential is permitted or required — the mock double and benchmark Redis instance need none.

Recorded evidence: user and assistant messages; classifier intent, confidence, and source; plan; model calls and usage; tool calls, arguments, results, retries, and errors for both `search_arxiv` calls and the `ingest_arxiv_papers` call; interrupt and resume; the arXiv client base-URL patch actually applied; the mock double's full `GET /events` request log; the Redis `arxiv:search:*` key dump (TTL and value envelope); the local storage listing (path, byte count, sha256); termination reason; elapsed time; and the Environment's initial/pre-approval/final database state.

Reconstruction differences: the HTTP/SSE, Redis chat-stream buffering, and canonical chat-message projection layers are intentionally excluded — this task's own Redis usage is the production arXiv cache, not the chat-stream layer. The graph, tool implementations, HITL behavior, and the `store_arxiv_pdf` persistence layer called by the tool remain production code; backing state (database, Redis, arXiv upstream) is isolated and synthetic.
