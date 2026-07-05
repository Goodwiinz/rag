# assistant-ui Runtime Bridge (Stage 1: Tool Calls) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Mount `@assistant-ui/react`'s ExternalStoreRuntime over the existing `/chat` state so `tool-fallback` renders tool calls in message bubbles, behind a feature flag.

**Architecture:** The runtime is a read-only projection of `useChatStore` — `convertMessage` maps `ChatPageMessage` → `ThreadMessageLike`; tool parts derive only from `ActivityStep[]` identity so token streaming never re-renders tool UI. `ChatBubble` swaps `ChatActivityStrip` for `MessagePrimitive.Parts` when `NEXT_PUBLIC_AUI_TOOL_UI=1`.

**Tech Stack:** Next.js 15, React 18, `@assistant-ui/react@0.14.26` (already a dependency via PR #996), zustand, vitest + RTL.

**Design doc:** `docs/plans/2026-07-04-aui-runtime-bridge-design.md`

**Working conventions:** All paths relative to repo root. Frontend commands run from `frontend/`. Type-check: `npx tsc --noEmit -p tsconfig.json`. Tests: `npx vitest run <path>`. This repo's PRs must branch from `origin/develop` (NOT local develop — see memory `project_local_repo_diverged_fork`). Branch: `feat/aui-runtime-bridge-stage1` off `origin/develop`.

**Critical context for the implementer:**
- `ActivityStep` (`frontend/src/components/chat/shared/cloudMessageView.ts:10-19`) has ONLY summary strings: `{tool, label, status: 'running'|'done'|'error', durationMs?, argsSummary?, resultSummary?}`. No raw args object. Map `argsText: argsSummary ?? ''`, `args: {}`, `result: resultSummary` (only when settled). Raw payloads are a later stage.
- `streamingSteps` in `useChatStore` changes reference ONLY on `tool_start`/`tool_end` (`frontend/src/hooks/chat/useChatStreaming.ts:496-537`) — never per token. All memoization keys off that reference.
- `ChatBubble` reads live steps at `frontend/src/components/chat/shared/ChatBubble.tsx:143-145` and mounts `ChatActivityStrip` at `:276-277`.
- `tool-fallback` (`frontend/src/components/assistant-ui/tool-fallback.tsx`) default-exports `ToolFallback` (verify export name in Task 4) and is `memo`-wrapped.

---

### Task 1: convertMessage — failing tests first

**Files:**
- Test: `frontend/src/components/chat/aui/__tests__/convertMessage.test.ts` (create)
- Create: `frontend/src/components/chat/aui/convertMessage.ts`

**Step 1: Write the failing tests**

```ts
import { describe, expect, it } from 'vitest';
import { convertMessage, toToolCallParts } from '../convertMessage';
import type { ChatPageMessage, ActivityStep } from '../../shared/cloudMessageView';

const base: ChatPageMessage = {
  id: 'm1',
  role: 'assistant',
  content: 'hello',
  timestamp: 1751666000000,
};

describe('convertMessage', () => {
  it('maps a plain assistant message to a single text part', () => {
    const out = convertMessage(base);
    expect(out.role).toBe('assistant');
    expect(out.content).toEqual([{ type: 'text', text: 'hello' }]);
    expect(out.id).toBe('m1');
  });

  it('maps toolExecutions to tool-call parts before the text part', () => {
    const steps: ActivityStep[] = [
      { tool: 'search_arxiv', label: 'Searching arXiv', status: 'done', durationMs: 1200, argsSummary: 'query: rag', resultSummary: '5 papers' },
      { tool: 'ingest', label: 'Ingesting', status: 'error', resultSummary: 'timeout' },
    ];
    const out = convertMessage({ ...base, toolExecutions: steps });
    const parts = out.content as any[];
    expect(parts[0]).toMatchObject({
      type: 'tool-call',
      toolCallId: 'm1-tool-0',
      toolName: 'search_arxiv',
      argsText: 'query: rag',
      result: '5 papers',
    });
    expect(parts[1]).toMatchObject({
      type: 'tool-call',
      toolCallId: 'm1-tool-1',
      toolName: 'ingest',
      isError: true,
      result: 'timeout',
    });
    expect(parts[2]).toEqual({ type: 'text', text: 'hello' });
  });

  it('running step maps to a tool-call part with no result', () => {
    const out = convertMessage({
      ...base,
      toolExecutions: [{ tool: 'search', label: 'Searching', status: 'running' }],
    });
    const part = (out.content as any[])[0];
    expect(part.result).toBeUndefined();
    expect(part.isError).toBeUndefined();
  });

  it('missing argsSummary maps to empty argsText and {} args', () => {
    const out = convertMessage({
      ...base,
      toolExecutions: [{ tool: 't', label: 't', status: 'done' }],
    });
    const part = (out.content as any[])[0];
    expect(part.args).toEqual({});
    expect(part.argsText).toBe('');
  });

  it('toToolCallParts is referentially stable for the same steps array', () => {
    const steps: ActivityStep[] = [{ tool: 't', label: 't', status: 'running' }];
    expect(toToolCallParts('m1', steps)).toBe(toToolCallParts('m1', steps));
  });
});
```

**Step 2: Run to verify failure**

Run: `npx vitest run src/components/chat/aui/__tests__/convertMessage.test.ts`
Expected: FAIL — module `../convertMessage` not found.

**Step 3: Minimal implementation**

```ts
// frontend/src/components/chat/aui/convertMessage.ts
import type { ThreadMessageLike } from '@assistant-ui/react';
import type { ActivityStep, ChatPageMessage } from '../shared/cloudMessageView';

type ToolCallPart = {
  type: 'tool-call';
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
  argsText: string;
  result?: string;
  isError?: true;
};

// Tool parts must be referentially stable across per-token re-conversions of
// the in-flight message: streamingSteps only changes reference on
// tool_start/tool_end, so a WeakMap keyed on the steps array is exact.
const partsCache = new WeakMap<ActivityStep[], ToolCallPart[]>();

export function toToolCallParts(
  messageId: string,
  steps: ActivityStep[]
): ToolCallPart[] {
  const cached = partsCache.get(steps);
  if (cached) return cached;
  const parts = steps.map((step, i): ToolCallPart => {
    const settled = step.status !== 'running';
    return {
      type: 'tool-call',
      toolCallId: `${messageId}-tool-${i}`,
      toolName: step.tool,
      args: {},
      argsText: step.argsSummary ?? '',
      ...(settled && step.resultSummary !== undefined
        ? { result: step.resultSummary }
        : {}),
      ...(step.status === 'error' ? { isError: true as const } : {}),
    };
  });
  partsCache.set(steps, parts);
  return parts;
}

export function convertMessage(message: ChatPageMessage): ThreadMessageLike {
  const toolParts = message.toolExecutions?.length
    ? toToolCallParts(message.id ?? 'local', message.toolExecutions)
    : [];
  return {
    id: message.id,
    role: message.role,
    createdAt: new Date(message.timestamp),
    content: [...toolParts, { type: 'text', text: message.content }],
  };
}
```

NOTE: if `ThreadMessageLike`'s tool-call part type rejects `argsText` or
string `result`, check `node_modules/@assistant-ui/react/dist/**/ThreadMessageLike.d.ts`
for the accepted union and adjust (args-as-`{}`+`argsText` is the documented
pattern; result may need `{ result: unknown }`). Do not cast to `any`.

**Step 4: Verify pass**

Run: `npx vitest run src/components/chat/aui/__tests__/convertMessage.test.ts`
Expected: 5 PASS. Then `npx tsc --noEmit -p tsconfig.json` — 0 errors.

**Step 5: Commit**

```bash
git add frontend/src/components/chat/aui/
git commit -m "feat(chat): convertMessage adapter for assistant-ui external store"
```

---

### Task 2: ChatRuntimeProvider

**Files:**
- Test: `frontend/src/components/chat/aui/__tests__/ChatRuntimeProvider.test.tsx` (create)
- Create: `frontend/src/components/chat/aui/ChatRuntimeProvider.tsx`

**Step 1: Failing test**

```tsx
import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { useThread } from '@assistant-ui/react';
import { ChatRuntimeProvider } from '../ChatRuntimeProvider';
import type { ChatPageMessage } from '../../shared/cloudMessageView';

function Probe() {
  const msgCount = useThread((t) => t.messages.length);
  const running = useThread((t) => t.isRunning);
  return <div data-testid="probe">{msgCount}:{String(running)}</div>;
}

const messages: ChatPageMessage[] = [
  { id: 'u1', role: 'user', content: 'hi', timestamp: 1 },
  { id: 'a1', role: 'assistant', content: 'hello', timestamp: 2 },
];

describe('ChatRuntimeProvider', () => {
  it('projects messages and isRunning into the runtime', () => {
    render(
      <ChatRuntimeProvider
        messages={messages}
        isRunning={true}
        onSend={vi.fn()}
        onCancel={vi.fn()}
      >
        <Probe />
      </ChatRuntimeProvider>
    );
    expect(screen.getByTestId('probe')).toHaveTextContent('2:true');
  });
});
```

**Step 2: Run — FAIL (module not found).**

**Step 3: Implementation**

```tsx
// frontend/src/components/chat/aui/ChatRuntimeProvider.tsx
'use client';

import { type ReactNode, useCallback } from 'react';
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
} from '@assistant-ui/react';
import type { ChatPageMessage } from '../shared/cloudMessageView';
import { convertMessage } from './convertMessage';

interface ChatRuntimeProviderProps {
  messages: ChatPageMessage[];
  isRunning: boolean;
  /** Delegates to the existing useChatStreaming send. Required by the
   * external-store API even though the composer stays custom in stage 1. */
  onSend: (text: string) => void;
  onCancel: () => void;
  children: ReactNode;
}

export function ChatRuntimeProvider({
  messages,
  isRunning,
  onSend,
  onCancel,
  children,
}: ChatRuntimeProviderProps) {
  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = message.content
        .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
        .map((p) => p.text)
        .join('\n');
      onSend(text);
    },
    [onSend]
  );

  const handleCancel = useCallback(async () => onCancel(), [onCancel]);

  const runtime = useExternalStoreRuntime({
    messages,
    isRunning,
    convertMessage,
    onNew,
    onCancel: handleCancel,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
```

NOTE: verify hook/prop names against installed 0.14.26 (`node_modules/@assistant-ui/react/dist`): `useExternalStoreRuntime`, `AssistantRuntimeProvider`, `useThread` selector signature. Adjust test/impl to actual API — do not fight the types.

**Step 4: Run test — PASS; tsc — 0 errors.**

**Step 5: Commit** — `feat(chat): ChatRuntimeProvider bridging chat store to assistant-ui`

---

### Task 3: Feature flag helper

**Files:**
- Create: `frontend/src/components/chat/aui/flag.ts`
- Test: covered by Task 5's component test (no dedicated test — one-liner)

```ts
// frontend/src/components/chat/aui/flag.ts
/** Stage-1 rollout flag for the assistant-ui tool-call renderer. */
export const AUI_TOOL_UI_ENABLED =
  process.env.NEXT_PUBLIC_AUI_TOOL_UI === '1';
```

Commit with Task 4.

---

### Task 4: AuiToolParts renderer (MessagePrimitive.Parts scoped to one message)

**Files:**
- Test: `frontend/src/components/chat/aui/__tests__/AuiToolParts.test.tsx` (create)
- Create: `frontend/src/components/chat/aui/AuiToolParts.tsx`

This is the riskiest task: `MessagePrimitive.Parts` must render inside a
message context. With ExternalStoreRuntime the idiomatic way is
`ThreadPrimitive.Messages` with a custom `AssistantMessage` component; but we
render inside `ChatBubble` per message. Approach: render an invisible
`ThreadPrimitive.Messages` ONLY for the target message is not possible —
instead use `MessageRuntimeProvider`-equivalent: check 0.14.26 for
`useMessageRuntime`/`MessageByIndexProvider` (in dist, look for
`MessageRuntimeProvider` or `ThreadPrimitive.Messages` `components` prop).

**Fallback approach (guaranteed):** render tool parts directly WITHOUT
MessagePrimitive: iterate the converted parts and render `<ToolFallback>` with
explicit props (it accepts `ToolCallMessagePartProps`-shaped props). The
runtime still owns state; only the per-part subscription sugar is skipped.
Stage 2 (whole message list) moves to real `ThreadPrimitive.Messages`.

**Step 1: Failing test**

```tsx
import { describe, expect, it } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AuiToolParts } from '../AuiToolParts';
import type { ActivityStep } from '../../shared/cloudMessageView';

const steps: ActivityStep[] = [
  { tool: 'search_arxiv', label: 'Searching arXiv', status: 'done', durationMs: 900, argsSummary: 'query: rag', resultSummary: '5 papers' },
];

describe('AuiToolParts', () => {
  it('renders a ToolFallback row per tool execution', () => {
    render(<AuiToolParts messageId="m1" steps={steps} isStreaming={false} />);
    expect(screen.getByText(/search_arxiv/)).toBeInTheDocument();
  });

  it('renders nothing for empty steps', () => {
    const { container } = render(
      <AuiToolParts messageId="m1" steps={[]} isStreaming={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
```

**Step 2: Run — FAIL.**

**Step 3: Implementation** (adjust ToolFallback prop names to its actual `ToolCallMessagePartProps` signature — read `frontend/src/components/assistant-ui/tool-fallback.tsx` exports first):

```tsx
// frontend/src/components/chat/aui/AuiToolParts.tsx
'use client';

import { memo } from 'react';
import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import type { ActivityStep } from '../shared/cloudMessageView';
import { toToolCallParts } from './convertMessage';

interface AuiToolPartsProps {
  messageId: string;
  steps: ActivityStep[];
  isStreaming: boolean;
}

export const AuiToolParts = memo(function AuiToolParts({
  messageId,
  steps,
  isStreaming,
}: AuiToolPartsProps) {
  if (steps.length === 0) return null;
  const parts = toToolCallParts(messageId, steps);
  return (
    <div data-slot="aui-tool-parts" className="flex flex-col gap-1 mb-2">
      {parts.map((part, i) => (
        <ToolFallback
          key={part.toolCallId}
          {...part}
          status={
            steps[i].status === 'running' && isStreaming
              ? { type: 'running' }
              : steps[i].status === 'error'
                ? { type: 'incomplete', reason: 'error' }
                : { type: 'complete' }
          }
        />
      ))}
    </div>
  );
});
```

NOTE: `status` shape must match `ToolCallMessagePartStatus` from
`@assistant-ui/react` — read the type; the literals above are a starting
guess. If ToolFallback requires runtime hooks (`useToolCallElapsed` throwing
outside runtime context), wrap the test render in `ChatRuntimeProvider` and/or
pass required context; if it hard-requires message runtime context, pivot to
mounting via `ThreadPrimitive.Messages` with `components={{ Message: ... }}`
hidden for non-target messages — decide based on the actual errors, document
the choice in the commit message.

**Step 4: Run — PASS; tsc clean.**

**Step 5: Commit** — `feat(chat): AuiToolParts renderer using tool-fallback` (include flag.ts)

---

### Task 5: ChatBubble integration behind flag

**Files:**
- Modify: `frontend/src/components/chat/shared/ChatBubble.tsx` (~:276-277, the ChatActivityStrip mount)
- Test: `frontend/src/components/chat/shared/__tests__/ChatBubble-aui.test.tsx` (create)

**Step 1: Failing test** — mock the flag on:

```tsx
import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';

vi.mock('@/components/chat/aui/flag', () => ({ AUI_TOOL_UI_ENABLED: true }));

import { ChatBubble } from '../ChatBubble';

describe('ChatBubble with AUI tool UI flag on', () => {
  it('renders AuiToolParts instead of ChatActivityStrip for a message with toolExecutions', () => {
    render(
      <ChatBubble
        message={{
          id: 'a1',
          role: 'assistant',
          content: 'done',
          timestamp: 1,
          toolExecutions: [
            { tool: 'search_arxiv', label: 'Searching arXiv', status: 'done' },
          ],
        }}
        index={0}
      />
    );
    expect(document.querySelector('[data-slot="aui-tool-parts"]')).toBeTruthy();
  });
});
```

(Match ChatBubble's actual required props — read the component first; add store mocks the existing ChatBubble tests use, copy their setup.)

**Step 2: Run — FAIL (strip renders, no aui-tool-parts slot).**

**Step 3: Implementation** — in `ChatBubble.tsx`, at the ChatActivityStrip mount:

```tsx
{activitySteps.length > 0 &&
  (AUI_TOOL_UI_ENABLED ? (
    <AuiToolParts
      messageId={message.id ?? `idx-${index}`}
      steps={activitySteps}
      isStreaming={isStreaming}
    />
  ) : (
    <ChatActivityStrip /* existing props unchanged */ />
  ))}
```

Preserve the existing condition semantics (`isStreaming || message.toolExecutions`).

**Step 4: Run new test + full chat suite:**
`npx vitest run src/components/chat/` — all pass (61 existing + new).

**Step 5: Commit** — `feat(chat): render tool calls via assistant-ui behind NEXT_PUBLIC_AUI_TOOL_UI`

---

### Task 6: Mount ChatRuntimeProvider in the chat page

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx` (wrap the message pane; near ChatMessageList render ~:982)

**Step 1:** Wrap message list subtree:

```tsx
<ChatRuntimeProvider
  messages={displayedMessages}
  isRunning={storeIsStreaming}
  onSend={handleSendMessage /* existing send handler */}
  onCancel={handleStopStreaming /* existing stop handler */}
>
  {/* existing ChatMessageList etc. */}
</ChatRuntimeProvider>
```

Use the page's actual variable names (read the file; `displayedMessages` /
handlers may differ). Gate the wrapper itself on `AUI_TOOL_UI_ENABLED` so
flag-off production builds don't even mount the runtime.

**Step 2:** `npx tsc --noEmit` — 0 errors. `npx vitest run src/components/chat/` — green.

**Step 3: Commit** — `feat(chat): mount assistant-ui runtime provider on chat page`

---

### Task 7: Streaming render-count guard test

**Files:**
- Test: `frontend/src/components/chat/aui/__tests__/streaming-stability.test.tsx` (create)

**Step 1:** Assert ToolFallback doesn't re-render across simulated token updates:

```tsx
import { describe, expect, it } from 'vitest';
import React, { Profiler, useState } from 'react';
import { act, render } from '@testing-library/react';
import { AuiToolParts } from '../AuiToolParts';
import type { ActivityStep } from '../../shared/cloudMessageView';

it('tool parts do not re-render on token updates (stable steps ref)', () => {
  const steps: ActivityStep[] = [
    { tool: 'search', label: 'Searching', status: 'running' },
  ];
  let renders = 0;
  let push: (s: string) => void = () => {};
  function Harness() {
    const [, setTok] = useState('');
    push = (s) => setTok(s);
    return (
      <Profiler id="tool" onRender={() => renders++}>
        <AuiToolParts messageId="m1" steps={steps} isStreaming />
      </Profiler>
    );
  }
  render(<Harness />);
  const after1 = renders;
  act(() => { for (let i = 0; i < 50; i++) push(`tok${i}`); });
  expect(renders).toBe(after1); // memo'd: parent state churn doesn't touch it
});
```

**Step 2:** Run — should PASS immediately (AuiToolParts is memo'd + parts cached). If it fails, that's a real leak — fix memoization, not the test.

**Step 3: Commit** — `test(chat): guard tool UI render stability during token streaming`

---

### Task 8: Validation sweep + PR

**Steps:**
1. `npx tsc --noEmit -p tsconfig.json` — 0 errors.
2. `npx vitest run src/components/chat/ src/components/assistant-ui/ 2>/dev/null` — all green.
3. `npx eslint src/components/chat/aui/ src/components/chat/shared/ChatBubble.tsx` — no errors (warnings matching pre-existing style rules acceptable).
4. Manual: `NEXT_PUBLIC_AUI_TOOL_UI=1 npm run dev`, open `/chat`, send a tool-calling prompt ("search arXiv for retrieval-augmented generation"), verify tool-fallback rows render live (spinner → check), collapse/expand works, reload thread → persisted steps re-render. Flag off → old strip, pixel-identical to today.
5. PR off `origin/develop`: branch `feat/aui-runtime-bridge-stage1`, title `feat(chat): assistant-ui runtime bridge — tool-call UI (stage 1)`. Body references the design doc, states flag default-off, lists later stages. Run `/pr-review-toolkit:review-pr` before opening.

---

## Deviations policy

Tasks 2/4 verify API names against installed `@assistant-ui/react@0.14.26` before coding — the docs summarize a moving 0.x API. If the fallback approach in Task 4 is taken (direct ToolFallback render without MessagePrimitive.Parts), note it in the PR body as stage-2 debt.
