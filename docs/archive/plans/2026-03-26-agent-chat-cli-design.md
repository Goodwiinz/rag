# Agent Chat CLI Design

**Date:** 2026-03-26  
**Branch:** `feature/agent-v2`  
**Approach:** Thin HTTP/SSE client over the existing backend agent API

---

## Decisions

| Decision | Choice |
| --- | --- |
| Execution path | Reuse `/api/v1/agent/stream` and `/api/v1/agent/stream/confirm` |
| Runtime | CLI is a client, not a second in-process agent runner |
| Debugging | Backend logs stay in a separate terminal |
| Deep tracing | LangSmith is the canonical execution trace |
| CLI output | Clean chat transcript by default, structured workflow events layered in |
| Scope | Dev-focused manual testing harness first, not a productized terminal app |

---

## 1. Goal

Build a developer-facing chat CLI for the backend agent execution flow so the team can manually test routing, tool loops, HITL confirmation, plan/reflection events, and project-aware behavior before investing in richer UI work.

The CLI should feel conversational like Claude Code or Codex, but it must remain a thin wrapper over the real backend API contract. The purpose is workflow validation, not creating a second agent runtime.

---

## 2. Existing Architecture Context

The current backend already exposes two execution surfaces over the same LangGraph agent:

- Background job execution in `backend/src/api/agent/jobs.py`
- SSE streaming execution in `backend/src/api/agent/streaming.py`

The frontend consumes the streaming surface through `frontend/src/services/agentChatService.ts`, which already parses these SSE events:

- `token`
- `tool_start`
- `tool_end`
- `rag_context`
- `plan`
- `reflection`
- `confirmation`
- `done`
- `error`

This means the lowest-risk CLI is an HTTP client that sends the same request payload and renders the same SSE events. It should not import `compile_agent_graph()` and run the graph directly.

---

## 3. Scope

### In scope for CLI v1

- Interactive terminal chat loop
- Persistent `thread_id` across turns
- Live token streaming
- Compact rendering for plan, tool, RAG, reflection, confirmation, done, and error events
- HITL confirmation via `y` / `n`
- Project/page context injection
- Session commands for common testing workflows
- LangSmith trace visibility (`run_id` and URL)
- Separate clean mode and debug mode

### Out of scope for CLI v1

- Full-screen TUI or pane-based UI
- Local file editing / shell execution
- In-process graph execution mode
- Multi-session persistence on disk
- Prompt history search, autocomplete, or terminal multiplexing
- Production/user-facing distribution

---

## 4. Interaction Model

The CLI should default to a clean transcript:

```text
you> add the newest transformer paper to my project
trace> thread=... session=... run=...
trace> https://smith.langchain.com/...
plan> 1. Search arXiv
plan> 2. Ingest top paper
plan> 3. Add document to project
tool> search_arxiv ...
tool> search_arxiv done
tool> ingest_arxiv_papers ...
tool> ingest_arxiv_papers done
agent> I found and added the newest transformer paper to your project.
```

Workflow events should appear inline, but remain compact. The backend terminal remains the place to watch logs, stack traces, and low-level execution details.

### Modes

- **Default mode**: human-readable transcript with concise event summaries
- **Debug mode**: adds timestamps, payload summaries, and trace/session metadata

### Slash commands

- `/help`
- `/new`
- `/thread`
- `/status`
- `/context project <id>`
- `/context clear`
- `/debug on`
- `/debug off`
- `/quit`

### Confirmation flow

When the backend emits a `confirmation` event:

1. pause normal prompt entry
2. render the requested tools, args, and message
3. accept `y` / `n`
4. call `/api/v1/agent/stream/confirm`
5. resume the same thread

---

## 5. API Contract

The CLI reuses the existing request shape from `frontend/src/services/agentChatService.ts`:

```json
{
  "messages": [{"role": "user", "content": "..." }],
  "page_context": {
    "type": "project",
    "project_id": "..."
  },
  "thread_id": "...",
  "use_rag": true
}
```

### Existing SSE events to support

- `token`
- `tool_start`
- `tool_end`
- `rag_context`
- `plan`
- `reflection`
- `confirmation`
- `done`
- `error`

### New SSE event to add

Add a `trace` event emitted once per run:

```json
{
  "thread_id": "...",
  "cli_session_id": "...",
  "langsmith_run_id": "...",
  "langsmith_url": "https://smith.langchain.com/..."
}
```

The CLI stores the latest trace payload in session state and shows it via `/status`.

---

## 6. LangSmith Tracing

LangSmith should become the canonical deep trace for CLI testing.

### Requirements

- enable LangSmith for both streaming and background execution paths
- attach stable metadata and tags:
  - `surface=cli`
  - `cli_session_id`
  - `thread_id`
  - `page_context_type`
  - `project_id`
  - `intent` when available
- capture the root LangSmith run id
- construct a LangSmith URL when tracing is enabled and the host is known
- expose the trace identity through the new `trace` SSE event

### Important implication

Today `configure_langsmith()` is explicitly called from the job runner, but not from the SSE path. That must be unified so the CLI path is traced the same way as the UI path.

---

## 7. CLI Architecture

### Files

- `backend/src/cli/agent_chat_cli.py`
  - REPL loop
  - slash-command dispatch
  - session state
- `backend/src/cli/agent_api_client.py`
  - HTTP streaming client for `/agent/stream` and `/agent/stream/confirm`
  - auth/org header construction
- `backend/src/cli/agent_event_parser.py`
  - SSE parsing into typed events
- `backend/src/cli/agent_cli_renderer.py`
  - transcript and workflow event rendering
- `backend/src/cli/types.py`
  - CLI event and session dataclasses

### Shared backend additions

- `backend/src/api/agent/trace_context.py`
  - request-scoped trace metadata helpers
  - session id, run id, LangSmith URL helpers
- updates to `backend/src/api/agent/streaming.py`
  - emit `trace` SSE event
- updates to `backend/src/api/agent/jobs.py`
  - reuse the same LangSmith bootstrap and trace metadata tagging
- updates to `backend/src/services/agent/observability.py`
  - centralize LangSmith enablement and URL construction

---

## 8. Rendering Strategy

The CLI should not dump raw JSON unless debug mode is on.

### Default rendering

- `token`: stream directly into the assistant line
- `tool_start`: `tool> <name> ...`
- `tool_end`: `tool> <name> done`
- `rag_context`: one-line summary of top sources
- `plan`: numbered steps
- `reflection`: pass/fail plus issues
- `confirmation`: blocking question with tool/action summary
- `error`: single highlighted error block

### Debug rendering

- timestamps per event
- truncated payload preview
- session/thread/run identifiers
- optional counts such as number of plan steps or retrieved contexts

---

## 9. Testing Strategy

### Unit tests

- SSE event parsing
- slash-command parsing
- renderer output formatting
- trace payload handling

### Integration-style tests

- mocked streaming sequence for a normal chat turn
- mocked confirmation + resume flow
- trace event propagation into CLI state

### Manual test checklist

Two-terminal workflow:

1. Terminal A: backend server logs
2. Terminal B: CLI session
3. Validate:
   - simple general chat
   - project-context request
   - tool execution sequence
   - destructive tool confirmation accept
   - destructive tool confirmation deny
   - planner event
   - reflection event
   - LangSmith run id and URL display

---

## 10. Rollout

Ship CLI v1 as a developer-only entrypoint:

```bash
cd backend
python -m src.cli.agent_chat_cli --base-url http://localhost:8000
```

Document it as the preferred manual-testing harness for backend agent workflow work. Once the CLI proves stable, the same trace and event contract can be reused to improve the frontend agent UX.
