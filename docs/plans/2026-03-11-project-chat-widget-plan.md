# Project Chat Widget Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a SciSpace-style collapsible floating chat panel on the project detail page with toggleable context chips and RAG-powered Q&A.

**Architecture:** Standalone `ProjectChatWidget` component tree mounted at page level in `projects/[id]/page.tsx`, independent of the existing Chat tab. Uses React state via a custom hook, calls existing `projectChatService` for backend communication. Context chips auto-populate from `projectStore` based on active tab.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide icons, shadcn/ui components (Badge, Button, ScrollArea, Tooltip), existing `projectChatService` + `projectStore`.

---

### Task 1: Types & Hook — `useProjectChatWidget`

**Files:**

- Create: `frontend/src/types/chat-widget.ts`
- Create: `frontend/src/hooks/useProjectChatWidget.ts`

**Step 1: Create widget types**

Create `frontend/src/types/chat-widget.ts`:

```typescript
export interface WidgetMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  citations?: WidgetCitation[];
}

export interface WidgetCitation {
  index: number;
  documentId: string;
  documentTitle: string;
  snippet?: string;
}

export interface ContextChip {
  id: string;
  label: string;
  type: "document" | "note" | "bibliography";
  enabled: boolean;
}
```

**Step 2: Create the hook**

Create `frontend/src/hooks/useProjectChatWidget.ts`:

```typescript
"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { projectChatService } from "@/services/projectChatService";
import { useProjectStore } from "@/store/projectStore";
import type { WidgetMessage, ContextChip } from "@/types/chat-widget";

interface UseProjectChatWidgetOptions {
  projectId: string;
  activeTab: string;
}

export function useProjectChatWidget({
  projectId,
  activeTab,
}: UseProjectChatWidgetOptions) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<WidgetMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [hasUnread, setHasUnread] = useState(false);
  const threadIdRef = useRef<string | null>(null);
  const conversationIdRef = useRef<string | null>(null);

  const { projectDocuments, projectNotes, bibliography } = useProjectStore();

  // Build context chips from current tab resources
  const contextChips = useMemo((): ContextChip[] => {
    switch (activeTab) {
      case "documents":
        return projectDocuments.map((doc) => ({
          id: doc.document_id,
          label: doc.document?.title || doc.document?.filename || "Untitled",
          type: "document" as const,
          enabled: true,
        }));
      case "notes":
        return projectNotes.map((note) => ({
          id: note.id,
          label: note.title,
          type: "note" as const,
          enabled: true,
        }));
      case "bibliography":
        return (
          bibliography?.citations?.map(
            (cit: { id: string; title: string }) => ({
              id: cit.id,
              label: cit.title,
              type: "bibliography" as const,
              enabled: true,
            }),
          ) ?? []
        );
      default:
        // Other tabs: show all project documents
        return projectDocuments.map((doc) => ({
          id: doc.document_id,
          label: doc.document?.title || doc.document?.filename || "Untitled",
          type: "document" as const,
          enabled: true,
        }));
    }
  }, [activeTab, projectDocuments, projectNotes, bibliography]);

  const [chipStates, setChipStates] = useState<Record<string, boolean>>({});

  // Merge chip states with generated chips
  const chips = useMemo(
    () =>
      contextChips.map((chip) => ({
        ...chip,
        enabled: chipStates[chip.id] ?? chip.enabled,
      })),
    [contextChips, chipStates],
  );

  // Reset chip states when tab changes (new chips appear)
  useEffect(() => {
    setChipStates({});
  }, [activeTab]);

  const toggleChip = useCallback((chipId: string) => {
    setChipStates((prev) => ({
      ...prev,
      [chipId]: !(prev[chipId] ?? true),
    }));
  }, []);

  const toggleAllChips = useCallback(
    (enabled: boolean) => {
      const newStates: Record<string, boolean> = {};
      for (const chip of contextChips) {
        newStates[chip.id] = enabled;
      }
      setChipStates(newStates);
    },
    [contextChips],
  );

  const toggle = useCallback(() => {
    setIsOpen((prev) => {
      if (!prev) setHasUnread(false);
      return !prev;
    });
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return;

      const userMessage: WidgetMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setInputValue("");
      setIsStreaming(true);

      try {
        const response = await projectChatService.startChatFromProject(
          projectId,
          {
            initial_message: content.trim(),
            conversation_id: conversationIdRef.current ?? undefined,
            thread_title: `Quick Chat - ${new Date().toLocaleDateString()}`,
          },
        );

        threadIdRef.current = response.thread_id;
        conversationIdRef.current = response.conversation_id;

        // For now, add a placeholder AI response
        // TODO: Replace with actual streaming response from backend
        const aiMessage: WidgetMessage = {
          id: `ai-${Date.now()}`,
          role: "assistant",
          content: "Thinking...",
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, aiMessage]);

        if (!isOpen) setHasUnread(true);
      } catch (error) {
        const errorMessage: WidgetMessage = {
          id: `error-${Date.now()}`,
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsStreaming(false);
      }
    },
    [projectId, isStreaming, isOpen],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    threadIdRef.current = null;
    conversationIdRef.current = null;
  }, []);

  return {
    isOpen,
    toggle,
    messages,
    chips,
    toggleChip,
    toggleAllChips,
    isStreaming,
    inputValue,
    setInputValue,
    sendMessage,
    clearMessages,
    hasUnread,
    activeTab,
  };
}
```

