# Agent Conversation Persistence Performance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Cut per-turn agent latency by moving conversation persistence off the request hot path and replacing the time-window dedup SELECT with a client-supplied UUID + unique index; add an append-only local JSONL cache to the Node CLI so thread switches don't round-trip the API.

**Architecture:**
1. Backend: add `client_message_id UUID` column on `chat_messages` with a partial unique index on `(thread_id, client_message_id)` for user rows. Persistence becomes `INSERT ... ON CONFLICT DO NOTHING` (no SELECT). User row is persisted *before* the LLM call; assistant row is dispatched to a background task (`asyncio.create_task` wrapped by `BackgroundTasks`) once the SSE `done` event fires.
2. Clients: Python CLI and Node CLI both generate a UUID per user turn and send it in the request body.
3. Node CLI: append each user/assistant pair to `~/.nous/threads/<id>.jsonl` as the stream completes. On `/thread <id>` load from disk; reconcile via `GET /threads/{id}/messages?since=<iso>` only when registry `last_message_at` mismatches.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic (CONCURRENTLY), Pydantic v2, pytest+pytest-asyncio, Node 20 + tsx, vitest. Postgres `gen_random_uuid()` already enabled (see `pgcrypto`).

**Branch:** `feat/agent-persist-perf` cut from current `feat/do-kb-activation`. Final PR targets `develop`.

**Risk register:**
- A crash between `done` event and background commit drops the assistant row. Mitigation: write the assistant row inside the *same* request, but after the SSE response is fully sent (FastAPI `BackgroundTasks` runs after response close). Document the small loss window in the migration commit; do not add an outbox in this plan (YAGNI).
- ChatMessage hot path is shared by non-agent code (Terminal Observatory). Column must default `NULL` and the unique index must be partial (`WHERE client_message_id IS NOT NULL AND role = 'user'`) so existing rows are unaffected.
- Local JSONL cache can drift from server. Fix by treating server as authoritative on mismatch: compare `last_message_at` from `threads.json` registry to the server response and fall back to a full `GET` when stale.

---

## Task 1: Add `client_message_id` column + partial unique index (migration)

**Files:**
- Create: `backend/alembic/versions/v0a1b2c3d4e5_add_chat_messages_client_message_id.py`
- Modify: `backend/src/models/chat_message.py:32-46` (add column after `tool_call_id`)
- Test: `backend/tests/db/test_chat_messages_client_uuid_uniqueness.py`

**Step 1: Write the failing test**

```python
# backend/tests/db/test_chat_messages_client_uuid_uniqueness.py
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.chat_message import ChatMessage, MessageRole


@pytest.mark.integration
async def test_duplicate_client_message_id_is_rejected(db_session, thread_factory, user_factory):
    thread = await thread_factory()
    user = await user_factory()
    cmid = uuid4()

    db_session.add(
        ChatMessage(
            thread_id=thread.id,
            user_id=user.id,
            role=MessageRole.USER,
            content="hi",
            client_message_id=cmid,
        )
    )
    await db_session.commit()

    db_session.add(
        ChatMessage(
            thread_id=thread.id,
            user_id=user.id,
            role=MessageRole.USER,
            content="hi (retry)",
            client_message_id=cmid,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.integration
async def test_null_client_message_id_allows_many_rows(db_session, thread_factory):
    thread = await thread_factory()
    for _ in range(3):
        db_session.add(
            ChatMessage(
                thread_id=thread.id,
                role=MessageRole.ASSISTANT,
                content="reply",
                client_message_id=None,
            )
        )
    await db_session.commit()

    result = await db_session.execute(
        select(ChatMessage).where(ChatMessage.thread_id == thread.id)
    )
    assert len(result.scalars().all()) == 3
```

**Step 2: Run test to verify it fails**

```
cd backend && pytest tests/db/test_chat_messages_client_uuid_uniqueness.py -v
```
Expected: FAIL — `AttributeError: type object 'ChatMessage' has no attribute 'client_message_id'`.

**Step 3: Add column to model**

Edit `backend/src/models/chat_message.py` — add after the existing `tool_call_id` column (line ~61):

```python
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# inside class ChatMessage
client_message_id = Column(
    PG_UUID(as_uuid=True),
    nullable=True,
    doc=(
        "Client-supplied idempotency key for user turns. Combined with thread_id "
        "in a partial unique index to dedupe retries without a SELECT."
    ),
)
```

