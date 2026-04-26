# Chat Missing Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the basic chat features that are either UI-only shells or missing entirely from `/chat` — thread rename/delete/multi-select, message regenerate, file attach, voice input, a visible ContextRail, and chat export.

**Architecture:** Frontend-only work. All backend endpoints already exist (`workspaceService.updateThread`, `deleteThread`, `bulkDeleteThreads`, `uploadDocument`). UI components (`ChatSidebar`, `ChatInput`, `TerminalChatBubble`, `ContextRail`) already have the empty `onClick`/prop hooks — we wire them up, add the missing state, and write tests around the new behavior.

**Tech Stack:** Next.js 15 App Router · React 18 client components · Zustand (`useChatStore`) · `workspaceService` (Axios) · lucide-react icons · Tailwind + CSS variables · Jest + `@testing-library/react` (existing test infra at `frontend/src/components/chat/__tests__/`).

**Phasing:** Four independent phases. Each one is committable/shippable on its own. P0 is the one the user literally named ("select the chat thread"), P1-P3 address the broader "lot of basic features missing" comment.

---

## Scope & Non-goals

**In scope:**

- P0 — Thread actions: multi-select mode, rename, delete, bulk-delete
- P1 — Message actions: regenerate assistant message, copy-all-messages
- P2 — Input features: file attach → document upload, basic voice input (Web Speech API), model picker dropdown
- P3 — Layout: lower `ContextRail` breakpoint from `xl:` → `lg:`, add "Export chat" menu (Markdown + JSON)

**Out of scope:** Share-by-link, collaborative editing, edit-past-message, per-thread search, pin/archive, keyboard-shortcut overhaul, HITL UI redesign, any backend changes.

**Pre-req check (one-time, before Task 1):**

- `cd frontend && npm install` — ensure deps resolved
- `npm run test -- --testPathPattern=ChatSidebar` — baseline: 11 tests pass
- `git checkout -b feat/chat-missing-features` from current branch
- Create worktree if preferred: `git worktree add ../RAG_system-chat-features feat/chat-missing-features`

---

## Phase P0 — Thread Actions (rename · delete · multi-select)

### Task 0.1: Extend `ChatSidebar` props with action callbacks (failing test)

**Files:**

- Test: `frontend/src/components/chat/__tests__/ChatSidebar.test.tsx` (modify)

**Step 1: Add failing tests at bottom of the existing `describe('ChatSidebar', ...)` block**

```tsx
it("calls onRename when rename hover action clicked", () => {
  const onRename = jest.fn();
  render(<ChatSidebar {...defaultProps} onRename={onRename} />);
  const row = screen.getByText("Alpha Chat").closest("button")!;
  fireEvent.mouseEnter(row);
  fireEvent.click(screen.getByLabelText("Rename Alpha Chat"));
  expect(onRename).toHaveBeenCalledWith("conv-1");
});

it("calls onDelete when delete hover action clicked", () => {
  const onDelete = jest.fn();
  render(<ChatSidebar {...defaultProps} onDelete={onDelete} />);
  const row = screen.getByText("Alpha Chat").closest("button")!;
  fireEvent.mouseEnter(row);
  fireEvent.click(screen.getByLabelText("Delete Alpha Chat"));
  expect(onDelete).toHaveBeenCalledWith("conv-1");
});

it("enters multi-select mode when Select toolbar button clicked", () => {
  render(<ChatSidebar {...defaultProps} />);
  fireEvent.click(screen.getByRole("button", { name: /^Select$/i }));
  // Checkboxes should now appear on each row
  expect(screen.getAllByRole("checkbox")).toHaveLength(3);
});

it("calls onBulkDelete with selected ids from multi-select mode", () => {
  const onBulkDelete = jest.fn();
  render(<ChatSidebar {...defaultProps} onBulkDelete={onBulkDelete} />);
  fireEvent.click(screen.getByRole("button", { name: /^Select$/i }));
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
  fireEvent.click(screen.getAllByRole("checkbox")[1]);
  fireEvent.click(screen.getByRole("button", { name: /Delete \(2\)/i }));
  expect(onBulkDelete).toHaveBeenCalledWith(["conv-1", "conv-2"]);
});
```