**Step 3: Verify types compile**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty 2>&1 | head -30`

If there are type errors related to the new files, fix them. Common issue: `bibliography.citations` shape may differ — adjust the mapping in the `bibliography` case accordingly.

**Step 4: Commit**

```bash
git add frontend/src/types/chat-widget.ts frontend/src/hooks/useProjectChatWidget.ts
git commit -m "feat(chat-widget): add types and useProjectChatWidget hook"
```

---

### Task 2: FAB Component — `ProjectChatWidget.tsx`

**Files:**

- Create: `frontend/src/components/chat-widget/ProjectChatWidget.tsx`

**Step 1: Create the root widget component with FAB**

Create `frontend/src/components/chat-widget/ProjectChatWidget.tsx`:

```typescript
'use client';

import React from 'react';
import { MessageCircle, X } from 'lucide-react';
import { useProjectChatWidget } from '@/hooks/useProjectChatWidget';
import { ChatPanel } from './ChatPanel';

interface ProjectChatWidgetProps {
  projectId: string;
  activeTab: string;
}

export function ProjectChatWidget({ projectId, activeTab }: ProjectChatWidgetProps) {
  const widget = useProjectChatWidget({ projectId, activeTab });

  return (
    <>
      {/* Chat Panel */}
      {widget.isOpen && (
        <ChatPanel
          messages={widget.messages}
          chips={widget.chips}
          isStreaming={widget.isStreaming}
          inputValue={widget.inputValue}
          activeTab={widget.activeTab}
          onInputChange={widget.setInputValue}
          onSend={widget.sendMessage}
          onClose={widget.toggle}
          onToggleChip={widget.toggleChip}
          onToggleAllChips={widget.toggleAllChips}
          onClear={widget.clearMessages}
        />
      )}

      {/* Floating Action Button */}
      <button
        onClick={widget.toggle}
        aria-label={widget.isOpen ? 'Close project chat' : 'Open project chat'}
        className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-all duration-200 hover:scale-105 hover:shadow-xl active:scale-95"
      >
        {widget.isOpen ? (
          <X className="h-5 w-5" />
        ) : (
          <div className="relative">
            <MessageCircle className="h-5 w-5" />
            {widget.hasUnread && (
              <span className="absolute -top-1.5 -right-1.5 h-3 w-3 rounded-full bg-destructive border-2 border-primary" />
            )}
          </div>
        )}
      </button>
    </>
  );
}
```

**Step 2: Create a placeholder ChatPanel**

Create `frontend/src/components/chat-widget/ChatPanel.tsx` (placeholder to avoid import error):

```typescript
'use client';

import React from 'react';
import type { WidgetMessage, ContextChip } from '@/types/chat-widget';

interface ChatPanelProps {
  messages: WidgetMessage[];
  chips: ContextChip[];
  isStreaming: boolean;
  inputValue: string;
  activeTab: string;
  onInputChange: (value: string) => void;
  onSend: (content: string) => Promise<void>;
  onClose: () => void;
  onToggleChip: (chipId: string) => void;
  onToggleAllChips: (enabled: boolean) => void;
  onClear: () => void;
}