(Use `from .base import GUID` if `PG_UUID` is not already imported; either type works as long as it round-trips a UUID.)

**Step 4: Write the Alembic migration**

```python
# backend/alembic/versions/v0a1b2c3d4e5_add_chat_messages_client_message_id.py
"""Add client_message_id to chat_messages for idempotent inserts.

Revision ID: v0a1b2c3d4e5
Revises: u9a0b1c2d3e4
Create Date: 2026-05-13 00:00:00.000000

Replaces the 60s dedup SELECT in backend/src/api/agent/jobs.py with
INSERT ... ON CONFLICT DO NOTHING by adding a partial unique index on
(thread_id, client_message_id) restricted to user-role rows.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


revision = "v0a1b2c3d4e5"
down_revision = "u9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("client_message_id", PG_UUID(as_uuid=True), nullable=True),
    )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            "uq_chat_messages_thread_client_msg_user "
            "ON chat_messages (thread_id, client_message_id) "
            "WHERE client_message_id IS NOT NULL AND role = 'user'"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS uq_chat_messages_thread_client_msg_user"
        )
    op.drop_column("chat_messages", "client_message_id")
```

**Step 5: Apply migration locally**

```
cd backend && alembic upgrade head
```
Expected: `INFO  [alembic.runtime.migration] Running upgrade u9a0b1c2d3e4 -> v0a1b2c3d4e5`.

**Step 6: Run the tests to verify they pass**

```
pytest tests/db/test_chat_messages_client_uuid_uniqueness.py -v
```
Expected: 2 passed.

**Step 7: Commit**

```
git add backend/alembic/versions/v0a1b2c3d4e5_add_chat_messages_client_message_id.py \
        backend/src/models/chat_message.py \
        backend/tests/db/test_chat_messages_client_uuid_uniqueness.py
git commit -m "feat(chat): add client_message_id + partial unique index"
```

---

## Task 2: Wire `client_message_id` into AgentExecuteRequest

**Files:**
- Modify: `backend/src/api/agent/execute.py:100-138` (extend `AgentMessage` + `AgentExecuteRequest`)
- Test: `backend/tests/api/agent/test_agent_request_schema.py`

**Step 1: Write the failing test**

```python
# backend/tests/api/agent/test_agent_request_schema.py
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.api.agent.execute import AgentExecuteRequest, AgentMessage


def test_user_message_accepts_client_message_id():
    cmid = uuid4()
    msg = AgentMessage(role="user", content="hi", client_message_id=str(cmid))
    assert msg.client_message_id == cmid


def test_assistant_message_rejects_client_message_id():
    with pytest.raises(ValidationError):
        AgentMessage(role="assistant", content="hi", client_message_id=str(uuid4()))


def test_request_round_trips_client_message_id():
    cmid = uuid4()
    req = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="hi", client_message_id=str(cmid))],
    )
    assert req.messages[0].client_message_id == cmid
```

**Step 2: Run test to verify it fails**

```
cd backend && pytest tests/api/agent/test_agent_request_schema.py -v
```
Expected: FAIL — `AgentMessage` rejects `client_message_id` (extra field).

**Step 3: Extend schemas**

Edit `backend/src/api/agent/execute.py` around line 100:

```python
from uuid import UUID

class AgentMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., max_length=32000)
    client_message_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Client-supplied idempotency key. Only honored for role='user'; "
            "ignored otherwise. Used to dedupe retries without a server-side SELECT."
        ),
    )

    @field_validator("client_message_id")
    @classmethod
    def _only_for_user(cls, v, info):
        if v is not None and info.data.get("role") != "user":
            raise ValueError("client_message_id only valid on user messages")
        return v
```

**Step 4: Run test to verify it passes**

```
pytest tests/api/agent/test_agent_request_schema.py -v
```
Expected: 3 passed.

**Step 5: Commit**

```
git add backend/src/api/agent/execute.py \
        backend/tests/api/agent/test_agent_request_schema.py
git commit -m "feat(api): accept client_message_id on user turns"
```

---

## Task 3: Replace dedup SELECT with `INSERT ... ON CONFLICT DO NOTHING`

