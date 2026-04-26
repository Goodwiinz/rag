# Chat UI/UX Consistency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver one consistent chat experience across `/chat` and `/search` by sharing chat bubble, composer, and shell primitives while preserving route-specific business logic.

**Architecture:** Extract canonical UI primitives from `frontend/app/(dashboard)/chat/page.tsx` into reusable `frontend/src/components/chat/shared/*` components. Introduce a shared message view-model adapter layer so both `/chat` and `/search` render the same visual/interaction contract. Keep `/chat` persistence/streaming logic and `/search` retrieval logic unchanged, only adapting their output to shared rendering.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS utility classes, framer-motion, Jest + Testing Library.

---

### Task 1: Create Shared Message View Model and Adapters

**Files:**
- Create: `frontend/src/components/chat/shared/messageViewModel.ts`
- Create: `frontend/src/components/chat/shared/__tests__/messageViewModel.test.ts`
- Modify: `frontend/src/components/chat/index.ts`

**Step 1: Write the failing test**

```typescript
import { mapChatRouteMessage, mapSearchResultToMessages } from '../messageViewModel';

describe('messageViewModel', () => {
  it('maps chat route messages to a shared view model', () => {
    const result = mapChatRouteMessage({ role: 'assistant', content: 'Hello', timestamp: 1700000000000 });
    expect(result.role).toBe('assistant');
    expect(result.content).toBe('Hello');
  });

  it('maps search response into user + assistant message sequence', () => {
    const messages = mapSearchResultToMessages({
      query: 'What is RAG?',
      answer: { synthesized_answer: 'RAG combines retrieval and generation.' },
      sources: [],
    } as any);

    expect(messages[0].role).toBe('user');
    expect(messages[1].role).toBe('assistant');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/messageViewModel.test.ts`
Expected: FAIL with missing module/export errors.

**Step 3: Write minimal implementation**

```typescript
export type ChatMessageViewModel = {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  modelName?: string;
  citations?: Array<{
    documentId?: string;
    externalReferenceId?: string;
    title: string;
    score: number;
    content?: string;
    source?: string;
  }>;
  isStreaming?: boolean;
  streamingContent?: string;
};

export function mapChatRouteMessage(input: {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  modelName?: string;
  citations?: ChatMessageViewModel['citations'];
}): ChatMessageViewModel {
  return { ...input };
}

export function mapSearchResultToMessages(searchResult: any): ChatMessageViewModel[] {
  const userMessage: ChatMessageViewModel = {
    role: 'user',
    content: searchResult.query,
    timestamp: Date.now(),
  };

  const assistantMessage: ChatMessageViewModel = {
    role: 'assistant',
    content:
      searchResult?.answer?.synthesized_answer ||
      searchResult?.answer?.answer ||
      '',
    timestamp: Date.now(),
    citations: (searchResult?.sources || []).map((s: any) => ({
      documentId: s.document_id,
      title: s.title || 'Unknown Source',
      score: typeof s.score === 'number' ? s.score : 0,
      content: s.content,
      source: s.source,
    })),
  };

  return [userMessage, assistantMessage];
}
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/messageViewModel.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/chat/shared/messageViewModel.ts frontend/src/components/chat/shared/__tests__/messageViewModel.test.ts frontend/src/components/chat/index.ts
git commit -m "feat(chat): add shared message view model adapters"
```

### Task 2: Extract Shared Chat Bubble Component

**Files:**
- Create: `frontend/src/components/chat/shared/ChatBubble.tsx`
- Create: `frontend/src/components/chat/shared/__tests__/ChatBubble.test.tsx`
- Modify: `frontend/src/components/chat/index.ts`

**Step 1: Write the failing test**

```typescript
import { render, screen } from '@testing-library/react';
import { ChatBubble } from '../ChatBubble';

describe('ChatBubble', () => {
  it('renders role badge and content for user message', () => {
    render(<ChatBubble message={{ role: 'user', content: 'Hello', timestamp: Date.now() }} index={0} />);
    expect(screen.getByText('QUERY')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('renders streaming cursor for assistant streaming state', () => {
    const { container } = render(
      <ChatBubble
        message={{ role: 'assistant', content: '', timestamp: Date.now() }}
        index={0}
        isStreaming
        streamingContent="Partial"
      />
    );
    expect(container.querySelector('[data-testid="streaming-cursor"]')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/ChatBubble.test.tsx`
Expected: FAIL with missing component/export.

**Step 3: Write minimal implementation**

```tsx
export function ChatBubble({ message, index, isStreaming, streamingContent, modelName, onCitationClick }: ChatBubbleProps) {
  // Extracted from existing /chat inline ChatMessage implementation.
  // Keep role styling, timestamp row, copy action, and citation footer behavior.
  // Add data-testid="streaming-cursor" on cursor span in streaming state.
}
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/ChatBubble.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/chat/shared/ChatBubble.tsx frontend/src/components/chat/shared/__tests__/ChatBubble.test.tsx frontend/src/components/chat/index.ts
git commit -m "feat(chat): extract shared chat bubble component"
```

### Task 3: Extract Shared Chat Composer with Unified Keyboard Behavior

**Files:**
- Create: `frontend/src/components/chat/shared/ChatComposer.tsx`
- Create: `frontend/src/components/chat/shared/__tests__/ChatComposer.test.tsx`
- Modify: `frontend/src/components/chat/index.ts`

**Step 1: Write the failing test**

