Status: approved

Dependencies:

- Azure/OpenAI deployments: live model inference; bounded calls and token cost.
- PostgreSQL: simulated isolated service initialized from production metadata.
- Document summarization model call: the same live deployment used by production tool code.
- Judge model: live and isolated from the Harness.
- RAG, memory, Neo4j, Redis, external connectors, arXiv, object storage, LangSmith, and production services: disabled or blocked.

Backend contracts: `summarize_document(document_id)` resolves only tenant-owned document identifiers. Passing the seeded project UUID returns the production-declared `recoverable` error and `list_project_documents` suggestion. Passing the seeded document UUID returns a grounded summary. Passing the missing UUID returns the production not-found error. `list_project_documents(project_id)` returns the one seeded document.

Data:

- Synthetic project UUID `00000000-0000-4000-8000-000000001001` with one tenant-owned document UUID `00000000-0000-4000-8000-000000001002`.
- Missing document UUID `00000000-0000-4000-8000-0000000010ff`, absent from every tenant.
- The real document contains a short source passage with several concrete findings and one explicit limitation so unsupported summaries are detectable.
- No projects or documents outside the declared fixture are visible to the Harness.
- Reset recreates schema and seed before every trial, including after timeout or Verifier failure.

Isolation: one database, user, organization, workspace, and thread per trial; deterministic UUIDs; no writes expected; outbound network allowlisted only to Harness and judge model endpoints.

Fidelity limits: this task exercises returned-payload error recovery, not raised network exceptions or real document extraction from object storage. Unit tests remain responsible for exception taxonomy and backoff timing.