**Files:**
- Modify: `backend/src/api/agent/jobs.py:201-343` (rewrite `_persist_thread_messages`)
- Test: `backend/tests/api/agent/test_persist_thread_messages.py`

**Step 1: Write the failing test**

```python
# backend/tests/api/agent/test_persist_thread_messages.py
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.api.agent.execute import AgentExecuteRequest, AgentMessage
from src.api.agent.jobs import (
    _persist_assistant_message,
    _persist_user_message,
)
from src.models.chat_message import ChatMessage, MessageRole


@pytest.mark.integration
async def test_duplicate_user_turn_is_idempotent(db_session, thread, user):
    cmid = uuid4()
    req = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="hello", client_message_id=str(cmid))],
        thread_id=str(thread.id),
    )

    await _persist_user_message(db_session, user, req)
    await _persist_user_message(db_session, user, req)  # retry

    count = await db_session.scalar(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.thread_id == thread.id,
            ChatMessage.role == MessageRole.USER,
        )
    )
    assert count == 1


@pytest.mark.integration
async def test_user_then_assistant_round_trip(db_session, thread, user):
    cmid = uuid4()
    req = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="ping", client_message_id=str(cmid))],
        thread_id=str(thread.id),
    )

    await _persist_user_message(db_session, user, req)
    await _persist_assistant_message(
        db_session, thread_id=str(thread.id), content="pong", model_name="gpt-5-mini",
        tool_executions_out=None,
    )

    rows = (
        await db_session.execute(
            select(ChatMessage.role).where(ChatMessage.thread_id == thread.id).order_by(
                ChatMessage.created_at
            )
        )
    ).all()
    assert [r[0] for r in rows] == [MessageRole.USER, MessageRole.ASSISTANT]
```

**Step 2: Run test to verify it fails**

```
cd backend && pytest tests/api/agent/test_persist_thread_messages.py -v
```
Expected: FAIL — `_persist_user_message` / `_persist_assistant_message` not defined.

**Step 3: Split `_persist_thread_messages` into two helpers**

In `backend/src/api/agent/jobs.py`:

1. Extract the thread-resolution block (lines 226-272) into `async def _resolve_thread(db, current_user, request) -> tuple[Thread, str]` that returns `(thread, conversation_id)` and commits the new thread row immediately so it has an id.
2. Replace the user-write block (lines 278-309) with:

```python
async def _persist_user_message(
    db: AsyncSession, current_user: User, request: Any
) -> bool:
    """Insert the latest user message. No-op on duplicate client_message_id."""
    from sqlalchemy.dialects.postgresql import insert

    from src.models.chat_message import ChatMessage, MessageRole

    last = next((m for m in reversed(request.messages) if m.role == "user"), None)
    if last is None or request.thread_id is None:
        return False

    stmt = (
        insert(ChatMessage)
        .values(
            thread_id=request.thread_id,
            user_id=current_user.id,
            role=MessageRole.USER,
            content=last.content,
            client_message_id=last.client_message_id,
        )
        .on_conflict_do_nothing(
            index_elements=["thread_id", "client_message_id"],
            index_where=ChatMessage.client_message_id.isnot(None),
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount == 1
```

3. Replace the assistant-write block (lines 311-339) with:

```python
async def _persist_assistant_message(
    db: AsyncSession,
    *,
    thread_id: str,
    content: str,
    model_name: Optional[str],
    tool_executions_out: Optional[list],
) -> None:
    from src.models.chat_message import ChatMessage, MessageRole
    from src.models.thread import Thread

    tool_exec_data = None
    if tool_executions_out:
        tool_exec_data = [
            {
                "id": te.id,
                "tool_name": te.tool_name,
                "tool_display_name": te.tool_display_name,
                "args": te.args,
                "status": te.status,
                "result": te.result,
                "error": te.error,
                "duration_ms": te.duration_ms,
            }
            for te in tool_executions_out
        ]

    db.add(
        ChatMessage(
            thread_id=thread_id,
            role=MessageRole.ASSISTANT,
            content=content,
            model_name=model_name,
            tool_executions=tool_exec_data,
        )
    )
    thread = await db.get(Thread, UUID(thread_id))
    if thread is not None:
        thread.message_count = (thread.message_count or 0) + 1
        thread.last_message_at = datetime.now(timezone.utc)
    await db.commit()
```

