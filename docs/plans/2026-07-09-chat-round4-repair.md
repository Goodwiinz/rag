# Chat Round 4 Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore safe, complete /chat provenance on reload and make every stream
terminal state accurate and fully cleaned up.

**Architecture:** Share backend message read serialization across v1, v2, and
the agent-list provenance fields; derive reload-only badges from canonical data;
and route confirmation through runStreamTurn with one outcome and cleanup policy.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js, React, Zustand, Vitest,
Playwright/manual dev-browser validation.

---

## Preconditions

- Branch from current origin/develop for implementation. It must include PR
  #1100 / a8dd8ce8 so work targets the always-on AUI path.
- Install frontend dependencies with the pinned package manager from repo root:

~~~sh
corepack pnpm@10.18.2 install --frozen-lockfile
~~~

- Run backend commands from repository root with .venv/bin/python. Run
  frontend commands from frontend/. Do not substitute a host pnpm version.

## Task 1: Pin safe serializer parity before refactoring

**Files:**

- Create: backend/tests/api/threads/test_message_response_serialization.py
- Read: backend/src/api/threads/workspaces.py:1416-1444
- Read: backend/src/api/threads/threads.py:980-1060
- Read: backend/src/api/agent/execute.py:790-805
- Read: backend/src/services/agent/_pii_redact.py:94-105

### Step 1: Write the failing test

Build one SimpleNamespace assistant message with UUID identifiers, UTC datetimes,
empty citations/attachments, stopped=True, plan, token_usage, and tool args
containing a real-looking email plus a sufficiently long sk-proj token.

Parametrize over the current externally visible formatter functions:

~~~python
from src.api.threads import threads as threads_mod
from src.api.threads import workspaces as workspaces_mod

SERIALIZERS = [
    workspaces_mod._message_to_response,
    threads_mod._format_message_response,
]
~~~

For every returned Pydantic response, assert:

~~~python
payload = serializer(message).model_dump()
assert payload["stopped"] is True
assert payload["plan"] == message.plan
assert payload["token_usage"] == message.token_usage
assert payload["tool_executions"][0]["args"] == {
    "email": "<email>",
    "api_key": "<token>",
}
~~~

Also write a direct test for the planned agent_provenance_fields helper. Assert
it produces the same redacted tool executions, plan, and token_usage for the
agent list endpoint.

### Step 2: Run the test to verify it fails

~~~sh
.venv/bin/python -m pytest -c backend/pytest.ini \
  backend/tests/api/threads/test_message_response_serialization.py -v
~~~

Expected: the workspace/v2 serializer fails because it omits stopped,
tool_executions, plan, and token_usage and has no redaction. The v1 case can
already pass.

### Step 3: Implement the common read policy

Create backend/src/api/threads/message_serialization.py. It owns citation and
attachment conversion plus the complete ChatMessageResponse construction:

~~~python
return ChatMessageResponse(
    # existing identity, content, citation, attachment, and timestamp fields
    stopped=message.stopped,
    tool_executions=redact_tool_executions(message.tool_executions),
    plan=message.plan,
    token_usage=message.token_usage,
)
~~~

For execute.py's different schema, expose:

~~~python
def agent_provenance_fields(message: ChatMessage) -> dict[str, Any]:
    return {
        "tool_executions": redact_tool_executions(message.tool_executions),
        "plan": message.plan,
        "token_usage": message.token_usage,
    }
~~~

Legacy nulls and empty lists retain their existing semantics. No helper may
return raw persisted tool arguments.

### Step 4: Delegate all three read paths

- Make threads.py _format_message_response call format_chat_message.
- Make workspaces.py _message_to_response call format_chat_message.
- Replace execute.py's three inline provenance assignments with
  **agent_provenance_fields(msg).
- Remove duplicate helpers/imports only after all three callers compile.

### Step 5: Run backend verification

~~~sh
.venv/bin/python -m pytest -c backend/pytest.ini \
  backend/tests/api/threads/test_message_response_serialization.py \
  backend/tests/api/threads/test_v1_create_message_delegates.py \
  backend/tests/api/threads/test_v2_create_message_delegates.py -v
~~~

Expected: PASS, with exactly the same redacted provenance visible through both
thread response serializers.

### Step 6: Commit

~~~sh
git add backend/src/api/threads/message_serialization.py \
  backend/src/api/threads/threads.py \
  backend/src/api/threads/workspaces.py \
  backend/src/api/agent/execute.py \
  backend/tests/api/threads/test_message_response_serialization.py
git commit -m "fix(chat): unify safe message read serialization"
~~~

## Task 2: Reconstruct reload badges from canonical message fields

**Files:**

- Modify: frontend/src/components/chat/shared/cloudMessageView.ts:136-164
- Modify: frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts

