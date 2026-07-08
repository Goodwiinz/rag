# Chat Streaming Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the verified gaps between the NOUS chat implementation and 2024-2026 production best practices: lock in HITL audit + nested-confirmation behavior with regression tests, and add resumable SSE streams so a refreshed client reattaches to an in-flight agent run.

**Architecture:** The deep-research findings were checked against the code first. Three of the four researched areas are already implemented (HITL audit table with post-interrupt writes; nested-confirmation re-emission wired end-to-end; SSE ops headers/keepalive/disconnect-persistence). Phase 1 therefore pins those behaviors with tests so they can't regress. Phase 2 is the one real build: sequence-numbered SSE events buffered in Redis under the existing `agent:job:` key scheme, a replay endpoint, and a frontend resume-on-mount path keyed off a per-thread active-run record. Phase 3 (view-model unification) is **deliberately dropped** — see rationale at the end.

**Tech Stack:** FastAPI SSE (`backend/src/api/agent/streaming.py`), Redis via `redis.asyncio` (`backend/src/services/agent/job_store.py` pattern), LangGraph checkpointer, Next.js 15 frontend with fetch-reader SSE parsing (`frontend/src/services/agentChatService.ts`), Zustand stores.

**Verified state of the world (evidence, do not re-derive):**

| Research recommendation | Current state |
|---|---|
| Idempotent HITL audit writes (node replays on resume) | ✅ Done — `record_hitl_decision` at `backend/src/services/agent/_nodes_tools.py:263` runs *after* `interrupt()` returns, writes `agent_hitl_audit` row via `_write_hitl_audit_row` (`_nodes_tools.py:140`), best-effort, PII-scrubbed |
| Nested confirmation must not dead-end | ✅ Done — confirm stream re-emits `confirmation` (`streaming.py:1015-1029`); frontend handles it inside `streamConfirm` (`useChatStreaming.ts:1147`) |
| SSE ops headers + keepalive + Last-Event-ID | Partial — headers (`streaming.py:57-59`) and 10s keepalive (`streaming.py:190-243`) done; **no `id:` field is ever emitted** and no resume exists |
| Disconnect ≠ cancel, persist partials | ✅ Done — disconnect branch persists partial with `stopped=True` (`streaming.py:524-560`, `972-997`) |
| Persist one UI view-model format | Already consolidated on one mapper (`cloudMessageView.ts`); denormalized blob rejected (see Phase 3) |

---

## Phase 1 — Regression-pin existing HITL behavior (tests only, no production code expected)

### Task 1: Audit-row idempotency test

**Files:**
- Test: `backend/tests/agent/test_hitl_audit_idempotency.py` (create)
- Reference (read only): `backend/src/services/agent/_nodes_tools.py:140-263`, `backend/src/models/agent_hitl_audit.py`

**Step 1: Write the test**

The risk this pins: LangGraph replays the whole node on `Command(resume=...)`. If anyone ever moves an audit write *before* `interrupt()`, decisions double-write. Test `record_hitl_decision` directly (unit level — no graph needed) and assert `hitl_log_raised` re-firing does NOT create rows:

```python
"""Pins: HITL audit rows are written exactly once per decision, post-interrupt.

LangGraph replays interrupt_node from the top on Command(resume=...), so any
audit write placed BEFORE interrupt() would double-write. hitl_log_raised
(pre-interrupt, re-fires on replay) must be log-only; record_hitl_decision
(post-interrupt, runs once) owns the durable row.
"""
import pytest
from unittest.mock import AsyncMock, patch

from src.services.agent._nodes_tools import hitl_log_raised, record_hitl_decision


def _fake_config():
    return {"configurable": {"thread_id": "t-1", "user_id": "u-1", "organization_id": "o-1"}}


DESTRUCTIVE_CALLS = [{"name": "ingest_arxiv_paper", "args": {"paper_id": "2401.00001"}}]


@pytest.mark.asyncio
async def test_log_raised_writes_no_db_row():
    with patch("src.services.agent._nodes_tools._write_hitl_audit_row", new=AsyncMock()) as write:
        hitl_log_raised(_fake_config(), DESTRUCTIVE_CALLS)
        hitl_log_raised(_fake_config(), DESTRUCTIVE_CALLS)  # replay re-fire
        write.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_decision_writes_exactly_one_row_per_call():
    with patch("src.services.agent._nodes_tools._write_hitl_audit_row", new=AsyncMock()) as write:
        await record_hitl_decision(_fake_config(), DESTRUCTIVE_CALLS, confirmed=True)
        assert write.await_count == 1
        decision_kwargs = write.await_args.kwargs
        assert decision_kwargs.get("decision", "approve") in ("approve", "reject") or True
```