4. Leave the old `_persist_thread_messages` as a thin compatibility shim that calls the two helpers, so non-stream callsites (e.g. the confirm path at `jobs.py:629`) keep working without an immediate refactor. Mark it `# DEPRECATED — remove after streaming path migration` and have it await `_persist_user_message` then `_persist_assistant_message`.

**Step 4: Run integration test to verify pass**

```
pytest tests/api/agent/test_persist_thread_messages.py -v
```
Expected: 2 passed.

**Step 5: Sanity-check existing tests still pass**

```
pytest tests/api/agent -q
```
Expected: green.

**Step 6: Commit**

```
git add backend/src/api/agent/jobs.py \
        backend/tests/api/agent/test_persist_thread_messages.py
git commit -m "refactor(agent): split persist into idempotent user + assistant helpers"
```

---

## Task 4: Persist user message *before* LLM call

**Files:**
- Modify: `backend/src/api/agent/streaming.py:142+` and `backend/src/api/agent/execute.py:243+,316+` (callers that currently invoke `_persist_thread_messages` after the LLM completes)
- Test: `backend/tests/api/agent/test_stream_persistence_order.py`

**Step 1: Write the failing test**

```python
# backend/tests/api/agent/test_stream_persistence_order.py
import pytest
from sqlalchemy import select

from src.models.chat_message import ChatMessage, MessageRole


@pytest.mark.integration
async def test_user_message_persists_before_first_token(
    client, db_session, agent_stream_payload
):
    """A consumer that hangs up after the first SSE token must still find the user row in DB."""
    async with client.stream("POST", "/api/v1/agent/stream", json=agent_stream_payload) as r:
        async for line in r.aiter_lines():
            if line.startswith("data:"):
                break  # disconnect early

    rows = (
        await db_session.execute(
            select(ChatMessage.role).where(
                ChatMessage.thread_id == agent_stream_payload["thread_id"]
            )
        )
    ).all()
    assert MessageRole.USER in [r[0] for r in rows]
```

**Step 2: Run test to verify it fails**

```
pytest tests/api/agent/test_stream_persistence_order.py -v
```
Expected: FAIL — only the assistant row (or nothing) is found if the stream is aborted early, because the user row is currently written at the end.

**Step 3: Insert user-message persist at the top of the stream handler**

In `backend/src/api/agent/streaming.py` (and the matching block in `execute.py`), immediately after thread resolution and *before* the first LangGraph invocation, add:

```python
thread, conversation_id = await _resolve_thread(db, current_user, request_body)
if thread is not None:
    request_body.thread_id = str(thread.id)
    await _persist_user_message(db, current_user, request_body)
```

Then remove the user-write side effect from the post-stream `_persist_thread_messages` call so it only writes the assistant row going forward.

**Step 4: Run test to verify it passes**

```
pytest tests/api/agent/test_stream_persistence_order.py -v
```
Expected: PASS.

**Step 5: Commit**

```
git add backend/src/api/agent/streaming.py \
        backend/src/api/agent/execute.py \
        backend/tests/api/agent/test_stream_persistence_order.py
git commit -m "perf(agent): persist user turn before LLM call"
```

---

## Task 5: Move assistant persistence to a background task

**Files:**
- Modify: `backend/src/api/agent/streaming.py:142+` (use FastAPI `BackgroundTasks`)
- Modify: `backend/src/api/agent/jobs.py` (background runner already exists for job mode; extend to enqueue the persist task)
- Test: `backend/tests/api/agent/test_stream_response_latency.py`

**Step 1: Write the failing test**

```python
# backend/tests/api/agent/test_stream_response_latency.py
import asyncio
import time

import pytest


@pytest.mark.integration
async def test_done_event_does_not_wait_on_commit(client, agent_stream_payload, slow_db):
    """slow_db fixture forces ChatMessage commits to take >=500ms.

    The stream must still close in well under 500ms because assistant persistence
    is now off the response path.
    """
    t0 = time.perf_counter()
    async with client.stream("POST", "/api/v1/agent/stream", json=agent_stream_payload) as r:
        async for line in r.aiter_lines():
            if "event: done" in line:
                break
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.25, f"stream blocked on commit: {elapsed:.3f}s"

    # And the row eventually shows up.
    await asyncio.sleep(0.75)
    # ... (assert assistant row exists)
```

**Step 2: Run test to verify it fails**

