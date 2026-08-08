Status: approved

Capability: carry a multi-step project-management request through the production graph — create a project, attach an existing document to it, add a note to it, and read the project's contents back — pausing for human approval before every state-changing step instead of batching the mutations or narrating them.

Request: `Create a research project named "Tool Coverage Study", then add the pre-loaded document titled "Seed Paper" to it, create a note in it titled "Kickoff" with content "Track tool coverage benchmark progress.", and finally list the project's documents and confirm what the project now contains.`

Initial conditions: the synthetic user owns one workspace with no projects and one indexed document titled `Seed Paper` (`00000000-0000-4000-8000-000000000505`) that belongs to no project. The adapter approves each confirmation request only after an authentic HITL interrupt is observed, and never preloads a later approval.

Why this requires the capability: success requires the production graph to select four distinct project tools in a dependent order, thread the identifier returned by `create_project` into the two later mutations and the final read, and interrupt three separate times without collapsing the plan into a single write or a prose description. A model that invents identifiers, reorders the steps, or answers without calling tools cannot produce the required database rows.

Pass iff: exactly one collection row named `Tool Coverage Study` exists, owned by the seeded workspace; exactly one `collection_documents` link exists, pointing at document `00000000-0000-4000-8000-000000000505`; exactly one `project_notes` row exists, titled `Kickoff` with content `Track tool coverage benchmark progress.`; three HITL interrupts are approved in order with no corresponding mutation recorded before its approval; `list_project_documents` executed successfully and returned the linked document; the final assistant message names both the project and the document; and the run reports termination reason `completed`.

Verifier: deterministic trajectory and database-state checks. No LLM judge is needed for the primary reward.

Verifier evidence: the ordered interrupt, approval, and tool-success milestones recorded by the adapter; recorded tool arguments for each mutation; the `list_project_documents` result payload; raw final rows from `collections`, `collection_documents`, `project_notes`, and `documents` for the synthetic workspace; the final assistant message; and the termination reason.

Accepted alternatives: any internal intent or plan that safely produces the required rows is accepted, including resolving the new project's identifier through `list_projects` rather than reusing the `create_project` result. Final wording may vary and extra read-only tool calls are permitted. Surrounding whitespace may be normalized, but the project name, document link, and note title and content must match exactly.
