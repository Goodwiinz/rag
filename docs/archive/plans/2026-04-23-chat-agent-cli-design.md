# NOUS CLI — Chat & Agent Terminal Interface

**Date:** 2026-04-23  
**Context:** Hackathon feature (weeks away). Replace broken Python CLI with a polished TypeScript + Ink terminal experience similar to Claude Code / OpenCode.

---

## Goals

- Interactive REPL and one-shot query mode
- Real-time streaming with tool call display
- Reliable browser OAuth (device flow with local callback server)
- Lives in the monorepo, exposed via `./nous` at the repo root

---

## Architecture

### Location

Code lives in `frontend/cli/`. A root-level `./nous` shell script is the user-facing entry point — users never need to know where it lives internally.

```
frontend/
└── cli/
    ├── index.ts              # Entry: parse argv → REPL or one-shot
    ├── auth/
    │   ├── deviceFlow.ts     # Local HTTP callback server + browser open
    │   └── store.ts          # ~/.nous/config.json read/write (tokens, thread_id)
    ├── components/
    │   ├── App.tsx           # Root Ink app, manages mode state
    │   ├── ChatMessage.tsx   # User/assistant message with markdown rendering
    │   ├── ToolCall.tsx      # Collapsible tool execution block
    │   ├── StreamingLine.tsx # Live token stream with cursor
    │   ├── Prompt.tsx        # Input line with slash-command autocomplete
    │   └── StatusBar.tsx     # Thread ID, model, active project context
    ├── hooks/
    │   ├── useStream.ts      # Wraps agentChatService.streamMessage for Ink
    │   └── useSlashCommands.ts
    └── services/
        └── client.ts         # Re-exports agentChatService + injects auth headers
```

**Entry point added to `frontend/package.json`:**

```json
"scripts": {
  "cli": "tsx cli/index.ts"
}
```

**Root wrapper `./nous`:**

```bash
#!/bin/bash
pnpm --prefix frontend cli "$@"
```

**Run:**

```bash
./nous                          # REPL mode
./nous "find ML papers"         # One-shot mode
./nous login                    # Authenticate
```

---

## Auth Flow

Uses a **local callback server** — the correct device flow pattern that avoids the polling issues of the old Python CLI.

```
1. ./nous login
2. CLI generates one-time state token
3. CLI starts local HTTP server on random port (e.g. 52341)
4. CLI opens browser → http://localhost:3000/cli-auth?redirect=http://localhost:52341/callback&state=<token>
5. Web app shows "Authorize NOUS CLI?" page — user clicks Allow
6. Web app completes Supabase auth, redirects to localhost:52341/callback?access_token=...&refresh_token=...
7. Local server receives callback, writes tokens to ~/.nous/config.json, shuts down
8. CLI prints "✓ Logged in as user@example.com"
```

**Token refresh:** On each CLI startup, check expiry in `~/.nous/config.json`. If expired, silently refresh via Supabase refresh token endpoint. If refresh fails, prompt user to run `./nous login`.

**Requires:** `frontend/app/(auth)/cli-auth/page.tsx` — "Authorize NOUS CLI?" confirmation page (route already exists).

---

## Modes

### One-shot

```bash
./nous "find me papers on ML healthcare"
```

- Streams response to stdout
- Uses last active `thread_id` from `~/.nous/config.json` or creates a new thread
- Exits when `done` event received

### REPL

```bash
./nous
```

- Launches full Ink app
- Persistent thread across messages
- Slash commands:

| Command                 | Action                   |
| ----------------------- | ------------------------ |
| `/new`                  | Start a new thread       |
| `/thread`               | Show current thread ID   |
| `/context project <id>` | Set project page context |
| `/context clear`        | Clear project context    |
| `/help`                 | Show command list        |
| `/quit` or Ctrl+C       | Exit                     |

---

## Ink Component Tree

```
<App>
  ├── <StatusBar>        — thread id, active project, model
  ├── <MessageList>      — scrollable conversation history
  │   ├── <ChatMessage>  — user or assistant message, markdown rendered
  │   └── <ToolCall>     — collapsible tool block
  ├── <StreamingLine>    — live token output while agent is responding
  └── <Prompt>           — input line with slash-command hints
```

---

## Streaming & Event Mapping

`useStream.ts` maps SSE events from `agentChatService.streamMessage` to Ink component state:

| SSE Event      | Action                                                             |
| -------------- | ------------------------------------------------------------------ |
| `token`        | Append to `streamingContent`, re-render `<StreamingLine>`          |
| `tool_start`   | Push `{ tool, status: "running", startTime }` to `toolCalls[]`     |
| `tool_end`     | Update `toolCalls[i].status = "done" \| "error"`, record duration  |
| `rag_context`  | Store citations, show count in `<StatusBar>`                       |
| `confirmation` | Pause input, render inline `[Y/n]` confirmation prompt             |
| `done`         | Move `streamingContent` → `<ChatMessage>`, clear `<StreamingLine>` |
| `error`        | Render red error block, re-enable input                            |

### Tool Call Display

```
▶ search_arxiv          running…
✓ search_arxiv          done  (0.8s)   ← collapsed, press Enter to expand
✗ ingest_arxiv_papers   error (2.1s)
```

### HITL Confirmation (inline)

```
⚠ Agent wants to ingest 3 papers into ML Healthcare
  → ingest_arxiv_papers({ paper_ids: [...] })
  Allow? [Y/n]  _
```

---

## Error Handling

| Scenario                | Behaviour                                                |
| ----------------------- | -------------------------------------------------------- |
| Network error / timeout | Red inline message, input stays open, thread preserved   |
| Auth token expired      | Auto-refresh silently; if fails → prompt `./nous login`  |
| Agent `error` SSE event | Display error block inline, don't crash REPL             |
| Ctrl+C during stream    | `AbortController.abort()`, print graceful cancel message |

---

## Testing

**Unit (Jest):**

- `deviceFlow.ts` — mock local HTTP server and Supabase callback
- `useSlashCommands.ts` — parse commands and edge cases
- `client.ts` — auth header injection, token refresh

**Component (ink-testing-library):**

- `<ToolCall>` — running / done / error states
- `<StreamingLine>` — token append behaviour
- `<Prompt>` — slash-command autocomplete

**E2E (Playwright):**

- Start backend locally, run `./nous "hello"` in one-shot mode, assert streaming response and exit code 0

**Hackathon manual checklist:**

- [ ] `./nous login` → browser opens, token saved
- [ ] `./nous "find ML papers"` → streams, exits cleanly
- [ ] `./nous` → REPL opens
- [ ] `/context project <id>` sets context, agent responds with it
- [ ] Tool calls visible during execution
- [ ] Ctrl+C exits cleanly without error

---

## Key Dependencies to Add

```json
"ink": "^4.4.1",
"ink-markdown": "^1.0.0",
"open": "^10.0.0",
"tsx": "^4.0.0"
```

`tsx` is likely already in `devDependencies`. `ink` and `open` are new.