### Step 1: Write failing reload-metadata tests

Map an assistant DB message with two citations and two tool executions but no
previously live metadata. Assert:

~~~ts
expect(mapped.metadata).toMatchObject({
  toolsUsed: ['Search Documents', 'Summarize Document'],
  sourcesCount: 2,
});
~~~

Keep a control case that a row with no latency, stopped, usage, citations, or
tool executions still returns metadata: undefined.

### Step 2: Run the test to verify it fails

~~~sh
cd frontend && corepack pnpm@10.18.2 exec vitest run \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts
~~~

Expected: FAIL because metadata currently carries only latency, stopped, and
token usage.

### Step 3: Derive the display values once

Refactor the mapper to compute citations and toolExecutions before the returned
ChatPageMessage:

~~~ts
const citations = dbMsg.citations?.map(normalizeCitation);
const toolExecutions = mapDbToolExecutions(dbMsg.tool_executions);
const metadata = {
  ...(toolExecutions?.length
    ? { toolsUsed: toolExecutions.map((step) => step.label) }
    : {}),
  ...(citations?.length ? { sourcesCount: citations.length } : {}),
  // preserve responseTimeMs, stopped, and tokenUsage
};
~~~

Use the computed values in the message. Set metadata to undefined only when
Object.keys(metadata).length is zero. Do not persist derived badge values.

### Step 4: Verify and commit

~~~sh
cd frontend && corepack pnpm@10.18.2 exec vitest run \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts \
  src/components/chat/shared/__tests__/cloudMessageView.toolResult.test.ts
git add src/components/chat/shared/cloudMessageView.ts \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts
git commit -m "fix(chat): derive reload provenance badges"
~~~

Expected: PASS.

## Task 3: Pin full cleanup for normal and confirmation exceptions

**Files:**

- Modify: frontend/src/hooks/__tests__/useChatStreaming.canonical.test.tsx
- Modify: frontend/src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx
- Modify: frontend/src/hooks/chat/useChatStreaming.ts:348-782

### Step 1: Add a normal-stream exception test

Mock streamMessage to emit a tool start then reject. Render the hook with
enableRAG true. After handleSubmit settles, assert the full store state:

~~~ts
expect(useChatStore.getState()).toMatchObject({
  isStreaming: false,
  streamingContent: '',
  streamingCitations: [],
  streamingSteps: [],
  isRetrievingRag: false,
});
~~~

### Step 2: Add a confirmation exception test

Start a normal stream that emits confirmation. Have streamConfirm emit a tool
start and reject with Error('confirm transport failed'). Assert:

~~~ts
expect(useAgentActivityStore.getState().runs['thread-A']?.state).toBe('error');
expect(useChatStore.getState().streamingSteps).toEqual([]);
expect(useChatStore.getState().isRetrievingRag).toBe(false);
~~~

Assert that the committed error has confirmation-specific wording.

For all hook tests, make setMessages stateful: apply a functional updater to
the prior message array, then inspect arrays after filtering messages marked
isStreaming or pendingApproval. Do not read the last mock call directly.

### Step 3: Confirm the current failures

~~~sh
cd frontend && corepack pnpm@10.18.2 exec vitest run \
  src/hooks/__tests__/useChatStreaming.canonical.test.tsx \
  src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx
~~~

Expected: FAIL. The normal finally block leaves steps and the RAG flag stale;
the confirmation finally records a rejection as done.

### Step 4: Add one presentation reset helper

Inside useChatStreaming add:

~~~ts
const resetStreamingPresentation = () => {
  useChatStore.setState({
    isStreaming: false,
    streamingContent: '',
    streamingCitations: [],
    streamingSteps: [],
    isRetrievingRag: false,
  });
};
~~~

Call it for every terminal path: successful response, empty response, error
callback, thrown promise, stop, confirmation pause, and nested confirmation.
Do not make this helper alter pendingConfirmation; nested gates have separate
semantics.

### Step 5: Re-run the tests

Run the command from Step 3.

Expected: the normal exception is green. The confirmation activity-state
assertion remains red until the shared-runner refactor in Task 4.

## Task 4: Make confirmation a runStreamTurn adapter

**Files:**

- Modify: frontend/src/hooks/chat/useChatStreaming.ts:348-782, 1035-1337
- Modify: frontend/src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx
- Modify if needed: frontend/src/hooks/__tests__/useChatStreaming.auiApproval.test.tsx

### Step 1: Add seed and outcome types

Place compact types by runStreamTurn:

~~~ts
type StreamTurnSeed = {
  steps?: ActivityStep[];
  plan?: PlanStep[];
  citations?: Array<Record<string, unknown>>;
};
type StreamTurnOutcome = 'done' | 'error' | 'stopped' | 'confirmation-paused';
~~~

