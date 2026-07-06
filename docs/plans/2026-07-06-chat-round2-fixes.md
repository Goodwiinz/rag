# /chat Round-2 Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the 10 verified findings from the 2026-07-06 round-2 /chat deep audit, grouped into 4 independently-shippable PRs (batches A–D).

**Architecture:** Four independent batches, each its own branch/PR off `develop`. **A** (backend confirm-stream data loss) and **B** (frontend reload regression) are highest value. **C** (backend authorization gaps — not reachable from the /chat UI, but real vulns) is security-scoped. **D** (frontend a11y + a perf dedup) is low-risk polish. Each batch is self-contained; do them in order but they don't depend on each other, so you may stop after any batch.

**Tech Stack:** Backend = FastAPI + SQLAlchemy async + structlog, tested with pytest/pytest-asyncio (`backend/tests/`). Frontend = Next.js 15 / React 18 / Zustand, tested with vitest (`frontend/`). Run frontend npm/npx from `frontend/`; run pytest from `backend/` (venv at `backend/.venv/`, or main-repo venv per project memory).

**Worktree/branch:** Fresh git worktree per the executor's isolation. One branch **per batch** (`fix/chat-confirm-stream-persistence`, `fix/chat-tool-result-reload`, `fix/chat-authz-gaps`, `fix/chat-a11y-cleanup`), each PR targeting `develop`, opened as **draft**. Safe-ops: never `git pull/checkout/reset` other branches, stage path-explicitly, `git fetch origin` before push. End commits with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. End PR bodies with the Claude Code footer.

**Verification baseline (repo gotchas):**
- Frontend: `npm run validate` is red pre-existing — verify with `npx tsc --noEmit` + targeted `npx vitest run <file>`.
- Backend: run targeted `pytest backend/tests/unit/api/<file> -v`. mypy strict, Black 88, isort.
- Never hardcode hex colors (none needed here).

---

## Findings recap (read before starting each batch)

All 10 confirmed by an adversarial verification pass. Full detail in memory `project_chat_deep_audit_round2.md`.

- **A1 (CRITICAL):** `stream_confirm_event_generator` disconnect branch (`backend/src/api/agent/streaming.py:889-899`) never persists the assistant row — unlike the main stream (`:504-546`). A destructive HITL tool commits, tab closes → no assistant message, no idempotency key.
- **A2 (IMPORTANT):** confirm loop (`streaming.py:834-838`) doesn't use `_graph_events_with_keepalive` — long silent resume → proxy cuts connection, frontend hangs silently.
- **B (IMPORTANT):** `mapDbToolExecutions` (`frontend/src/components/chat/shared/cloudMessageView.ts:75-79`) only reads `e.result` when it's a string, but backend persists it as a parsed object → successful-tool result summaries vanish on reload.
- **C1 (IMPORTANT, direct-API only):** `create_message` attaches `attachment_ids` with no Document ownership check (`chat_service.py:829-835`); response leaks foreign doc title/mime.
- **C2 (IMPORTANT, direct-API only):** `get_message` (`chat_service.py:954-984`) omits `Thread.is_deleted` filter → messages of soft-deleted threads stay accessible via GET/PATCH/DELETE.
- **C3 (IMPORTANT, direct-API only):** `list_messages` `before_id` lookup (`chat_service.py:1017-1023`) unscoped by thread → cross-tenant timestamp oracle + silently-wrong paging.
- **D1 (IMPORTANT):** `ChatInput` attachments never cleared on send (`ChatInput.tsx`) → stale chips + blob-URL leak.
- **D2 (IMPORTANT, a11y):** mobile drawer `aria-modal` without focus trap / `inert` (`page.tsx:794-861`).
- **D3 (IMPORTANT, a11y):** HITL Approve/Deny leaves focus on `<body>`; no restore to composer (`page.tsx:807-811`).
- **D4 (PERF):** double message fetch on first thread visit (`useChatSession.ts:581-630` `getThread` + store `loadMessages`).

---

# BATCH A — Confirm-stream data loss (branch `fix/chat-confirm-stream-persistence`)

### Task A1: Persist the partial assistant answer on confirm-stream disconnect

**Files:**
- Modify: `backend/src/api/agent/streaming.py` (`stream_confirm_event_generator`, ~lines 830-899)
- Test: `backend/tests/unit/api/test_agent_streaming_confirm_disconnect.py` (extend existing)

**Step 1: Write the failing test**