Adjust the assertion on `write.await_args` to the actual `_write_hitl_audit_row` signature after reading `_nodes_tools.py:140-175` — assert `decision == "approve"` for `confirmed=True`. If `hitl_log_raised` is not importable as a standalone function (it may be inline), pin the invariant structurally instead: assert via `inspect.getsource(interrupt_node)` that `_write_hitl_audit_row`/`record_hitl_decision` appear only *after* the `interrupt(` call. Prefer the behavioral mock test if the functions are importable.

**Step 2: Run it**

Run: `cd backend && .venv/bin/python -m pytest tests/agent/test_hitl_audit_idempotency.py -v`
Expected: PASS (this pins existing correct behavior; if it FAILS, the code regressed — investigate before touching the test).

**Step 3: Commit**

```bash
git add backend/tests/agent/test_hitl_audit_idempotency.py
git commit -m "test(agent): pin HITL audit single-write-per-decision invariant"
```

### Task 2: Nested-confirmation loop contract test

**Files:**
- Test: `frontend/src/components/chat/shared/__tests__/nestedConfirmation.contract.test.ts` (create)
- Reference (read only): `frontend/src/services/agentChatService.ts:351-469` (`streamConfirm`), `frontend/src/hooks/chat/useChatStreaming.ts:976-1153`

**Step 1: Write the test**

Pin the service-layer contract: a `confirmation` SSE event arriving on the *confirm* stream reaches `onConfirmation` (this is what makes nested confirms loop instead of dead-ending). Mock `fetch` with a ReadableStream emitting the SSE frames, mirroring the existing contract-test style in `__tests__` (check `frontend/src/components/chat/shared/__tests__/` for the args-preview contract tests updated in commit fd528208 and copy their fetch-mock helper if one exists):

```typescript
import { describe, it, expect, vi, afterEach } from 'vitest';
import { agentChatService } from '@/services/agentChatService';

function sseResponse(frames: string): Response {
  const stream = new ReadableStream({
    start(c) {
      c.enqueue(new TextEncoder().encode(frames));
      c.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

afterEach(() => vi.restoreAllMocks());

describe('streamConfirm nested confirmation', () => {
  it('invokes onConfirmation when the confirm stream emits a further confirmation event', async () => {
    const frames =
      'event: token\ndata: {"content":"ok, ingested."}\n\n' +
      'event: confirmation\ndata: {"thread_id":"t-1","confirmation":{"tools":[{"name":"create_note"}],"message":"Create note?"}}\n\n';
    vi.spyOn(global, 'fetch').mockResolvedValue(sseResponse(frames));

    const onConfirmation = vi.fn();
    const onDone = vi.fn();
    await agentChatService.streamConfirm(
      { thread_id: 't-1', confirmed: true },
      { onConfirmation, onDone },
    );

    expect(onConfirmation).toHaveBeenCalledWith(
      't-1',
      expect.objectContaining({ message: 'Create note?' }),
    );
    expect(onDone).not.toHaveBeenCalled(); // backend returns after confirmation, no done frame
  });
});
```

Adjust `streamConfirm`'s exact signature/auth plumbing to match `agentChatService.ts:351` (it may need a token or headers mock — copy whatever the existing service tests do).

**Step 2: Run it**

Run: `cd frontend && npx vitest run src/components/chat/shared/__tests__/nestedConfirmation.contract.test.ts`
Expected: PASS. (Note: `npm run validate` has known pre-existing failures — run targeted vitest only.)

**Step 3: Commit**

```bash
git add frontend/src/components/chat/shared/__tests__/nestedConfirmation.contract.test.ts
git commit -m "test(chat): pin nested-confirmation loop contract on confirm stream"
```

---

## Phase 2 — Resumable SSE streams

**Design (minimum viable resume):**

- Every SSE frame on `/stream` and `/stream/confirm` gets an `id: <seq>` line (monotonic int per run).
- The generator tees each frame into a Redis list `agent:stream:{stream_id}` (RPUSH, TTL 1h — same TTL as jobs) and writes an active-stream pointer `agent:stream:active:{thread_id} = stream_id` cleared on `done`/`error`.
- New endpoint `GET /api/v1/agent/stream/resume/{thread_id}?after=<seq>`: 204 if no active stream; otherwise replays buffered frames > `seq` from Redis, then live-follows by polling the list until the terminal frame (1s poll; the buffer is the source of truth — no pub/sub needed for v1).
- Generation must survive the original client's disconnect for resume to mean anything: when an active-stream record exists, the disconnect branch **keeps draining the graph into Redis** instead of `aclose()`ing it.
- Frontend: persist `{threadId, streamId, lastSeq}` in `agentActivityStore`; on chat mount with a matching record, call the resume endpoint and feed frames through the same `dispatchData` parser.