**Step 2: Run — expect all four to FAIL**

```bash
cd frontend && npm run test -- --testPathPattern=ChatSidebar
```

Expected: 4 new failures ("onRename is not a function", no `role=checkbox` found, etc.)

**Step 3: Commit the failing tests**

```bash
git add src/components/chat/__tests__/ChatSidebar.test.tsx
git commit -m "test(chat): add failing tests for sidebar thread actions"
```

---

### Task 0.2: Implement rename/delete hover actions in `ChatSidebar`

**Files:**

- Modify: `frontend/src/components/chat/ChatSidebar.tsx` (whole file, ~80 LOC added)

**Step 1: Add props + imports**

At top of file, extend the icon imports:

```tsx
import {
  CheckSquare,
  ChevronDown,
  MessageSquare,
  Pencil,
  Plus,
  Search,
  Square,
  Trash2,
  X,
} from "lucide-react";
```

Extend the `ChatSidebarProps` interface:

```tsx
interface ChatSidebarProps {
  conversations: SidebarConversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename?: (id: string) => void;
  onDelete?: (id: string) => void;
  onBulkDelete?: (ids: string[]) => void;
  className?: string;
}
```

**Step 2: Add multi-select state + toolbar wiring**

Inside the component, after `const [searchQuery, setSearchQuery] = useState('');`:

```tsx
const [selectMode, setSelectMode] = useState(false);
const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

const toggleSelected = (id: string) => {
  setSelectedIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });
};

const exitSelectMode = () => {
  setSelectMode(false);
  setSelectedIds(new Set());
};
```

Replace the dead "Select" button (current lines 84-92) with a toolbar that toggles mode and exposes a delete-selected action:

```tsx
{
  !selectMode ? (
    <button
      onClick={() => setSelectMode(true)}
      className="w-full flex items-center justify-start gap-2 py-1.5 px-3 rounded border border-[var(--terminal-border)] hover:border-[var(--terminal-text-dim)] hover:bg-[var(--terminal-elevated)] transition-all group"
      style={{ fontFamily: "'JetBrains Mono', monospace" }}
    >
      <CheckSquare className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
      <span className="text-[10px] text-[var(--terminal-text-dim)] uppercase tracking-wider">
        Select
      </span>
    </button>
  ) : (
    <div className="flex items-center gap-2">
      <button
        onClick={() => {
          if (onBulkDelete && selectedIds.size > 0) {
            onBulkDelete(Array.from(selectedIds));
            exitSelectMode();
          }
        }}
        disabled={selectedIds.size === 0}
        className="flex-1 flex items-center justify-center gap-2 py-1.5 px-3 rounded border border-[var(--error-red)]/40 text-[var(--error-red)] disabled:opacity-40 hover:bg-[var(--error-red)]/10 transition"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        <Trash2 className="w-3.5 h-3.5" />
        <span className="text-[10px] uppercase tracking-wider">
          Delete ({selectedIds.size})
        </span>
      </button>
      <button
        onClick={exitSelectMode}
        className="p-1.5 rounded border border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]"
        aria-label="Exit select mode"
      >
        <X className="w-3.5 h-3.5 text-[var(--terminal-text-dim)]" />
      </button>
    </div>
  );
}
```

**Step 3: Wire per-row hover actions + checkbox**

In the thread `.map()` render (around current line 133), wrap the row and add hover actions. Replace the single `<button>` with a conditional:

