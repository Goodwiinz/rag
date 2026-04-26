# Agent Chat CLI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a developer-facing chat CLI that exercises the real backend agent streaming flow, supports HITL confirmation, and surfaces LangSmith trace metadata for manual workflow testing.

**Architecture:** Build a thin HTTP/SSE client under `backend/src/cli/` that talks to `/api/v1/agent/stream` and `/api/v1/agent/stream/confirm`. Reuse shared backend LangSmith bootstrap and add a new `trace` SSE event so the CLI can show `thread_id`, `cli_session_id`, `langsmith_run_id`, and the trace URL without duplicating graph execution logic.

**Tech Stack:** FastAPI, LangGraph, LangSmith, httpx, Python asyncio, pytest

**Design doc:** `docs/plans/2026-03-26-agent-chat-cli-design.md`

---

## Task 1: Add Shared Agent Trace Context Helpers

**Files:**
- Create: `backend/src/api/agent/trace_context.py`
- Modify: `backend/src/services/agent/observability.py`
- Test: `backend/tests/unit/api/test_agent_trace_context.py`

**Step 1: Write the failing test**

```python
from src.api.agent.trace_context import build_trace_payload


def test_build_trace_payload_includes_ids_and_optional_url():
    payload = build_trace_payload(
        thread_id="thread-1",
        cli_session_id="cli-1",
        langsmith_run_id="run-1",
        langsmith_base_url="https://smith.langchain.com",
    )

    assert payload["thread_id"] == "thread-1"
    assert payload["cli_session_id"] == "cli-1"
    assert payload["langsmith_run_id"] == "run-1"
    assert payload["langsmith_url"].endswith("/run-1")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/api/test_agent_trace_context.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing function

**Step 3: Write minimal implementation**

```python
# backend/src/api/agent/trace_context.py
from typing import Optional


def build_trace_payload(
    *,
    thread_id: str,
    cli_session_id: str,
    langsmith_run_id: str = "",
    langsmith_base_url: str = "",
) -> dict:
    payload = {
        "thread_id": thread_id,
        "cli_session_id": cli_session_id,
        "langsmith_run_id": langsmith_run_id,
        "langsmith_url": "",
    }
    if langsmith_run_id and langsmith_base_url:
        payload["langsmith_url"] = (
            f"{langsmith_base_url.rstrip('/')}/o/default/projects/p/default/runs/{langsmith_run_id}"
        )
    return payload
```

Also add a small helper in `observability.py` to read the LangSmith base URL from env with a safe default.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/api/test_agent_trace_context.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/agent/trace_context.py backend/src/services/agent/observability.py backend/tests/unit/api/test_agent_trace_context.py
git commit -m "feat(agent): add shared trace context helpers for cli runs"
```

---

## Task 2: Enable LangSmith Bootstrap For Streaming Runs

**Files:**
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/src/api/agent/jobs.py`
- Modify: `backend/src/services/agent/observability.py`
- Test: `backend/tests/unit/api/test_agent_streaming_trace_bootstrap.py`

**Step 1: Write the failing test**

```python
from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_stream_event_generator_configures_langsmith_before_running_graph():
    from src.api.agent.streaming import stream_event_generator

    request = type("R", (), {"is_disconnected": AsyncMock(return_value=True)})()
    body = type("Body", (), {
        "messages": [],
        "page_context": {},
        "thread_id": "thread-1",
    })()
    user = object()
    db = object()

    with patch("src.services.agent.observability.configure_langsmith") as configure:
        gen = stream_event_generator(body, request, user, db)
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
        configure.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/api/test_agent_streaming_trace_bootstrap.py -v`
Expected: FAIL because `configure_langsmith()` is not called in the streaming path

**Step 3: Write minimal implementation**

Call `configure_langsmith()` near the start of `stream_event_generator()` and `stream_confirm_event_generator()`, mirroring the existing job runner behavior in `jobs.py`.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/api/test_agent_streaming_trace_bootstrap.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/agent/streaming.py backend/src/api/agent/jobs.py backend/src/services/agent/observability.py backend/tests/unit/api/test_agent_streaming_trace_bootstrap.py
git commit -m "feat(agent): enable langsmith bootstrap for streaming execution"
```

