# Agent Citations and Workspace Threads Design

**Date:** 2026-09-12
**Issue:** #1622
**Status:** approved for implementation planning

## Goal

Make agent answers carry the provenance returned by knowledge-base tool calls,
and make the chat sidebar show every accessible thread in the active workspace
regardless of which historical conversation contains it.

The repair must preserve existing conversation-scoped APIs and historical data.
It must not merge or delete the hundreds of conversation rows already present in
the live workspace.

## Confirmed root causes

The agent graph has two retrieval channels with different behavior. The RAG node
writes normalized chunks to `state["retrieved_contexts"]`; synthesis numbers that
context as `[Doc N]`, streaming emits it, and assistant-message persistence turns
it into `Citation` rows. The `do_kb_retrieve` tool instead leaves the same source
data only inside `state["tool_executions"][].result.chunks`. Consequently the
model receives contradictory no-retrieval guidance after a successful tool call,
the live stream emits no citation context, and the committed message has no
citations.

The sidebar is scoped to one conversation. `useChatSession` resolves or restores a
single `default-conversation-id`, calls the conversation-level thread endpoint,
and replaces the sidebar with only that response. The backend agent fallback also
creates a new `Conversation` whenever an explicit thread lookup misses. These two
behaviors produced hundreds of one-thread conversations while the sidebar showed
at most one container's threads.

## Chosen architecture

### Canonical retrieval provenance

Add one pure normalization boundary in the agent service that recognizes a
successful `do_kb_retrieve` execution and converts each safe chunk to the existing
retrieved-context envelope:

- `document_id` from the canonical UUID resolved by the tool;
- `title` from the tool's redacted title;
- `content` from the chunk's `text`;
- `score` and `score_source` from the retrieval result;
- an internal origin marker identifying tool-derived context when prompt shaping
  needs to avoid duplicating the complete tool payload.

The tool node merges these contexts with any contexts already produced during the
turn. It preserves first-retrieved order, deduplicates repeated chunks using the
canonical document identity plus normalized content, and applies an explicit
turn-level cap. Empty, failed, malformed, non-finite, or unresolved chunks are
ignored rather than converted into plausible-looking citations. Title-only
`search_documents` results are not evidence and are not promoted.

`state["retrieved_contexts"]` remains the single downstream contract. Post-tool
synthesis receives stable `[Doc N]` numbering and no longer receives the false
"No documents were retrieved" instruction. The streaming adapter emits newly
promoted contexts through the existing RAG-context event. The existing assistant
message persistence path creates citation rows in the same transaction as the
message and preserves citation data across reloads.

Prompt rendering must not duplicate full multi-kilobyte chunks already present in
tool messages. Tool-derived contexts therefore render as a compact numbered source
map while the corresponding tool message remains the content-bearing evidence.
RAG-node contexts keep the existing full fenced-document rendering. Both origins
share one numbering order and one persisted citation list.

### Workspace-wide thread listing

Add a read-only, paginated endpoint:

`GET /api/v2/workspaces/{workspace_id}/threads`

The endpoint returns the existing `ThreadListResponse`. Each `ThreadResponse`
already carries its actual `conversation_id`, so the response needs no new thread
view model. The query:

- resolves workspace access through the canonical membership-aware access funnel;
- joins threads through non-deleted conversations in the requested workspace;
- excludes deleted threads, conversations, and workspaces;
- applies any supported status filter identically to the count and row queries;
- orders the complete workspace result by recent thread activity with a stable ID
  tie-breaker;
- paginates globally across conversations; and
- uses the existing bounded latest-message preview expression.

Existing nested and standalone conversation-level thread endpoints remain
unchanged for compatibility.

The frontend adds a generated-contract-backed workspace-thread service method.
`useChatSession` uses this method for cold initialization, warm restoration, and
pagination. It maps every row with that row's `conversation_id`; the default
conversation remains only the parent used when a user creates a new thread. A
successful new-thread creation is inserted into the workspace-wide list without
waiting for a full reload, and a later refresh reconciles server order.

Persisted conversation IDs may still accelerate choosing a parent for a new
thread, but they no longer scope or replace the sidebar. A stale persisted ID must
not hide valid workspace threads.

### Thread resolution and creation safety

An explicit `request.thread_id` is authoritative. Resolution uses the shared
workspace access rules and verifies that the caller may edit the containing
workspace. A missing, deleted, or inaccessible explicit ID returns a controlled
resolution failure; it never falls through to an unrelated conversation or
creates a replacement thread.

When a caller supplies no thread ID, the agent may create a durable thread. It
first selects an editable, non-deleted conversation in the intended workspace,
preferring the page-context workspace and then the user's default editable
workspace. It creates a conversation only when that workspace has none. The new
thread retains the existing agent marker and title behavior.

This change prevents future container proliferation without rewriting historical
rows.

## Data flow