```typescript
import { fireEvent, render, screen } from '@testing-library/react';
import { ChatComposer } from '../ChatComposer';

describe('ChatComposer', () => {
  it('submits on Enter', () => {
    const onSubmit = jest.fn();
    render(<ChatComposer value="hello" onChange={() => {}} onSubmit={onSubmit} onStop={() => {}} isLoading={false} isDisabled={false} />);
    fireEvent.keyDown(screen.getByPlaceholderText(/inject query|type your message/i), { key: 'Enter' });
    expect(onSubmit).toHaveBeenCalled();
  });

  it('does not submit on Shift+Enter', () => {
    const onSubmit = jest.fn();
    render(<ChatComposer value="hello" onChange={() => {}} onSubmit={onSubmit} onStop={() => {}} isLoading={false} isDisabled={false} />);
    fireEvent.keyDown(screen.getByPlaceholderText(/inject query|type your message/i), { key: 'Enter', shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/ChatComposer.test.tsx`
Expected: FAIL with missing component/export.

**Step 3: Write minimal implementation**

```tsx
export function ChatComposer(props: ChatComposerProps) {
  // Extract from /chat inline ChatInput:
  // - model selector slot area
  // - RAG toggle slot area
  // - textarea autosize
  // - Enter/Shift+Enter behavior
  // - send/stop CTA state
  // Keep visual tokens exactly aligned with ChatBubble theme.
}
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/ChatComposer.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/chat/shared/ChatComposer.tsx frontend/src/components/chat/shared/__tests__/ChatComposer.test.tsx frontend/src/components/chat/index.ts
git commit -m "feat(chat): extract shared chat composer"
```

### Task 4: Refactor `/chat` to Use Shared Bubble and Composer

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Modify: `frontend/src/components/chat/index.ts`
- Test: `frontend/src/components/chat/shared/__tests__/ChatBubble.test.tsx`
- Test: `frontend/src/components/chat/shared/__tests__/ChatComposer.test.tsx`

**Step 1: Write failing integration-oriented assertion test**

```typescript
// Add assertion in existing component test file that /chat route-specific mapper
// still shows QUERY badge + assistant RECEIVED badge with shared ChatBubble.
// (If route test harness is unavailable, add focused render test for wrapper that composes ChatBubble+ChatComposer.)
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/ChatBubble.test.tsx src/components/chat/shared/__tests__/ChatComposer.test.tsx`
Expected: FAIL after route wiring mismatch.

**Step 3: Write minimal implementation**

```tsx
// In frontend/app/(dashboard)/chat/page.tsx:
// - Remove inline ChatMessage and ChatInput component definitions.
// - Import ChatBubble and ChatComposer from shared components.
// - Keep existing business logic and pass mapped props.
// - Keep citation panel behavior and scroll behavior unchanged.
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/ChatBubble.test.tsx src/components/chat/shared/__tests__/ChatComposer.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/app/(dashboard)/chat/page.tsx frontend/src/components/chat/index.ts
git commit -m "refactor(chat): use shared bubble and composer in chat route"
```

### Task 5: Convert `/search` to Chat-First UI with Shared Primitives

**Files:**
- Modify: `frontend/app/(dashboard)/search/page.tsx`
- Create: `frontend/src/components/chat/shared/__tests__/SearchChatMode.test.tsx`
- Modify: `frontend/src/components/chat/shared/messageViewModel.ts`

**Step 1: Write the failing test**

```typescript
import { render, screen } from '@testing-library/react';
import SearchPage from '@/app/(dashboard)/search/page';

describe('SearchPage chat mode', () => {
  it('renders shared composer affordance', () => {
    render(<SearchPage />);
    expect(screen.getByPlaceholderText(/inject query into neural stream/i)).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/SearchChatMode.test.tsx`
Expected: FAIL because `/search` still uses standalone search terminal structure.

**Step 3: Write minimal implementation**

```tsx
// In frontend/app/(dashboard)/search/page.tsx:
// - Replace bespoke search layout with shared chat shell composition.
// - Render query as user ChatBubble, synthesized answer as assistant ChatBubble.
// - Keep searchService call and result handling intact.
// - Reuse shared ChatComposer for input and submit behavior.
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/SearchChatMode.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/app/(dashboard)/search/page.tsx frontend/src/components/chat/shared/__tests__/SearchChatMode.test.tsx frontend/src/components/chat/shared/messageViewModel.ts
git commit -m "feat(search): adopt shared chat-first ui"
```

### Task 6: Final Verification and Documentation

**Files:**
- Modify (if needed): `docs/plans/2026-02-18-chat-ui-ux-consistency-design.md`
- Optional update: `frontend/src/components/chat/index.ts`

**Step 1: Run focused test suite**

Run:

```bash
npm --prefix frontend test -- --watch=false --runInBand \
  src/utils/__tests__/citationParser.test.ts \
  src/components/chat/shared/__tests__/messageViewModel.test.ts \
  src/components/chat/shared/__tests__/ChatBubble.test.tsx \
  src/components/chat/shared/__tests__/ChatComposer.test.tsx \
  src/components/chat/shared/__tests__/SearchChatMode.test.tsx
```

Expected: PASS

**Step 2: Run lint and type-check for touched frontend files**

Run:

```bash
npm --prefix frontend run lint
npm --prefix frontend run type-check
```

Expected: no blocking errors for touched scope (or documented existing pre-existing issues).

**Step 3: Manual verification checklist**

- Verify `/chat` and `/search` show identical bubble visual language.
- Verify identical metadata row (role badge/time/model) placement.
- Verify Enter/Shift+Enter parity.
- Verify citation click behavior opens expected panel/navigation.
- Verify mobile viewport keeps composer usable and bubbles readable.

**Step 4: Final commit**

```bash
git add frontend docs/plans/2026-02-18-chat-ui-ux-consistency-design.md
git commit -m "feat(chat-search): unify chat ui ux across routes"
```

## Skill References

- Use `@test-driven-development` for every code change cycle.
- Use `@verification-before-completion` before reporting done.
- Use `@receiving-code-review` if review feedback conflicts with design goals.