The existing test (`test_confirm_stream_acloses_graph_on_disconnect`) only asserts the iterator is aclosed. Add a second test asserting the partial answer is persisted. The disconnect graph already yields one `on_chat_model_stream` chunk with content `"x"` before disconnect — so after the fix, `_persist_assistant_message_safe` must be called with `content="x", stopped=True`.

Add to the same file:

```python
@pytest.mark.asyncio
async def test_confirm_stream_persists_partial_on_disconnect():
    """A destructive HITL tool may have already committed; the partial
    assistant answer streamed before the disconnect must be persisted
    (stopped=True), mirroring the main stream's disconnect branch."""
    from src.api.agent.streaming import stream_confirm_event_generator

    graph = _DisconnectGraph()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    body = SimpleNamespace(thread_id="thread-789", confirmed=True, model="")
    current_user = Mock(id="user-1", organization_id="org-1")

    persist = AsyncMock(return_value="assistant-row-1")
    with (
        patch("src.services.agent.observability.configure_langsmith", return_value=None),
        patch("src.services.agent.checkpointer.get_checkpointer", new=AsyncMock(return_value=object())),
        patch("src.services.agent.memory.get_memory_store", new=AsyncMock(return_value=object())),
        patch("src.services.agent.graph.compile_agent_graph", return_value=graph),
        patch("src.api.agent.streaming._jobs_mod._persist_assistant_message_safe", new=persist),
        patch("src.api.agent.streaming._latest_user_client_message_id", new=AsyncMock(return_value="user-cmid-1")),
        patch("src.api.agent.streaming.AsyncSessionLocal", return_value=AsyncMock()),
    ):
        async for _ in stream_confirm_event_generator(body, request, current_user):
            pass

    persist.assert_awaited_once()
    kwargs = persist.await_args.kwargs
    assert kwargs["content"] == "x"
    assert kwargs["stopped"] is True
    assert kwargs["thread_id"] == "thread-789"
    # idempotency key derived from the original user turn's client_message_id
    assert kwargs["client_message_id"] is not None
```

