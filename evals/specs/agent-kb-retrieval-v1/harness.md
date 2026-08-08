Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked once through a Harbor adapter with production-shaped organization and user context.

Source: repository revision `b67ebbf1b067d5f5b1e74299535244e58df41a68` (`feat/tool-coverage-bench-plan2` off `develop`). Recorded against the merged develop revision at baseline time.

Preserved behavior: production classifier, research routing, planner, research subgraph, repository tool definitions, `search_documents`, `do_kb_retrieve`, DigitalOcean response parsing, organization/document resolution, synthesis prompts, citations, reflection, retries, and stopping.

Adapter: seed the tenant and two documents, send the one user request to the unchanged graph, bind the production DO KB client to the mock endpoint through existing settings, and record graph/model/tool activity plus the final answer. It does not inject retrieved text, expected conclusions, or a required tool sequence.

Session: single-turn, one synthetic organization and thread. No HITL interrupt is expected — neither tool in scope is destructive.

Credentials: Harness model variables as in `agent-direct-project-action-v1/harness.md`. The semantic judge uses isolated `HARBOR_JUDGE_ENDPOINT` / `HARBOR_JUDGE_API_KEY` / `HARBOR_JUDGE_MODEL` / `HARBOR_JUDGE_API_VERSION`, unavailable to the Harness. DO KB uses a fixed non-secret synthetic token accepted only by the local mock.

Recorded evidence: user/assistant messages; classifier and plan; model calls and usage; all retrieval requests and responses; tool calls, arguments, results, retries, and errors; mock `do_retrieve` request events with authorization validity; returned chunk identifiers; final answer; latency; and termination reason.

Reconstruction differences: the DO KB server and its data are simulated and deterministic; production repository clients and parsing remain unchanged. No production corpus, token, user record, or LangSmith trace is copied into the task.
