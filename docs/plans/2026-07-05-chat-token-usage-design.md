# Per-turn token usage on chat messages — design

**Date:** 2026-07-05
**Scope:** Surface per-turn LLM token usage (input/output) on assistant messages in `/chat`. Frontend-only; backend already emits the data.

## Problem

The agent SSE stream already emits a `usage` event (`{input_tokens, output_tokens}`, accumulated per turn) right before `done` (`backend/src/api/agent/streaming.py`). The frontend SSE parser has no case for it, so the event is silently dropped and users never see token cost.

## Approach (chosen)

Per-turn tokens only, rendered as a small muted entry in the existing message footer tool-strip (next to response time). No context-window %, no ring/bar, no assistant-ui dependency, no backend change.

Rejected: cumulative thread context-% ring — needs a model context-window number NOUS doesn't expose anywhere, plus cumulative accounting that checkpointing + summarization make unreliable. YAGNI.

## Data flow

1. **`agentChatService.ts`** — add `onUsage?: (input, output) => void` to the `streamMessage` callbacks; add `case 'usage':` in the SSE switch → `callbacks.onUsage?.(data.input_tokens, data.output_tokens)`.
2. **`useChatStreaming.ts`** — a `turnTokenUsage` local captures the latest usage during the stream; on completion, fold `{ tokenUsage: { input, output } }` into `finalAssistantMessage.metadata`.
3. **`cloudMessageView.ts` + `ChatBubble.tsx`** — extend the `metadata` type with `tokenUsage?: { input: number; output: number }`; render it in the `ToolStrip` footer as `⊚ 1.2k in · 340 out` (compact formatting, `title` tooltip with exact counts), theme-class colored, shown only when present.

## Edge cases

- No `usage` event (error / user abort before completion) → no `tokenUsage` in metadata → nothing rendered. Never show zeros.
- Multiple LLM calls per turn → backend already accumulates; frontend takes the last (final) usage payload.
- Regenerated turn → new metadata replaces old naturally (per-message).

## Persistence note (honest limitation)

Token usage shows for the **live turn** only. The workspace DB message schema stores `latency_ms`/`stopped` but has no token columns, so `tokenUsage` is not persisted — a page reload will not re-show token counts on old messages. Persisting would require a backend column + `createMessage` change; out of scope. `responseTimeMs` has the same in-memory-only behaviour for the current session already.

## Testing

- vitest: `agentChatService` parses a `usage` SSE event and invokes `onUsage` with the right numbers (and defaults missing counts to 0).
- vitest: `ChatBubble`/`ToolStrip` renders the token entry when `metadata.tokenUsage` present, hides it when absent.
- Manual: preview `/chat`, send a message, confirm badge appears with plausible counts.

## History

First built in a harness worktree on 2026-07-05; that worktree + its `.git` were destroyed by an external process before push. Rebuilt from a fresh `Goodwiinz/rag` clone (`nous-fix`) on branch `feat/chat-token-usage-display`, re-verified against post-#1011 develop.