---

## Task 3: Add `trace` SSE Event To Agent Streaming

**Files:**
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `frontend/src/services/agentChatService.ts`
- Test: `backend/tests/unit/api/test_agent_streaming_trace_event.py`

**Step 1: Write the failing test**

```python
import pytest


@pytest.mark.asyncio
async def test_streaming_emits_trace_event_before_other_workflow_events():
    from src.api.agent.streaming import _format_sse_event

    payload = _format_sse_event(
        "trace",
        {
            "thread_id": "thread-1",
            "cli_session_id": "cli-1",
            "langsmith_run_id": "run-1",
            "langsmith_url": "https://smith.langchain.com/run-1",
        },
    )

    assert payload.startswith("event: trace")
    assert '"langsmith_run_id": "run-1"' in payload
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/api/test_agent_streaming_trace_event.py -v`
Expected: FAIL because there is no shared formatting helper or trace event

**Step 3: Write minimal implementation**

Add a tiny helper in `streaming.py`:

```python
def _format_sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\\ndata: {_json.dumps(data)}\\n\\n"
```

Emit a `trace` event once per run after config is assembled and before iterating graph events. Update `frontend/src/services/agentChatService.ts` to accept and ignore `trace` so the web client remains compatible.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/api/test_agent_streaming_trace_event.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/agent/streaming.py frontend/src/services/agentChatService.ts backend/tests/unit/api/test_agent_streaming_trace_event.py
git commit -m "feat(agent): emit trace sse event for cli and ui clients"
```

---

## Task 4: Create CLI SSE Event Parser

**Files:**
- Create: `backend/src/cli/types.py`
- Create: `backend/src/cli/agent_event_parser.py`
- Test: `backend/tests/unit/cli/test_agent_event_parser.py`

**Step 1: Write the failing test**

```python
from src.cli.agent_event_parser import parse_sse_lines


def test_parse_sse_lines_returns_trace_and_token_events():
    events = list(parse_sse_lines([
        "event: trace",
        'data: {"thread_id":"t1","cli_session_id":"c1","langsmith_run_id":"r1","langsmith_url":"u1"}',
        "",
        "event: token",
        'data: {"content":"Hello"}',
        "",
    ]))

    assert events[0].type == "trace"
    assert events[0].data["langsmith_run_id"] == "r1"
    assert events[1].type == "token"
    assert events[1].data["content"] == "Hello"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_event_parser.py -v`
Expected: FAIL with missing module

**Step 3: Write minimal implementation**

```python
# backend/src/cli/types.py
from dataclasses import dataclass


@dataclass
class CLIEvent:
    type: str
    data: dict
```

```python
# backend/src/cli/agent_event_parser.py
import json
from collections.abc import Iterable, Iterator
from src.cli.types import CLIEvent


def parse_sse_lines(lines: Iterable[str]) -> Iterator[CLIEvent]:
    event_type = ""
    for line in lines:
        if line.startswith("event: "):
            event_type = line[7:].strip()
        elif line.startswith("data: ") and event_type:
            yield CLIEvent(type=event_type, data=json.loads(line[6:]))
        elif line == "":
            event_type = ""
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_event_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/types.py backend/src/cli/agent_event_parser.py backend/tests/unit/cli/test_agent_event_parser.py
git commit -m "feat(cli): add typed sse event parser"
```

---

## Task 5: Create HTTP Streaming Client For Agent SSE

**Files:**
- Create: `backend/src/cli/agent_api_client.py`
- Test: `backend/tests/unit/cli/test_agent_api_client.py`

**Step 1: Write the failing test**

```python
import pytest


@pytest.mark.asyncio
async def test_build_stream_headers_includes_auth_and_org():
    from src.cli.agent_api_client import build_stream_headers

    headers = build_stream_headers(token="tok", organization_id="org-1")

    assert headers["Authorization"] == "Bearer tok"
    assert headers["X-Organization-ID"] == "org-1"
    assert headers["Content-Type"] == "application/json"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_api_client.py -v`
Expected: FAIL with missing module

**Step 3: Write minimal implementation**

```python
# backend/src/cli/agent_api_client.py
import httpx