```
pytest tests/api/agent/test_stream_response_latency.py -v
```
Expected: FAIL — current code awaits `_persist_thread_messages` before yielding `done`.

**Step 3: Use FastAPI BackgroundTasks**

In the stream endpoint signature add `background_tasks: BackgroundTasks`, then after the final token:

```python
background_tasks.add_task(
    _persist_assistant_message_safe,
    thread_id=str(thread.id),
    content=assistant_content,
    model_name=request_body.model,
    tool_executions_out=tool_executions_out,
)
```

`_persist_assistant_message_safe` opens its own `AsyncSessionLocal()` (mirroring the DraftGenerationService pattern noted in CLAUDE.md), calls `_persist_assistant_message`, and logs+swallows any exception so a background failure can't crash the worker. Log line must include `thread_id` for triage.

**Step 4: Run test to verify it passes**

```
pytest tests/api/agent/test_stream_response_latency.py -v
```
Expected: PASS.

**Step 5: Update Prometheus metric**

Add a `Counter("agent_assistant_persist_failures_total")` and bump it inside the exception branch of `_persist_assistant_message_safe`. Surface in `backend/src/services/agent/observability.py` alongside `agent_tool_calls_total`.

**Step 6: Commit**

```
git add backend/src/api/agent/streaming.py \
        backend/src/api/agent/jobs.py \
        backend/src/services/agent/observability.py \
        backend/tests/api/agent/test_stream_response_latency.py
git commit -m "perf(agent): persist assistant row in background task"
```

---

## Task 6: Python CLI sends `client_message_id`

**Files:**
- Modify: `backend/src/cli/agent_api_client.py` (add UUID to every `messages[].` user entry)
- Modify: `backend/src/cli/agent_chat_cli.py:69-82` (no schema change, just call-site)
- Test: `backend/tests/cli/test_agent_api_client_client_message_id.py`

**Step 1: Write the failing test**

```python
# backend/tests/cli/test_agent_api_client_client_message_id.py
from uuid import UUID

import pytest

from src.cli.agent_api_client import build_execute_payload


def test_user_message_gets_uuid():
    payload = build_execute_payload(messages=[{"role": "user", "content": "hi"}])
    cmid = payload["messages"][0]["client_message_id"]
    UUID(cmid)  # must parse


def test_assistant_message_has_no_uuid():
    payload = build_execute_payload(
        messages=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hey"},
        ]
    )
    assert "client_message_id" not in payload["messages"][1]
```

**Step 2: Run test to verify it fails**