Note for implementer: confirm the patch target `src.api.agent.streaming._jobs_mod._persist_assistant_message_safe` matches how the module references it (the code calls `_jobs_mod._persist_assistant_message_safe`). Also confirm `_latest_user_client_message_id` is imported into the streaming module namespace (it's used at `:943`); patch it where it's looked up.

**Step 2: Run to verify it fails**

Run (from repo root): `pytest backend/tests/unit/api/test_agent_streaming_confirm_disconnect.py -v`
Expected: new test FAILS (`persist.assert_awaited_once()` — nothing is persisted today); existing test still PASSES.

**Step 3: Implement — accumulate tokens + persist on disconnect**

In `stream_confirm_event_generator`:

(a) Before the loop (near line 833, alongside `client_disconnected = False`), add an accumulator:

```python
        client_disconnected = False
        # Accumulate user-facing tokens so a mid-resume disconnect can persist
        # the partial answer server-side (a resumed turn may have already
        # committed a destructive tool — losing the assistant row entirely
        # leaves the thread with a confirm action and no record of the result).
        streamed_parts: list[str] = []
```

(b) In the `on_chat_model_stream` branch (line 843-849), capture the chunk into the accumulator, right where it yields the token:

```python
                if kind == "on_chat_model_stream":
                    if not _is_user_facing_token_event(event):
                        continue
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        streamed_parts.append(chunk.content)
                        yield f"event: token\ndata: {_json.dumps({'content': chunk.content})}\n\n"
                        tokens_emitted = True
```

(c) Replace the disconnect branch (lines 892-899) so it persists the partial, mirroring the main stream (`:517-545`). Derive `assistant_cmid` the same way the post-loop path does (`:941-958`):

```python
        if client_disconnected:
            with contextlib.suppress(Exception):
                await confirm_event_iter.aclose()
            logger.info(
                "SSE confirm client disconnected; cancelled resumed run for thread %s",
                request_body.thread_id,
            )
            partial = "".join(streamed_parts)
            if partial:
                disconnect_cmid: Optional[str] = None
                try:
                    user_cmid = await _latest_user_client_message_id(
                        db, request_body.thread_id
                    )
                    if user_cmid is not None:
                        disconnect_cmid = str(
                            _uuid.uuid5(
                                _uuid.NAMESPACE_URL, f"nous-assistant:{user_cmid}"
                            )
                        )
                except Exception:
                    logger.warning(
                        "Failed to derive assistant client_message_id for "
                        "disconnected resume of thread %s; assistant row will "
                        "not be idempotent",
                        request_body.thread_id,
                        exc_info=True,
                    )
                stop_kwargs = dict(
                    thread_id=request_body.thread_id,
                    content=partial,
                    model_name=getattr(request_body, "model", "") or None,
                    tool_executions_out=None,
                    retrieved_contexts=None,
                    latency_ms=None,
                    stopped=True,
                    client_message_id=disconnect_cmid,
                    token_usage=(
                        {
                            "input_tokens": turn_input_tokens,
                            "output_tokens": turn_output_tokens,
                        }
                        if (turn_input_tokens or turn_output_tokens)
                        else None
                    ),
                )
                if background_tasks is not None:
                    background_tasks.add_task(
                        _jobs_mod._persist_assistant_message_safe, **stop_kwargs
                    )
                else:
                    await _jobs_mod._persist_assistant_message_safe(**stop_kwargs)
            return
```

Note: this deliberately persists `tool_executions_out=None` — reading them needs a checkpoint fetch on a path that must stay cheap (client already hung up), exactly as the main stream comments at `:528-530`. Add a matching `# ponytail:` note. Confirm `_uuid` and `Optional` are already imported in the module (they are — used at `:941-951` and elsewhere).

**Step 4: Run to verify it passes**

Run: `pytest backend/tests/unit/api/test_agent_streaming_confirm_disconnect.py -v`
Expected: both tests PASS.

**Step 5: Commit**

```bash
git add backend/src/api/agent/streaming.py backend/tests/unit/api/test_agent_streaming_confirm_disconnect.py
git commit -m "fix(chat): persist partial assistant answer on confirm-stream disconnect"
```

---

### Task A2: Add keepalive to the confirm stream

**Files:**
- Modify: `backend/src/api/agent/streaming.py` (`stream_confirm_event_generator` loop, ~lines 834-887)
- Test: `backend/tests/unit/api/test_agent_streaming_confirm_keepalive.py` (create)

**Step 1: Write the failing test**

Model it on how the main stream emits `event: heartbeat`. The keepalive helper yields a `{"type": "keepalive"}` item when the graph is silent for `_SSE_KEEPALIVE_SECONDS`. Simplest deterministic test: a graph whose `__anext__` first returns a keepalive-triggering gap is hard to simulate on a timer, so instead assert structurally that the confirm generator routes its events through `_graph_events_with_keepalive` and forwards a `keepalive` item as an `event: heartbeat` frame. Use a fake keepalive-wrapper.

```python
"""Confirm stream must emit heartbeat frames during long silent resume phases,
like the main /stream path — otherwise a proxy idle-timeout cuts the connection
with no done/error and the client hangs."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest


class _SilentThenDoneGraph:
    def __init__(self):
        self._items = iter([
            {"event": "on_chat_model_stream", "name": "llm_node",
             "metadata": {"langgraph_node": "llm_node"},
             "data": {"chunk": SimpleNamespace(content="hi")}},
        ])
    def astream_events(self, *a, **k):
        return self
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration
    async def aclose(self):
        pass
    async def aget_state(self, config):
        return SimpleNamespace(
            values={"user_id": "user-1", "page_context": {}, "messages": [
                SimpleNamespace(type="ai", content="hi")], "tool_executions": []},
            tasks=(),
        )


@pytest.mark.asyncio
async def test_confirm_stream_emits_heartbeat_from_keepalive():
    import src.api.agent.streaming as st

    async def fake_keepalive(event_iter, request):
        # One keepalive, then forward the real event, then stop.
        yield {"type": "keepalive", "elapsed_ms": 123}
        async for e in event_iter:
            yield {"type": "event", "event": e}

    graph = _SilentThenDoneGraph()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(thread_id="t-1", confirmed=True, model="")
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch.object(st, "_graph_events_with_keepalive", fake_keepalive),
        patch("src.services.agent.observability.configure_langsmith", return_value=None),
        patch("src.services.agent.checkpointer.get_checkpointer", new=AsyncMock(return_value=object())),
        patch("src.services.agent.memory.get_memory_store", new=AsyncMock(return_value=object())),
        patch("src.services.agent.graph.compile_agent_graph", return_value=graph),
        patch("src.api.agent.streaming._jobs_mod._persist_assistant_message_safe", new=AsyncMock(return_value="a1")),
        patch("src.api.agent.streaming._latest_user_client_message_id", new=AsyncMock(return_value=None)),
        patch("src.api.agent.streaming.AsyncSessionLocal", return_value=AsyncMock()),
    ):
        events = [e async for e in stream_confirm_event_generator_ref(st, body, request, current_user)]

    assert any(e.startswith("event: heartbeat") for e in events)


def stream_confirm_event_generator_ref(st, *args):
    return st.stream_confirm_event_generator(*args)
```

(The `_ref` indirection is just to bind the patched module symbol; the implementer may inline it.)

**Step 2: Run to verify it fails**

Run: `pytest backend/tests/unit/api/test_agent_streaming_confirm_keepalive.py -v`
Expected: FAIL — today the confirm loop iterates the raw graph iterator, never routes through `_graph_events_with_keepalive`, so no `heartbeat` frame is emitted.

**Step 3: Implement — wrap the confirm loop in the keepalive helper**

Rewrite the confirm loop (lines 834-887) to mirror the main stream's structure (`:405-419`). The current `async for event in confirm_event_iter:` becomes `async for item in _graph_events_with_keepalive(confirm_event_iter, request):` with the disconnect/keepalive/event dispatch:

```python
        stream_started_at = time.monotonic()
        async with asyncio.timeout(300):
            async for item in _graph_events_with_keepalive(
                confirm_event_iter, request
            ):
                if item["type"] == "disconnect":
                    client_disconnected = True
                    break
                if item["type"] == "keepalive":
                    elapsed_ms = int((time.monotonic() - stream_started_at) * 1000)
                    yield (
                        "event: heartbeat\n"
                        f"data: {_json.dumps({'elapsed_ms': elapsed_ms})}\n\n"
                    )
                    continue
                event = item["event"]

                kind = event.get("event", "")
                name = event.get("name", "")
                # ... existing on_chat_model_stream / on_tool_* / plan / reflection
                #     branches unchanged, now operating on `event` ...
```

Delete the now-redundant inline `if await request.is_disconnected():` check (the helper handles disconnect and yields the `disconnect` sentinel). Keep the `streamed_parts.append` from Task A1 inside the token branch. Confirm `time` is imported (it is — used at `:413`). Ensure `stream_started_at` doesn't collide with an existing name in this function (it doesn't; the main stream uses its own).