1. The user opens chat; the client resolves the workspace and requests the first
   workspace-wide thread page.
2. The user selects or creates a thread. The client sends that thread's real ID to
   the agent stream.
3. The backend resolves the explicit thread through the canonical access boundary.
4. `do_kb_retrieve` returns safe, tenant-scoped chunks in its tool result.
5. The tool node promotes and merges those chunks into canonical retrieved context.
6. Synthesis cites the numbered contexts, and streaming publishes the same source
   data to the active turn.
7. Assistant persistence writes the message and its citation rows atomically.
8. Terminal frontend reconciliation reloads the server-canonical message, retaining
   sources and footnotes after refresh.

## Error handling and observability

- Inaccessible workspaces and explicit threads fail closed with the existing
  non-enumerating not-found behavior.
- A legitimately empty workspace thread list returns an empty page; access failure
  is never represented as an empty success.
- A malformed retrieval result is logged with tool name, call ID, and rejection
  category, without logging chunk text or user query content.
- If citation persistence fails, the existing required assistant-persistence path
  reports failure rather than claiming a fully saved answer.
- Workspace-thread query logs may include workspace ID, page size, and result count,
  but not message previews.
- No endpoint or fallback performs a fan-out request per conversation.

## Compatibility and generated contracts

The workspace-wide endpoint is additive. The backend OpenAPI snapshot and generated
frontend TypeScript types are regenerated together. Touched frontend service types
adopt the generated schema according to `docs/engineering/api-contracts.md`.

No database migration is required. Existing conversations and threads remain
addressable by their current IDs, and existing conversation-scoped clients keep
their behavior.

## Test strategy

All production changes follow red-green-refactor.

Backend coverage must prove:

- successful knowledge-base tool chunks become canonical retrieved contexts;
- repeated chunks across multiple tool calls deduplicate in first-seen order;
- malformed, failed, unsafe, and title-only results do not create citations;
- the turn cap is enforced without changing the source numbering order;
- post-tool synthesis receives a numbered source map instead of false no-retrieval
  guidance;
- both normal and confirmation/resume streaming expose and persist tool-derived
  citations;
- message persistence creates reloadable citation rows;
- workspace thread listing respects membership, ancestor soft deletion, status
  filters, stable activity order, global pagination, and preview bounds;
- inaccessible workspace and explicit-thread resolution fail closed; and
- threadless agent requests reuse an editable conversation and create one only when
  necessary.

Frontend coverage must prove:

- initial sidebar data contains threads from multiple conversation IDs;
- warm restoration does not let a cached conversation ID scope the sidebar;
- workspace-wide pagination appends rather than replaces rows;
- a deep-linked thread outside the first page is restored without losing the first
  page;
- a newly created thread appears immediately with its real conversation ID; and
- live and reloaded agent answers render the same source list and inline markers.

Verification includes focused backend and frontend suites, architecture guards,
OpenAPI drift checks, changed-file lint/type gates, and a Chromium Playwright flow
that creates a thread, performs knowledge-base retrieval, confirms visible sources,
reloads, and confirms both the thread and sources remain visible.

## Files expected to change

- `backend/src/services/agent/_nodes_tools.py`
- `backend/src/services/agent/_nodes_llm.py`
- `backend/src/services/agent/agent_execution_service.py`
- `backend/src/api/agent/streaming.py`
- `backend/src/services/threads/thread_service.py`
- `backend/src/api/threads/workspace_routes/threads.py`
- agent and thread backend tests
- `backend/openapi.json`
- `frontend/src/services/workspaceService.ts`
- `frontend/src/hooks/chat/useChatSession.ts`
- focused frontend hook/component tests
- `frontend/src/types/generated/api.d.ts`
- a focused Playwright chat regression test or extension of the existing chat flow

Exact file boundaries may narrow during implementation, but behavior must not be
duplicated across stream/job or nested/standalone paths.

## Out of scope

- Merging, deleting, or reparenting historical conversation rows.
- A data-cleanup migration for the existing one-thread conversation containers.
- Treating title/filename search results as content evidence.
- Adding citations for external tools whose result contracts do not carry canonical
  document provenance.
- Closing #1610's remaining low-severity findings.
- Browser verification or closure of #1603, except where the #1622 regression flow
  overlaps its chat surface.

## Success criteria

- A knowledge-base tool answer persists at least one citation for every retained
  evidence chunk used by the turn, and the same sources are available live and
  after reload.
- Synthesis can reference tool-derived evidence with stable `[Doc N]` markers.
- The sidebar lists all accessible workspace threads through one bounded endpoint,
  independent of conversation-container count.
- An explicit thread lookup miss creates no conversation or thread.
- New threadless agent sessions reuse an editable conversation whenever possible.
- Existing APIs and historical data remain intact.
- Focused tests, contract generation, browser regression, and repository gates pass.