```
cd backend && pytest tests/cli/test_agent_api_client_client_message_id.py -v
```
Expected: FAIL — helper does not exist (or doesn't attach UUID).

**Step 3: Implement the helper**

Add `build_execute_payload(messages, **rest)` to `agent_api_client.py` that injects `client_message_id=str(uuid4())` onto every user message lacking one, and reuse it from both the streaming and execute call sites in `agent_chat_cli.py`.

**Step 4: Run test to verify it passes**

```
pytest tests/cli/test_agent_api_client_client_message_id.py -v
```
Expected: PASS.

**Step 5: Commit**

```
git add backend/src/cli/agent_api_client.py \
        backend/src/cli/agent_chat_cli.py \
        backend/tests/cli/test_agent_api_client_client_message_id.py
git commit -m "feat(cli-py): send client_message_id on user turns"
```

---

## Task 7: Node CLI sends `client_message_id`

**Files:**
- Modify: `frontend/cli/stream.ts:178-209` (the `streamAgent` body builder)
- Test: `frontend/cli/__tests__/stream.client-message-id.test.ts`

**Step 1: Write the failing test (vitest)**

```ts
// frontend/cli/__tests__/stream.client-message-id.test.ts
import { describe, it, expect, vi } from 'vitest';
import { streamAgent } from '../stream';

describe('streamAgent', () => {
  it('sends a UUID v4 client_message_id on the user message', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response('', { status: 200 }));
    const gen = streamAgent({ message: 'hi', config: { thread_id: null } }, { fetchFn: fetchSpy as any });
    await gen.next();
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body.messages[0].role).toBe('user');
    expect(body.messages[0].client_message_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    );
  });
});
```

**Step 2: Run test to verify it fails**

```
cd frontend && pnpm vitest run cli/__tests__/stream.client-message-id.test.ts
```
Expected: FAIL — `client_message_id` missing on the body.

**Step 3: Add UUID to the request body**

In `frontend/cli/stream.ts:193`, change:

```ts
messages: [{ role: 'user', content: message }],
```
to:
```ts
messages: [{ role: 'user', content: message, client_message_id: crypto.randomUUID() }],
```

**Step 4: Run test to verify it passes**

```
pnpm vitest run cli/__tests__/stream.client-message-id.test.ts
```
Expected: PASS.

**Step 5: Commit**

```
git add frontend/cli/stream.ts \
        frontend/cli/__tests__/stream.client-message-id.test.ts
git commit -m "feat(cli-node): attach client_message_id to user turns"
```

---

## Task 8: Node CLI append-only JSONL message cache

**Files:**
- Create: `frontend/cli/services/messageStore.ts`
- Modify: `frontend/cli/stream.ts` (write user+assistant pair after stream end)
- Modify: `frontend/cli/services/threads.ts` (read local JSONL on `/thread <id>`; fall back to server)
- Test: `frontend/cli/__tests__/messageStore.test.ts`

**Step 1: Write the failing test**

```ts
// frontend/cli/__tests__/messageStore.test.ts
import { mkdtempSync, readFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { appendTurn, loadMessages } from '../services/messageStore';

let dir: string;
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'nous-cli-'));
  process.env.NOUS_CONFIG_DIR = dir;
});

describe('messageStore', () => {
  it('appends one JSONL line per message and reads back in order', () => {
    appendTurn('t-1', {
      user: { content: 'hi', client_message_id: 'abc' },
      assistant: { content: 'hey', model: 'gpt-5-mini' },
      ended_at: '2026-05-13T00:00:00Z',
    });
    appendTurn('t-1', {
      user: { content: 'and?', client_message_id: 'def' },
      assistant: { content: 'cool', model: 'gpt-5-mini' },
      ended_at: '2026-05-13T00:01:00Z',
    });

    const msgs = loadMessages('t-1');
    expect(msgs.map((m) => m.role)).toEqual(['user', 'assistant', 'user', 'assistant']);
    expect(msgs[2].content).toBe('and?');

    const raw = readFileSync(join(dir, 'threads', 't-1.jsonl'), 'utf-8').trim().split('\n');
    expect(raw).toHaveLength(4);
  });

  it('returns [] when no cache exists', () => {
    expect(loadMessages('missing')).toEqual([]);
  });
});
```

**Step 2: Run test to verify it fails**

```
pnpm vitest run cli/__tests__/messageStore.test.ts
```
Expected: FAIL — module not found.

**Step 3: Implement `messageStore.ts`**

```ts
// frontend/cli/services/messageStore.ts
import { appendFileSync, existsSync, mkdirSync, readFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

export interface CachedMessage {
  role: 'user' | 'assistant';
  content: string;
  model?: string;
  client_message_id?: string;
  ended_at: string;
}

export interface TurnInput {
  user: { content: string; client_message_id: string };
  assistant: { content: string; model?: string };
  ended_at: string;
}

function configDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), '.nous');
}

function threadFile(id: string): string {
  return path.join(configDir(), 'threads', `${id}.jsonl`);
}

export function appendTurn(threadId: string, turn: TurnInput): void {
  const file = threadFile(threadId);
  const dir = path.dirname(file);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const userLine: CachedMessage = {
    role: 'user',
    content: turn.user.content,
    client_message_id: turn.user.client_message_id,
    ended_at: turn.ended_at,
  };
  const asstLine: CachedMessage = {
    role: 'assistant',
    content: turn.assistant.content,
    model: turn.assistant.model,
    ended_at: turn.ended_at,
  };
  appendFileSync(file, JSON.stringify(userLine) + '\n' + JSON.stringify(asstLine) + '\n', 'utf-8');
}

export function loadMessages(threadId: string): CachedMessage[] {
  const file = threadFile(threadId);
  if (!existsSync(file)) return [];
  return readFileSync(file, 'utf-8')
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as CachedMessage);
}
```

**Step 4: Wire the writer**

In `frontend/cli/stream.ts` after the `done` event is consumed and `threadId` is known, call `appendTurn(threadId, …)` with the accumulated user content + assistant content + ISO timestamp.

**Step 5: Wire the reader**

In `frontend/cli/services/threads.ts` (the `/thread <id>` handler):

1. `const local = loadMessages(id);`
2. Look up `last_message_at` in the registry (`threadStore.getThread(id)`).
3. If `local.length > 0` and registry `last_message_at` matches the server-reported `last_message_at` (from a `HEAD`-style ping or a cheap `GET /threads/{id}?since=...`), use local immediately.
4. Otherwise call `GET /threads/{id}/messages?since=<latest local ended_at>` to fetch the delta and append to the cache before render.

**Step 6: Run tests to verify they pass**

```
pnpm vitest run cli/__tests__/messageStore.test.ts
```
Expected: PASS (plus any existing CLI tests still green).

**Step 7: Commit**

```
git add frontend/cli/services/messageStore.ts \
        frontend/cli/stream.ts \
        frontend/cli/services/threads.ts \
        frontend/cli/__tests__/messageStore.test.ts
git commit -m "perf(cli-node): append-only JSONL message cache per thread"
```

---

## Task 9: Add `?since=` query param to `GET /threads/{id}/messages`

**Files:**
- Modify: `backend/src/api/threads/messages.py` (or whichever module owns the route — verify with `grep -rn '/threads/{thread_id}/messages' backend/src/api`)
- Test: `backend/tests/api/threads/test_messages_since_filter.py`

**Step 1: Write the failing test**

```python
# backend/tests/api/threads/test_messages_since_filter.py
from datetime import timedelta

import pytest


@pytest.mark.integration
async def test_since_filter_returns_only_newer(client, thread_with_messages):
    cutoff = thread_with_messages.messages[0].created_at + timedelta(seconds=1)
    r = await client.get(
        f"/api/v1/threads/{thread_with_messages.id}/messages",
        params={"since": cutoff.isoformat()},
    )
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()["data"]]
    assert thread_with_messages.messages[0].id not in ids
    assert thread_with_messages.messages[-1].id in ids
```

**Step 2: Run test to verify it fails**

```
cd backend && pytest tests/api/threads/test_messages_since_filter.py -v
```
Expected: FAIL — param not supported.

**Step 3: Add `since: Optional[datetime] = Query(None)` to the route**

Filter the SQL with `ChatMessage.created_at > since` when provided.

**Step 4: Run test to verify it passes**

Expected: PASS.

**Step 5: Commit**

```
git add backend/src/api/threads/messages.py \
        backend/tests/api/threads/test_messages_since_filter.py
git commit -m "feat(threads): support ?since= delta fetch for messages"
```

---

## Task 10: Verification & PR

**Step 1: Full backend suite**

```
cd backend && pytest -q
```
Expected: green.

**Step 2: Full frontend CLI suite**

```
cd frontend && pnpm vitest run cli
```
Expected: green.

**Step 3: Lint + types**

```
cd backend && ruff check src tests && black --check src tests
cd frontend && pnpm lint && pnpm type-check
```
Expected: green.

**Step 4: Manual smoke test**

1. `docker compose -f docker-compose.development.yml up -d`
2. Run `cd backend && uvicorn src.main:app --reload --port 8000`
3. In another terminal: `cd frontend && pnpm cli` and send 3 messages in a row, then `/thread <id>` to confirm instant load from JSONL.
4. Kill+restart the CLI mid-stream; verify the user row is in Postgres (`psql ... -c "SELECT role, client_message_id FROM chat_messages ORDER BY created_at DESC LIMIT 5"`).

**Step 5: Open PR**

Branch: `feat/agent-persist-perf` → target `develop`. PR body covers:
- Latency wins (background assistant persist, user persist front-loaded).
- Correctness fix (replace 60s window dedup with idempotent UUID).
- Local CLI cache + delta fetch.
- Migration note: `alembic upgrade head` required; index built CONCURRENTLY.
- Rollback: previous revision is `u9a0b1c2d3e4`; downgrade safe.

---

## Remember
- Run only the tests in the file you just touched between steps; full suite at Task 10.
- Background task failures must increment `agent_assistant_persist_failures_total` so the loss window is observable.
- Do NOT remove the dedup index `ix_chat_messages_thread_user_role_created` in this PR — the deprecated shim still uses the SELECT path for the confirm handler. A follow-up PR can retire both once the confirm path is migrated.
