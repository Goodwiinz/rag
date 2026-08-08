Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked once through a Harbor adapter with production-shaped organization and user context.

Source: repository revision `18f2cf2b28557e3572bc8b286e1838c1b1252d39` (`feat/tool-coverage-bench-plan3` off `feat/tool-coverage-bench-plan2`). Recorded against the merged develop revision at baseline time.

Preserved behavior: production classifier, `knowledge_graph` intent routing, the DATA subgraph, repository tool definitions, `search_knowledge_graph`, `explore_entity_neighborhood`, `find_entity_paths`, `get_graph_stats`, the `knowledge_graph_service` singleton driver and circuit breaker, tenant-scoping predicates (`_entity_scope_predicate`, `_two_endpoint_scope`), the DATA-subgraph deterministic reflection guards (the expensive LLM critique is intentionally skipped for `knowledge_graph` turns), synthesis prompts, and stopping.

Adapter: seed the tenant and the fixed ~20-entity graph through the SAME `knowledge_graph_service` singleton instance the tools import, self-check that the seed is queryable through that singleton before the graph runs (the neo4j-singleton-trap guard), send the one user request to the unchanged graph, and record graph/model/tool activity, an independent post-run Cypher count, and the final answer. It does not inject retrieved graph data, expected conclusions, or a required tool sequence.

Session: single-turn, one synthetic organization and thread. No HITL interrupt is expected -- none of the five knowledge-graph tools carry the destructive policy tag.

Credentials: Harness model variables as in `agent-direct-project-action-v1/harness.md`. The semantic judge uses isolated `HARBOR_JUDGE_ENDPOINT` / `HARBOR_JUDGE_API_KEY` / `HARBOR_JUDGE_MODEL` / `HARBOR_JUDGE_API_VERSION`, unavailable to the Harness. Neo4j uses a fixed non-secret synthetic password accepted only by the local container.

Recorded evidence: user/assistant messages; classifier intent and confidence; model calls and usage; tool calls, arguments, results, retries, and errors; the DATA-subgraph tool-loop count; an independent Cypher entity/relationship count run directly against the Neo4j container, bypassing `knowledge_graph_service`; final answer; latency; and termination reason.

Reconstruction differences: Neo4j is a real, disposable per-trial container rather than production's persistent multi-tenant instance, but the driver, circuit breaker, and Cypher the repository issues against it are unchanged. No production graph, token, user record, or LangSmith trace is copied into the task.