**Scope cut (ponytail):** no Redis Streams/XADD, no pub/sub fan-out, no multi-device. One list per run, poll-follow. Upgrade path: swap the poll loop for `websocket/redis_integration.py` pub/sub if latency matters.

### Task 3: Stream buffer module (backend)

**Files:**
- Create: `backend/src/services/agent/stream_buffer.py`
- Test: `backend/tests/agent/test_stream_buffer.py` (create)

**Step 1: Write the failing test**

Use `fakeredis` if it's already a dev dependency (check `backend/requirements-dev.txt` / `pyproject.toml`); otherwise mock the redis client the same way existing `job_store` tests do (read `backend/tests/` for the pattern first — reuse it).

```python
import json
import pytest

from src.services.agent import stream_buffer


@pytest.mark.asyncio
async def test_append_and_read_after_seq(fake_redis):
    sid = await stream_buffer.start_stream("thread-1")
    await stream_buffer.append(sid, 1, "event: token\ndata: {\"content\":\"a\"}\n\n")
    await stream_buffer.append(sid, 2, "event: token\ndata: {\"content\":\"b\"}\n\n")

    frames = await stream_buffer.read_after(sid, after_seq=1)
    assert len(frames) == 1
    assert frames[0].seq == 2

    assert await stream_buffer.active_stream_id("thread-1") == sid
    await stream_buffer.finish_stream("thread-1", sid)
    assert await stream_buffer.active_stream_id("thread-1") is None
```

**Step 2: Run it** — `cd backend && .venv/bin/python -m pytest tests/agent/test_stream_buffer.py -v` — Expected: FAIL (module missing).

**Step 3: Implement `stream_buffer.py`**

Follow `job_store.py`'s client conventions exactly (`_get_redis`, `settings.REDIS_URL`, `decode_responses=True`, TTL 3600):

```python
"""Redis buffer for resumable SSE streams.

One list per run: agent:stream:{stream_id} holds JSON {seq, frame} entries.
agent:stream:active:{thread_id} points at the in-flight run (cleared on finish).
ponytail: poll-follow over a plain list; swap to pub/sub if replay latency matters.
"""
import json
import uuid
from dataclasses import dataclass

from src.services.agent.job_store import _get_redis  # reuse the lazy singleton

_TTL = 3600
_BUF = "agent:stream:{sid}"
_ACTIVE = "agent:stream:active:{tid}"


@dataclass
class BufferedFrame:
    seq: int
    frame: str


async def start_stream(thread_id: str) -> str:
    sid = str(uuid.uuid4())
    r = await _get_redis()
    await r.set(_ACTIVE.format(tid=thread_id), sid, ex=_TTL)
    return sid


async def append(sid: str, seq: int, frame: str) -> None:
    r = await _get_redis()
    key = _BUF.format(sid=sid)
    await r.rpush(key, json.dumps({"seq": seq, "frame": frame}))
    await r.expire(key, _TTL)


async def read_after(sid: str, after_seq: int) -> list[BufferedFrame]:
    r = await _get_redis()
    raw = await r.lrange(_BUF.format(sid=sid), 0, -1)
    out = []
    for item in raw:
        d = json.loads(item)
        if d["seq"] > after_seq:
            out.append(BufferedFrame(seq=d["seq"], frame=d["frame"]))
    return out


async def active_stream_id(thread_id: str) -> str | None:
    r = await _get_redis()
    return await r.get(_ACTIVE.format(tid=thread_id))


async def finish_stream(thread_id: str, sid: str) -> None:
    r = await _get_redis()
    key = _ACTIVE.format(tid=thread_id)
    if await r.get(key) == sid:  # don't clobber a newer run's pointer
        await r.delete(key)
```

If `_get_redis` is module-private in a way that makes reuse ugly, add a public `get_redis()` alias in `job_store.py` rather than a second client. Every append/read must stay best-effort at call sites (buffering must never break live streaming).

**Step 4: Run tests** — Expected: PASS.

**Step 5: Commit** — `git add backend/src/services/agent/stream_buffer.py backend/tests/agent/test_stream_buffer.py && git commit -m "feat(agent): redis stream buffer for resumable SSE"`

### Task 4: Emit `id:` + tee frames in the stream generators

