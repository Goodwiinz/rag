# Global Agent Chat Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the project-scoped Quick Chat widget into a global AI agent available on every page, with context detection, tool execution, persistent conversations, and an expandable panel-to-sidebar UI.

**Architecture:** Extend existing chat infrastructure — reuse `ChatService`, `Thread`/`ChatMessage` models, `/chat/completions` endpoint. Add agent tool execution backend (`/api/v1/agent/execute`). Replace per-page `ProjectChatWidget` with global `GlobalAgentChat` mounted in `SidebarLayout`. New `useGlobalAgent` hook handles context detection, tool dispatch, streaming, and persistence.

**Tech Stack:** Next.js 15, React 18, TypeScript, Zustand, FastAPI, OpenAI function-calling (gpt-4o), existing PostgreSQL models, SSE streaming.

**Design doc:** `docs/plans/2026-03-15-global-agent-chat-design.md`

---

## Task 1: Agent Types & Store Foundation

**Files:**

- Create: `frontend/src/types/agent-chat.ts`
- Create: `frontend/src/store/agentChatStore.ts`
- Test: `frontend/src/store/__tests__/agentChatStore.test.ts`

**Step 1: Write the types file**

```typescript
// frontend/src/types/agent-chat.ts

/**
 * Types for the Global Agent Chat system.
 * Extends chat-widget types with agent-specific capabilities.
 */

// ============================================================================
// Page Context Types
// ============================================================================

export type PageContextType =
  | "project"
  | "chat"
  | "documents"
  | "arxiv"
  | "research"
  | "analytics"
  | "overview"
  | "settings"
  | "upload"
  | "entities"
  | "diagnostics"
  | "unknown";

export interface PageContext {
  type: PageContextType;
  label: string;
  /** Project ID if on a project page */
  projectId?: string;
  /** Project name for display */
  projectName?: string;
  /** Additional context metadata */
  metadata?: Record<string, unknown>;
}

// ============================================================================
// Agent Message Types
// ============================================================================

export interface AgentCitation {
  documentId: string;
  documentTitle: string;
  snippet?: string;
  page?: number;
  score?: number;
}

export interface ToolExecution {
  id: string;
  toolName: string;
  toolDisplayName: string;
  args: Record<string, unknown>;
  status: "running" | "completed" | "failed";
  result?: unknown;
  error?: string;
  durationMs?: number;
}

export interface AgentMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  timestamp: Date;
  citations?: AgentCitation[];
  toolExecutions?: ToolExecution[];
  isStreaming?: boolean;
  /** Backend thread message ID for persistence */
  backendMessageId?: string;
}

// ============================================================================
// Thread Types
// ============================================================================

export interface AgentThread {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messageCount: number;
  lastMessage?: string;
  pageContext?: PageContext;
  /** Linked project ID if started from project page */
  projectId?: string;
}

// ============================================================================
// UI State Types
// ============================================================================

export type AgentUIMode = "closed" | "panel" | "sidebar";

export interface AgentChatState {
  /** Current UI mode */
  uiMode: AgentUIMode;
  /** Active thread ID */
  activeThreadId: string | null;
  /** Thread list */
  threads: AgentThread[];
  /** Messages for active thread */
  messages: AgentMessage[];
  /** Whether assistant is streaming */
  isStreaming: boolean;
  /** Current input value */
  inputValue: string;
  /** Unread indicator */
  hasUnread: boolean;
  /** Current page context */
  pageContext: PageContext;
  /** Loading states */
  isLoadingThreads: boolean;
  isLoadingMessages: boolean;
}

export interface AgentChatActions {
  // UI
  openPanel: () => void;
  openSidebar: () => void;
  close: () => void;
  toggle: () => void;
  // Input
  setInputValue: (value: string) => void;
  // Messages
  sendMessage: () => Promise<void>;
  clearMessages: () => void;
  // Threads
  newThread: () => void;
  selectThread: (threadId: string) => void;
  loadThreads: () => Promise<void>;
  loadThreadMessages: (threadId: string) => Promise<void>;
  // Context
  setPageContext: (context: PageContext) => void;
}
```

**Step 2: Write failing test for the store**

```typescript
// frontend/src/store/__tests__/agentChatStore.test.ts

import { useAgentChatStore } from "@/store/agentChatStore";

describe("agentChatStore", () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
  });

  describe("initial state", () => {
    it("starts with closed UI mode", () => {
      const state = useAgentChatStore.getState();
      expect(state.uiMode).toBe("closed");
    });

    it("has no active thread", () => {
      const state = useAgentChatStore.getState();
      expect(state.activeThreadId).toBeNull();
    });

    it("has empty messages", () => {
      const state = useAgentChatStore.getState();
      expect(state.messages).toEqual([]);
    });

    it("has unknown page context", () => {
      const state = useAgentChatStore.getState();
      expect(state.pageContext.type).toBe("unknown");
    });
  });

  describe("UI mode transitions", () => {
    it("openPanel sets mode to panel", () => {
      useAgentChatStore.getState().openPanel();
      expect(useAgentChatStore.getState().uiMode).toBe("panel");
    });

    it("openSidebar sets mode to sidebar", () => {
      useAgentChatStore.getState().openSidebar();
      expect(useAgentChatStore.getState().uiMode).toBe("sidebar");
    });

    it("close sets mode to closed", () => {
      useAgentChatStore.getState().openPanel();
      useAgentChatStore.getState().close();
      expect(useAgentChatStore.getState().uiMode).toBe("closed");
    });

    it("toggle cycles closed → panel → closed", () => {
      useAgentChatStore.getState().toggle();
      expect(useAgentChatStore.getState().uiMode).toBe("panel");
      useAgentChatStore.getState().toggle();
      expect(useAgentChatStore.getState().uiMode).toBe("closed");
    });

    it("openPanel clears unread", () => {
      useAgentChatStore.setState({ hasUnread: true });
      useAgentChatStore.getState().openPanel();
      expect(useAgentChatStore.getState().hasUnread).toBe(false);
    });
  });

  describe("input management", () => {
    it("setInputValue updates input", () => {
      useAgentChatStore.getState().setInputValue("hello");
      expect(useAgentChatStore.getState().inputValue).toBe("hello");
    });
  });

  describe("page context", () => {
    it("setPageContext updates context", () => {
      useAgentChatStore.getState().setPageContext({
        type: "project",
        label: "Test Project",
        projectId: "abc-123",
        projectName: "Test Project",
      });
      const ctx = useAgentChatStore.getState().pageContext;
      expect(ctx.type).toBe("project");
      expect(ctx.projectId).toBe("abc-123");
    });
  });

  describe("thread management", () => {
    it("newThread clears active thread and messages", () => {
      useAgentChatStore.setState({
        activeThreadId: "thread-1",
        messages: [
          { id: "1", role: "user", content: "hi", timestamp: new Date() },
        ],
      });
      useAgentChatStore.getState().newThread();
      expect(useAgentChatStore.getState().activeThreadId).toBeNull();
      expect(useAgentChatStore.getState().messages).toEqual([]);
    });

    it("selectThread sets activeThreadId", () => {
      useAgentChatStore.getState().selectThread("thread-42");
      expect(useAgentChatStore.getState().activeThreadId).toBe("thread-42");
    });
  });
});
```

