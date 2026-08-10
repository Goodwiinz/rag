Status: approved

Capability: apply an approved project skill from the exact durable version frozen at turn start, preserve that snapshot across HITL resume, and safely create the requested project artifact without drifting to a newly activated version.

Request: `Use the active evidence-note project skill and the document in this project to create a source-grounded project note about sparse transformer attention.`

Initial conditions: version 1 of `evidence-note` is active when the turn snapshot is created; version 2 activates immediately afterward. The open project contains one source document and no note. The adapter approves only an authentic `create_project_note` confirmation.

Why this requires the capability: the skill body is not in the request or prompt catalog and is available only through the conditional loader. Following the currently active version instead of the frozen snapshot, loading another project/version, or writing before approval all violate the runtime contract.

Pass iff: the durable turn snapshot contains only version 1 metadata and exposes the conditional loader; the Harness loads `evidence-note` through that snapshot and receives version 1 with its independently recomputed content hash; version 2 is active in the catalog before the note write but never appears in the turn's loaded versions; the runtime snapshot ID and project binding are unchanged across HITL pause/resume; no note exists before approval; afterward exactly one note exists in the seeded project; its content is source-grounded and materially follows version 1 rather than version 2; no other write or cross-project access occurs; and the run terminates with a final assistant response and no pending tool call.

Verifier: deterministic authorization, snapshot, version/hash, HITL, database-state, note-format, and seeded-fact gates.

Verifier evidence: raw skill/version/activation rows; durable runtime snapshot before invocation and after resume; independently hashed version bodies; Harness tool bindings and load result; interrupt/approval events; initial/final note rows; source document; final response; and termination reason.

Prohibited effects: exposing skill bodies in the catalog prompt, loading version 2 or another project's skill, changing snapshot identity on resume, pre-approval mutation, extra notes, and production access.

Agent-visible information: request, project page context, compact version-1 catalog metadata frozen in state, version-1 instructions returned by the loader, source document/tool results, and the approval message. Version 2 contents, raw database rows, and Verifier criteria are hidden.

Accepted alternatives: note title and prose may vary when consistent with version-1 instructions. The Harness may load the skill once or reuse the same frozen result; no exact internal wording or reasoning path is required.