def build_stream_headers(*, token: str = "", organization_id: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if organization_id:
        headers["X-Organization-ID"] = organization_id
    return headers


class AgentAPIClient:
    def __init__(self, base_url: str, token: str = "", organization_id: str = ""):
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"))
        self._headers = build_stream_headers(
            token=token, organization_id=organization_id
        )
```

Add async methods:

- `stream_message(request_body)`
- `stream_confirm(thread_id, confirmed)`

Return an async iterator of parsed CLI events.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_api_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/agent_api_client.py backend/tests/unit/cli/test_agent_api_client.py
git commit -m "feat(cli): add agent streaming api client"
```

---

## Task 6: Create CLI Renderer For Transcript And Workflow Events

**Files:**
- Create: `backend/src/cli/agent_cli_renderer.py`
- Test: `backend/tests/unit/cli/test_agent_cli_renderer.py`

**Step 1: Write the failing test**

```python
from src.cli.agent_cli_renderer import render_event
from src.cli.types import CLIEvent


def test_render_event_formats_plan_compactly():
    event = CLIEvent(
        type="plan",
        data={"steps": [{"step": 1, "description": "Search arXiv"}], "reasoning": ""},
    )

    text = render_event(event, debug=False)

    assert "plan>" in text
    assert "1. Search arXiv" in text
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_cli_renderer.py -v`
Expected: FAIL with missing module

**Step 3: Write minimal implementation**

Implement pure formatting helpers:

- `render_trace()`
- `render_tool_start()`
- `render_tool_end()`
- `render_plan()`
- `render_reflection()`
- `render_confirmation()`
- `render_error()`

Keep `token` rendering separate so the REPL can stream it incrementally.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_cli_renderer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/agent_cli_renderer.py backend/tests/unit/cli/test_agent_cli_renderer.py
git commit -m "feat(cli): add workflow event renderer"
```

---

## Task 7: Build REPL Session State And Slash Commands

**Files:**
- Modify: `backend/src/cli/types.py`
- Create: `backend/src/cli/agent_chat_cli.py`
- Test: `backend/tests/unit/cli/test_agent_chat_cli_commands.py`

**Step 1: Write the failing test**

```python
from src.cli.agent_chat_cli import apply_command
from src.cli.types import CLISessionState


def test_context_project_command_updates_project_context():
    state = CLISessionState()

    next_state, output = apply_command(state, "/context project proj-1")

    assert next_state.page_context["type"] == "project"
    assert next_state.page_context["project_id"] == "proj-1"
    assert "proj-1" in output
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_commands.py -v`
Expected: FAIL with missing module

**Step 3: Write minimal implementation**

Add session state:

```python
from dataclasses import dataclass, field


@dataclass
class CLISessionState:
    thread_id: str = ""
    cli_session_id: str = ""
    debug: bool = False
    page_context: dict = field(default_factory=lambda: {"type": "general"})
    latest_trace: dict = field(default_factory=dict)
```

Implement:

- `/help`
- `/new`
- `/thread`
- `/status`
- `/context project <id>`
- `/context clear`
- `/debug on`
- `/debug off`
- `/quit`

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_commands.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/types.py backend/src/cli/agent_chat_cli.py backend/tests/unit/cli/test_agent_chat_cli_commands.py
git commit -m "feat(cli): add repl state and slash commands"
```

---

## Task 8: Add Confirmation And Resume Flow

**Files:**
- Modify: `backend/src/cli/agent_chat_cli.py`
- Modify: `backend/src/cli/agent_api_client.py`
- Test: `backend/tests/unit/cli/test_agent_chat_cli_confirmation.py`

**Step 1: Write the failing test**

```python
import pytest
from src.cli.types import CLIEvent


@pytest.mark.asyncio
async def test_confirmation_event_routes_to_resume_call():
    from src.cli.agent_chat_cli import handle_confirmation_event

    event = CLIEvent(
        type="confirmation",
        data={"thread_id": "thread-1", "confirmation": {"message": "Proceed?"}},
    )

    called = {}

    async def fake_resume(thread_id: str, confirmed: bool):
        called["thread_id"] = thread_id
        called["confirmed"] = confirmed

    await handle_confirmation_event(event, fake_resume, user_input="y")

    assert called == {"thread_id": "thread-1", "confirmed": True}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_confirmation.py -v`
Expected: FAIL because confirmation handling does not exist yet

**Step 3: Write minimal implementation**

Implement a small handler that:

- renders the confirmation block
- accepts `y` / `n`
- calls `stream_confirm()`
- resumes normal streaming

Keep it blocking and simple for v1.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_confirmation.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/agent_chat_cli.py backend/src/cli/agent_api_client.py backend/tests/unit/cli/test_agent_chat_cli_confirmation.py
git commit -m "feat(cli): support hitl confirmation and resume"
```

---

## Task 9: Wire End-To-End Stream Handling And Entry Point

**Files:**
- Modify: `backend/src/cli/agent_chat_cli.py`
- Test: `backend/tests/unit/cli/test_agent_chat_cli_stream_flow.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-minimal.txt`

**Step 1: Write the failing test**

```python
import pytest
from src.cli.types import CLIEvent


@pytest.mark.asyncio
async def test_chat_turn_updates_trace_and_thread_state():
    from src.cli.agent_chat_cli import run_turn
    from src.cli.types import CLISessionState

    state = CLISessionState(cli_session_id="cli-1")

    async def fake_stream_message(*args, **kwargs):
        for event in [
            CLIEvent(type="trace", data={"thread_id": "thread-1", "cli_session_id": "cli-1", "langsmith_run_id": "run-1", "langsmith_url": "u1"}),
            CLIEvent(type="token", data={"content": "Hello"}),
            CLIEvent(type="done", data={"status": "complete"}),
        ]:
            yield event

    next_state = await run_turn(state, "hello", fake_stream_message)

    assert next_state.thread_id == "thread-1"
    assert next_state.latest_trace["langsmith_run_id"] == "run-1"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_stream_flow.py -v`
Expected: FAIL because the REPL turn runner does not process stream events yet

**Step 3: Write minimal implementation**

Implement:

- `run_turn()`
- `main()`
- argparse flags:
  - `--base-url`
  - `--token`
  - `--org-id`
  - `--project-id`
  - `--debug`
- `python -m src.cli.agent_chat_cli` entrypoint

Only add new dependencies if truly required. Since `httpx` already exists in backend requirements, avoid adding anything else.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_stream_flow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/agent_chat_cli.py backend/tests/unit/cli/test_agent_chat_cli_stream_flow.py backend/requirements.txt backend/requirements-minimal.txt
git commit -m "feat(cli): add end-to-end agent chat cli entrypoint"
```

---

## Task 10: Verify The Full CLI Flow And Document Usage

**Files:**
- Create: `backend/docs/agent-chat-cli.md`
- Modify: `docs/plans/2026-03-26-agent-chat-cli-design.md`
- Modify: `docs/plans/2026-03-26-agent-chat-cli-plan.md`

**Step 1: Write the failing test**

There is no new automated test in this task. The test is the manual verification checklist below.

**Step 2: Run manual verification**

Run backend in terminal A:

```bash
cd backend
uvicorn src.main:app --reload
```

Run CLI in terminal B:

```bash
cd backend
python -m src.cli.agent_chat_cli --base-url http://localhost:8000 --debug
```

Verify:

1. simple chat streams tokens
2. `/context project <id>` updates context
3. a tool-using prompt shows tool start/end lines
4. destructive action prompts for confirmation
5. `y` resumes and completes
6. LangSmith `run_id` and URL print
7. `/status` shows thread id, session id, context, and trace metadata

**Step 3: Write minimal documentation**

Document:

- how to start the CLI
- required auth/org env vars or flags
- slash commands
- expected LangSmith output
- recommended two-terminal workflow: backend logs + CLI

**Step 4: Re-run focused tests and type checks**

Run:

```bash
cd backend && python -m pytest tests/unit/api/test_agent_trace_context.py tests/unit/api/test_agent_streaming_trace_bootstrap.py tests/unit/api/test_agent_streaming_trace_event.py tests/unit/cli -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/docs/agent-chat-cli.md docs/plans/2026-03-26-agent-chat-cli-design.md docs/plans/2026-03-26-agent-chat-cli-plan.md
git commit -m "docs(cli): add agent chat cli usage and implementation docs"
```
