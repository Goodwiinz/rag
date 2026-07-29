# Agent Stream Final-State Fast Path Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the redundant post-stream checkpoint read from completed agent turns while preserving HITL interrupt detection and fallback behavior.

**Architecture:** Capture the root `on_chain_end` output already delivered by `astream_events` and use it as the final state for normally completed turns. Continue reading the checkpoint when the root output is absent or ends with unresolved tool calls, because LangGraph does not expose pending interrupt metadata in the root event.

**Tech Stack:** Python 3.11, FastAPI SSE, LangGraph event streaming, pytest.

---

### Task 1: Add the completed-turn regression

**Files:**
- Modify: `backend/tests/unit/api/test_agent_streaming_nonstreamed_final.py`

**Step 1: Write the failing test**

Add a fake graph that emits a root `on_chain_end` event containing the final assistant state, counts `aget_state` calls, and returns an empty snapshot for the required pre-run stale-interrupt check. Assert that the answer and `done` events are emitted and that `aget_state` was called exactly once.

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/api/test_agent_streaming_nonstreamed_final.py::test_completed_stream_reuses_root_output_without_final_checkpoint_read -q
```

Expected: FAIL because the current finalization path calls `aget_state` a second time.

### Task 2: Reuse the root stream output

**Files:**
- Modify: `backend/src/api/agent/streaming.py`

**Step 1: Capture root output**

Store dictionary output from a parentless `on_chain_end` event while consuming graph events.

**Step 2: Preserve interrupt safety**

Use the captured output directly only when it is non-empty and its final message has no unresolved `tool_calls`. Otherwise, retain the existing `graph.aget_state(config)` path so pending HITL tasks are detected from the checkpoint.

**Step 3: Run test to verify it passes**

Run the focused regression test from Task 1 and expect PASS.

### Task 3: Verify contracts and commit

**Files:**
- Test: `backend/tests/unit/api/test_agent_streaming_nonstreamed_final.py`
- Test: `backend/tests/unit/api/test_agent_streaming_done_tool_executions.py`
- Test: `backend/tests/unit/api/test_agent_streaming_trace_event.py`
- Test: `backend/tests/unit/api/test_agent_clear_stale_interrupt.py`

**Step 1: Run focused streaming tests**

Run:

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/api/test_agent_streaming_nonstreamed_final.py \
  tests/unit/api/test_agent_streaming_done_tool_executions.py \
  tests/unit/api/test_agent_streaming_trace_event.py \
  tests/unit/api/test_agent_clear_stale_interrupt.py -q
```

Expected: all tests PASS.

**Step 2: Run formatting and lint checks**

Run Black check and Ruff on the two changed Python files.

**Step 3: Commit**

Commit the plan, regression, and implementation with:

```bash
git commit -m "perf(agent): avoid redundant final checkpoint read"
```
