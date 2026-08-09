Status: approved

Entrypoint: `src.services.agent.graph.compile_agent_graph`, invoked by the existing NOUS Harbor agent and a task-owned adapter.

Source: repository revision `27018e69c0c9e0339aab5db5f76d34e1715a316c`; final source and image digests are recorded with the run.

Preserved behavior: production research classification/subgraph, planner, `do_kb_retrieve`, tool-loop accounting, compactor threshold and identifier preservation, research loop ceiling, forced synthesis, reflection gate, iteration ledger write, model selection, retries, and stopping.

Adapter: create one graph thread with a writable isolated iteration-ledger directory, send the approved instruction, and record updates until completion. It does not set loop counters, fabricate prior messages, force a route, or invoke compaction/reflection directly.

Session: one single-turn session. Each next KB query becomes visible only in the preceding tool result, preventing parallel preloading of the chain.

Credentials: Harness model variables. A fixed synthetic DO KB token is accepted only by the local double.

Recorded evidence: user/assistant messages; query-by-query tool calls and results; mock-service events; tool and error counters; compaction replacements/count; forced-synthesis marker; reflection result and route; iteration-ledger JSON; final response; timing; usage; and termination reason.

Reconstruction differences: the DigitalOcean KB service and corpus are simulated, while the production client, retrieval tool, graph, compactor, forced-synthesis node, reflection, and ledger code are preserved. HTTP/SSE rendering and production storage are excluded.
