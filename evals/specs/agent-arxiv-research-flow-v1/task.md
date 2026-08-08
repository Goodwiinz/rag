Status: approved

Capability: search arXiv through the production research flow, reuse a shared Redis result cache instead of re-querying, and safely ingest selected papers into a project — pausing for human approval before any document row or storage object is created.

Request: `Search arXiv for deterministic benchmark retrieval evaluation.`

Initial conditions: the synthetic user owns one workspace and one empty project; no document exists for the organization; the shared Redis result cache is empty; the arXiv API and PDF host are both a deterministic protocol double serving a two-paper fixture corpus. After the initial search completes, the harness sends the byte-identical search again on the same thread, then asks the agent to ingest both returned papers into the seeded project — approving the ingest only after an authentic HITL confirmation request is observed.

Why this requires the capability: success requires the production graph to route a research-intent turn to `search_arxiv`, cap results to the implementation's limit, serve a repeated identical query from the shared Redis cache rather than issuing a second upstream query, then expose and safely call the state-changing `ingest_arxiv_papers` tool — pausing before any mutation, resuming only after approval, persisting checksum-verified objects, and reporting document identifiers distinct from the arXiv paper IDs it was given.

Pass iff: the first search returns at most 5 papers drawn only from the fixture corpus; the second identical search is served from cache with no second query reaching the double; no document or project-link row exists before the ingest approval; afterward exactly the two requested papers exist as `COMPLETED` documents with a `search_vector`, each backed by a local storage object whose bytes match its recorded checksum, each linked to the seeded project, and each with a document UUID that is not the arXiv paper ID; the Redis result-cache key is present with a bounded TTL; and the run terminates with a user-visible acknowledgement naming the ingested result rather than a pending tool call.

Verifier: deterministic trajectory, database-state, Redis-state, and mock-event checks. No LLM judge is needed or configured — semantic scoring is N/A for this task.

Verifier evidence: ordered interrupt/resume and tool-execution events recorded by the adapter; raw initial/pre-approval/final rows for the synthetic organization and project; the mock double's request-event log; the Redis cache entries under `arxiv:search:*`; the local storage listing; final assistant message; and termination reason.

Accepted alternatives: any internal intent, plan, or tool-call ordering that safely produces the two required documents and the cache hit is accepted. Final wording may vary. Surrounding whitespace may be normalized, but the material paper identities, project attachment, and document count must match.
