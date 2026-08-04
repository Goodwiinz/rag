Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked once through a Harbor adapter with production-shaped organization and user context.

Source: repository revision `6e618d0fb5874fa262b783345000f1496e52d7c7` (`develop`; agent code delivered by `756367d7b015c7e2b2d2b6d69092feb9e3dd0c40`).

Preserved behavior: production classifier, research routing, planner, research subgraph, repository tool definitions, `do_kb_retrieve`, DigitalOcean response parsing, organization/document resolution, sensitive-value redaction, normalized content deduplication, Cohere rerank wrapper, synthesis prompts, citations, reflection, retries, and stopping.

Adapter: send one user request to the unchanged graph, bind production clients to Environment endpoints through existing settings, and record graph/model/tool activity plus the final answer. It does not inject retrieved text, expected conclusions, or a required tool sequence.

Session: single-turn, one synthetic organization and thread.

Credentials: Harness model variables listed in `agent-direct-project-action-v1/harness.md`. The semantic judge uses isolated `HARBOR_JUDGE_API_KEY` and `HARBOR_JUDGE_MODEL`, which are unavailable to the Harness. DigitalOcean and Cohere use fixed non-secret synthetic tokens accepted only by local services.

Recorded evidence: user/assistant messages; classifier and plan; model calls and usage; all retrieval/rerank requests and responses; tool calls, results, retries, and errors; postprocess counters; returned chunk identifiers and score provenance; citations; final answer; latency; and termination reason.

Reconstruction differences: DO KB and Cohere servers and their data are simulated and deterministic; production repository clients and parsing remain unchanged. No production corpus, token, user record, or LangSmith trace is copied into the task.
