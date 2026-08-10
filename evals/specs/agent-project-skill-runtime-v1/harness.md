Status: approved

Entrypoint: production `create_runtime_snapshot` plus `src.services.agent.graph.compile_agent_graph`, invoked by the existing NOUS Harbor agent and a task-owned adapter.

Source: repository revision `27018e69c0c9e0339aab5db5f76d34e1715a316c`; final repository, image, task, and Harness digests are recorded.

Preserved behavior: project authorization; approved-skill catalog resolution; durable runtime snapshot creation; prompt catalog rendering; conditional `load_project_skill` binding; exact frozen-version loading and hash checks; loaded-version audit; project-note tool behavior; HITL pause/resume using the same checkpoint and runtime snapshot; model loop, reflection, and stopping.

Adapter: create the runtime snapshot through production code, activate a newer approved skill version after the snapshot is durable, then invoke the production graph with `runtime_state_fields`/`runtime_config_fields`. On an authentic `create_project_note` interrupt, record state and resume the same session with approval. It does not place skill instructions in the prompt or choose the tool call.

Session: one project-scoped turn with one fixed approval after an authentic HITL request. The same thread, checkpoint, and runtime snapshot ID must survive resume.

Credentials: Harness model variables. No production database or skill-catalog credential is permitted.

Recorded evidence: initial/final active skill rows; durable snapshot row and catalog; prompt-safe catalog metadata; tool bindings; `load_project_skill` call/result; loaded version/hash; interrupt/resume; runtime snapshot IDs before and after resume; note database state; final response; timing; usage; and errors.

Reconstruction differences: PostgreSQL and project/document/skill records are isolated synthetic state. Production catalog, snapshot, loader, graph, project-note tool, and HITL logic are unchanged; API/frontend authoring and distributed workers are excluded.
