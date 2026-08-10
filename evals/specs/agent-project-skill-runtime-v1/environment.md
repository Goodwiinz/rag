Status: approved

Dependencies:

- Azure/OpenAI deployments: live Harness inference through the shared allowlisting proxy.
- PostgreSQL: simulated isolated service created from production metadata, holding project, document, project-skill, version, approval, activation, snapshot, and note rows.
- LangGraph checkpointer: repository PostgreSQL checkpointer against the isolated database.
- RAG, memory, Neo4j, Redis, external services, object storage, LangSmith, and production credentials: disabled or blocked.

Backend contracts: production project-skill authorization and approval services expose only active, latest-scan-passed versions. `create_runtime_snapshot` persists the eligible catalog and tool metadata. `load_project_skill` accepts only the model-controlled skill name; snapshot, user, and project IDs come from server config. `create_project_note` mutates only after HITL approval.

Data:

- One synthetic tenant/user/workspace/project and one seeded document about sparse transformer attention, including a measured benefit and an explicit limitation.
- Skill `evidence-note` version 1 is approved and active when the turn snapshot is created. Its instructions require a source-grounded note organized as Finding, Evidence, and Uncertainty.
- Version 2 is also approved but becomes active immediately after the durable turn snapshot and before the first model call. It requests a materially different Executive Brief format, making mid-turn drift observable without answer-coded content.
- The project has no note initially. Reset restores version 1 as active and removes snapshots, load records, and notes before every trial.

Isolation: one database and graph thread per trial; deterministic IDs and skill contents/hashes; real monotonic time; outbound network allowlisted only to model endpoints; judge credentials and raw database access unavailable to the Harness.

Fidelity limits: the activation race is scheduled deterministically rather than concurrently across pods. It validates frozen-version behavior, authorization, and HITL resume, not catalog UI, scanner throughput, or distributed transaction timing.