**Step 4: Run both confirm tests**

Run: `pytest backend/tests/unit/api/test_agent_streaming_confirm_disconnect.py backend/tests/unit/api/test_agent_streaming_confirm_keepalive.py -v`
Expected: all PASS. Also run the existing confirm suite to catch regressions: `pytest backend/tests/unit/api/ -k confirm -v`.

**Step 5: Commit + push + draft PR**

```bash
git add backend/src/api/agent/streaming.py backend/tests/unit/api/test_agent_streaming_confirm_keepalive.py
git commit -m "fix(chat): add SSE keepalive to the HITL confirm stream"
git fetch origin
git push -u origin fix/chat-confirm-stream-persistence
gh pr create --draft --base develop --title "fix(chat): confirm-stream disconnect persistence + keepalive" --body "..."
```
PR body: summarize A1+A2 from the findings recap, note the accepted limitation (disconnect persist carries no tool_executions/plan — same cheap-path tradeoff as the main stream). End with the Claude Code footer.

---

# BATCH B — Tool-result reload regression (branch `fix/chat-tool-result-reload`)

### Task B1: Stringify object tool results so summaries survive reload

**Files:**
- Modify: `frontend/src/components/chat/shared/cloudMessageView.ts` (lines 47-91)
- Test: `frontend/src/components/chat/shared/__tests__/cloudMessageView.toolResult.test.ts` (create; confirm dir — else colocate next to an existing shared test)

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from 'vitest';
import { mapDbToolExecutions } from '@/components/chat/shared/cloudMessageView';