**Step 3: Run test to verify it fails**

Run: `cd frontend && npx jest src/store/__tests__/agentChatStore.test.ts --no-coverage`
Expected: FAIL — cannot resolve `@/store/agentChatStore`

**Step 4: Write the store implementation**

```typescript
// frontend/src/store/agentChatStore.ts

import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type {
  AgentChatState,
  AgentChatActions,
  AgentMessage,
  AgentThread,
  AgentUIMode,
  PageContext,
} from "@/types/agent-chat";

const DEFAULT_PAGE_CONTEXT: PageContext = {
  type: "unknown",
  label: "Dashboard",
};

interface AgentChatStore extends AgentChatState, AgentChatActions {
  reset: () => void;
}

const initialState: AgentChatState = {
  uiMode: "closed",
  activeThreadId: null,
  threads: [],
  messages: [],
  isStreaming: false,
  inputValue: "",
  hasUnread: false,
  pageContext: DEFAULT_PAGE_CONTEXT,
  isLoadingThreads: false,
  isLoadingMessages: false,
};

export const useAgentChatStore = create<AgentChatStore>()(
  immer((set, get) => ({
    ...initialState,

    // UI
    openPanel: () =>
      set((state) => {
        state.uiMode = "panel";
        state.hasUnread = false;
      }),

    openSidebar: () =>
      set((state) => {
        state.uiMode = "sidebar";
        state.hasUnread = false;
      }),

    close: () =>
      set((state) => {
        state.uiMode = "closed";
      }),

    toggle: () =>
      set((state) => {
        if (state.uiMode === "closed") {
          state.uiMode = "panel";
          state.hasUnread = false;
        } else {
          state.uiMode = "closed";
        }
      }),

    // Input
    setInputValue: (value: string) =>
      set((state) => {
        state.inputValue = value;
      }),

    // Messages
    sendMessage: async () => {
      // Implemented in Task 5 (agent service integration)
    },

    clearMessages: () =>
      set((state) => {
        state.messages = [];
        state.activeThreadId = null;
        state.isStreaming = false;
      }),

    // Threads
    newThread: () =>
      set((state) => {
        state.activeThreadId = null;
        state.messages = [];
        state.inputValue = "";
      }),

    selectThread: (threadId: string) =>
      set((state) => {
        state.activeThreadId = threadId;
      }),

    loadThreads: async () => {
      // Implemented in Task 5
    },

    loadThreadMessages: async (threadId: string) => {
      // Implemented in Task 5
    },

    // Context
    setPageContext: (context: PageContext) =>
      set((state) => {
        state.pageContext = context;
      }),

    // Reset
    reset: () => set(() => ({ ...initialState })),
  })),
);
```

**Step 5: Run test to verify it passes**

Run: `cd frontend && npx jest src/store/__tests__/agentChatStore.test.ts --no-coverage`
Expected: PASS — all 10 tests green

**Step 6: Commit**

```bash
git add frontend/src/types/agent-chat.ts frontend/src/store/agentChatStore.ts frontend/src/store/__tests__/agentChatStore.test.ts
git commit -m "feat(agent-chat): add types, Zustand store, and tests for global agent chat"
```

---

## Task 2: usePageContext Hook

**Files:**

- Create: `frontend/src/hooks/usePageContext.ts`
- Test: `frontend/src/hooks/__tests__/usePageContext.test.tsx`

**Step 1: Write failing test**

```typescript
// frontend/src/hooks/__tests__/usePageContext.test.tsx

import { renderHook } from "@testing-library/react";

// Mock next/navigation
const mockPathname = jest.fn<string, []>();
jest.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
  useParams: () => ({}),
}));

// Mock project store
const mockCurrentProject = jest.fn();
jest.mock("@/store/projectStore", () => ({
  useProjectStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ currentProject: mockCurrentProject() }),
}));

import { usePageContext } from "@/hooks/usePageContext";

describe("usePageContext", () => {
  beforeEach(() => {
    mockPathname.mockReturnValue("/");
    mockCurrentProject.mockReturnValue(null);
  });

  it("returns overview context for root path", () => {
    mockPathname.mockReturnValue("/");
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe("overview");
  });

  it("returns documents context for /documents", () => {
    mockPathname.mockReturnValue("/documents");
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe("documents");
    expect(result.current.label).toBe("Documents");
  });

  it("returns arxiv context for /arxiv", () => {
    mockPathname.mockReturnValue("/arxiv");
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe("arxiv");
  });

  it("returns project context with project data", () => {
    mockPathname.mockReturnValue("/projects/abc-123");
    mockCurrentProject.mockReturnValue({ id: "abc-123", name: "My Project" });
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe("project");
    expect(result.current.projectId).toBe("abc-123");
    expect(result.current.projectName).toBe("My Project");
  });

  it("returns chat context for /chat", () => {
    mockPathname.mockReturnValue("/chat");
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe("chat");
  });

  it("returns unknown for unrecognized paths", () => {
    mockPathname.mockReturnValue("/something-random");
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe("unknown");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest src/hooks/__tests__/usePageContext.test.tsx --no-coverage`
Expected: FAIL — cannot resolve `@/hooks/usePageContext`

**Step 3: Write the hook**

```typescript
// frontend/src/hooks/usePageContext.ts

"use client";

import { useMemo } from "react";
import { usePathname } from "next/navigation";
import { useProjectStore } from "@/store/projectStore";
import type { PageContext, PageContextType } from "@/types/agent-chat";

const PATH_CONTEXT_MAP: Record<
  string,
  { type: PageContextType; label: string }
> = {
  "/": { type: "overview", label: "Overview" },
  "/dashboard": { type: "overview", label: "Overview" },
  "/documents": { type: "documents", label: "Documents" },
  "/arxiv": { type: "arxiv", label: "ArXiv Papers" },
  "/chat": { type: "chat", label: "Chat" },
  "/research": { type: "research", label: "Research" },
  "/analytics": { type: "analytics", label: "Analytics" },
  "/diagnostics": { type: "diagnostics", label: "Diagnostics" },
  "/settings": { type: "settings", label: "Settings" },
  "/upload": { type: "upload", label: "Upload" },
  "/entities": { type: "entities", label: "Entities" },
};

export function usePageContext(): PageContext {
  const pathname = usePathname();
  const currentProject = useProjectStore((s) => s.currentProject);

  return useMemo(() => {
    if (!pathname) {
      return { type: "unknown" as PageContextType, label: "Dashboard" };
    }

    // Project pages: /projects/:id or /projects/:id/...
    const projectMatch = pathname.match(/^\/projects\/([^/]+)/);
    if (projectMatch) {
      const projectId = projectMatch[1];
      return {
        type: "project" as PageContextType,
        label: currentProject?.name || "Project",
        projectId,
        projectName: currentProject?.name,
      };
    }

    // Direct path match
    const match = PATH_CONTEXT_MAP[pathname];
    if (match) {
      return { ...match };
    }

    // Prefix match for nested routes (e.g., /chat/thread-id)
    for (const [path, ctx] of Object.entries(PATH_CONTEXT_MAP)) {
      if (path !== "/" && pathname.startsWith(path + "/")) {
        return { ...ctx };
      }
    }

    return { type: "unknown" as PageContextType, label: "Dashboard" };
  }, [pathname, currentProject]);
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest src/hooks/__tests__/usePageContext.test.tsx --no-coverage`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/hooks/usePageContext.ts frontend/src/hooks/__tests__/usePageContext.test.tsx
git commit -m "feat(agent-chat): add usePageContext hook for automatic page context detection"
```

---

## Task 3: Agent Chat UI Components (Panel Mode)

**Files:**

- Create: `frontend/src/components/agent-chat/AgentFAB.tsx`
- Create: `frontend/src/components/agent-chat/AgentPanel.tsx`
- Create: `frontend/src/components/agent-chat/AgentPanelHeader.tsx`
- Create: `frontend/src/components/agent-chat/AgentContextBar.tsx`
- Create: `frontend/src/components/agent-chat/AgentMessageList.tsx`
- Create: `frontend/src/components/agent-chat/AgentMessageItem.tsx`
- Create: `frontend/src/components/agent-chat/ToolExecutionCard.tsx`
- Create: `frontend/src/components/agent-chat/AgentInput.tsx`
- Create: `frontend/src/components/agent-chat/GlobalAgentChat.tsx`
- Test: `frontend/src/components/agent-chat/__tests__/GlobalAgentChat.test.tsx`
- Test: `frontend/src/components/agent-chat/__tests__/AgentFAB.test.tsx`

**Step 1: Write AgentFAB component**

```typescript
// frontend/src/components/agent-chat/AgentFAB.tsx