export function ChatPanel({ onClose }: ChatPanelProps) {
  return (
    <div className="fixed bottom-[88px] right-6 z-50 w-[380px] h-[520px] rounded-xl border border-border bg-background shadow-2xl flex flex-col">
      <div className="p-3 border-b border-border flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">Quick Chat</span>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          Close
        </button>
      </div>
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Panel placeholder
      </div>
    </div>
  );
}
```

**Step 3: Verify it compiles**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 4: Commit**

```bash
git add frontend/src/components/chat-widget/
git commit -m "feat(chat-widget): add ProjectChatWidget root with FAB and placeholder panel"
```

---

### Task 3: Wire Widget into Project Detail Page

**Files:**

- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx`

**Step 1: Import and render the widget**

In `frontend/app/(dashboard)/projects/[id]/page.tsx`, add the import at the top with the other imports:

```typescript
import { ProjectChatWidget } from "@/components/chat-widget/ProjectChatWidget";
```

Then render it at the end of the return JSX, after the `DraftExportModal` closing tag and before the final closing `</div>`:

```typescript
      {/* Floating Chat Widget */}
      <ProjectChatWidget projectId={projectId} activeTab={activeTab} />
    </div>
  );
```

**Step 2: Verify it compiles and renders**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

Visually verify at `http://localhost:3000/projects/<any-project-id>` — you should see the FAB in the bottom-right corner. Clicking it should toggle the placeholder panel.

**Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/projects/\[id\]/page.tsx
git commit -m "feat(chat-widget): wire ProjectChatWidget into project detail page"
```

---

### Task 4: ChatContextBar — Toggleable Context Chips

**Files:**

- Create: `frontend/src/components/chat-widget/ChatContextBar.tsx`

**Step 1: Build the context bar component**

Create `frontend/src/components/chat-widget/ChatContextBar.tsx`:

```typescript
'use client';

import React from 'react';
import { FileText, StickyNote, BookOpen } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { ContextChip } from '@/types/chat-widget';

interface ChatContextBarProps {
  chips: ContextChip[];
  activeTab: string;
  onToggleChip: (chipId: string) => void;
  onToggleAllChips: (enabled: boolean) => void;
}

const tabLabels: Record<string, string> = {
  documents: 'Documents',
  notes: 'Notes',
  bibliography: 'Bibliography',
  drafts: 'Documents',
  chat: 'Documents',
  matrix: 'Documents',
  pipeline: 'Documents',
};

const chipIcons: Record<string, React.ElementType> = {
  document: FileText,
  note: StickyNote,
  bibliography: BookOpen,
};