**Files:**
- Modify: `backend/src/api/agent/streaming.py` — `_format_sse_event` (line 183), `stream_event_generator` (line 246), `stream_confirm_event_generator` (line 732), disconnect branch (lines 524-560)
- Test: `backend/tests/agent/test_streaming_resume.py` (create)

**Step 1: Write the failing test**

Test `_format_sse_event` gains an optional seq, and (with the buffer mocked) that the generator tees frames and clears the active pointer on `done`. Drive the generator the same way existing tests in `backend/tests/` drive it (find the existing streaming tests first — e.g. the done-payload/confirm-turn tests from PR #1057 — and reuse their graph/request mocking).

```python
def test_format_sse_event_includes_id():
    from src.api.agent.streaming import _format_sse_event
    out = _format_sse_event("token", {"content": "x"}, seq=7)
    assert out.startswith("id: 7\n")
    assert "event: token\n" in out
    # No seq → unchanged legacy frame
    assert _format_sse_event("token", {"content": "x"}).startswith("event: ")
```

**Step 2: Run** — Expected: FAIL (unexpected keyword `seq`).

**Step 3: Implement**

In `_format_sse_event`:

```python
def _format_sse_event(event_type: str, data: Any, seq: int | None = None) -> str:
    prefix = f"id: {seq}\n" if seq is not None else ""
    return f"{prefix}event: {event_type}\ndata: {_json.dumps(data)}\n\n"
```

In both generators: initialize `seq = 0` and `stream_sid = await stream_buffer.start_stream(thread_id)` (wrapped in try/except — Redis down must not kill streaming; `stream_sid = None` on failure). Wrap every `yield` of an SSE frame so it increments `seq`, formats with `seq=seq`, and best-effort `await stream_buffer.append(stream_sid, seq, frame)` when `stream_sid` is set. The cleanest mechanical approach given the many yield sites: a tiny local helper

```python
async def _emit(event_type: str, data: Any) -> str:
    nonlocal seq
    seq += 1
    frame = _format_sse_event(event_type, data, seq=seq)
    if stream_sid is not None:
        try:
            await stream_buffer.append(stream_sid, seq, frame)
        except Exception:
            pass  # buffering is best-effort
    return frame
```

and replace `yield _format_sse_event(X, Y)` with `yield await _emit(X, Y)` throughout both generators (token 452/597, tool_start 462, tool_end 469, rag_context 476, plan 483, reflection 501, confirmation 582/721/1029, usage 665, done 682/1151, error, heartbeat). After the `done`/`error`/final-`confirmation` frame: `await stream_buffer.finish_stream(thread_id, stream_sid)`.

**Disconnect branch change (lines 524-560):** currently `await event_stream_iter.aclose()` cancels the run. Change to: if `stream_sid` is set, do NOT `aclose()` — keep iterating the graph events, calling `_emit(...)` (which buffers) without yielding, until the stream completes, then persist + `finish_stream` as the normal path does. Keep the existing partial-persist as the fallback when `stream_sid is None` (Redis unavailable). Do the same in the confirm-path disconnect branch (972-997). Note `_graph_events_with_keepalive` returns early on disconnect (lines 211-213) — drain the underlying `event_stream_iter` directly in the disconnect branch, not the keepalive wrapper.

**Step 4: Run the new test + the existing streaming test suite** — `cd backend && .venv/bin/python -m pytest tests/agent/ -k "stream" -v` — Expected: all PASS (existing done-payload tests must not break; legacy frames without resume are unchanged except the added `id:` lines, which SSE parsers ignore).

**Step 5: Commit** — `git commit -m "feat(agent): sequence-numbered SSE frames teed to redis; drain-to-buffer on disconnect"`

### Task 5: Resume endpoint

**Files:**
- Modify: `backend/src/api/agent/execute.py` (add route; follow the auth/ownership pattern of `get_job_status` at line 357)
- Test: `backend/tests/agent/test_streaming_resume.py` (extend)

**Step 1: Write the failing test** — with buffer mocked: 204 when `active_stream_id` returns None; when active, response replays frames after `?after=` then follows until a `done` frame appears in the buffer.

**Step 2: Run** — FAIL (404 route missing).

**Step 3: Implement**

```python
@router.get("/stream/resume/{thread_id}")
async def resume_stream(
    thread_id: str,
    request: Request,
    after: int = 0,
    current_user: User = Depends(get_current_user),
):
    # Ownership: reuse the same thread-ownership check the confirm path uses
    # (_validate_confirmable_job / thread lookup) — an unscoped resume leaks
    # another tenant's stream. MANDATORY per CLAUDE.md tenant-scope rule.
    sid = await stream_buffer.active_stream_id(thread_id)
    if sid is None:
        return Response(status_code=204)

    async def replay():
        last = after
        while True:
            for f in await stream_buffer.read_after(sid, last):
                last = f.seq
                yield f.frame
                if "event: done" in f.frame or "event: error" in f.frame:
                    return
            if await request.is_disconnected():
                return
            if await stream_buffer.active_stream_id(thread_id) != sid and not await stream_buffer.read_after(sid, last):
                return  # run finished and pointer cleared; buffer drained
            await asyncio.sleep(1.0)  # ponytail: poll-follow; pub/sub if latency matters

    return StreamingResponse(replay(), media_type="text/event-stream", headers=_SSE_HEADERS)
```

Reuse the existing `_SSE_HEADERS` dict from `streaming.py:57-59`. Verify the ownership check against how `streaming.py` resolves thread → user before streaming (copy that exact guard).

**Step 4: Run tests** — PASS. **Step 5: Commit** — `git commit -m "feat(agent): GET /stream/resume/{thread_id} replay endpoint"`

### Task 6: Frontend resume-on-mount

**Files:**
- Modify: `frontend/src/services/agentChatService.ts` (add `resumeStream(threadId, afterSeq, callbacks)` — reuse the existing reader/parser: extract the read-loop from `streamMessage` lines 235-345 into a shared `consumeSse(response, callbacks)` helper rather than duplicating it; track `id:` lines in the parser and expose `lastSeq` to callbacks)
- Modify: `frontend/src/stores/agentActivityStore.ts` (persist `{streamSeq}` on the existing per-thread `Run` record; the store already keys runs by threadId)
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts` (mount effect: if the activity store has an unfinished run for `currentThreadId`, call `resumeStream(threadId, lastSeq, sameCallbacks)`; wire the same callback set used at lines 581-722 so resumed frames flow through the identical code path — no second rendering path)
- Test: `frontend/src/components/chat/shared/__tests__/resumeStream.contract.test.ts` (create — same fetch-mock pattern as Task 2: mock a 204 → no callbacks fire; mock a replay body → tokens + done dispatch)

**Steps:** failing test → run (`npx vitest run ...`) → implement → run → commit `feat(chat): resume in-flight agent stream on mount`.

Key constraints:
- The resumed frames MUST go through the same `dispatchData` switch and the same `useChatStreaming` callbacks — a second parse/render path is exactly the dual-path drift bug class this codebase keeps fixing.
- `lastSeq` updates on every frame (persist to the store throttled — reuse the existing RAF batching refs, don't add a new mechanism).
- On `done` of a resumed stream, clear the run record (existing `finishRun`).
- Per feedback_chat_streaming_cleanup memory: clear `isStreaming` BEFORE `setMessages` on stream end.

### Task 7: End-to-end verify

**Step 1:** Backend targeted suite: `cd backend && .venv/bin/python -m pytest tests/agent/ -v` — all PASS.
**Step 2:** Frontend: `cd frontend && npm run type-check && npx vitest run src/components/chat/shared/__tests__/` — PASS (validate has known pre-existing reds; don't use it as the gate).
**Step 3:** Manual (user runs backend — never start/kill it yourself per feedback_no_pkill_backend): start a long agent turn in the browser, hard-refresh mid-stream, confirm the transcript catches up and completes. Use /verify skill discipline: observe the actual flow, not just tests.
**Step 4:** Commit any fixes; then `/code-review` on the branch before PR (PR targets `develop`, branch from `origin/develop` per project_local_repo_diverged_fork memory).

---

## Phase 3 — View-model unification: DROPPED (decision record)

Selected for planning, but exploration showed the premise is already satisfied and the denormalization would make things worse:

- Everything the UI needs already persists: `chat_messages.tool_executions`, `.plan`, `.token_usage` (JSONB) + citations/attachments relations, all round-tripping through `_format_message_response` (`backend/src/api/threads/threads.py:979-1061`).
- The drift class of bugs was caused by *two mappers*, and was already fixed by consolidating on one (`mapDbMessageToChatPageMessage`, `cloudMessageView.ts:124-153` — see its header comment). The industry "persist the UIMessage" advice is aimed at codebases without that consolidation.
- A `ui_view_model` blob column would freeze citations (currently a queryable, FK'd relation) into opaque JSON, add a migration to a table with known alembic-head debt, and duplicate every message's data — for a re-derivation that is a ~30-line pure function over a paginated list.

Re-open only if: the derivation logic needs to change while historical turns must render exactly as originally streamed, or profiling shows `mapDbMessageToChatPageMessage` as a real cost. Neither holds today.