'use client';

import React from 'react';
import { Bot, X } from 'lucide-react';
import { useAgentChatStore } from '@/store/agentChatStore';

export function AgentFAB() {
  const uiMode = useAgentChatStore((s) => s.uiMode);
  const toggle = useAgentChatStore((s) => s.toggle);
  const hasUnread = useAgentChatStore((s) => s.hasUnread);

  const isOpen = uiMode !== 'closed';

  return (
    <button
      onClick={toggle}
      aria-label={isOpen ? 'Close agent chat' : 'Open agent chat'}
      className="fixed bottom-6 right-6 z-50 h-12 w-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-all flex items-center justify-center group"
    >
      {isOpen ? (
        <X className="h-5 w-5" />
      ) : (
        <Bot className="h-5 w-5" />
      )}
      {hasUnread && !isOpen && (
        <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-destructive border-2 border-background" />
      )}
      {/* Keyboard shortcut hint */}
      {!isOpen && (
        <span className="absolute -top-8 right-0 text-[10px] text-muted-foreground bg-popover border border-border rounded px-1.5 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
          ⌘K
        </span>
      )}
    </button>
  );
}
```

**Step 2: Write AgentContextBar**

```typescript
// frontend/src/components/agent-chat/AgentContextBar.tsx

'use client';

import React from 'react';
import { MapPin } from 'lucide-react';
import type { PageContext } from '@/types/agent-chat';

interface AgentContextBarProps {
  context: PageContext;
}

export function AgentContextBar({ context }: AgentContextBarProps) {
  if (context.type === 'unknown') return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-muted/30 text-xs text-muted-foreground">
      <MapPin className="h-3 w-3 shrink-0" />
      <span className="truncate">
        {context.type === 'project' && context.projectName
          ? `Project: ${context.projectName}`
          : context.label}
      </span>
    </div>
  );
}
```

**Step 3: Write ToolExecutionCard**

```typescript
// frontend/src/components/agent-chat/ToolExecutionCard.tsx

'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import type { ToolExecution } from '@/types/agent-chat';

interface ToolExecutionCardProps {
  execution: ToolExecution;
}

