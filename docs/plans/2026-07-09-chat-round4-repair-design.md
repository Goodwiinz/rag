# Chat Round 4 Repair Design

**Status:** Approved 2026-07-09  
**Scope:** R4-F1 through R4-F4 are one repair PR. R4-F5 is a separate dev-release gate.

## Goal

Make a completed /chat turn render the same provenance after reload as it did live,
prevent a confirmation failure from becoming a successful activity run, and ensure
every failed stream clears transient UI state.

## Context and constraints

- The backend is the canonical message writer; do not add client-side message
  persistence or a JSON blob representing the UI view model.
- Historic tool executions can contain raw arguments. Every browser-facing
  read serializer must apply serve-time redact_tool_executions.
- toolsUsed and sourcesCount are display derivatives. They must be reconstructed
  from canonical tool executions and citations, not persisted again.
- The merged AUI-only rendering path always creates a transient placeholder and
  can use functional setMessages updaters. Tests must apply updater functions
  and filter committed messages rather than inspect mock-call order.
- A browser smoke test is still the only proof that the retired AUI fallback
  works on dev.

## Options considered

1. Patch the workspace serializer, confirmation callback, and mapper locally.
   This is fast but preserves exactly the drift class that produced the findings.
2. Share read serialization policy and the stream lifecycle. Recommended.
   It removes the unsafe route divergence and ensures submit/resume/confirm
   use one terminal-state policy.
3. Rewrite the hook as a new state machine. This is larger than the verified
   surface and is unsafe before the AUI-only path has browser evidence.

## Chosen architecture

### Safe backend read contract

Create backend/src/api/threads/message_serialization.py with two functions:

- format_chat_message(message) returns ChatMessageResponse for both
  backend/src/api/threads/threads.py and backend/src/api/threads/workspaces.py.
- agent_provenance_fields(message) returns redacted tool_executions, plan, and
  token_usage for backend/src/api/agent/execute.py, whose MessageResponse is a
  different Pydantic model.

Both functions call redact_tool_executions. The common formatter owns citations,
attachments, stopped, plan, and token_usage. Route-local helpers become thin
delegates; routers must not import one another.

### Reload projection

In mapDbMessageToChatPageMessage, normalize citations and map tool executions
once, then derive metadata.toolsUsed from activity-step labels and
metadata.sourcesCount from the citation count. Keep responseTimeMs, stopped,
and tokenUsage. Omit metadata only when every field is absent.

### Shared stream lifecycle

Make runStreamTurn the only SSE callback/finalization owner for submit, resume,
and confirmation. Confirmation supplies seeded settled steps, plan, citations,
and a streamConfirm starter adapter.

Use the terminal outcomes below:

| Outcome | Activity run | Pending confirmation | Presentation |
|---|---|---|---|
| done | done | clear | fully reset |
| error, including a rejected promise | error | clear | fully reset |
| user stop | stopped | clear | fully reset |
| nested confirmation | running | replace | fully reset, gate retained |

A single resetStreamingPresentation helper must clear isStreaming,
streamingContent, streamingCitations, streamingSteps, and isRetrievingRag.

### R4-F5 dev release gate

After the repair is deployed to dev, exercise the AUI-only build in a browser:
normal tool turn, approve, deny, nested confirmation, and stream error cleanup.
Record the deployment SHA, test account/fixture, timestamp, and outcome in
the audit ledger and PR. No result means the retirement remains unverified.

## Regression strategy

- Backend test: v1 and v2 format the same assistant row with matching complete
  fields and redacted token/email arguments; agent list provenance uses the
  same policy.
- Mapper test: toolsUsed and sourcesCount appear after reload without any
  previously live metadata.
- Hook test: normal and confirm exceptions clear every streaming field, and a
  failed confirmation ends as error. Existing success, stop, and nested flows
  remain green.
- Browser test: assert the actual streaming-to-committed transition and in-band
  approval behavior, which jsdom cannot prove.