```tsx
<div
  key={conv.id}
  className={cn(
    "group/row relative w-full rounded-lg transition-all border",
    isActive
      ? "bg-[var(--phosphor-green)]/5 border-[var(--phosphor-green)]/20"
      : "bg-transparent border-transparent hover:bg-[var(--terminal-elevated)]",
  )}
>
  <button
    onClick={() => {
      if (selectMode) toggleSelected(conv.id);
      else onSelect(conv.id);
    }}
    className="w-full text-left flex gap-3 p-2.5"
  >
    {selectMode && (
      <input
        type="checkbox"
        checked={selectedIds.has(conv.id)}
        onChange={() => toggleSelected(conv.id)}
        onClick={(e) => e.stopPropagation()}
        className="mt-1 accent-[var(--phosphor-green)]"
        aria-label={`Select ${conv.title}`}
      />
    )}
    {/* existing MessageSquare icon + title + preview block stays as-is */}
  </button>

  {!selectMode && (
    <div className="absolute right-2 top-2 hidden group-hover/row:flex items-center gap-1">
      {onRename && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRename(conv.id);
          }}
          aria-label={`Rename ${conv.title}`}
          className="p-1 rounded hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]"
        >
          <Pencil className="w-3 h-3" />
        </button>
      )}
      {onDelete && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(conv.id);
          }}
          aria-label={`Delete ${conv.title}`}
          className="p-1 rounded hover:bg-[var(--error-red)]/10 text-[var(--terminal-text-dim)] hover:text-[var(--error-red)]"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      )}
    </div>
  )}
</div>
```

**Step 4: Run tests**

```bash
npm run test -- --testPathPattern=ChatSidebar
```

Expected: all 15 tests PASS (11 pre-existing + 4 new).

**Step 5: Commit**

```bash
git add src/components/chat/ChatSidebar.tsx
git commit -m "feat(chat): add rename/delete hover actions and multi-select mode to sidebar"
```

---

### Task 0.3: Wire page.tsx to service calls + confirmation

**Files:**

- Modify: `frontend/app/(dashboard)/chat/page.tsx:960-976`

**Step 1: Add handlers just above the `return` statement (near line 957)**

```tsx
const handleRenameThread = useCallback(
  async (threadId: string) => {
    const target = conversations.find((c) => c.id === threadId);
    const nextTitle = window.prompt("Rename thread", target?.title ?? "");
    if (!nextTitle || nextTitle.trim() === target?.title) return;
    try {
      const updated = await workspaceService.updateThread(threadId, {
        title: nextTitle.trim(),
      });
      setConversations((prev) =>
        prev.map((c) =>
          c.id === threadId ? { ...c, title: updated.title } : c,
        ),
      );
    } catch (err) {
      console.error("[Chat] Rename failed", err);
    }
  },
  [conversations],
);

const handleDeleteThread = useCallback(
  async (threadId: string) => {
    if (!window.confirm("Delete this thread? This cannot be undone.")) return;
    try {
      await workspaceService.deleteThread(threadId);
      setConversations((prev) => prev.filter((c) => c.id !== threadId));
      if (activeConversationId === threadId) {
        setActiveConversationId(null);
        setMessages([]);
        setCurrentThread(null);
        router.push(getNewChatUrl());
      }
    } catch (err) {
      console.error("[Chat] Delete failed", err);
    }
  },
  [activeConversationId, router, setCurrentThread],
);

const handleBulkDeleteThreads = useCallback(
  async (ids: string[]) => {
    if (!window.confirm(`Delete ${ids.length} threads? This cannot be undone.`))
      return;
    try {
      await workspaceService.bulkDeleteThreads(ids);
      setConversations((prev) => prev.filter((c) => !ids.includes(c.id)));
      if (activeConversationId && ids.includes(activeConversationId)) {
        setActiveConversationId(null);
        setMessages([]);
        setCurrentThread(null);
        router.push(getNewChatUrl());
      }
    } catch (err) {
      console.error("[Chat] Bulk delete failed", err);
    }
  },
  [activeConversationId, router, setCurrentThread],
);
```

**Step 2: Pass them to `<ChatSidebar>` (around line 961)**