export function ToolExecutionCard({ execution }: ToolExecutionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusIcon = {
    running: <Loader2 className="h-3 w-3 animate-spin text-primary" />,
    completed: <CheckCircle2 className="h-3 w-3 text-green-500" />,
    failed: <XCircle className="h-3 w-3 text-destructive" />,
  }[execution.status];

  return (
    <div className="border border-border rounded-md bg-muted/20 text-xs my-1">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-muted/40 transition-colors text-left"
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} tool execution: ${execution.toolDisplayName}`}
      >
        {isExpanded ? (
          <ChevronDown className="h-3 w-3 shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0" />
        )}
        {statusIcon}
        <span className="text-foreground font-medium truncate">
          {execution.toolDisplayName}
        </span>
        {execution.durationMs != null && (
          <span className="ml-auto text-muted-foreground">
            {execution.durationMs}ms
          </span>
        )}
      </button>
      {isExpanded && execution.result && (
        <div className="px-3 pb-2 text-muted-foreground border-t border-border pt-2">
          <pre className="whitespace-pre-wrap break-words text-[11px]">
            {typeof execution.result === 'string'
              ? execution.result
              : JSON.stringify(execution.result, null, 2)}
          </pre>
        </div>
      )}
      {isExpanded && execution.error && (
        <div className="px-3 pb-2 text-destructive border-t border-border pt-2">
          {execution.error}
        </div>
      )}
    </div>
  );
}
```

**Step 4: Write AgentMessageItem**

```typescript
// frontend/src/components/agent-chat/AgentMessageItem.tsx

'use client';

import React from 'react';
import { User, Bot } from 'lucide-react';
import { ToolExecutionCard } from './ToolExecutionCard';
import type { AgentMessage } from '@/types/agent-chat';

interface AgentMessageItemProps {
  message: AgentMessage;
}

export function AgentMessageItem({ message }: AgentMessageItemProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? '' : 'bg-muted/20'}`}>
      <div
        className={`shrink-0 h-6 w-6 rounded-full flex items-center justify-center ${
          isUser ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
        }`}
      >
        {isUser ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-foreground whitespace-pre-wrap break-words">
          {message.content}
          {message.isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-primary animate-pulse ml-0.5 align-text-bottom" />
          )}
        </div>
        {/* Tool executions */}
        {message.toolExecutions?.map((exec) => (
          <ToolExecutionCard key={exec.id} execution={exec} />
        ))}
        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.citations.map((cite, i) => (
              <span
                key={`${cite.documentId}-${i}`}
                className="inline-flex items-center text-[10px] bg-primary/10 text-primary rounded px-1.5 py-0.5"
                title={cite.snippet}
              >
                {cite.documentTitle}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 5: Write AgentMessageList**

```typescript
// frontend/src/components/agent-chat/AgentMessageList.tsx

'use client';

import React, { useRef, useEffect } from 'react';
import { Bot } from 'lucide-react';
import { AgentMessageItem } from './AgentMessageItem';
import type { AgentMessage } from '@/types/agent-chat';

interface AgentMessageListProps {
  messages: AgentMessage[];
  isStreaming: boolean;
}

export function AgentMessageList({ messages, isStreaming }: AgentMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, isStreaming]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
        <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center mb-3">
          <Bot className="h-5 w-5 text-muted-foreground" />
        </div>
        <p className="text-sm font-medium text-foreground">AI Research Agent</p>
        <p className="text-xs text-muted-foreground mt-1 max-w-[260px]">
          Ask questions, search papers, manage projects, and more. I can see your current page context.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.map((msg) => (
        <AgentMessageItem key={msg.id} message={msg} />
      ))}
      {isStreaming && messages[messages.length - 1]?.role !== 'assistant' && (
        <div className="flex gap-3 px-4 py-3 bg-muted/20">
          <div className="shrink-0 h-6 w-6 rounded-full bg-muted flex items-center justify-center">
            <Bot className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
```

**Step 6: Write AgentInput**

```typescript
// frontend/src/components/agent-chat/AgentInput.tsx

'use client';

import React, { useRef, useEffect } from 'react';
import { Send } from 'lucide-react';

interface AgentInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export function AgentInput({
  value,
  onChange,
  onSend,
  disabled = false,
  placeholder = 'Ask the agent...',
}: AgentInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) {
        onSend();
      }
    }
  };

  return (
    <div className="border-t border-border p-3">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
        />
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="shrink-0 h-9 w-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
```

**Step 7: Write AgentPanelHeader**

```typescript
// frontend/src/components/agent-chat/AgentPanelHeader.tsx

'use client';

import React from 'react';
import { Maximize2, Trash2, X, Plus } from 'lucide-react';

interface AgentPanelHeaderProps {
  onExpand: () => void;
  onClear: () => void;
  onClose: () => void;
  onNewThread: () => void;
  hasMessages: boolean;
}

export function AgentPanelHeader({
  onExpand,
  onClear,
  onClose,
  onNewThread,
  hasMessages,
}: AgentPanelHeaderProps) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
      <h3 id="agent-panel-title" className="text-sm font-medium text-foreground">
        Agent
      </h3>
      <div className="flex items-center gap-1">
        <button
          onClick={onNewThread}
          aria-label="New conversation"
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onClear}
          aria-label="Clear chat messages"
          disabled={!hasMessages}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onExpand}
          aria-label="Expand to sidebar"
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onClose}
          aria-label="Close agent chat"
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
```

**Step 8: Write AgentPanel**

```typescript
// frontend/src/components/agent-chat/AgentPanel.tsx

'use client';

import React, { useRef, useEffect } from 'react';
import { AgentPanelHeader } from './AgentPanelHeader';
import { AgentContextBar } from './AgentContextBar';
import { AgentMessageList } from './AgentMessageList';
import { AgentInput } from './AgentInput';
import type { AgentMessage, PageContext } from '@/types/agent-chat';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface AgentPanelProps {
  messages: AgentMessage[];
  isStreaming: boolean;
  inputValue: string;
  pageContext: PageContext;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onClear: () => void;
  onClose: () => void;
  onExpand: () => void;
  onNewThread: () => void;
}

export function AgentPanel({
  messages,
  isStreaming,
  inputValue,
  pageContext,
  onInputChange,
  onSend,
  onClear,
  onClose,
  onExpand,
  onNewThread,
}: AgentPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Focus trap
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;

    requestAnimationFrame(() => {
      const textarea = panel.querySelector<HTMLElement>('textarea');
      textarea?.focus();
    });

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Tab') return;
      const focusable = panel!.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    panel.addEventListener('keydown', handleKeyDown);
    return () => panel.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div ref={panelRef} className="flex flex-col h-full">
      <AgentPanelHeader
        onExpand={onExpand}
        onClear={onClear}
        onClose={onClose}
        onNewThread={onNewThread}
        hasMessages={messages.length > 0}
      />
      <AgentContextBar context={pageContext} />
      <AgentMessageList messages={messages} isStreaming={isStreaming} />
      <AgentInput
        value={inputValue}
        onChange={onInputChange}
        onSend={onSend}
        disabled={isStreaming}
      />
    </div>
  );
}
```

**Step 9: Write GlobalAgentChat (root component)**

```typescript
// frontend/src/components/agent-chat/GlobalAgentChat.tsx

'use client';

import React, { useEffect, useCallback } from 'react';
import { AgentFAB } from './AgentFAB';
import { AgentPanel } from './AgentPanel';
import { useAgentChatStore } from '@/store/agentChatStore';
import { usePageContext } from '@/hooks/usePageContext';

export function GlobalAgentChat() {
  const uiMode = useAgentChatStore((s) => s.uiMode);
  const messages = useAgentChatStore((s) => s.messages);
  const isStreaming = useAgentChatStore((s) => s.isStreaming);
  const inputValue = useAgentChatStore((s) => s.inputValue);
  const pageContext = useAgentChatStore((s) => s.pageContext);
  const close = useAgentChatStore((s) => s.close);
  const openSidebar = useAgentChatStore((s) => s.openSidebar);
  const setInputValue = useAgentChatStore((s) => s.setInputValue);
  const sendMessage = useAgentChatStore((s) => s.sendMessage);
  const clearMessages = useAgentChatStore((s) => s.clearMessages);
  const newThread = useAgentChatStore((s) => s.newThread);
  const setPageContext = useAgentChatStore((s) => s.setPageContext);

  // Auto-detect and update page context
  const detectedContext = usePageContext();
  useEffect(() => {
    setPageContext(detectedContext);
  }, [detectedContext, setPageContext]);

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K to toggle
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        useAgentChatStore.getState().toggle();
      }
      // Escape to close
      if (e.key === 'Escape' && uiMode !== 'closed') {
        close();
      }
    },
    [uiMode, close]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      {/* Mobile backdrop */}
      {uiMode !== 'closed' && (
        <div
          className="fixed inset-0 z-40 bg-black/50 sm:hidden"
          aria-hidden="true"
          onClick={close}
        />
      )}

      {/* Panel mode */}
      {uiMode === 'panel' && (
        <div
          className="fixed bottom-[88px] right-6 z-50 w-[400px] h-[560px] max-sm:w-full max-sm:h-[100dvh] max-sm:bottom-0 max-sm:left-0 max-sm:right-0 max-sm:rounded-b-none max-sm:rounded-t-xl bg-background border border-border rounded-xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200"
          role="dialog"
          aria-modal="true"
          aria-label="Agent chat panel"
          aria-labelledby="agent-panel-title"
        >
          <AgentPanel
            messages={messages}
            isStreaming={isStreaming}
            inputValue={inputValue}
            pageContext={pageContext}
            onInputChange={setInputValue}
            onSend={() => void sendMessage()}
            onClear={clearMessages}
            onClose={close}
            onExpand={openSidebar}
            onNewThread={newThread}
          />
        </div>
      )}

      {/* Sidebar mode */}
      {uiMode === 'sidebar' && (
        <div
          className="fixed top-0 right-0 z-50 w-[420px] h-full bg-background border-l border-border shadow-xl animate-in slide-in-from-right duration-200"
          role="dialog"
          aria-modal="true"
          aria-label="Agent chat sidebar"
          aria-labelledby="agent-panel-title"
        >
          <AgentPanel
            messages={messages}
            isStreaming={isStreaming}
            inputValue={inputValue}
            pageContext={pageContext}
            onInputChange={setInputValue}
            onSend={() => void sendMessage()}
            onClear={clearMessages}
            onClose={close}
            onExpand={close}
            onNewThread={newThread}
          />
        </div>
      )}

      {/* FAB */}
      <AgentFAB />
    </>
  );
}
```

**Step 10: Write tests**

```typescript
// frontend/src/components/agent-chat/__tests__/AgentFAB.test.tsx

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentFAB } from '../AgentFAB';
import { useAgentChatStore } from '@/store/agentChatStore';

describe('AgentFAB', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
  });

  it('renders open button when closed', () => {
    render(<AgentFAB />);
    expect(screen.getByLabelText('Open agent chat')).toBeInTheDocument();
  });

  it('renders close button when open', () => {
    useAgentChatStore.getState().openPanel();
    render(<AgentFAB />);
    expect(screen.getByLabelText('Close agent chat')).toBeInTheDocument();
  });

  it('toggles on click', () => {
    render(<AgentFAB />);
    fireEvent.click(screen.getByLabelText('Open agent chat'));
    expect(useAgentChatStore.getState().uiMode).toBe('panel');
  });

  it('shows unread badge when hasUnread and closed', () => {
    useAgentChatStore.setState({ hasUnread: true });
    const { container } = render(<AgentFAB />);
    expect(container.querySelector('.bg-destructive')).toBeInTheDocument();
  });
});
```

```typescript
// frontend/src/components/agent-chat/__tests__/GlobalAgentChat.test.tsx

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { GlobalAgentChat } from '../GlobalAgentChat';
import { useAgentChatStore } from '@/store/agentChatStore';

// Mock usePageContext
jest.mock('@/hooks/usePageContext', () => ({
  usePageContext: () => ({ type: 'overview', label: 'Overview' }),
}));

// Mock next/navigation
jest.mock('next/navigation', () => ({
  usePathname: () => '/',
  useParams: () => ({}),
}));

describe('GlobalAgentChat', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
  });

  it('renders FAB by default', () => {
    render(<GlobalAgentChat />);
    expect(screen.getByLabelText('Open agent chat')).toBeInTheDocument();
  });

  it('shows panel when opened', () => {
    useAgentChatStore.getState().openPanel();
    render(<GlobalAgentChat />);
    expect(screen.getByLabelText('Agent chat panel')).toBeInTheDocument();
  });

  it('shows sidebar when expanded', () => {
    useAgentChatStore.getState().openSidebar();
    render(<GlobalAgentChat />);
    expect(screen.getByLabelText('Agent chat sidebar')).toBeInTheDocument();
  });

  it('shows empty state message when no messages', () => {
    useAgentChatStore.getState().openPanel();
    render(<GlobalAgentChat />);
    expect(screen.getByText('AI Research Agent')).toBeInTheDocument();
  });

  it('closes on Escape key', () => {
    useAgentChatStore.getState().openPanel();
    render(<GlobalAgentChat />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(useAgentChatStore.getState().uiMode).toBe('closed');
  });
});
```

**Step 11: Run tests**

Run: `cd frontend && npx jest src/components/agent-chat/ --no-coverage`
Expected: PASS

**Step 12: Commit**

```bash
git add frontend/src/components/agent-chat/
git commit -m "feat(agent-chat): add UI components - FAB, panel, sidebar, message list, context bar"
```

---

## Task 4: Mount GlobalAgentChat & Remove ProjectChatWidget

**Files:**

- Modify: `frontend/app/(dashboard)/layout.tsx`
- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx` (remove ProjectChatWidget import/usage)

**Step 1: Update dashboard layout to mount GlobalAgentChat**

In `frontend/app/(dashboard)/layout.tsx`, add `GlobalAgentChat` inside the layout after `SidebarLayout`:

```typescript
// Add import
import dynamic from 'next/dynamic';

const GlobalAgentChat = dynamic(
  () => import('@/components/agent-chat/GlobalAgentChat').then((m) => m.GlobalAgentChat),
  { ssr: false }
);

// In the return, add after SidebarLayout closing tag:
return (
  <SidebarLayout showBreadcrumb={shouldShowBreadcrumb} showHeader={shouldShowHeader}>
    {children}
    <GlobalAgentChat />
  </SidebarLayout>
);
```

**Step 2: Remove ProjectChatWidget from project page**

In `frontend/app/(dashboard)/projects/[id]/page.tsx`, remove the `ProjectChatWidget` import and its `<ProjectChatWidget ... />` JSX.

**Step 3: Verify type-check passes**

Run: `cd frontend && npm run type-check`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/app/(dashboard)/layout.tsx frontend/app/(dashboard)/projects/[id]/page.tsx
git commit -m "feat(agent-chat): mount GlobalAgentChat globally, remove project-scoped widget"
```

---

## Task 5: Agent Service & Chat Completion Integration

**Files:**

- Create: `frontend/src/services/agentChatService.ts`
- Modify: `frontend/src/store/agentChatStore.ts` (wire up sendMessage, loadThreads, loadThreadMessages)

**Step 1: Create the agent chat service**

```typescript
// frontend/src/services/agentChatService.ts

import { apiClient } from "@/services/apiClient";
import type {
  AgentMessage,
  AgentThread,
  PageContext,
} from "@/types/agent-chat";

export interface AgentExecuteRequest {
  messages: Array<{ role: string; content: string }>;
  page_context: {
    type: string;
    project_id?: string;
    metadata?: Record<string, unknown>;
  };
  model?: string;
  use_rag?: boolean;
  max_context_docs?: number;
  thread_id?: string;
}

export interface AgentExecuteResponse {
  message: {
    role: string;
    content: string;
  };
  model: string;
  usage: Record<string, number>;
  finish_reason: string;
  timestamp: string;
  rag_enabled: boolean;
  retrieved_contexts?: Array<{
    document_id?: string;
    title: string;
    content: string;
    score: number;
  }>;
  tool_executions?: Array<{
    id: string;
    tool_name: string;
    tool_display_name: string;
    args: Record<string, unknown>;
    status: string;
    result?: unknown;
    error?: string;
    duration_ms?: number;
  }>;
  thread_id: string;
  conversation_id: string;
}

export interface ThreadListResponse {
  threads: Array<{
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
    last_message_at?: string;
    source_project_id?: string;
  }>;
  total: number;
}

export interface ThreadMessagesResponse {
  messages: Array<{
    id: string;
    role: string;
    content: string;
    created_at: string;
    tool_name?: string;
    tool_call_id?: string;
    citations?: Array<{
      document_id: string;
      document_title: string;
      snippet?: string;
      page_number?: number;
      score?: number;
    }>;
  }>;
  total: number;
}

class AgentChatService {
  /**
   * Execute an agent chat completion. Falls back to /chat/completions
   * until the dedicated /agent/execute endpoint is built.
   */
  async execute(request: AgentExecuteRequest): Promise<AgentExecuteResponse> {
    // Use existing chat completions endpoint with page context injected into system prompt
    const systemPrompt = this.buildSystemPrompt(request.page_context);
    const response = await apiClient.post<AgentExecuteResponse>(
      "/api/v1/chat/completions",
      {
        messages: [
          { role: "system", content: systemPrompt },
          ...request.messages,
        ],
        model: request.model || "gpt-4o",
        use_rag: request.use_rag ?? true,
        max_context_docs: request.max_context_docs ?? 5,
      },
    );
    return {
      ...response,
      thread_id: request.thread_id || "",
      conversation_id: "",
    };
  }

  /**
   * List agent threads (source = 'agent')
   */
  async listThreads(): Promise<ThreadListResponse> {
    return apiClient.get<ThreadListResponse>("/api/v1/agent/threads");
  }

  /**
   * Get messages for a thread
   */
  async getThreadMessages(threadId: string): Promise<ThreadMessagesResponse> {
    return apiClient.get<ThreadMessagesResponse>(
      `/api/v1/agent/threads/${threadId}/messages`,
    );
  }

  private buildSystemPrompt(
    pageContext: AgentExecuteRequest["page_context"],
  ): string {
    let contextLine = "";
    if (pageContext.type === "project" && pageContext.project_id) {
      contextLine = `The user is currently viewing a project (ID: ${pageContext.project_id}).`;
    } else if (pageContext.type !== "unknown") {
      contextLine = `The user is currently on the ${pageContext.type} page.`;
    }

    return `You are an AI research agent for a RAG system. You help users search documents, manage projects, find ArXiv papers, create notes, and analyze research.

${contextLine}

When answering questions, use retrieved document context when available. Cite sources using [Doc N] format.
Be concise and action-oriented. When the user asks you to do something, confirm what you did.`;
  }
}

export const agentChatService = new AgentChatService();
```

**Step 2: Wire up the store's sendMessage**

Update `frontend/src/store/agentChatStore.ts` — replace the `sendMessage` stub:

```typescript
// In the store, update sendMessage implementation:

sendMessage: async () => {
  const state = get();
  const trimmed = state.inputValue.trim();
  if (!trimmed || state.isStreaming) return;

  const userMessage: AgentMessage = {
    id: `user-${Date.now()}`,
    role: 'user',
    content: trimmed,
    timestamp: new Date(),
  };

  set((s) => {
    s.messages.push(userMessage);
    s.inputValue = '';
    s.isStreaming = true;
  });

  try {
    const { agentChatService } = await import('@/services/agentChatService');

    const messagesForApi = get().messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }));

    const response = await agentChatService.execute({
      messages: messagesForApi,
      page_context: {
        type: get().pageContext.type,
        project_id: get().pageContext.projectId,
      },
      thread_id: get().activeThreadId ?? undefined,
    });

    const assistantMessage: AgentMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: response.message.content,
      timestamp: new Date(),
      citations: response.retrieved_contexts?.map((ctx) => ({
        documentId: ctx.document_id || '',
        documentTitle: ctx.title,
        snippet: ctx.content.slice(0, 200),
        score: ctx.score,
      })),
      toolExecutions: response.tool_executions?.map((exec) => ({
        id: exec.id,
        toolName: exec.tool_name,
        toolDisplayName: exec.tool_display_name,
        args: exec.args,
        status: exec.status as 'running' | 'completed' | 'failed',
        result: exec.result,
        error: exec.error,
        durationMs: exec.duration_ms,
      })),
    };

    set((s) => {
      s.messages.push(assistantMessage);
      s.isStreaming = false;
      if (response.thread_id) {
        s.activeThreadId = response.thread_id;
      }
      if (s.uiMode === 'closed') {
        s.hasUnread = true;
      }
    });
  } catch (error) {
    console.error('Agent chat error:', error);
    set((s) => {
      s.messages.push({
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date(),
      });
      s.isStreaming = false;
    });
  }
},
```

**Step 3: Run type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/services/agentChatService.ts frontend/src/store/agentChatStore.ts
git commit -m "feat(agent-chat): add agent chat service and wire up message sending"
```

---

## Task 6: Backend Agent Execute Endpoint

**Files:**

- Create: `backend/src/api/agent/__init__.py`
- Create: `backend/src/api/agent/execute.py`
- Modify: `backend/src/main.py` (register router)

**Step 1: Create agent API module**

```python
# backend/src/api/agent/__init__.py

"""Agent API routes for AI agent execution and thread management"""

from .execute import router as agent_router

__all__ = ["agent_router"]
```

**Step 2: Create agent execute endpoint**

```python
# backend/src/api/agent/execute.py

"""
Agent execution endpoint.
Wraps chat completions with tool-calling capabilities and page context injection.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core.dependencies import get_current_user
from src.models.user import User
from src.services.infrastructure.azure_openai_service import azure_openai_service
from src.services.search.hybrid_search_service import hybrid_search_service
from src.models.search_schemas import SearchQuery

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


# ============================================================================
# Request / Response Schemas
# ============================================================================


class AgentMessage(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, system, tool")
    content: str = Field(..., description="Message content")


class PageContextRequest(BaseModel):
    type: str = Field(default="unknown", description="Page context type")
    project_id: Optional[str] = Field(default=None, description="Project ID if on project page")
    metadata: Optional[Dict[str, Any]] = None


class AgentExecuteRequest(BaseModel):
    messages: List[AgentMessage] = Field(..., description="Conversation messages")
    page_context: PageContextRequest = Field(default_factory=PageContextRequest)
    model: str = Field(default="gpt-4o")
    use_rag: bool = Field(default=True)
    max_context_docs: int = Field(default=5, ge=1, le=10)
    thread_id: Optional[str] = None


class RetrievedContextResponse(BaseModel):
    document_id: Optional[str] = None
    title: str
    content: str
    score: float


class ToolExecutionResponse(BaseModel):
    id: str
    tool_name: str
    tool_display_name: str
    args: Dict[str, Any]
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentExecuteResponse(BaseModel):
    message: AgentMessage
    model: str
    usage: Dict[str, int]
    finish_reason: str
    timestamp: str
    rag_enabled: bool = False
    retrieved_contexts: Optional[List[RetrievedContextResponse]] = None
    tool_executions: Optional[List[ToolExecutionResponse]] = None
    thread_id: str = ""
    conversation_id: str = ""


# ============================================================================
# System Prompt Builder
# ============================================================================


def build_agent_system_prompt(page_context: PageContextRequest) -> str:
    context_line = ""
    if page_context.type == "project" and page_context.project_id:
        context_line = f"The user is viewing a project (ID: {page_context.project_id})."
    elif page_context.type != "unknown":
        context_line = f"The user is on the {page_context.type} page."

    return f"""You are an AI research agent for a RAG-powered academic research system.
You help users search documents, manage research projects, find ArXiv papers, create notes, and analyze research.

{context_line}

When answering questions, use retrieved document context when available.
Cite sources using [Doc N] format inline.
Be concise and action-oriented."""


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    current_user: User = Depends(get_current_user),
):
    """Execute an agent chat completion with optional RAG and tool calling."""
    logger.info(
        "Agent execute request",
        extra={
            "user_id": str(current_user.id),
            "page_context": request.page_context.type,
            "message_count": len(request.messages),
            "use_rag": request.use_rag,
        },
    )

    system_prompt = build_agent_system_prompt(request.page_context)
    retrieved_contexts: List[RetrievedContextResponse] = []

    # RAG retrieval
    if request.use_rag and request.messages:
        last_user_msg = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            None,
        )
        if last_user_msg:
            try:
                search_request = SearchQuery(
                    query=last_user_msg,
                    limit=request.max_context_docs,
                    search_type="hybrid",
                )
                search_results = await hybrid_search_service.search(search_request)

                for i, result in enumerate(search_results.results[:request.max_context_docs]):
                    doc_content = result.content[:3000] if result.content else ""
                    retrieved_contexts.append(
                        RetrievedContextResponse(
                            document_id=str(result.document_id) if result.document_id else None,
                            title=result.title or f"Document {i + 1}",
                            content=doc_content,
                            score=result.score or 0.0,
                        )
                    )

                if retrieved_contexts:
                    context_text = "\n\n".join(
                        f"[Doc {i + 1}] {ctx.title}:\n{ctx.content}"
                        for i, ctx in enumerate(retrieved_contexts)
                    )
                    system_prompt += f"\n\nRetrieved context:\n{context_text}"

            except Exception as e:
                logger.warning("RAG retrieval failed, proceeding without context", exc_info=e)

    # Build messages for LLM
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in request.messages:
        llm_messages.append({"role": msg.role, "content": msg.content})

    # Call LLM
    try:
        response = await azure_openai_service.chat_completion(
            messages=llm_messages,
            model=request.model,
            temperature=0.7,
            max_tokens=2048,
        )

        return AgentExecuteResponse(
            message=AgentMessage(
                role="assistant",
                content=response["choices"][0]["message"]["content"],
            ),
            model=request.model,
            usage=response.get("usage", {}),
            finish_reason=response["choices"][0].get("finish_reason", "stop"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            rag_enabled=request.use_rag,
            retrieved_contexts=retrieved_contexts if retrieved_contexts else None,
            thread_id=request.thread_id or "",
            conversation_id="",
        )

    except Exception as e:
        logger.error("Agent LLM call failed", exc_info=e)
        raise HTTPException(status_code=500, detail="Agent execution failed")


@router.get("/health")
async def agent_health():
    """Health check for agent service."""
    return {"status": "ok", "service": "agent"}
```

**Step 3: Register router in main.py**

In `backend/src/main.py`, add:

```python
# Add import (near line 48 with other chat imports)
from src.api.agent import agent_router

# Add router registration (near line 342 with chat_router)
app.include_router(agent_router)  # Agent execution endpoints
```

**Step 4: Commit**

```bash
git add backend/src/api/agent/ backend/src/main.py
git commit -m "feat(agent-chat): add backend /api/v1/agent/execute endpoint with RAG"
```

---

## Task 7: Thread Persistence Endpoints

**Files:**

- Modify: `backend/src/api/agent/execute.py` (add thread list/messages endpoints)

**Step 1: Add thread listing and message retrieval**

Append to `backend/src/api/agent/execute.py`:

```python
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models import Thread, ChatMessage as ChatMessageModel, Conversation, Workspace

# ... add these endpoints:

class ThreadSummary(BaseModel):
    id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    message_count: int
    last_message_at: Optional[str]
    source_project_id: Optional[str]

class ThreadListResponse(BaseModel):
    threads: List[ThreadSummary]
    total: int

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None

class ThreadMessagesResponse(BaseModel):
    messages: List[MessageResponse]
    total: int


@router.get("/threads", response_model=ThreadListResponse)
async def list_agent_threads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List threads created by the agent for the current user."""
    query = (
        select(Thread)
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            Workspace.owner_id == current_user.id,
            Thread.status != "archived",
        )
        .order_by(desc(Thread.updated_at))
        .limit(50)
    )
    result = await db.execute(query)
    threads = result.scalars().all()

    return ThreadListResponse(
        threads=[
            ThreadSummary(
                id=str(t.id),
                title=t.title,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
                message_count=t.message_count or 0,
                last_message_at=t.last_message_at.isoformat() if t.last_message_at else None,
                source_project_id=str(t.source_project_id) if t.source_project_id else None,
            )
            for t in threads
        ],
        total=len(threads),
    )


@router.get("/threads/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def get_thread_messages(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a specific agent thread."""
    query = (
        select(Thread)
        .options(selectinload(Thread.messages))
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            Thread.id == thread_id,
            Workspace.owner_id == current_user.id,
        )
    )
    result = await db.execute(query)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    return ThreadMessagesResponse(
        messages=[
            MessageResponse(
                id=str(m.id),
                role=m.role.value if hasattr(m.role, 'value') else m.role,
                content=m.content or "",
                created_at=m.created_at.isoformat(),
                tool_name=m.tool_name,
                tool_call_id=m.tool_call_id,
            )
            for m in sorted(thread.messages, key=lambda x: x.created_at)
        ],
        total=len(thread.messages),
    )
```

**Step 2: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "feat(agent-chat): add thread listing and message retrieval endpoints"
```

---

## Task 8: Wire Thread Persistence in Frontend Store

**Files:**

- Modify: `frontend/src/store/agentChatStore.ts` (implement loadThreads, loadThreadMessages)
- Modify: `frontend/src/services/agentChatService.ts` (update to use /agent/execute)

**Step 1: Update service to use agent endpoint**

In `frontend/src/services/agentChatService.ts`, update the `execute` method:

```typescript
async execute(request: AgentExecuteRequest): Promise<AgentExecuteResponse> {
  return apiClient.post<AgentExecuteResponse>('/api/v1/agent/execute', request);
}
```

**Step 2: Implement loadThreads and loadThreadMessages in store**

```typescript
loadThreads: async () => {
  set((s) => { s.isLoadingThreads = true; });
  try {
    const { agentChatService } = await import('@/services/agentChatService');
    const response = await agentChatService.listThreads();
    set((s) => {
      s.threads = response.threads.map((t) => ({
        id: t.id,
        title: t.title || 'Untitled',
        createdAt: new Date(t.created_at),
        updatedAt: new Date(t.updated_at),
        messageCount: t.message_count,
        lastMessage: undefined,
        projectId: t.source_project_id || undefined,
      }));
      s.isLoadingThreads = false;
    });
  } catch (error) {
    console.error('Failed to load threads:', error);
    set((s) => { s.isLoadingThreads = false; });
  }
},

loadThreadMessages: async (threadId: string) => {
  set((s) => { s.isLoadingMessages = true; });
  try {
    const { agentChatService } = await import('@/services/agentChatService');
    const response = await agentChatService.getThreadMessages(threadId);
    set((s) => {
      s.messages = response.messages.map((m) => ({
        id: m.id,
        role: m.role as 'user' | 'assistant' | 'tool',
        content: m.content,
        timestamp: new Date(m.created_at),
        citations: m.citations?.map((c) => ({
          documentId: c.document_id,
          documentTitle: c.document_title,
          snippet: c.snippet,
          page: c.page_number,
          score: c.score,
        })),
        backendMessageId: m.id,
      }));
      s.activeThreadId = threadId;
      s.isLoadingMessages = false;
    });
  } catch (error) {
    console.error('Failed to load thread messages:', error);
    set((s) => { s.isLoadingMessages = false; });
  }
},
```

**Step 3: Run type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/store/agentChatStore.ts frontend/src/services/agentChatService.ts
git commit -m "feat(agent-chat): wire thread persistence - load threads and messages"
```

---

## Task 9: Sidebar Mode — Thread List

**Files:**

- Create: `frontend/src/components/agent-chat/AgentThreadList.tsx`
- Modify: `frontend/src/components/agent-chat/GlobalAgentChat.tsx` (use AgentSidebar in sidebar mode)
- Create: `frontend/src/components/agent-chat/AgentSidebar.tsx`

**Step 1: Write AgentThreadList**

```typescript
// frontend/src/components/agent-chat/AgentThreadList.tsx

'use client';

import React from 'react';
import { MessageSquare } from 'lucide-react';
import type { AgentThread } from '@/types/agent-chat';

interface AgentThreadListProps {
  threads: AgentThread[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  isLoading: boolean;
}

export function AgentThreadList({
  threads,
  activeThreadId,
  onSelectThread,
  isLoading,
}: AgentThreadListProps) {
  if (isLoading) {
    return (
      <div className="p-3 space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 bg-muted animate-pulse rounded-md" />
        ))}
      </div>
    );
  }

  if (threads.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-muted-foreground">
        No conversations yet
      </div>
    );
  }

  return (
    <div className="p-2 space-y-1 overflow-y-auto">
      {threads.map((thread) => (
        <button
          key={thread.id}
          onClick={() => onSelectThread(thread.id)}
          className={`w-full text-left px-3 py-2 rounded-md text-xs transition-colors ${
            thread.id === activeThreadId
              ? 'bg-primary/10 text-primary'
              : 'text-foreground hover:bg-muted'
          }`}
        >
          <div className="flex items-center gap-2">
            <MessageSquare className="h-3 w-3 shrink-0" />
            <span className="truncate font-medium">{thread.title}</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5 text-muted-foreground">
            <span>{thread.messageCount} messages</span>
            <span>·</span>
            <span>{formatRelativeDate(thread.updatedAt)}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

function formatRelativeDate(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}
```

**Step 2: Write AgentSidebar**

```typescript
// frontend/src/components/agent-chat/AgentSidebar.tsx

'use client';

import React, { useEffect } from 'react';
import { Minimize2, Plus, X } from 'lucide-react';
import { AgentContextBar } from './AgentContextBar';
import { AgentMessageList } from './AgentMessageList';
import { AgentInput } from './AgentInput';
import { AgentThreadList } from './AgentThreadList';
import { useAgentChatStore } from '@/store/agentChatStore';

export function AgentSidebar() {
  const messages = useAgentChatStore((s) => s.messages);
  const isStreaming = useAgentChatStore((s) => s.isStreaming);
  const inputValue = useAgentChatStore((s) => s.inputValue);
  const pageContext = useAgentChatStore((s) => s.pageContext);
  const threads = useAgentChatStore((s) => s.threads);
  const activeThreadId = useAgentChatStore((s) => s.activeThreadId);
  const isLoadingThreads = useAgentChatStore((s) => s.isLoadingThreads);
  const close = useAgentChatStore((s) => s.close);
  const openPanel = useAgentChatStore((s) => s.openPanel);
  const setInputValue = useAgentChatStore((s) => s.setInputValue);
  const sendMessage = useAgentChatStore((s) => s.sendMessage);
  const clearMessages = useAgentChatStore((s) => s.clearMessages);
  const newThread = useAgentChatStore((s) => s.newThread);
  const selectThread = useAgentChatStore((s) => s.selectThread);
  const loadThreads = useAgentChatStore((s) => s.loadThreads);
  const loadThreadMessages = useAgentChatStore((s) => s.loadThreadMessages);

  useEffect(() => {
    void loadThreads();
  }, [loadThreads]);

  const handleSelectThread = (threadId: string) => {
    selectThread(threadId);
    void loadThreadMessages(threadId);
  };

  return (
    <div className="flex h-full">
      {/* Thread list sidebar */}
      <div className="w-[200px] border-r border-border flex flex-col shrink-0">
        <div className="flex items-center justify-between px-3 py-3 border-b border-border">
          <span className="text-xs font-medium text-foreground">Threads</span>
          <button
            onClick={newThread}
            aria-label="New conversation"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
        <AgentThreadList
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={handleSelectThread}
          isLoading={isLoadingThreads}
        />
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <h3 id="agent-panel-title" className="text-sm font-medium text-foreground">
            Agent
          </h3>
          <div className="flex items-center gap-1">
            <button
              onClick={openPanel}
              aria-label="Collapse to panel"
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <Minimize2 className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={close}
              aria-label="Close agent chat"
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <AgentContextBar context={pageContext} />
        <AgentMessageList messages={messages} isStreaming={isStreaming} />
        <AgentInput
          value={inputValue}
          onChange={setInputValue}
          onSend={() => void sendMessage()}
          disabled={isStreaming}
        />
      </div>
    </div>
  );
}
```

**Step 3: Update GlobalAgentChat to use AgentSidebar**

In `frontend/src/components/agent-chat/GlobalAgentChat.tsx`, replace the sidebar `<AgentPanel>` with `<AgentSidebar>`:

```typescript
// Import AgentSidebar
import { AgentSidebar } from './AgentSidebar';

// In the sidebar mode section, replace AgentPanel with:
{uiMode === 'sidebar' && (
  <div
    className="fixed top-0 right-0 z-50 w-[420px] h-full bg-background border-l border-border shadow-xl animate-in slide-in-from-right duration-200"
    role="dialog"
    aria-modal="true"
    aria-label="Agent chat sidebar"
  >
    <AgentSidebar />
  </div>
)}
```

**Step 4: Run type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/agent-chat/
git commit -m "feat(agent-chat): add sidebar mode with thread list and navigation"
```

---

## Task 10: Integration Test & Final Validation

**Step 1: Run all agent-chat tests**

Run: `cd frontend && npx jest src/components/agent-chat/ src/store/__tests__/agentChatStore.test.ts src/hooks/__tests__/usePageContext.test.tsx --no-coverage`
Expected: All tests pass

**Step 2: Run full type-check**

Run: `cd frontend && npm run type-check`
Expected: No errors

**Step 3: Run full test suite**

Run: `cd frontend && npm run test -- --no-coverage`
Expected: All existing tests + new tests pass

**Step 4: Final commit with all fixes**

If any fixes were needed, commit them:

```bash
git add -A
git commit -m "test(agent-chat): fix integration issues and ensure all tests pass"
```

---

## Summary

| Task | Description                         | Key Files                                        |
| ---- | ----------------------------------- | ------------------------------------------------ |
| 1    | Types & Zustand store               | `types/agent-chat.ts`, `store/agentChatStore.ts` |
| 2    | usePageContext hook                 | `hooks/usePageContext.ts`                        |
| 3    | UI components (panel mode)          | `components/agent-chat/*.tsx`                    |
| 4    | Mount globally, remove old widget   | `layout.tsx`, `projects/[id]/page.tsx`           |
| 5    | Agent chat service                  | `services/agentChatService.ts`                   |
| 6    | Backend /agent/execute endpoint     | `api/agent/execute.py`                           |
| 7    | Thread persistence endpoints        | `api/agent/execute.py`                           |
| 8    | Wire thread persistence in frontend | `agentChatStore.ts`, `agentChatService.ts`       |
| 9    | Sidebar mode with thread list       | `AgentSidebar.tsx`, `AgentThreadList.tsx`        |
| 10   | Integration test & validation       | All files                                        |