describe('mapDbToolExecutions result summary', () => {
  it('summarizes an object result persisted by the backend', () => {
    const steps = mapDbToolExecutions([
      {
        tool_name: 'search_documents',
        status: 'success',
        // backend persists parsed JSON — an OBJECT, not a string
        result: { message: 'Found 3 relevant documents' },
      } as never,
    ]);
    expect(steps?.[0].resultSummary).toBe('Found 3 relevant documents');
  });

  it('still handles a string result (legacy rows / error field)', () => {
    const steps = mapDbToolExecutions([
      { tool_name: 't', status: 'success', result: 'plain text' } as never,
    ]);
    expect(steps?.[0].resultSummary).toBe('plain text');
  });

  it('leaves resultSummary undefined when there is no result', () => {
    const steps = mapDbToolExecutions([
      { tool_name: 't', status: 'success' } as never,
    ]);
    expect(steps?.[0].resultSummary).toBeUndefined();
  });
});
```

**Step 2: Run to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/chat/shared/__tests__/cloudMessageView.toolResult.test.ts`
Expected: first test FAILS (object result → `undefined` today).

**Step 3: Implement**

Make `summarizeToolResult` accept `unknown` and stringify objects internally (the lazier, single-point fix vs. stringifying at every call site):

```ts
export function summarizeToolResult(
  result: unknown
): string | undefined {
  if (result == null || result === '') return undefined;
  const raw = typeof result === 'string' ? result : JSON.stringify(result);
  try {
    const parsed: unknown = typeof result === 'string' ? JSON.parse(raw) : result;
    if (parsed && typeof parsed === 'object') {
      const obj = parsed as Record<string, unknown>;
      const msg = obj.error ?? obj.message ?? obj.summary;
      if (typeof msg === 'string' && msg.length > 0) return truncate(msg);
    }
  } catch {
    // not JSON — fall through to raw text
  }
  return truncate(raw);
}
```

Then simplify the caller in `mapDbToolExecutions` (lines 75-79) — pass `e.result` straight through:

```ts
    const resultSummary = e.error
      ? summarizeToolResult(e.error)
      : summarizeToolResult(e.result);
```

Check the `DbToolExecution.result` type — if it's typed `string | undefined`, widen it to `unknown` (or `Record<string, unknown> | string | null`) so `tsc` accepts passing the object. Grep for the interface (likely in the same file or a types file) and update it.

Also update the live-stream caller if needed: `useChatStreaming.ts` `onToolEnd` calls `summarizeToolResult(result)` with the SSE string — still valid under the widened signature, no change required. Verify with grep that no other caller breaks.

**Step 4: Run to verify it passes + type-check**

Run: `npx vitest run src/components/chat/shared/__tests__/cloudMessageView.toolResult.test.ts && npx tsc --noEmit`
Expected: PASS, no new type errors.

**Step 5: Commit + push + draft PR**

```bash
git add frontend/src/components/chat/shared/cloudMessageView.ts frontend/src/components/chat/shared/__tests__/cloudMessageView.toolResult.test.ts
git commit -m "fix(chat): preserve tool-result summaries across thread reload"
git fetch origin && git push -u origin fix/chat-tool-result-reload
gh pr create --draft --base develop --title "fix(chat): tool-result summaries vanish on reload" --body "..."
```

---

# BATCH C — Backend authorization gaps (branch `fix/chat-authz-gaps`)

