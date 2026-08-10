Status: approved

Dependencies:

- Azure/OpenAI deployment: live Harness inference through the shared allowlisting proxy.
- DigitalOcean Knowledge Base: simulated local protocol double reached through the production client; request log is Verifier-readable but unavailable to the Harness.
- PostgreSQL: simulated isolated tenant/project metadata needed to resolve the KB and project scope.
- Iteration ledger: isolated writable filesystem directory, empty at trial start.
- Memory, Neo4j, Redis, arXiv, external connectors, object storage, LangSmith, and production services: disabled or blocked.

Backend contracts: `do_kb_retrieve(query, top_k)` retains production argument caps, project authorization, post-processing, and result schema. The double maps six sequential query tokens (`NOUS-LONG-1` through `NOUS-LONG-6`) to deterministic chunks; each response reveals only the next token. The sixth response marks `END`.

Data:

- One tenant/project with a provisioned synthetic KB identifier.
- For stages 1-5, two unique source chunks of approximately 7,000 characters each, containing a stage-specific verified finding, stable document identifiers, and exactly one `Next query` token.
- Stage 6 contains the final finding and `END`, but cannot be known before a successful stage-6 retrieval.
- Chunk volume crosses the production compaction threshold before the research loop ceiling.
- Reset clears database rows, mock events, and ledger files before every trial.

Isolation: one database, mock service, graph thread, and ledger directory per trial; deterministic IDs; real monotonic time; outbound network allowlisted only to model endpoints and the internal KB double.

Fidelity limits: synthetic chunks are larger and more regular than ordinary KB results to deterministically reach the production control limits. The production post-processing and graph receive their real shapes; throughput and distributed filesystem behavior are not measured.