export function ChatContextBar({
  chips,
  activeTab,
  onToggleChip,
  onToggleAllChips,
}: ChatContextBarProps) {
  const enabledCount = chips.filter((c) => c.enabled).length;
  const allEnabled = enabledCount === chips.length;
  const label = tabLabels[activeTab] ?? 'Documents';

  if (chips.length === 0) {
    return (
      <div className="px-3 py-2 border-b border-border">
        <span className="text-xs text-muted-foreground">No context available</span>
      </div>
    );
  }

  return (
    <div className="px-3 py-2 border-b border-border space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          Chatting with: {label} ({enabledCount})
        </span>
        <button
          onClick={() => onToggleAllChips(!allEnabled)}
          className="text-[10px] text-primary hover:underline"
        >
          {allEnabled ? 'Deselect all' : 'Select all'}
        </button>
      </div>
      <TooltipProvider delayDuration={300}>
        <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-thin">
          {chips.map((chip) => {
            const Icon = chipIcons[chip.type] ?? FileText;
            return (
              <Tooltip key={chip.id}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => onToggleChip(chip.id)}
                    className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] transition-colors shrink-0 ${
                      chip.enabled
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-transparent text-muted-foreground border border-border hover:border-muted-foreground/50'
                    }`}
                  >
                    <Icon className="h-3 w-3" />
                    <span className="max-w-[80px] truncate">{chip.label}</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p className="text-xs">{chip.label}</p>
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </TooltipProvider>
    </div>
  );
}
```

**Step 2: Verify it compiles**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 3: Commit**

```bash
git add frontend/src/components/chat-widget/ChatContextBar.tsx
git commit -m "feat(chat-widget): add ChatContextBar with toggleable context chips"
```

---

### Task 5: ChatMessageList & ChatMessageItem

**Files:**

- Create: `frontend/src/components/chat-widget/ChatMessageList.tsx`
- Create: `frontend/src/components/chat-widget/ChatMessageItem.tsx`

**Step 1: Create ChatMessageItem**

Create `frontend/src/components/chat-widget/ChatMessageItem.tsx`:

```typescript
'use client';

import React from 'react';
import { User, Bot } from 'lucide-react';
import type { WidgetMessage } from '@/types/chat-widget';

interface ChatMessageItemProps {
  message: WidgetMessage;
}

export function ChatMessageItem({ message }: ChatMessageItemProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={`flex gap-2 animate-in fade-in slide-in-from-bottom-2 duration-200 ${
        isUser ? 'flex-row-reverse' : 'flex-row'
      }`}
    >
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
          isUser ? 'bg-primary/15' : 'bg-muted'
        }`}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5 text-primary" />
        ) : (
          <Bot className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </div>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-foreground'
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}
```

**Step 2: Create ChatMessageList**

Create `frontend/src/components/chat-widget/ChatMessageList.tsx`:

```typescript
'use client';

import React, { useRef, useEffect } from 'react';
import { MessageCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatMessageItem } from './ChatMessageItem';
import type { WidgetMessage } from '@/types/chat-widget';

interface ChatMessageListProps {
  messages: WidgetMessage[];
  isStreaming: boolean;
}

export function ChatMessageList({ messages, isStreaming }: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
        <MessageCircle className="h-8 w-8 text-muted-foreground/30 mb-3" />
        <p className="text-sm font-medium text-muted-foreground">Ask anything</p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Questions will use your selected context
        </p>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div role="log" aria-live="polite" className="flex flex-col gap-3 p-3">
        {messages.map((message) => (
          <ChatMessageItem key={message.id} message={message} />
        ))}
        {isStreaming && (
          <div className="flex gap-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted">
              <div className="flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
```

**Step 3: Verify it compiles**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 4: Commit**

```bash
git add frontend/src/components/chat-widget/ChatMessageItem.tsx frontend/src/components/chat-widget/ChatMessageList.tsx
git commit -m "feat(chat-widget): add ChatMessageList and ChatMessageItem components"
```

---

### Task 6: ChatPanelInput — Compact Input

**Files:**

- Create: `frontend/src/components/chat-widget/ChatPanelInput.tsx`

**Step 1: Create the input component**

Create `frontend/src/components/chat-widget/ChatPanelInput.tsx`:

```typescript
'use client';

import React, { useRef, useCallback, useEffect } from 'react';
import { Send } from 'lucide-react';

interface ChatPanelInputProps {
  value: string;
  isStreaming: boolean;
  onChange: (value: string) => void;
  onSend: (content: string) => Promise<void>;
}

export function ChatPanelInput({ value, isStreaming, onChange, onSend }: ChatPanelInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    if (value.trim() && !isStreaming) {
      void onSend(value);
    }
  }, [value, isStreaming, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Auto-resize textarea (max 3 lines)
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 72)}px`;
  }, [value]);

  return (
    <div className="p-3 border-t border-border">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question..."
          disabled={isStreaming}
          rows={1}
          className="flex-1 resize-none rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={!value.trim() || isStreaming}
          aria-label="Send message"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
```

**Step 2: Verify it compiles**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 3: Commit**

```bash
git add frontend/src/components/chat-widget/ChatPanelInput.tsx
git commit -m "feat(chat-widget): add ChatPanelInput with auto-resize and Enter to send"
```

---

### Task 7: Assemble ChatPanel — Full Panel Component

**Files:**

- Modify: `frontend/src/components/chat-widget/ChatPanel.tsx`

**Step 1: Replace the placeholder ChatPanel with the full implementation**

Replace entire contents of `frontend/src/components/chat-widget/ChatPanel.tsx`:

```typescript
'use client';

import React, { useEffect, useCallback } from 'react';
import { X, Trash2 } from 'lucide-react';
import { ChatContextBar } from './ChatContextBar';
import { ChatMessageList } from './ChatMessageList';
import { ChatPanelInput } from './ChatPanelInput';
import type { WidgetMessage, ContextChip } from '@/types/chat-widget';

interface ChatPanelProps {
  messages: WidgetMessage[];
  chips: ContextChip[];
  isStreaming: boolean;
  inputValue: string;
  activeTab: string;
  onInputChange: (value: string) => void;
  onSend: (content: string) => Promise<void>;
  onClose: () => void;
  onToggleChip: (chipId: string) => void;
  onToggleAllChips: (enabled: boolean) => void;
  onClear: () => void;
}

export function ChatPanel({
  messages,
  chips,
  isStreaming,
  inputValue,
  activeTab,
  onInputChange,
  onSend,
  onClose,
  onToggleChip,
  onToggleAllChips,
  onClear,
}: ChatPanelProps) {
  // Close on Escape
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div
      role="dialog"
      aria-label="Project quick chat"
      className="fixed bottom-[88px] right-6 z-50 w-[380px] h-[520px] rounded-xl border border-border bg-background shadow-2xl flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-200 max-sm:inset-x-0 max-sm:bottom-0 max-sm:w-full max-sm:h-[85vh] max-sm:rounded-t-xl max-sm:rounded-b-none"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border shrink-0">
        <span className="text-sm font-medium text-foreground">Quick Chat</span>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={onClear}
              aria-label="Clear chat"
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            onClick={onClose}
            aria-label="Close chat panel"
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Context Chips */}
      <ChatContextBar
        chips={chips}
        activeTab={activeTab}
        onToggleChip={onToggleChip}
        onToggleAllChips={onToggleAllChips}
      />

      {/* Messages */}
      <ChatMessageList messages={messages} isStreaming={isStreaming} />

      {/* Input */}
      <ChatPanelInput
        value={inputValue}
        isStreaming={isStreaming}
        onChange={onInputChange}
        onSend={onSend}
      />
    </div>
  );
}
```

**Step 2: Verify it compiles**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 3: Visual verification**

Open `http://localhost:3000/projects/<project-id>` and verify:

- FAB appears bottom-right
- Clicking FAB opens panel with header, context chips, empty state, and input
- Switching tabs updates the context chips
- Typing and pressing Enter sends a message
- Escape closes the panel
- X button closes the panel
- Trash button clears messages

**Step 4: Commit**

```bash
git add frontend/src/components/chat-widget/ChatPanel.tsx
git commit -m "feat(chat-widget): assemble full ChatPanel with context bar, messages, and input"
```

---

### Task 8: Responsive & Mobile Behavior

**Files:**

- Modify: `frontend/src/components/chat-widget/ChatPanel.tsx` (already has `max-sm:` classes from Task 7)
- Modify: `frontend/src/components/chat-widget/ProjectChatWidget.tsx`

**Step 1: Add mobile backdrop to ProjectChatWidget**

In `frontend/src/components/chat-widget/ProjectChatWidget.tsx`, add a backdrop overlay for mobile when panel is open. Update the return JSX:

```typescript
  return (
    <>
      {/* Mobile backdrop */}
      {widget.isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 sm:hidden"
          onClick={widget.toggle}
          aria-hidden="true"
        />
      )}

      {/* Chat Panel */}
      {widget.isOpen && (
        <ChatPanel
          messages={widget.messages}
          chips={widget.chips}
          isStreaming={widget.isStreaming}
          inputValue={widget.inputValue}
          activeTab={widget.activeTab}
          onInputChange={widget.setInputValue}
          onSend={widget.sendMessage}
          onClose={widget.toggle}
          onToggleChip={widget.toggleChip}
          onToggleAllChips={widget.toggleAllChips}
          onClear={widget.clearMessages}
        />
      )}

      {/* Floating Action Button */}
      <button
        onClick={widget.toggle}
        aria-label={widget.isOpen ? 'Close project chat' : 'Open project chat'}
        className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-all duration-200 hover:scale-105 hover:shadow-xl active:scale-95"
      >
        {widget.isOpen ? (
          <X className="h-5 w-5" />
        ) : (
          <div className="relative">
            <MessageCircle className="h-5 w-5" />
            {widget.hasUnread && (
              <span className="absolute -top-1.5 -right-1.5 h-3 w-3 rounded-full bg-destructive border-2 border-primary" />
            )}
          </div>
        )}
      </button>
    </>
  );
```

**Step 2: Verify it compiles**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`

**Step 3: Commit**

```bash
git add frontend/src/components/chat-widget/ProjectChatWidget.tsx
git commit -m "feat(chat-widget): add mobile backdrop and responsive behavior"
```

---

### Task 9: Accessibility Pass

**Files:**

- Modify: `frontend/src/components/chat-widget/ChatPanel.tsx`
- Modify: `frontend/src/components/chat-widget/ProjectChatWidget.tsx`

**Step 1: Add focus trap to ChatPanel**

In `frontend/src/components/chat-widget/ChatPanel.tsx`, add a `useEffect` that traps focus inside the panel when open. Add after the existing Escape key handler effect:

```typescript
// Focus trap
const panelRef = React.useRef<HTMLDivElement>(null);

useEffect(() => {
  const panel = panelRef.current;
  if (!panel) return;

  const focusableElements = panel.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
  );
  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  firstElement?.focus();

  const handleTab = (e: KeyboardEvent) => {
    if (e.key !== "Tab") return;
    if (e.shiftKey) {
      if (document.activeElement === firstElement) {
        e.preventDefault();
        lastElement?.focus();
      }
    } else {
      if (document.activeElement === lastElement) {
        e.preventDefault();
        firstElement?.focus();
      }
    }
  };

  panel.addEventListener("keydown", handleTab);
  return () => panel.removeEventListener("keydown", handleTab);
}, [messages]); // Re-run when messages change (new buttons may appear)
```

Add `ref={panelRef}` to the root `<div>` of the panel.

**Step 2: Verify accessibility**

- Tab through the panel — focus should cycle within
- Escape should close
- Screen reader should announce messages via `aria-live="polite"`

**Step 3: Commit**

```bash
git add frontend/src/components/chat-widget/ChatPanel.tsx frontend/src/components/chat-widget/ProjectChatWidget.tsx
git commit -m "feat(chat-widget): add focus trap and accessibility improvements"
```

---

### Task 10: Type-Check & Final Validation

**Files:**

- All chat-widget files

**Step 1: Run full type-check**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npx tsc --noEmit --pretty`

Fix any type errors.

**Step 2: Run lint**

Run: `cd /Users/goodwiinz/development/RAG_system/frontend && npm run lint 2>&1 | tail -20`

Fix any lint issues.

**Step 3: Visual smoke test**

At `http://localhost:3000/projects/<project-id>`:

1. FAB visible in bottom-right
2. Click FAB -> panel opens with slide-up animation
3. Context chips show project documents
4. Switch to Notes tab -> chips update to notes
5. Toggle a chip off/on
6. Type a message, press Enter -> user message appears, AI placeholder appears
7. Press Escape -> panel closes
8. FAB icon changes between MessageCircle and X
9. Resize browser to mobile width -> panel goes full-width

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(chat-widget): complete project chat widget implementation"
```

---

## File Summary

| File                                                        | Action                              |
| ----------------------------------------------------------- | ----------------------------------- |
| `frontend/src/types/chat-widget.ts`                         | Create                              |
| `frontend/src/hooks/useProjectChatWidget.ts`                | Create                              |
| `frontend/src/components/chat-widget/ProjectChatWidget.tsx` | Create                              |
| `frontend/src/components/chat-widget/ChatPanel.tsx`         | Create                              |
| `frontend/src/components/chat-widget/ChatContextBar.tsx`    | Create                              |
| `frontend/src/components/chat-widget/ChatMessageList.tsx`   | Create                              |
| `frontend/src/components/chat-widget/ChatMessageItem.tsx`   | Create                              |
| `frontend/src/components/chat-widget/ChatPanelInput.tsx`    | Create                              |
| `frontend/app/(dashboard)/projects/[id]/page.tsx`           | Modify (add import + render widget) |