Extend its options with seed, activityThreadId, and an errorMessage factory.
Seeded values initialize the runner's local steps, plan, and citations so a
confirmed turn still commits pre-interrupt provenance.

### Step 2: Move shared callbacks/finalization into the runner

Move confirmation token, tool, RAG, plan, usage, reflection, done, error,
activity, final-message, and cleanup behavior into runStreamTurn. Keep
confirmation wording as an injected error-message factory, never as a second
callback implementation.

Use this precedence:

~~~ts
if (nestedConfirmation) return 'confirmation-paused';
if (streamHadError || caughtError) return 'error';
if (stoppedByUserRef.current) return 'stopped';
return 'done';
~~~

Finish activity only for done, error, or stopped. A nested confirmation keeps
the run open. A caught error calls finishRun(threadId, 'error'), never done.

### Step 3: Reduce handleConfirmation

Keep only:

1. ownership guard and isConfirming toggle;
2. a runStreamTurn call with the pending-confirmation seed and streamConfirm
   starter adapter;
3. pendingConfirmation replacement/clear based on returned outcome;
4. isConfirming cleanup.

Delete its duplicated callbacks, local step maps, message builder, and partial
cleanup. Preserve focus behavior outside the runner.

### Step 4: Run focused hook verification

~~~sh
cd frontend && corepack pnpm@10.18.2 exec vitest run \
  src/hooks/__tests__/useChatStreaming.canonical.test.tsx \
  src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx \
  src/hooks/__tests__/useChatStreaming.auiApproval.test.tsx \
  src/hooks/__tests__/useChatStreaming.auiPlaceholder.test.tsx \
  src/hooks/__tests__/useChatStreaming.resume.test.tsx \
  src/hooks/__tests__/useChatStreaming.doneToolExecutions.test.tsx
~~~

Expected: PASS. The rejected confirmation is error, nested confirmation remains
pending/running, and successful confirmation retains seeded provenance plus
server tool executions.

### Step 5: Commit

~~~sh
git add src/hooks/chat/useChatStreaming.ts \
  src/hooks/__tests__/useChatStreaming.canonical.test.tsx \
  src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx \
  src/hooks/__tests__/useChatStreaming.auiApproval.test.tsx
git commit -m "fix(chat): unify confirmation stream lifecycle"
~~~

## Task 5: Close the R4-F5 browser release gate

**Files:**

- Update after test: ~/.audit-ledgers/rag/chat-audit-round4.md
- Update after test: repair PR verification section
- Read: a8dd8ce8 and the deployed dev revision

### Step 1: Identify the actual dev artifact

Use the repository-defined dev access path to verify the deployment SHA. Record
the deployment URL, SHA, test account/fixture, and timestamp. Do not infer a
public endpoint.

### Step 2: Run browser scenarios

Run these scenarios with no AUI fallback flag:

1. a tool-using streamed turn commits once with tool UI, plan, sources, and token badge;
2. approve an in-band destructive action;
3. deny one and verify composer focus returns;
4. approve the first of two destructive actions and act on the nested gate;
5. trigger the available error path and verify the next turn has no spinner or old tool chips.

### Step 3: Record the evidence

Write each exact result, including failures or blocked prerequisites, to the
external audit ledger and PR. Do not mark R4-F5 verified without the evidence.

## Task 6: Full verification and review

### Step 1: Backend suite

~~~sh
.venv/bin/python -m pytest -c backend/pytest.ini backend/tests/api/threads/ -v
~~~

Expected: PASS.

### Step 2: Frontend suite and types

~~~sh
cd frontend
corepack pnpm@10.18.2 exec vitest run \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts \
  src/components/chat/shared/__tests__/cloudMessageView.toolResult.test.ts \
  src/hooks/__tests__/useChatStreaming.canonical.test.tsx \
  src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx \
  src/hooks/__tests__/useChatStreaming.auiApproval.test.tsx \
  src/hooks/__tests__/useChatStreaming.auiPlaceholder.test.tsx \
  src/hooks/__tests__/useChatStreaming.resume.test.tsx \
  src/hooks/__tests__/useChatStreaming.doneToolExecutions.test.tsx
corepack pnpm@10.18.2 exec tsc --noEmit
~~~

Expected: PASS. Report exact blocked command/output instead of claiming green.

### Step 3: Final review checklist

- Every browser-facing persisted tool execution passes through
  redact_tool_executions.
- No new database column or duplicate badge persistence exists.
- Confirmation has no separate SSE callback/finalization implementation.
- Every stream terminal path invokes the full presentation reset.
- Browser-gate evidence is linked before closing R4-F5.

