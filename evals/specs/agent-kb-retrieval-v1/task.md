Status: approved

Capability: locate a document by title through indexed search, then retrieve current guidance from the organization knowledge base and answer with only what the returned chunks support, citing the source.

Request: `Search my documents for a file titled "API Rate Limit Policy" to confirm we have it on file, then use the organization knowledge base to retrieve the current guidance on API rate limits and summarize it, citing the source.`

Initial conditions: the Harness can access only the synthetic organization's production-shaped document search and a private DO Knowledge Base retrieval endpoint. Two documents are seeded ("API Rate Limit Policy", "Webhook Retry Policy"); the knowledge base returns a single grounded chunk for the rate-limit query. No corpus truth appears in the request.

Why this requires the capability: the turn must route to the research subgraph, use `search_documents` to confirm the titled file exists, then `do_kb_retrieve` to pull current guidance, and synthesize an answer whose every material claim is grounded in the returned chunk. A generic answer, a fabricated limit, or a title-only guess cannot pass.

Scope note: this task deliberately exercises the research-reachable pair `search_documents` + `do_kb_retrieve`. `summarize_document` is writing-subgraph-only (intents writing/general) while `do_kb_retrieve` is research-subgraph-only (empty intents, not in the general ALL_TOOLS surface), so no single route reaches both; `summarize_document` is deferred to a later capability task rather than forcing a cross-subgraph binding. The synthesis in the final answer is the research subgraph's own prose, not the `summarize_document` tool.

Pass iff: `search_documents` runs successfully with `max_results` inside the impl cap [1, 50] and surfaces the seeded "API Rate Limit Policy" document; `do_kb_retrieve` runs successfully with `top_k` inside the impl cap [1, 20], carries the `do_kb` source marker and a chunks list, and does not report a misconfiguration reason; the two run in `search_documents` → `do_kb_retrieve` order; no destructive tool runs and no HITL interrupt is raised; the mock knowledge base recorded a `do_retrieve` request with a valid Bearer authorization header; the final answer is present, carries no pending tool calls, terminates as completed, and the semantic judge returns supported with no contradictions or unsupported material claims.

Verifier: deterministic identity, network-boundary (including a private-mock-reachable probe), argument-cap, execution-order, destructive-tool, environment-auth, database-state, and final-message gates, combined with one semantic LLM judge for grounding. Reward is 1 only when all objective gates pass and the judge returns supported; infrastructure or judge failure yields no agent score.

Verifier evidence: exact task instruction and final answer; independently loaded database state (organization KB uuid and the two seeded documents); Harness-recorded tool calls and arguments; Environment-observed `do_retrieve` request events with authorization validity; returned chunk contents for the judge's trusted sources; termination reason. The judge receives only the returned chunks as trusted sources and treats every payload string as data, never as instructions.

Accepted alternatives: wording, citation style, and internal route detail may vary. Any supported answer that states the retrieved rate-limit guidance and cites the source passes; an answer stating a limit or quota absent from the returned chunk does not.