> These are NOT reachable from the live /chat UI (verified: no `attachment_ids` sent, deleted threads leave the sidebar, `before_id` is always the user's own message). They are real backend IDOR/authz gaps exploitable via direct API calls. Ship as one security-scoped PR.

### Task C1: Ownership-check `attachment_ids` in create_message

**Files:**
- Modify: `backend/src/services/threads/chat_service.py` (`create_message`, lines 829-835)
- Test: `backend/tests/api/threads/` (create `test_message_attachment_ownership.py`)

**Step 1: Read the existing org-scoped Document lookup pattern**

Before writing code, grep for how documents are ownership-checked elsewhere: `grep -rn "organization_id" backend/src/services/documents/ | head`. Reuse that pattern (org filter on `Document`). Confirm the `Document` model's owning column (`organization_id`) and how the caller's org is available in `create_message` (from `user_id` → user's org, or via `thread.conversation.workspace`). Determine the correct scope: the CLAUDE.md rule is `organization_id`; the workspace owner is `Workspace.owner_id`. Use whichever the documents service uses for "can this user attach this doc" — most likely `Document.organization_id == <caller's org>`.

**Step 2: Write the failing test**

Write a service-level test: seed a document owned by org B, call `create_message` as a user in org A with that `document_id` in `attachment_ids`, assert either (a) the attachment is rejected/skipped (no `MessageAttachment` row) or (b) it raises. Pick the behavior that matches the documents service's convention (skip-with-log vs raise). Model setup on an existing `backend/tests/api/threads/` test's fixtures.

**Step 3: Implement**

Replace lines 829-835 with an ownership-filtered lookup:

```python
        # Handle attachments — only documents the caller's org owns may be
        # attached (else a guessed foreign doc UUID leaks its title/mime into
        # this thread via _format_message_response). Mirrors the org-scoping
        # rule every document query must follow.
        if data.attachment_ids:
            owned = await self._filter_owned_document_ids(
                data.attachment_ids, user_id
            )
            for doc_id in owned:
                self.db.add(
                    MessageAttachment(message_id=message.id, document_id=doc_id)
                )
```

Implement `_filter_owned_document_ids` as a small helper on the service that selects `Document.id` where `id IN attachment_ids AND <org scope for user_id>`, returning the surviving ids. Reuse the documents-service scoping expression found in Step 1 rather than inventing one. Log dropped ids at warning.

**Step 4: Run + type-check**

Run: `pytest backend/tests/api/threads/test_message_attachment_ownership.py -v`
Expected: PASS. Then `mypy backend/src/services/threads/chat_service.py` (or the project's mypy invocation) — clean.

**Step 5: Commit**

```bash
git add backend/src/services/threads/chat_service.py backend/tests/api/threads/test_message_attachment_ownership.py
git commit -m "fix(chat): reject foreign-org documents in message attachment_ids (IDOR)"
```

---

### Task C2: Filter soft-deleted threads in get_message

**Files:**
- Modify: `backend/src/services/threads/chat_service.py` (`get_message`, lines 958-984)
- Test: `backend/tests/api/threads/test_get_message_soft_deleted_thread.py` (create)

**Step 1: Write the failing test**

Seed a thread + message, soft-delete the thread (`thread.is_deleted = True`), call `get_message(message_id, user_id)`, assert it returns `None`. Add a companion assertion that a message in a live thread still returns.

**Step 2: Run to verify it fails**

Run: `pytest backend/tests/api/threads/test_get_message_soft_deleted_thread.py -v`
Expected: FAIL — currently returns the message.

**Step 3: Implement**

`get_message` loads `ChatMessage.thread` via `selectinload`; the cleanest guard is a post-load check (avoids a join that fights the selectinload). After the workspace-access check (line 979-982), add:

```python
        # A soft-deleted thread must revoke access to its individual messages —
        # every other read path filters Thread.is_deleted, get_message did not.
        if message.thread.is_deleted:
            return None
```

(Placing it as a Python check after load is correct because `selectinload(ChatMessage.thread)` already fetched the thread row including `is_deleted`. If the team prefers a SQL-level filter, add `.join(Thread).where(Thread.is_deleted == False)` to the statement instead — either is acceptable; the Python check is the smaller diff.)

**Step 4: Run to verify it passes**

Run: `pytest backend/tests/api/threads/test_get_message_soft_deleted_thread.py -v`
Expected: PASS. Also run any existing message GET/PATCH/DELETE route tests to confirm live-thread behavior unbroken: `pytest backend/tests/api/threads/ -v`.

**Step 5: Commit**

```bash
git add backend/src/services/threads/chat_service.py backend/tests/api/threads/test_get_message_soft_deleted_thread.py
git commit -m "fix(chat): revoke message access for soft-deleted threads"
```

---

### Task C3: Scope the before_id cursor lookup to the thread

**Files:**
- Modify: `backend/src/services/threads/chat_service.py` (`list_messages`, lines 1017-1023)
- Test: `backend/tests/api/threads/test_messages_before_id_scoping.py` (create)

**Step 1: Write the failing test**

Seed thread A (user's) and thread B (any). Grab a message id from thread B. Call `list_messages(thread_id=A.id, user_id, before_id=<B message id>)`. After the fix, the foreign `before_id` must NOT apply thread B's timestamp as a cutoff — assert the returned set for thread A is identical to calling without `before_id` (the foreign cursor is ignored because it doesn't belong to thread A). Contrast: a valid thread-A `before_id` still paginates correctly.

**Step 2: Run to verify it fails**

Run: `pytest backend/tests/api/threads/test_messages_before_id_scoping.py -v`
Expected: FAIL — today the foreign cursor's timestamp leaks in and filters thread A's results.

**Step 3: Implement**

Add the thread scope to the cursor lookup (line 1019):

```python
        if before_id:
            # Scope the cursor lookup to THIS thread — an unscoped id lookup let
            # a foreign message's timestamp drive pagination (cross-tenant
            # timestamp oracle + silently-wrong paging). A before_id that isn't
            # in this thread is simply ignored.
            before_stmt = select(ChatMessage).where(
                ChatMessage.id == before_id,
                ChatMessage.thread_id == thread_id,
            )
            before_result = await self.db.execute(before_stmt)
            before_msg = before_result.scalars().first()
            if before_msg:
                base_conditions.append(ChatMessage.created_at < before_msg.created_at)
```

**Step 4: Run to verify it passes**

Run: `pytest backend/tests/api/threads/test_messages_before_id_scoping.py backend/tests/api/threads/test_messages_order_param.py -v`
Expected: PASS (order_param test confirms normal pagination still works).

**Step 5: Commit + push + draft PR**

```bash
git add backend/src/services/threads/chat_service.py backend/tests/api/threads/test_messages_before_id_scoping.py
git commit -m "fix(chat): scope before_id pagination cursor to the thread"
git fetch origin && git push -u origin fix/chat-authz-gaps
gh pr create --draft --base develop --title "fix(chat): backend authorization gaps (attachment IDOR, soft-delete access, cursor scope)" --body "..."
```
PR body: state clearly these are direct-API-reachable authz gaps (not triggered by the /chat UI), one paragraph per C1/C2/C3. Footer.

---

# BATCH D — a11y + cleanup (branch `fix/chat-a11y-cleanup`)

### Task D1: Clear composer attachments on send

**Files:**
- Modify: `frontend/src/components/chat/ChatInput.tsx`

**Step 1: Implement (small, UI-state; test via a focused vitest if the component renders in jsdom, else rely on tsc + manual note)**

Add a `clearAttachments` that revokes image URLs and empties state, and call it in both submit paths (`handleComposerSubmit` after `onSubmit()`, and the Enter branch in `handleKeyDown` at line ~217-228 after `onSubmit()`):

```ts
  const clearAttachments = (): void => {
    setAttachments((prev) => {
      prev.forEach((a) => a.url && URL.revokeObjectURL(a.url));
      return [];
    });
  };
```

In `handleComposerSubmit`:
```ts
  const handleComposerSubmit = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    if (!isLoading && value.trim() && !isOverLimit) {
      onSubmit();
      clearAttachments();
    }
  };
```
And after the `onSubmit()` call in the Enter-key branch of `handleKeyDown` (line ~228), add `clearAttachments();` on the same guarded path (only when the message actually sends — mirror the existing `value.trim()`/`!isLoading` guard there; read lines 217-230 and match it exactly).

**Step 2: Verify**

If a `ChatInput` vitest exists, add a test that renders, calls addFiles (mock `URL.createObjectURL`/`revokeObjectURL` via `vi.stubGlobal`), submits, and asserts chips cleared + `revokeObjectURL` called. If jsdom can't render `ComposerPrimitive` (assistant-ui provider), skip the test and verify with `npx tsc --noEmit` only; note the manual-verification gap in the commit body. Do not fight the provider.

**Step 3: Commit**

```bash
git add frontend/src/components/chat/ChatInput.tsx
git commit -m "fix(chat): clear composer attachments and revoke blob URLs on send"
```

---

### Task D2 + D3: Focus trap on mobile drawer + restore focus after HITL

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

**Step 1: HITL focus restore (D3) — the smaller one first**

The effect at lines 807-811 focuses `approveRef` when a confirmation appears but never restores focus when it clears. Track the previous value and restore to the composer on the non-null→null transition:

```tsx
  const approveRef = useRef<HTMLButtonElement>(null);
  const prevPendingConfirmationRef = useRef<PendingConfirmation | null>(null);
  useEffect(() => {
    const had = prevPendingConfirmationRef.current;
    if (pendingConfirmation) {
      approveRef.current?.focus();
    } else if (had) {
      // Confirmation resolved — return focus to the composer instead of
      // dropping it to <body> (the Approve/Deny button just unmounted).
      chatInputRef.current?.focus();
    }
    prevPendingConfirmationRef.current = pendingConfirmation;
  }, [pendingConfirmation, chatInputRef]);
```

(Use the `PendingConfirmation` type already imported/derived in the file. If Batch A of round-1's `activeConfirmation` scoping has merged, key this off whatever drives the banner — but round-2 is independent of that PR, so `pendingConfirmation` is the safe reference; the executor should read the current file state and adapt.)

**Step 2: Mobile drawer focus trap (D2)**

The drawer (lines ~816-861, `role="dialog" aria-modal="true"`) has open-focus + Escape but no Tab wrap and no background `inert`. Add a Tab-wrap handler on the drawer container. Ponytail: a full focus-trap library is overkill — a keydown handler that wraps Tab/Shift+Tab at the drawer's focusable boundaries is ~15 lines and native:

```tsx
  const handleDrawerKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== 'Tab') return;
    const root = drawerRef.current;
    if (!root) return;
    const focusables = root.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
    );
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }, []);
```

Attach `onKeyDown={handleDrawerKeyDown}` to the `motion.div` drawer panel (the one with `ref={drawerRef}` at ~line 828) — merge with any existing `onKeyDown` (the Escape handler). If Escape lives on the same element, combine both into one handler. `drawerRef` already exists (line 828). Skipped: `inert` on background — the Tab-wrap alone satisfies the keyboard-trap requirement (WCAG 2.4.3/4.1.2); add `// ponytail:` noting `inert` on the main content is the fuller fix if screen-reader virtual-cursor escape is later reported.

