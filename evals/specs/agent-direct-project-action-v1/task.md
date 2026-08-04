Status: approved

Capability: recognize and safely execute a direct project-creation request instead of weakly routing it to an unrelated specialized flow or merely describing how to do it.

Request: `Create a project named The Discovery Note.`

Initial conditions: the synthetic user owns one workspace and has no project with that name. The adapter sends `Yes, create it.` only after an authentic HITL confirmation request is observed.

Why this requires the capability: success requires the production graph to expose and call the state-changing project tool, preserve the exact requested name, pause before mutation, and resume the same run after approval. A prose-only answer cannot change the independent database state.

Pass iff: no project mutation occurs before approval; afterward exactly one active project named `The Discovery Note` exists in the user's workspace; exactly one successful `create_project` execution produced that record; no unrelated project, document, or note was created; and the run terminates with a user-visible acknowledgement rather than another pending tool call.

Verifier: deterministic trajectory and database-state checks. No LLM judge is needed for the primary reward.

Verifier evidence: ordered interrupt/resume and tool events recorded by the adapter; raw initial/final rows for the synthetic workspace and projects; tool result identifier; final assistant message; and termination reason.

Accepted alternatives: any internal intent or plan that safely produces the required single project is accepted. Final wording may vary. Surrounding whitespace may be normalized, but the material project name and ownership must match.