```tsx
<ChatSidebar
  conversations={conversations}
  activeId={activeConversationId}
  onSelect={(id) => {
    setActiveConversationId(id);
    setCurrentThread(id);
    router.push(getSelectedThreadUrl(id));
  }}
  onNew={() => {
    setActiveConversationId(null);
    setMessages([]);
    setCurrentThread(null);
    router.push(getNewChatUrl());
  }}
  onRename={handleRenameThread}
  onDelete={handleDeleteThread}
  onBulkDelete={handleBulkDeleteThreads}
/>
```

**Step 3: Type-check + lint**

```bash
npm run type-check && npm run lint -- --quiet src/components/chat/ChatSidebar.tsx app/\(dashboard\)/chat/page.tsx
```

Expected: exit 0.

**Step 4: Commit**

```bash
git add app/\(dashboard\)/chat/page.tsx
git commit -m "feat(chat): wire sidebar rename/delete/bulk-delete handlers"
```

---

## Phase P1 — Message Actions (regenerate · copy-all)

### Task 1.1: Wire `onRetry` in `TerminalChatBubble`

**Files:**

- Modify: `frontend/src/components/chat/shared/TerminalChatBubble.tsx:133-142` (it already accepts an `onRetry` prop but the page never passes one)
- Modify: `frontend/app/(dashboard)/chat/page.tsx` (add `handleRegenerate`, pass to assistant bubbles only)
- Test: `frontend/src/components/chat/__tests__/TerminalChatBubble.test.tsx` (new file — we don't have one yet)

**Step 1: Create the failing test**

```tsx
// TerminalChatBubble.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { TerminalChatBubble } from "../shared/TerminalChatBubble";

describe("TerminalChatBubble", () => {
  it("does NOT show retry on user messages", () => {
    render(
      <TerminalChatBubble
        message={{ role: "user", content: "hi", timestamp: Date.now() }}
      />,
    );
    expect(
      screen.queryByLabelText(/retry|regenerate/i),
    ).not.toBeInTheDocument();
  });

  it("calls onRetry when regenerate button clicked on assistant message", () => {
    const onRetry = jest.fn();
    render(
      <TerminalChatBubble
        message={{ role: "assistant", content: "hi", timestamp: Date.now() }}
        onRetry={onRetry}
      />,
    );
    fireEvent.click(screen.getByLabelText(/retry|regenerate/i));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
```

**Step 2: Run → expect 2 failures.**

**Step 3: In `TerminalChatBubble.tsx` around line 130-142, guard the retry button so it only renders for assistants + has an aria-label:**

```tsx
{
  message.role === "assistant" && onRetry && (
    <button onClick={onRetry} aria-label="Regenerate response" className="...">
      <RefreshCw className="h-3.5 w-3.5" />
    </button>
  );
}
```

**Step 4: In `page.tsx`, add `handleRegenerate` — reuse `handleSubmit`'s flow with the last user message as input:**

```tsx
const handleRegenerate = useCallback(
  (assistantMessageIndex: number) => {
    const priorUser = [...displayedMessages]
      .slice(0, assistantMessageIndex)
      .reverse()
      .find((m) => m.role === "user");
    if (!priorUser) return;
    setMessages((prev) => prev.slice(0, assistantMessageIndex)); // drop bad reply
    setInput(priorUser.content);
    // Defer submit so state flush happens first
    setTimeout(() => handleSubmit(), 0);
  },
  [displayedMessages, handleSubmit],
);
```

Then in the bubble map (search page.tsx for `<TerminalChatBubble`):

```tsx
<TerminalChatBubble
  key={message.id ?? index}
  message={message}
  onCitationClick={handleCitationClick}
  onRetry={
    message.role === "assistant" ? () => handleRegenerate(index) : undefined
  }
/>
```

**Step 5: Run tests + type-check + commit**

```bash
npm run test -- --testPathPattern=TerminalChatBubble && npm run type-check
git add src/components/chat/shared/TerminalChatBubble.tsx src/components/chat/__tests__/TerminalChatBubble.test.tsx app/\(dashboard\)/chat/page.tsx
git commit -m "feat(chat): wire regenerate action on assistant messages"
```

---

## Phase P2 — Input Features (file attach · voice · model picker)

### Task 2.1: File attach → `workspaceService.uploadDocument`

**Files:**

- Modify: `frontend/src/components/chat/ChatInput.tsx:144-153`
- Modify: `frontend/app/(dashboard)/chat/page.tsx` (pass `onAttach`)

**Step 1: Extend `ChatInputProps` with `onAttach?: (files: FileList) => void`.**

**Step 2: Replace the Paperclip button with a hidden `<input type="file" multiple>` + label trigger:**

```tsx
<label
  className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] ... cursor-pointer"
  aria-label="Attach artifact"
>
  <Paperclip className="w-4 h-4 ..." />
  <input
    type="file"
    multiple
    className="hidden"
    onChange={(e) => {
      if (e.target.files && onAttach) onAttach(e.target.files);
      e.target.value = "";
    }}
  />
</label>
```

**Step 3: In `page.tsx`, add `handleAttach` that uploads each file via `workspaceService.uploadDocument({ file, workspace_id: workspace.id })` and shows progress toast (reuse existing `sonner` `toast` if present; otherwise console.log placeholder).**

**Step 4: Test: create `ChatInput.test.tsx` asserting that `onAttach` is called with a `FileList` when a file is chosen. Use `Object.defineProperty(input, 'files', { value: dataTransfer.files })`.**

**Step 5: Commit: `feat(chat): wire file attach to workspace document upload`**

---

### Task 2.2: Voice input (Web Speech API, best-effort)

**Files:**

- Modify: `frontend/src/components/chat/ChatInput.tsx:154-164`

**Step 1: Guard the feature so it's a no-op if `window.SpeechRecognition` is undefined.**

```tsx
const [isListening, setIsListening] = useState(false);
const recognitionRef = useRef<any>(null);

const toggleVoice = () => {
  const SR =
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition;
  if (!SR) return;
  if (isListening) {
    recognitionRef.current?.stop();
    setIsListening(false);
    return;
  }
  const r = new SR();
  r.continuous = false;
  r.interimResults = false;
  r.lang = "en-US";
  r.onresult = (e: any) => onChange(value + e.results[0][0].transcript);
  r.onend = () => setIsListening(false);
  recognitionRef.current = r;
  r.start();
  setIsListening(true);
};
```

**Step 2: Bind `onClick={toggleVoice}` and pulse the Mic icon when `isListening`.**

**Step 3: Unit test — mock `window.SpeechRecognition`, assert the button toggles class / calls `start`/`stop`.**

**Step 4: Commit: `feat(chat): add voice input via Web Speech API`**

---

### Task 2.3: Model picker dropdown

**Files:**

- Modify: `frontend/src/components/chat/ChatHeader.tsx`
- Modify: `frontend/src/store/chat-store.ts` (add `selectedModel: string` + setter)

**Step 1: Define supported models locally (reuse `ModelSelector.tsx` if it already implements this — check first).**

```bash
grep -n "export" frontend/src/components/chat/ModelSelector.tsx | head
```

**Step 2: If `ModelSelector` already exists with the shape we need, just drop it into the header. Otherwise: build minimal `<select>` wrapped in styled button (match terminal aesthetic).**

**Step 3: Persist selected model in `useChatStore`; pipe it into `agentChatService.streamAgentResponse({ model: selectedModel, ... })`.**

**Step 4: Test: asserts `chat-store` state changes on model selection.**

**Step 5: Commit: `feat(chat): add model picker to chat header`**

---

## Phase P3 — Layout Polish (ContextRail breakpoint · export)

### Task 3.1: Lower ContextRail breakpoint

**Files:**

- Modify: `frontend/app/(dashboard)/chat/layout.tsx:1012`

**Step 1: Change `"hidden xl:flex shrink-0 w-[360px] ..."` to `"hidden lg:flex shrink-0 w-[320px] ..."`. Verify at 1024px viewport in DevTools.**

**Step 2: Visual check + commit. No tests needed — pure CSS.**

```bash
git add app/\(dashboard\)/chat/layout.tsx
git commit -m "feat(chat): show ContextRail at lg breakpoint (≥1024px) instead of xl"
```

---

### Task 3.2: Export chat (Markdown + JSON)

**Files:**

- Create: `frontend/src/components/chat/shared/exportConversation.ts`
- Modify: `frontend/src/components/chat/ChatHeader.tsx` (add "Export" menu button)

**Step 1: Write `exportConversation.ts`:**

```ts
import type { Message } from "@/types/chat";

export function exportAsMarkdown(title: string, messages: Message[]): string {
  const header = `# ${title}\n\n`;
  const body = messages
    .map((m) => {
      const who = m.role === "user" ? "**You**" : "**Assistant**";
      return `${who} · ${new Date(m.timestamp).toISOString()}\n\n${m.content}\n`;
    })
    .join("\n---\n\n");
  return header + body;
}

