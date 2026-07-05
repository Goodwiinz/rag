# assistant-ui Runtime Bridge for /chat — Design (Stage 1: Tool Calls)

**Date:** 2026-07-04
**Status:** Approved
**Related:** PR #996 (tool-fallback component, unmounted), assistant-ui docs (`/docs/api-reference/external-store/runtime.md`, `/docs/ui/tool-fallback.md`)

## Goal

Mount a real `@assistant-ui/react` runtime over the existing chat state so the
`tool-fallback` component renders tool calls natively in `/chat`, replacing
`ChatActivityStrip` rows inside message bubbles. This is stage 1 of an
incremental migration — SSE parsing, stores, persistence, HITL, and the
composer are untouched.

## Strategy (decided)

- **Incremental bridge** via `useExternalStoreRuntime` — the runtime is a
  projection over `useChatStore`; no state duplication, rollback-friendly.
  (Rejected: big-bang rebuild on LocalRuntime — rewrites streaming +
  persistence, highest risk. Rejected: render-only shim — user wants the real
  runtime.)
- **Stage 1 scope: tool calls only.** Bubbles, markdown, citations, composer
  unchanged. `ChatActivityStrip` stays for agent-panel usages until stage 2.
- **HITL stays on the existing interrupt/confirm flow** (`POST
  /confirm/{job_id}`). tool-fallback renders status/args/result only; its
  approval bar (`respondToApproval`) is a later stage.

## Architecture

### New files

- `src/components/chat/aui/ChatRuntimeProvider.tsx` — wraps the message pane in
  `AssistantRuntimeProvider` using `useExternalStoreRuntime({ messages,
  isRunning, convertMessage, onNew, onCancel })`.
  - `messages`: `ChatPageMessage[]` from the store (committed) + the in-flight
    assistant message while streaming.
  - `isRunning`: `storeIsStreaming`.
  - `onNew`: **required by the API** — delegates to the existing
    `useChatStreaming` send. Functional, not a throw, though unused until the
    composer stage.
  - `onCancel`: delegates to existing stop.
- `src/components/chat/aui/convertMessage.ts` — the `convertMessage`
  implementation: `ChatPageMessage → ThreadMessageLike`.
  - text content → one `text` part, rendered by the **existing markdown
    renderer** wrapped as the assistant-ui `Text` component (visuals
    unchanged).
  - `toolExecutions: ActivityStep[]` → `tool-call` parts:
    `{ type: 'tool-call', toolCallId, toolName: step.tool, args, result }`.
  - Status mapping: `running` → part without `result` on a running message;
    `done` → `complete` with result; `error` → result with `isError`.

### Rendering integration

`MessagePrimitive.Parts` with
`components={{ Text: ExistingMarkdown, tools: { Fallback: ToolFallback } }}`
(per assistant-ui docs, tool-call parts spread into the fallback as props).
`ChatBubble` keeps its chrome (avatar, timestamps, actions); the
`ChatActivityStrip` mount at `ChatBubble.tsx:277` is replaced by the part
renderer behind the feature flag.

### Feature flag

`NEXT_PUBLIC_AUI_TOOL_UI` (default off in prod) gates new renderer vs
`ChatActivityStrip` — instant rollback.

## Streaming render contract (perf-critical)

Established fact from code trace: `streamingSteps` in `useChatStore` updates
**only on `tool_start`/`tool_end` events** (`useChatStreaming.ts:496-537`),
never per token. The design pins tool-part identity to that:

1. **Committed messages** keep stable object identity (already memoized in
   `ChatMessageList`) → `convertMessage` is cached per message identity by the
   library → zero conversion work per token.
2. **In-flight message**: only its `text` part rebuilds per token. Tool-call
   parts are derived solely from the `streamingSteps` array reference — cached
   (`useMemo` / `WeakMap` keyed on that reference) so per-token re-conversion
   reuses the *same part objects* (same `args`/`result` references).
3. `ToolFallback` root is `memo`-wrapped — stable part props mean no tool-UI
   re-render during the token flood.
4. **Guard test**: component test asserts ToolFallback render count stays flat
   across N simulated token updates (React Profiler API under vitest).
5. Fallback lever (only if profiling shows cost): rAF-batch token commits in
   `useChatStreaming`. Measure first.

## Error handling

- Adapter defensive: missing `args` → `{}`; malformed `resultSummary` → plain
  string result. A tool-part mapping failure omits that part (dev-only
  `console.warn`), never crashes the bubble.
- Radix Collapsible height animation inside virtualized lists is unverified:
  the flag applies to the non-virtualized `ChatMessageList` path first;
  `VirtualizedMessageList` stays flag-off until measured.

## Testing

- Unit: `convertMessage` mapping (statuses, streaming projection, malformed
  data, referential stability of tool parts across token updates).
- Component (vitest + RTL): bubble renders ToolFallback for a message with
  `toolExecutions`; live transition running → done; render-count guard test.
- Existing chat suite (61 tests) stays green.
- Visual check on dev with a tool-calling turn (e.g. arXiv search + ingest).

## Risks

- `@assistant-ui/react` is 0.x — pin exact version (0.14.26).
- Dual sources of truth during migration (store + runtime projection) —
  mitigated by projection-only design; the runtime never owns state.
- Virtualization interplay (above).

## Later stages (out of scope)

1. HITL approvals through tool-fallback (`respondToApproval` → confirm
   endpoint), retiring the separate confirm UI.
2. Whole message list on `Thread`/`MessagePrimitive` (retire
   `ChatBubble`/`ChatActivityStrip`).
3. Composer primitives (slash commands, voice, attachments re-adapted).