**Step 3: Verify**

Run: `npx tsc --noEmit`
Expected: clean. If `ChatPage.auth.test.tsx` or similar renders the page, run it to catch breakage: `npx vitest run src/components/chat/__tests__/`. These are a11y behaviors hard to assert in jsdom (focus + Tab); rely on tsc + existing page tests, and note manual verification (keyboard-Tab the drawer; Approve a HITL prompt and confirm focus returns to composer) in the PR body.

**Step 4: Commit**

```bash
git add "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "fix(chat): trap focus in mobile drawer and restore focus after HITL confirm"
```

---

### Task D4: De-duplicate the first-visit thread message fetch

**Files:**
- Modify: `frontend/src/hooks/chat/useChatSession.ts` (lazy-load effect, ~lines 581-630)

**Step 1: Understand both fetch paths first**

Read `useChatSession.ts:581-630` (the `getThread` lazy effect) and `chat-store.ts:454-463` (`setCurrentThread` → `loadMessages`). Both fire on thread select; both fetch the same thread's messages into two different caches. The store's `loadMessages` is the canonical one (feeds `state.messages[threadId]`); the `getThread` effect populates the local `conversations[].messages` React cache.

**Step 2: Decide the lazy fix**

The lazy, lowest-risk change: guard the `getThread` effect so it skips when the store already has (or is loading) messages for that thread. The store exposes `state.messages[threadId]` and the pagination/loading state. Add a check at the top of the effect body: if `useChatStore.getState().messages[activeConversationId]?.length` is already populated (or `loadingOlder`/an in-flight load flag is set), return without calling `getThread`.