export function exportAsJson(title: string, messages: Message[]): string {
  return JSON.stringify({ title, messages }, null, 2);
}

export function downloadFile(name: string, mime: string, content: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
```

**Step 2: Unit tests for each function (pure — easy TDD):**

```ts
// exportConversation.test.ts
import { exportAsMarkdown, exportAsJson } from "../exportConversation";

it("serializes messages as markdown with role headers", () => {
  const md = exportAsMarkdown("Demo", [
    { role: "user", content: "hi", timestamp: 0 },
    { role: "assistant", content: "hey", timestamp: 1 },
  ]);
  expect(md).toMatch(/^# Demo/);
  expect(md).toContain("**You**");
  expect(md).toContain("**Assistant**");
});

it("serializes messages as parseable JSON", () => {
  const json = exportAsJson("Demo", [
    { role: "user", content: "hi", timestamp: 0 },
  ]);
  const parsed = JSON.parse(json);
  expect(parsed.title).toBe("Demo");
  expect(parsed.messages).toHaveLength(1);
});
```

**Step 3: Add export menu in `ChatHeader` — Radix `DropdownMenu` with two items.**

**Step 4: Commit: `feat(chat): add markdown + json export`**

---

## Final Verification

**After all phases:**

```bash
cd frontend
npm run validate       # lint + type-check + test
npm run build          # prod build succeeds
```

**Manual smoke test** (if local stack available):

1. `/chat` renders sidebar with threads
2. Hover a thread → Pencil + Trash icons appear
3. Click Pencil → prompt → title updates in UI and DB
4. Click Trash → confirm → row disappears
5. Click "Select" → checkboxes appear, pick 2, click "Delete (2)" → both gone
6. Send a message, wait for assistant reply, click RefreshCw → assistant regenerates
7. Click Paperclip → file picker opens → select a PDF → appears in uploads
8. Click Mic (Chrome) → say something → text appears in input
9. Resize window to 1100px → ContextRail visible
10. Open header Export menu → download .md and .json files

**Rollback strategy:** each phase is a distinct commit series. Revert with `git revert <phase-start>..<phase-end>` if a phase regresses.

**Risk notes:**

- `bulkDeleteThreads` partial failures — backend returns `BulkThreadResponse` with per-id status; we currently ignore that. Fine for first pass; surface errors in a follow-up if users complain.
- Web Speech API is Chromium-only — graceful no-op elsewhere is intentional.
- Model picker: don't ship without verifying `agentChatService` actually accepts the `model` param; otherwise just wire to state and leave a TODO for the service pipe.

---

## Execution Handoff

Plan saved to `docs/plans/2026-04-20-chat-missing-features-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** — I dispatch a fresh subagent per task, review between tasks, commit after each step.

**2. Parallel Session (separate)** — Open a new session inside a worktree with executing-plans, batch through with checkpoints.

Which?