Do NOT rip out the effect entirely — `displayedMessages` currently merges both caches via `selectDisplayedMessages`, and removing one source risks a regression in the merge. The guard is the smaller, safer diff. Add a `// ponytail:` note that the fuller fix is to feed `displayedMessages` solely from the store and delete the local `conversations[].messages` cache.

**Step 3: Implement + verify**

Implement the guard, then:
Run: `npx tsc --noEmit && npx vitest run src/hooks/__tests__/`
Expected: clean, existing session tests pass. Manually verify (or via network panel) that opening a thread now fires one messages fetch, not two — note this in the PR body since it's hard to unit-assert.

**Step 4: Commit + push + draft PR**

```bash
git add frontend/src/hooks/chat/useChatSession.ts
git commit -m "perf(chat): skip redundant getThread fetch when store already has messages"
git fetch origin && git push -u origin fix/chat-a11y-cleanup
gh pr create --draft --base develop --title "fix(chat): composer attachment cleanup, drawer/HITL focus, dedupe thread fetch" --body "..."
```

---

## Final verification (per batch, before each PR)

- **Backend batches (A, C):** `pytest backend/tests/unit/api/ -k "confirm or stream" -v` (A) / `pytest backend/tests/api/threads/ -v` (C). mypy on changed files.
- **Frontend batches (B, D):** `npx tsc --noEmit` + the targeted vitest files listed in each task. Do NOT run `npm run validate` (red pre-existing).
- Each PR is **draft**, base `develop`, body per the notes above, Claude Code footer.

## Suggested execution order

A → B → C → D (value-descending). Each is independent; safe to stop after any batch. Batch A is the priority — it's silent, unrecoverable data loss after a destructive tool runs.
